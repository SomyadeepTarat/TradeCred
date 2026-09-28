from decimal import Decimal
from typing import Literal
from uuid import UUID

from iso4217 import Currency
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import APIError
from app.integrations.ledger.mock import value_bucket
from app.models.domain import Document, Receivable, Role, User
from app.models.domain import ReceivableStatus as S
from app.models.financing import FinancingOffer
from app.models.ledger import AuditEvent
from app.schemas.ledger import AuditResponse
from app.schemas.receivable_views import (
    DashboardSummary,
    ReceivableDetail,
    ReceivablePage,
    ReceivableView,
)
from app.services.receivable_access import financier_scope
from app.services.state_machine import TRANSITIONS


class ReceivableQueries:
    def __init__(self, session: AsyncSession, settings: Settings, user: User) -> None:
        self.session, self.settings, self.user = session, settings, user

    def _scope(self) -> ColumnElement[bool]:
        if self.user.role == Role.ADMIN:
            return Receivable.id.is_not(None)
        if self.user.role == Role.FINANCIER:
            return financier_scope(self.user.organization_id)
        if self.user.role == Role.EXPORTER:
            return Receivable.exporter_org_id == self.user.organization_id
        raise APIError(
            403,
            "UNAUTHORIZED_ROLE",
            "Receivables workspace requires exporter or administrator access.",
        )

    def _view(self, row: Receivable) -> ReceivableView:
        # Administrators receive a sanitized view, not private commercial values.
        private = self.user.role == Role.EXPORTER
        exponent = Currency(row.currency).exponent
        amount = format(Decimal(row.face_value_minor).scaleb(-int(exponent or 0)), "f")
        return ReceivableView(
            id=row.id,
            asset_id=row.asset_id,
            exporter_org_id=row.exporter_org_id,
            invoice_number=row.invoice_number if private else None,
            buyer_id=row.buyer_id if private else None,
            invoice_date=row.invoice_date if self.user.role != Role.FINANCIER else None,
            due_date=row.due_date,
            currency=row.currency,
            face_value=amount if private else None,
            face_value_bucket=value_bucket(row.face_value_minor, row.currency),
            status=row.status,
            invoice_fingerprint=row.invoice_fingerprint,
            document_hash=row.document_hash,
            owner_org_id=row.owner_org_id,
            financing_agreement_hash=row.financing_agreement_hash,
            ebrc_status=row.ebrc_status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list(
        self,
        status: S | None,
        limit: int,
        offset: int,
        view: Literal["all", "available", "assigned", "offers"] = "all",
    ) -> ReceivablePage:
        scope = self._scope()
        if self.user.role == Role.FINANCIER:
            if view == "available":
                scope = scope & (Receivable.status == S.FINANCE_AVAILABLE)
            elif view == "assigned":
                scope = scope & (Receivable.owner_org_id == self.user.organization_id)
            elif view == "offers":
                scope = scope & Receivable.id.in_(
                    select(FinancingOffer.receivable_id).where(
                        FinancingOffer.financier_org_id == self.user.organization_id
                    )
                )
        grouped = (
            await self.session.execute(
                select(Receivable.status, func.count()).where(scope).group_by(Receivable.status)
            )
        ).all()
        counts = {state: count for state, count in grouped}
        settled = {S.PAYMENT_CONFIRMED, S.REALIZED, S.EBRC_ELIGIBLE, S.CLOSED}
        filtered = select(Receivable).where(scope)
        if status is not None:
            filtered = filtered.where(Receivable.status == status)
        rows = await self.session.scalars(
            filtered.order_by(Receivable.created_at.desc(), Receivable.id.desc())
            .limit(limit)
            .offset(offset)
        )
        events = await self.session.scalars(
            select(AuditEvent)
            .join(Receivable, AuditEvent.receivable_id == Receivable.id)
            .where(scope)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(5)
        )
        total = sum(counts.values())
        return ReceivablePage(
            items=[self._view(row) for row in rows],
            total=counts.get(status, 0) if status is not None else total,
            summary=DashboardSummary(
                total=total,
                available=counts.get(S.FINANCE_AVAILABLE, 0),
                financed=sum(counts.get(s, 0) for s in {S.FINANCED, S.OVERDUE, S.DISPUTED}),
                settled=sum(counts.get(s, 0) for s in settled),
            ),
            recent_activity=[]
            if self.user.role == Role.FINANCIER
            else [AuditResponse.model_validate(event) for event in events],
        )

    async def detail(self, receivable_id: UUID) -> ReceivableDetail:
        row = await self.session.scalar(
            select(Receivable).where(self._scope(), Receivable.id == receivable_id)
        )
        if row is None:
            raise APIError(404, "RECEIVABLE_NOT_FOUND", "Receivable not found.")
        document_id = await self.session.scalar(
            select(Document.id).where(Document.receivable_id == row.id)
        )
        actions = []
        candidates = {
            "submit": S.SUBMITTED,
            "verify": S.VERIFIED,
            "register": S.REGISTERED,
            "open-financing": S.FINANCE_AVAILABLE,
            "realize": S.REALIZED,
            "ebrc-eligible": S.EBRC_ELIGIBLE,
            "close": S.CLOSED,
        }
        for action, target in candidates.items():
            role_allowed = (
                self.user.role == Role.ADMIN
                if action in {"verify", "realize", "ebrc-eligible", "close"}
                else self.user.role
                in (
                    {Role.EXPORTER}
                    if self.settings.ledger_backend == "drunix"
                    else {Role.EXPORTER, Role.ADMIN}
                )
                if action == "register"
                else self.user.role == Role.EXPORTER
            )
            if role_allowed and target in TRANSITIONS.get(row.status, frozenset()) and document_id:
                actions.append(action)
        return ReceivableDetail(
            **self._view(row).model_dump(),
            document_available=document_id is not None and self.user.role == Role.EXPORTER,
            available_actions=actions,
            ledger_backend=row.ledger_backend or self.settings.ledger_backend,
        )
