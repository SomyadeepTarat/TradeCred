from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.core.config import Settings
from app.core.errors import APIError
from app.integrations.storage.base import DocumentStorage, DocumentTooLargeError
from app.models.domain import Document, Receivable, ReceivableStatus, User
from app.repositories.receivables import ReceivableRepository
from app.schemas.receivables import DraftResponse, IntegrityResponse, InvoiceMetadata
from app.services.audit_service import record_audit
from app.services.document_service import validate_pdf
from app.services.fingerprint_service import (
    amount_to_minor,
    canonical_invoice,
    document_hash,
    invoice_fingerprint,
)


class ReceivableService:
    def __init__(
        self,
        session: AsyncSession,
        storage: DocumentStorage,
        settings: Settings,
        request_id: str | None = None,
    ) -> None:
        self.request_id = request_id or str(uuid4())
        self.session = session
        self.repository = ReceivableRepository(session)
        self.storage = storage
        self.settings = settings

    async def create_draft(self, metadata: str, upload: UploadFile, user: User) -> DraftResponse:
        try:
            invoice = InvoiceMetadata.model_validate_json(metadata)
        except ValidationError as exc:
            raise APIError(
                422, "INVALID_INVOICE_METADATA", "Provide valid invoice metadata as documented."
            ) from exc
        if upload.content_type != "application/pdf":
            raise APIError(
                415, "UNSUPPORTED_DOCUMENT_TYPE", "The document must be application/pdf."
            )
        data = await upload.read(self.settings.max_upload_bytes + 1)
        if len(data) > self.settings.max_upload_bytes:
            raise APIError(413, "UPLOAD_TOO_LARGE", "PDF exceeds the upload size limit.")
        await run_in_threadpool(validate_pdf, data)
        amount_minor = amount_to_minor(invoice.amount, invoice.currency)
        identity = canonical_invoice(
            exporter_id=user.organization_id,
            buyer_id=invoice.buyer_id,
            invoice_number=invoice.invoice_number,
            currency=invoice.currency,
            amount_minor=amount_minor,
            invoice_date=invoice.invoice_date,
        )
        fingerprint = invoice_fingerprint(identity)
        digest = document_hash(data)
        receivable_id, document_id = uuid4(), uuid4()
        key = document_id.hex + ".pdf"
        draft = Receivable(
            id=receivable_id,
            exporter_org_id=user.organization_id,
            buyer_id=invoice.buyer_id,
            invoice_number=invoice.invoice_number,
            invoice_date=invoice.invoice_date,
            currency=invoice.currency,
            face_value_minor=amount_minor,
            due_date=invoice.due_date,
            document_hash=digest,
            invoice_fingerprint=fingerprint,
            status=ReceivableStatus.DRAFT,
        )
        document = Document(
            id=document_id,
            receivable_id=receivable_id,
            uploaded_by_user_id=user.id,
            storage_key=key,
            document_hash=digest,
            size_bytes=len(data),
            content_type="application/pdf",
        )
        actor_id, actor_org = user.id, user.organization_id
        try:
            await self.repository.add_draft(draft, document)
        except IntegrityError as exc:
            await self.session.rollback()
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint == "receivables_invoice_fingerprint_key":
                record_audit(
                    self.session,
                    "DUPLICATE_REJECTED",
                    actor_user_id=actor_id,
                    actor_org_id=actor_org,
                    request_id=self.request_id,
                    metadata={"fingerprint": fingerprint, "reason": "LOCAL_DUPLICATE"},
                )
                try:
                    await self.session.commit()
                except SQLAlchemyError as audit_error:
                    await self.session.rollback()
                    raise APIError(
                        503, "DATABASE_UNAVAILABLE", "Could not record duplicate rejection."
                    ) from audit_error
                raise APIError(
                    409, "DUPLICATE_RECEIVABLE", "This invoice is already recorded locally."
                ) from exc
            raise APIError(503, "DATABASE_UNAVAILABLE", "The draft could not be saved.") from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise APIError(503, "DATABASE_UNAVAILABLE", "The draft could not be saved.") from exc
        try:
            await run_in_threadpool(self.storage.write, key, data)
        except OSError as exc:
            await self.session.rollback()
            raise APIError(
                503, "DOCUMENT_STORAGE_UNAVAILABLE", "The document could not be stored."
            ) from exc
        try:
            record_audit(
                self.session,
                "RECEIVABLE_CREATED",
                actor_user_id=actor_id,
                actor_org_id=actor_org,
                request_id=self.request_id,
                receivable_id=receivable_id,
                metadata={"fingerprint": fingerprint, "toStatus": "DRAFT"},
            )
            await self.session.commit()
        except SQLAlchemyError as exc:
            await self.session.rollback()
            # The commit may have reached PostgreSQL. Preserve the file rather than
            # deleting data referenced by a possibly committed row. Never report success.
            raise APIError(
                503, "DATABASE_UNAVAILABLE", "Could not confirm the draft was saved."
            ) from exc
        return DraftResponse(
            id=receivable_id,
            status=ReceivableStatus.DRAFT,
            document_id=document_id,
            document_hash=digest,
            invoice_fingerprint=fingerprint,
            currency=invoice.currency,
            face_value_minor=amount_minor,
        )

    async def _read_owned(self, receivable_id: UUID, user: User) -> tuple[Document, bytes]:
        document = await self.repository.owned_document(receivable_id, user.organization_id)
        if document is None:
            raise APIError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
        try:
            data = await run_in_threadpool(
                self.storage.read,
                document.storage_key,
                self.settings.max_upload_bytes,
            )
        except DocumentTooLargeError as exc:
            raise APIError(
                409, "DOCUMENT_INTEGRITY_FAILED", "Stored document exceeds its size limit."
            ) from exc
        except (OSError, ValueError) as exc:
            raise APIError(
                503, "DOCUMENT_STORAGE_UNAVAILABLE", "The document is unavailable."
            ) from exc
        return document, data

    async def check_integrity(self, receivable_id: UUID, user: User) -> IntegrityResponse:
        document, data = await self._read_owned(receivable_id, user)
        actual = document_hash(data)
        return IntegrityResponse(
            document_id=document.id,
            expected_hash=document.document_hash,
            actual_hash=actual,
            verified=actual == document.document_hash and len(data) == document.size_bytes,
        )

    async def download(self, receivable_id: UUID, user: User) -> bytes:
        document, data = await self._read_owned(receivable_id, user)
        if document_hash(data) != document.document_hash or len(data) != document.size_bytes:
            raise APIError(
                409, "DOCUMENT_INTEGRITY_FAILED", "Stored document failed its integrity check."
            )
        return data
