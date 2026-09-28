"""Explicitly scoped local mock fixture reset. Never mutates a real ledger."""

from datetime import date

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.domain import Document, Receivable
from app.models.drunix import LedgerArtifact
from app.models.financing import FinancingAgreement, FinancingOffer, MockDisbursement
from app.models.ledger import AuditEvent, LedgerTransaction, MockLedgerAsset, MockLedgerPrivate
from app.models.settlement import PaymentEvent

INVOICES = ("EXP-2026-1042", "DEMO-VERIFIED-01", "DEMO-FINANCED-01", "DEMO-REALIZED-01")


async def reset_demo(
    session: AsyncSession, settings: Settings, *, apply: bool = False
) -> list[dict[str, str]]:
    if settings.ledger_backend != "mock":
        raise ValueError("Reset is supported only in explicit mock mode.")
    if apply:
        # Prevent interleaved writes while checking and removing the related rows.
        await session.execute(text("SET LOCAL lock_timeout = '5s'"))
        await session.execute(
            text(
                "LOCK TABLE receivables, documents, financing_offers, "
                "financing_agreements, mock_disbursements, payment_events, audit_events, "
                "mock_ledger_assets, mock_ledger_private, ledger_transactions, ledger_artifacts "
                "IN EXCLUSIVE MODE"
            )
        )
    if await session.scalar(select(LedgerArtifact.key).limit(1)) is not None:
        raise ValueError("Database contains Drunix recovery inputs; reset is refused.")
    rows = list(
        await session.scalars(
            select(Receivable)
            .where(
                Receivable.exporter_org_id == "ORG_EXPORTER_ALPHA",
                Receivable.invoice_number.in_(INVOICES),
            )
            .order_by(Receivable.invoice_number)
        )
    )
    for row in rows:
        if (
            row.ledger_backend not in {None, "mock"}
            or row.ledger_network is not None
            or row.buyer_id != "BUYER-DE-001"
            or row.currency != "EUR"
            or row.face_value_minor != 1080000
            or row.invoice_date != date(2026, 9, 21)
            or row.due_date != date(2026, 11, 25)
        ):
            raise ValueError(
                "A named fixture has different terms or ledger binding; reset is refused."
            )
    plan = [
        {"id": str(r.id), "invoice": r.invoice_number, "asset_id": r.asset_id or ""} for r in rows
    ]
    if not apply or not rows:
        return plan
    ids = [r.id for r in rows]
    assets = [r.asset_id for r in rows if r.asset_id]
    agreements = select(FinancingAgreement.id).where(FinancingAgreement.receivable_id.in_(ids))
    await session.execute(
        delete(MockDisbursement).where(MockDisbursement.agreement_id.in_(agreements))
    )
    for model in (FinancingAgreement, FinancingOffer, PaymentEvent, Document):
        await session.execute(delete(model).where(model.receivable_id.in_(ids)))
    # Preserve audit/security evidence and signed simulator attempts, but retire detail links.
    await session.execute(
        update(AuditEvent).where(AuditEvent.receivable_id.in_(ids)).values(receivable_id=None)
    )
    for ledger_model in (LedgerTransaction, MockLedgerPrivate, MockLedgerAsset):
        await session.execute(delete(ledger_model).where(ledger_model.asset_id.in_(assets)))
    await session.execute(delete(Receivable).where(Receivable.id.in_(ids)))
    return plan
