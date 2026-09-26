from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import APIError
from app.integrations.ledger.base import LedgerActor, LedgerReceipt, Registration
from app.integrations.ledger.factory import create_ledger_client
from app.integrations.storage.base import DocumentTooLargeError
from app.integrations.storage.local import LocalDocumentStorage
from app.models.domain import Document, Receivable, Role
from app.models.domain import ReceivableStatus as Status
from app.models.ledger import AuditEvent
from app.schemas.ledger import AuditResponse, HistoryResponse, LifecycleResponse, RegistryResponse
from app.services.audit_service import record_audit
from app.services.fingerprint_service import canonical_invoice, document_hash, invoice_fingerprint
from app.services.state_machine import require_transition


class LedgerService:
    def __init__(
        self, session: AsyncSession, settings: Settings, actor: LedgerActor, request_id: str
    ) -> None:
        self.session, self.settings, self.actor, self.request_id = (
            session,
            settings,
            actor,
            request_id,
        )

    def _audit(
        self,
        event: str,
        *,
        receivable: Receivable | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        record_audit(
            self.session,
            event,
            actor_user_id=self.actor.user_id,
            actor_org_id=self.actor.organization_id,
            request_id=self.request_id,
            receivable_id=receivable.id if receivable else None,
            asset_id=receivable.asset_id if receivable else None,
            metadata=metadata,
        )

    async def _load(self, receivable_id: UUID, lock: bool = False) -> Receivable:
        statement = select(Receivable).where(Receivable.id == receivable_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(statement)
        if row is None or (
            self.actor.role != Role.ADMIN
            and (
                self.actor.role != Role.EXPORTER
                or row.exporter_org_id != self.actor.organization_id
            )
        ):
            raise APIError(404, "RECEIVABLE_NOT_FOUND", "Receivable not found.")
        return row

    async def _verify_integrity(self, row: Receivable) -> None:
        document = await self.session.scalar(
            select(Document).where(Document.receivable_id == row.id)
        )
        if document is None or row.document_hash is None or row.invoice_fingerprint is None:
            raise APIError(
                409, "DOCUMENT_REQUIRED", "Upload an invoice document before submission."
            )
        try:
            data = await run_in_threadpool(
                LocalDocumentStorage(self.settings.document_storage_path).read,
                document.storage_key,
                self.settings.max_upload_bytes,
            )
        except (OSError, ValueError, DocumentTooLargeError) as exc:
            raise APIError(
                503, "DOCUMENT_STORAGE_UNAVAILABLE", "Invoice document is unavailable."
            ) from exc
        identity = canonical_invoice(
            exporter_id=row.exporter_org_id,
            buyer_id=row.buyer_id,
            invoice_number=row.invoice_number,
            currency=row.currency,
            amount_minor=row.face_value_minor,
            invoice_date=row.invoice_date,
        )
        if (
            document_hash(data) != row.document_hash
            or document.document_hash != row.document_hash
            or len(data) != document.size_bytes
            or invoice_fingerprint(identity) != row.invoice_fingerprint
        ):
            raise APIError(
                409,
                "DOCUMENT_INTEGRITY_FAILED",
                "Invoice metadata or document failed integrity verification.",
            )

    async def advance(self, receivable_id: UUID, target: Status) -> LifecycleResponse:
        try:
            return await self._advance(receivable_id, target)
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise APIError(
                503, "LEDGER_UNAVAILABLE", "The transaction could not be confirmed."
            ) from exc
        except APIError as exc:
            await self.session.rollback()
            if exc.code == "DUPLICATE_RECEIVABLE":
                self._audit("DUPLICATE_REJECTED", metadata={"reason": exc.code, "backend": "mock"})
                try:
                    await self.session.commit()
                except SQLAlchemyError as audit_error:
                    await self.session.rollback()
                    raise APIError(
                        503, "DATABASE_UNAVAILABLE", "Could not record duplicate rejection."
                    ) from audit_error
            raise

    async def _advance(self, receivable_id: UUID, target: Status) -> LifecycleResponse:
        if target == Status.VERIFIED and self.actor.role != Role.ADMIN:
            raise APIError(403, "UNAUTHORIZED_ROLE", "Only an administrator may verify invoices.")
        if (
            target in {Status.SUBMITTED, Status.FINANCE_AVAILABLE}
            and self.actor.role != Role.EXPORTER
        ):
            raise APIError(
                403, "UNAUTHORIZED_ROLE", "Only the owning exporter may perform this action."
            )
        row = await self._load(receivable_id, lock=True)
        receipt: LedgerReceipt | None = None
        previous = row.status
        retry = target == Status.REGISTERED and row.asset_id is not None
        if not retry:
            require_transition(previous, target)
        if target in {Status.SUBMITTED, Status.VERIFIED, Status.REGISTERED} and not retry:
            await self._verify_integrity(row)
        if target == Status.REGISTERED:
            if not row.document_hash or not row.invoice_fingerprint:
                raise APIError(409, "DOCUMENT_REQUIRED", "Invoice hashes are missing.")
            ledger = create_ledger_client(self.session, self.settings, self.actor)
            receipt = await ledger.register_receivable(
                Registration(
                    asset_id="TC-" + row.id.hex,
                    invoice_fingerprint=row.invoice_fingerprint,
                    document_hash=row.document_hash,
                    exporter_org_id=row.exporter_org_id,
                    currency=row.currency,
                    face_value_minor=row.face_value_minor,
                    due_date=row.due_date,
                )
            )
        elif target == Status.FINANCE_AVAILABLE:
            if row.asset_id is None:
                raise APIError(409, "ASSET_NOT_REGISTERED", "Register the receivable first.")
            ledger = create_ledger_client(self.session, self.settings, self.actor)
            receipt = await ledger.transition_receivable(row.asset_id, target)
        elif target not in {Status.SUBMITTED, Status.VERIFIED}:
            raise APIError(
                409, "INVALID_STATE_TRANSITION", "This workflow is not exposed in this milestone."
            )
        row.status = receipt.asset.status if receipt else target
        if receipt:
            row.asset_id = receipt.asset.asset_id
            row.owner_org_id = receipt.asset.owner_org_id
            row.financing_agreement_hash = receipt.asset.agreement_hash
        if receipt is None or not receipt.replayed:
            metadata = {"fromStatus": previous.value, "toStatus": row.status.value}
            if receipt:
                metadata.update(backend="mock", transactionId=receipt.transaction_id)
            event = {
                Status.SUBMITTED: "RECEIVABLE_SUBMITTED",
                Status.VERIFIED: "RECEIVABLE_VERIFIED",
                Status.REGISTERED: "RECEIVABLE_REGISTERED",
                Status.FINANCE_AVAILABLE: "RECEIVABLE_OPENED",
            }[target]
            self._audit(event, receivable=row, metadata=metadata)
        result = LifecycleResponse(
            id=row.id,
            status=row.status,
            asset_id=row.asset_id,
            transaction_id=receipt.transaction_id if receipt else None,
            backend="mock" if receipt else None,
            replayed=receipt.replayed if receipt else False,
        )
        await self.session.commit()
        return result

    async def registry(self, fingerprint: str) -> RegistryResponse:
        try:
            ledger = create_ledger_client(self.session, self.settings, self.actor)
            asset = await ledger.find_by_fingerprint(fingerprint)
            result = RegistryResponse(
                fingerprint=fingerprint, exists=asset is not None, eligible=asset is None
            )
            if asset:
                result.asset_id, result.status = asset.asset_id, asset.status
                result.locked = asset.status == Status.LOCKED
                result.financed = asset.status in {
                    Status.FINANCED,
                    Status.PAYMENT_CONFIRMED,
                    Status.REALIZED,
                    Status.EBRC_ELIGIBLE,
                    Status.CLOSED,
                    Status.OVERDUE,
                    Status.DISPUTED,
                }
                result.eligible = asset.status == Status.FINANCE_AVAILABLE
                result.reason = (
                    "RECEIVABLE_ALREADY_FINANCED"
                    if result.financed
                    else "RECEIVABLE_ALREADY_LOCKED"
                    if result.locked
                    else None
                    if result.eligible
                    else "RECEIVABLE_NOT_OPEN_FOR_FINANCING"
                )
            self._audit(
                "DUPLICATE_CHECKED",
                metadata={
                    "fingerprint": fingerprint,
                    "status": asset.status if asset else "ABSENT",
                    "backend": "mock",
                },
            )
            await self.session.commit()
            return result
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise APIError(503, "LEDGER_UNAVAILABLE", "Registry lookup is unavailable.") from exc

    async def history(self, receivable_id: UUID) -> HistoryResponse:
        try:
            row = await self._load(receivable_id)
            events = await self.session.scalars(
                select(AuditEvent)
                .where(AuditEvent.receivable_id == row.id)
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
            entries = []
            if row.asset_id:
                entries = await create_ledger_client(
                    self.session, self.settings, self.actor
                ).get_history(row.asset_id)
            return HistoryResponse(
                events=[AuditResponse.model_validate(event) for event in events], ledger=entries
            )
        except SQLAlchemyError as exc:
            raise APIError(503, "LEDGER_UNAVAILABLE", "History is unavailable.") from exc
