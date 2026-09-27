from sqlalchemy import ColumnElement, exists, or_, select

from app.models.domain import Receivable, ReceivableStatus
from app.models.financing import FinancingOffer


def financier_scope(organization_id: str) -> ColumnElement[bool]:
    return (Receivable.asset_id.is_not(None)) & or_(
        Receivable.status == ReceivableStatus.FINANCE_AVAILABLE,
        Receivable.owner_org_id == organization_id,
        exists(
            select(FinancingOffer.id).where(
                FinancingOffer.receivable_id == Receivable.id,
                FinancingOffer.financier_org_id == organization_id,
            )
        ),
    )
