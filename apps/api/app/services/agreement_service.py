import hashlib
import json
from datetime import UTC, datetime


def agreement_payload(
    *,
    asset_id: str,
    exporter_org_id: str,
    financier_org_id: str,
    advance_amount_minor: int,
    currency: str,
    discount_rate_bps: int,
    tenor_days: int,
    accepted_at: datetime,
) -> dict[str, str | int]:
    return dict(
        agreementVersion="TC-AGR-1",
        assetId=asset_id,
        exporterOrgId=exporter_org_id,
        financierOrgId=financier_org_id,
        advanceAmountMinor=advance_amount_minor,
        currency=currency,
        discountRateBps=discount_rate_bps,
        tenorDays=tenor_days,
        acceptedAt=accepted_at.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        termsVersion="demo-v1",
        assignmentStatus="CONSORTIUM_FINANCING_LOCK",
    )


def canonical_agreement(payload: dict[str, str | int]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def agreement_hash(payload: dict[str, str | int]) -> str:
    return hashlib.sha256(canonical_agreement(payload).encode("utf-8")).hexdigest()
