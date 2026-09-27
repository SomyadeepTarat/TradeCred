from datetime import UTC, datetime, timedelta, timezone

from app.services.agreement_service import agreement_hash, agreement_payload, canonical_agreement


def test_canonical_agreement_is_stable_and_commits_all_terms():
    values = dict(
        asset_id="TC-1",
        exporter_org_id="EXPORTER",
        financier_org_id="BANK",
        advance_amount_minor=975000,
        currency="EUR",
        discount_rate_bps=250,
        tenor_days=60,
        accepted_at=datetime(2026, 9, 26, 12, 30, tzinfo=UTC),
    )
    payload = agreement_payload(**values)
    canonical = canonical_agreement(payload)
    assert canonical == (
        '{"acceptedAt":"2026-09-26T12:30:00.000000Z","advanceAmountMinor":975000,'
        '"agreementVersion":"TC-AGR-1","assetId":"TC-1","assignmentStatus":"CONSORTIUM_FINANCING_LOCK",'
        '"currency":"EUR","discountRateBps":250,"exporterOrgId":"EXPORTER","financierOrgId":"BANK",'
        '"tenorDays":60,"termsVersion":"demo-v1"}'
    )
    reordered = dict(reversed(list(payload.items())))
    assert agreement_hash(reordered) == agreement_hash(payload)
    local = values | {
        "accepted_at": datetime(2026, 9, 26, 18, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    }
    assert agreement_hash(agreement_payload(**local)) == agreement_hash(payload)
    for key, value in [
        ("advanceAmountMinor", 975001),
        ("currency", "INR"),
        ("discountRateBps", 251),
        ("tenorDays", 61),
        ("financierOrgId", "OTHER"),
        ("termsVersion", "different"),
    ]:
        assert agreement_hash(payload | {key: value}) != agreement_hash(payload)
