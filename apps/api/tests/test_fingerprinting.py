from datetime import date

import pytest

from app.services.fingerprint_service import (
    amount_to_minor,
    canonical_bytes,
    canonical_invoice,
    document_hash,
    invoice_fingerprint,
)


def identity(**changes: object):
    fields = dict(
        exporter_id="ORG_EXPORTER_ALPHA",
        buyer_id="BUYER-DE-001",
        invoice_number="EXP-2026-1042",
        currency="EUR",
        amount_minor=1080000,
        invoice_date=date(2026, 9, 21),
    )
    fields.update(changes)
    return canonical_invoice(**fields)


def test_fixed_canonical_vector() -> None:
    assert canonical_bytes(identity()) == (
        b'{"version":"TC-FP-1","exporterId":"ORG_EXPORTER_ALPHA","buyerId":"BUYER-DE-001",'
        b'"invoiceNumber":"EXP-2026-1042","currency":"EUR","amountMinor":1080000,"invoiceDate":"2026-09-21"}'
    )
    assert (
        invoice_fingerprint(identity())
        == "febfe7ea6bba251d86dcbc6444a714a1da9e2797ec8959f5ae910a3d2140453b"
    )
    assert canonical_bytes(dict(reversed(list(identity().items())))) == canonical_bytes(identity())


@pytest.mark.parametrize(
    "changes",
    [
        {"exporter_id": " org_exporter_alpha ", "buyer_id": " buyer-de-001 "},
        {"currency": " eur "},
        {"invoice_number": " exp - 2026 - 1042 "},
        {"invoice_number": "EXP-\t2026-\n1042"},
        {"invoice_number": "  EXP-2026-1042 "},
    ],
)
def test_format_variants_same_fingerprint(changes: dict[str, object]) -> None:
    assert invoice_fingerprint(identity(**changes)) == invoice_fingerprint(identity())


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_minor": 1080001},
        {"invoice_date": date(2026, 9, 22)},
        {"buyer_id": "BUYER-DE-002"},
        {"exporter_id": "ORG_EXPORTER_BETA"},
        {"invoice_number": "EXP-2026-01042"},
        {"invoice_number": "EXP20261042"},
        {"invoice_number": "EXP/2026/1042"},
        {"currency": "USD"},
    ],
)
def test_business_identity_changes_fingerprint(changes: dict[str, object]) -> None:
    assert invoice_fingerprint(identity(**changes)) != invoice_fingerprint(identity())


def test_changed_pdf_changes_only_document_hash(pdf_bytes: bytes) -> None:
    first = pdf_bytes
    second = pdf_bytes + b"\n"
    assert document_hash(first) != document_hash(second)
    assert invoice_fingerprint(identity()) == invoice_fingerprint(
        identity(invoice_number="exp-2026-1042")
    )


@pytest.mark.parametrize(
    "amount,currency,expected",
    [
        ("10800.00", "EUR", 1080000),
        ("10800", "eur", 1080000),
        (" 10800.0000 ", "INR", 1080000),
        ("123", "JPY", 123),
        ("1.234", "KWD", 1234),
        ("0.29", "USD", 29),
        ("92233720368547758.07", "EUR", 9223372036854775807),
    ],
)
def test_exact_minor_units(amount: str, currency: str, expected: int) -> None:
    assert amount_to_minor(amount, currency) == expected


@pytest.mark.parametrize(
    "amount,currency",
    [
        ("0", "EUR"),
        ("-1", "EUR"),
        ("NaN", "EUR"),
        ("Infinity", "EUR"),
        ("1e3", "EUR"),
        ("1,000", "EUR"),
        ("1.001", "EUR"),
        ("1.5", "JPY"),
        ("1", "ZZZ"),
        ("1", "XAU"),
        ("92233720368547758.08", "EUR"),
        (1.2, "EUR"),
        (True, "EUR"),
    ],
)
def test_ambiguous_or_invalid_amounts_rejected(amount: object, currency: str) -> None:
    with pytest.raises(ValueError):
        amount_to_minor(amount, currency)


@pytest.mark.parametrize(
    "changes",
    [
        {"invoice_number": "---"},
        {"invoice_number": "INV#001"},
        {"invoice_number": "ＩＮＶ1"},
        {"buyer_id": "BUY ER"},
        {"buyer_id": "straße"},
        {"amount_minor": True},
        {"amount_minor": 1.5},
    ],
)
def test_ambiguous_identity_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        identity(**changes)
