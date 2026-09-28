"""Create fictional demo fixtures through authenticated APIs, never direct state edits."""

import json
import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import httpx
from dotenv import load_dotenv
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

ROOT = Path(__file__).resolve().parents[1]


def seed_fixtures(client: httpx.Client, password: str) -> dict[str, str]:
    headers = {}
    for role in ("exporter", "admin", "bank", "settlement"):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": role + "@tradecred.demo", "password": password},
        )
        response.raise_for_status()
        headers[role] = {"Authorization": "Bearer " + response.json()["access_token"]}

    def call(method: str, path: str, role: str, **kwargs):
        result = client.request(method, "/api/v1/" + path, headers=headers[role], **kwargs)
        if result.is_error:
            code = result.json().get("error", {}).get("code", "REQUEST_FAILED")
            raise RuntimeError(f"Demo request failed: {method} {path}: {code}")
        return result.json()

    existing = []
    offset = 0
    while True:
        page = call("GET", f"receivables?limit=100&offset={offset}", "exporter")
        existing.extend(page["items"])
        offset += 100
        if offset >= page["total"]:
            break
    directory = ROOT / "data" / "demo"
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for number, target in (
        ("EXP-2026-1042", "FINANCE_AVAILABLE"),
        ("DEMO-VERIFIED-01", "VERIFIED"),
        ("DEMO-FINANCED-01", "FINANCED"),
        ("DEMO-REALIZED-01", "REALIZED"),
    ):
        metadata = dict(
            buyerId="BUYER-DE-001",
            invoiceNumber=number,
            invoiceDate="2026-09-21",
            currency="EUR",
            amount="10800.00",
            dueDate="2026-11-25",
        )
        writer = PdfWriter()
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        lines = [
            "FICTIONAL DEMO INVOICE - NOT VALID FOR PAYMENT",
            "Alpha Looms Demo",
            f"Invoice: {number}",
            "Buyer: BUYER-DE-001",
            "Invoice date: 2026-09-21",
            "Due date: 2026-11-25",
            "Face value: EUR 10,800.00",
            "TradeCred sandbox fixture. No real customer or bank data.",
        ]
        stream = DecodedStreamObject()
        stream.set_data(
            (
                "BT /F1 14 Tf 45 780 Td "
                + " 0 -32 Td ".join("(" + line + ") Tj" for line in lines)
                + " ET"
            ).encode("ascii")
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.add_metadata({"/Title": f"Fictional Alpha Looms invoice {number} — EUR 10,800"})
        buffer = BytesIO()
        writer.write(buffer)
        document = buffer.getvalue()
        (directory / (number + ".pdf")).write_bytes(document)
        (directory / (number + ".json")).write_text(json.dumps(metadata, indent=2) + "\n")
        row = next((r for r in existing if r["invoice_number"] == number), None)
        if row is not None and any(
            row[field] != expected
            for field, expected in {
                "buyer_id": "BUYER-DE-001",
                "invoice_date": "2026-09-21",
                "currency": "EUR",
                "face_value": "10800.00",
                "due_date": "2026-11-25",
            }.items()
        ):
            raise RuntimeError(f"Existing {number} has different terms; refusing to modify it.")
        if row is None:
            row = call(
                "POST",
                "receivables",
                "exporter",
                data={"metadata": json.dumps(metadata)},
                files={"document": (number + ".pdf", document, "application/pdf")},
            )
        path = "receivables/" + row["id"]
        manifest[number] = row["id"]
        # Continue interrupted setup, preserving any state beyond the fixture's target.
        order = [
            "DRAFT",
            "SUBMITTED",
            "VERIFIED",
            "REGISTERED",
            "FINANCE_AVAILABLE",
            "LOCKED",
            "FINANCED",
            "PAYMENT_CONFIRMED",
            "REALIZED",
            "EBRC_ELIGIBLE",
            "CLOSED",
        ]
        while order.index(row["status"]) < order.index(target):
            state = row["status"]
            if state in {"DRAFT", "SUBMITTED", "VERIFIED", "REGISTERED"}:
                action, role = {
                    "DRAFT": ("submit", "exporter"),
                    "SUBMITTED": ("verify", "admin"),
                    "VERIFIED": ("register", "exporter"),
                    "REGISTERED": ("open-financing", "exporter"),
                }[state]
                call("POST", path + "/" + action, role)
            elif state == "FINANCE_AVAILABLE":
                offers = call("GET", path + "/offers", "bank")["offers"]
                offered = next(
                    (
                        o
                        for o in offers
                        if o["status"] == "OFFERED"
                        and datetime.fromisoformat(o["expires_at"].replace("Z", "+00:00"))
                        > datetime.now(UTC)
                    ),
                    None,
                )
                if offered is None:
                    offered = call(
                        "POST",
                        path + "/offers",
                        "bank",
                        json={
                            "advanceAmount": "9750.00",
                            "currency": "EUR",
                            "discountRateBps": 250,
                            "tenorDays": 60,
                            "expiresAt": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                        },
                    )
                call("POST", "offers/" + offered["id"] + "/accept", "exporter")
            elif state == "LOCKED":
                call("POST", path + "/disbursement/mock", "bank")
            elif state == "FINANCED":
                result = call(
                    "POST",
                    "simulator/events",
                    "settlement",
                    json={
                        "asset_id": row["asset_id"],
                        "amount_minor": 1080000,
                        "currency": "EUR",
                        "reference": "IRM-DEMO-SEED-01",
                        "mode": "valid",
                    },
                )
                if not result["accepted"]:
                    raise RuntimeError("Seed settlement was rejected: " + result["code"])
            elif state == "PAYMENT_CONFIRMED":
                call("POST", path + "/realize", "admin")
            row = call("GET", path, "exporter")
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    load_dotenv(ROOT / ".env")
    with httpx.Client(
        base_url=os.environ.get("DEMO_API_URL", "http://127.0.0.1:8000"),
        timeout=70,
        trust_env=False,
    ) as client:
        manifest = seed_fixtures(client, os.environ.get("DEMO_PASSWORD", ""))
    print("Demo fixtures prepared through API workflows; advanced records preserved.")
    for invoice, row_id in manifest.items():
        print(f"{invoice}: /receivables/{row_id}")
    print("Duplicate fixture: upload data/demo/EXP-2026-1042.pdf with its matching JSON metadata.")


if __name__ == "__main__":
    main()
