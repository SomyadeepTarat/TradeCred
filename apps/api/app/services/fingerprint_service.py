"""TC-FP-1 canonical business identity, independent of the uploaded artifact."""

import hashlib
import json
import re
from datetime import date
from decimal import Decimal
from typing import Literal, TypedDict

from iso4217 import Currency

MAX_AMOUNT_MINOR = 2**63 - 1


class CanonicalInvoice(TypedDict):
    version: Literal["TC-FP-1"]
    exporterId: str
    buyerId: str
    invoiceNumber: str
    currency: str
    amountMinor: int
    invoiceDate: str


def normalize_identifier(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value):
        raise ValueError(
            "Identifiers must contain only ASCII letters, digits, hyphens or underscores."
        )
    return value.upper()


def normalize_invoice_number(value: str) -> str:
    # Whitespace is formatting. Preserve punctuation that may identify a different invoice.
    compact = "".join(value.split())
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,120}", compact):
        raise ValueError("Unsupported invoice-number characters.")
    normalized = compact.upper()
    if not re.search(r"[A-Z0-9]", normalized):
        raise ValueError("Invoice number must contain at least one letter or digit.")
    return normalized


def normalize_currency(value: str) -> str:
    value = value.strip().upper()
    try:
        currency = Currency(value)
    except ValueError as exc:
        raise ValueError("Unknown ISO-4217 currency.") from exc
    if currency.exponent is None:
        raise ValueError("Currency has no defined minor units.")
    return value


def amount_to_minor(amount: str, currency: str) -> int:
    """Accept decimal text, never binary floats, exponent notation or implicit rounding."""
    if not isinstance(amount, str) or not re.fullmatch(
        r"[0-9]{1,19}(?:\.[0-9]{1,4})?", amount.strip()
    ):
        raise ValueError("Amount must be a positive decimal string without grouping or exponents.")
    exponent = Currency(normalize_currency(currency)).exponent
    assert isinstance(exponent, int)
    scaled = Decimal(amount.strip()) * (10**exponent)
    if scaled != scaled.to_integral_value():
        raise ValueError("Amount has fractional minor units; rounding is not permitted.")
    result = int(scaled)
    if not 0 < result <= MAX_AMOUNT_MINOR:
        raise ValueError("Amount is outside the supported positive 64-bit range.")
    return result


def canonical_invoice(
    *,
    exporter_id: str,
    buyer_id: str,
    invoice_number: str,
    currency: str,
    amount_minor: int,
    invoice_date: date,
) -> CanonicalInvoice:
    if type(amount_minor) is not int or not 0 < amount_minor <= MAX_AMOUNT_MINOR:
        raise ValueError("amountMinor must be a positive 64-bit integer.")
    if type(invoice_date) is not date:
        raise ValueError("invoiceDate must be a date, without a time component.")
    return {
        "version": "TC-FP-1",
        "exporterId": normalize_identifier(exporter_id),
        "buyerId": normalize_identifier(buyer_id),
        "invoiceNumber": normalize_invoice_number(invoice_number),
        "currency": normalize_currency(currency),
        "amountMinor": amount_minor,
        "invoiceDate": invoice_date.isoformat(),
    }


def canonical_bytes(invoice: CanonicalInvoice) -> bytes:
    # Explicit order is part of the public TC-FP-1 contract; never sort alphabetically.
    values: dict[str, object] = dict(invoice)
    ordered = {
        key: values[key]
        for key in (
            "version",
            "exporterId",
            "buyerId",
            "invoiceNumber",
            "currency",
            "amountMinor",
            "invoiceDate",
        )
    }
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def invoice_fingerprint(invoice: CanonicalInvoice) -> str:
    return hashlib.sha256(canonical_bytes(invoice)).hexdigest()


def document_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
