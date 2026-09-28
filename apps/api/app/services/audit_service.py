from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import AuditEvent

SAFE_FIELDS = {
    "fingerprint",
    "eventId",
    "offerId",
    "agreementHash",
    "paymentId",
    "fromStatus",
    "toStatus",
    "backend",
    "transactionId",
    "reason",
    "status",
}


def record_audit(
    session: AsyncSession,
    event_type: str,
    *,
    actor_user_id: UUID,
    actor_org_id: str,
    request_id: str,
    receivable_id: UUID | None = None,
    asset_id: str | None = None,
    metadata: dict[str, str] | None = None,
) -> None:
    if metadata and not metadata.keys() <= SAFE_FIELDS:
        raise ValueError("Unsupported audit metadata field.")
    session.add(
        AuditEvent(
            event_type=event_type,
            actor_user_id=actor_user_id,
            actor_org_id=actor_org_id,
            request_id=request_id,
            receivable_id=receivable_id,
            asset_id=asset_id,
            metadata_json=metadata or {},
            created_at=datetime.now(UTC),
        )
    )
