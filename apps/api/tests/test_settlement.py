import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_database_engine
from app.core.errors import APIError
from app.main import create_app
from app.models.domain import Receivable, User
from app.models.ledger import LedgerTransaction, MockLedgerAsset
from app.models.settlement import PaymentEvent, SecurityEvent
from app.security.signatures import DOMAIN
from app.services.settlement_service import SettlementService
from tests.helpers import login
from tests.test_financing import offer, setup

pytestmark = pytest.mark.integration
URL = "/api/v1/settlement/events"


@pytest.fixture
def bank_key(tmp_path, monkeypatch):
    key = Ed25519PrivateKey.generate()
    path = tmp_path / "public.pem"
    path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    monkeypatch.setenv(
        "BANK_TRUSTED_KEYS",
        json.dumps(
            {
                "test-key": {
                    "bank_id": "BANK_SETTLEMENT_01",
                    "organization_id": "ORG_SETTLEMENT_BANK",
                    "public_key_path": str(path),
                }
            }
        ),
    )
    return key


def financed(client, pdf_bytes, payout=True):
    owner, admin, bank, nbfc, draft, path = setup(client, pdf_bytes)
    first = offer(client, path, bank)
    assert client.post(f"/api/v1/offers/{first}/accept", headers=owner).status_code == 200
    if payout:
        assert client.post(path + "/disbursement/mock", headers=bank).status_code == 200
    asset = client.get(path, headers=owner).json()["asset_id"]
    return asset, draft, path, owner, bank, nbfc, admin


def payload(asset, **changes):
    return (
        dict(
            eventId="PAY-" + uuid4().hex,
            assetId=asset,
            bankId="BANK_SETTLEMENT_01",
            bankReference="IRM-DEMO-938291",
            amountMinor=1080000,
            currency="EUR",
            timestamp=datetime.now(UTC).isoformat(),
            nonce=uuid4().hex,
        )
        | changes
    )


def signed(key, event):
    body = json.dumps(event, separators=(",", ":")).encode()
    return body, {
        "X-TradeCred-Key-Id": "test-key",
        "Content-Type": "application/json",
        "X-TradeCred-Signature": base64.b64encode(key.sign(DOMAIN + body)).decode(),
    }


def test_valid_settlement_and_receipt_privacy(database, storage_root, pdf_bytes, bank_key):
    with TestClient(create_app()) as client:
        asset, draft, path, owner, bank, nbfc, admin = financed(client, pdf_bytes)
        event = payload(asset)
        body, headers = signed(bank_key, event)
        response = client.post(URL, content=body, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "PAYMENT_CONFIRMED"
        assert response.json()["transaction_id"].startswith("MOCK-")
        assert client.get(path, headers=owner).json()["status"] == "PAYMENT_CONFIRMED"
        for identity in (owner, bank, admin, login(client, "settlement@tradecred.demo")):
            read = client.get(URL + "/" + event["eventId"], headers=identity)
            assert read.status_code == 200
            assert read.headers["cache-control"] == "no-store"
            assert "bankReference" not in read.text and "amountMinor" not in read.text
        assert client.get(URL + "/" + event["eventId"], headers=nbfc).status_code == 404
        assert client.get(URL + "/" + event["eventId"]).status_code == 401
        for changes in ({}, {"eventId": "PAY-new"}, {"nonce": uuid4().hex}):
            replay_body, replay_headers = signed(bank_key, event | changes)
            replay = client.post(URL, content=replay_body, headers=replay_headers)
            assert replay.status_code == 409
            assert replay.json()["error"]["code"] == "PAYMENT_EVENT_REPLAY"
    with Session(database) as session:
        row = session.get(Receivable, UUID(draft["id"]))
        assert row.status == session.get(MockLedgerAsset, asset).status == "PAYMENT_CONFIRMED"
        assert row.settlement_reference == event["bankReference"]
        assert session.scalar(select(func.count()).select_from(PaymentEvent)) == 1
        assert session.scalar(select(func.count()).select_from(SecurityEvent)) == 3


@pytest.mark.parametrize(
    "case,code",
    [
        ("signature", "INVALID_PAYMENT_SIGNATURE"),
        ("tampered", "INVALID_PAYMENT_SIGNATURE"),
        ("unknown_key", "INVALID_PAYMENT_SIGNATURE"),
        ("missing", "INVALID_PAYMENT_SIGNATURE"),
        ("bank", "UNTRUSTED_BANK"),
        ("stale", "PAYMENT_TIMESTAMP_EXPIRED"),
        ("future", "PAYMENT_TIMESTAMP_EXPIRED"),
        ("amount", "PAYMENT_AMOUNT_MISMATCH"),
        ("currency", "PAYMENT_CURRENCY_MISMATCH"),
        ("state", "INVALID_STATE_TRANSITION"),
        ("float", "INVALID_PAYMENT_EVENT"),
        ("naive", "INVALID_PAYMENT_EVENT"),
        ("reference", "INVALID_PAYMENT_EVENT"),
        ("duplicate_json", "INVALID_PAYMENT_EVENT"),
        ("oversize", "INVALID_PAYMENT_EVENT"),
        ("disabled", "UNTRUSTED_BANK"),
    ],
)
def test_rejected_event_never_changes_state(
    database, storage_root, pdf_bytes, bank_key, case, code
):
    with TestClient(create_app()) as client:
        asset, draft, path, owner, bank, nbfc, admin = financed(client, pdf_bytes, case != "state")
        changes = {
            "bank": {"bankId": "OTHER_BANK"},
            "stale": {"timestamp": (datetime.now(UTC) - timedelta(minutes=6)).isoformat()},
            "future": {"timestamp": (datetime.now(UTC) + timedelta(minutes=6)).isoformat()},
            "amount": {"amountMinor": 975000},
            "currency": {"currency": "INR"},
            "float": {"amountMinor": 1080000.0},
            "naive": {"timestamp": "2026-09-27T00:00:00"},
            "reference": {"bankReference": " "},
        }.get(case, {})
        body, headers = signed(bank_key, payload(asset, **changes))
        if case == "signature":
            headers["X-TradeCred-Signature"] = "invalid"
        elif case == "tampered":
            body += b" "
        elif case == "unknown_key":
            headers["X-TradeCred-Key-Id"] = "unknown"
        elif case == "missing":
            headers = {}
        elif case in {"duplicate_json", "oversize"}:
            body = body[:-1] + b',"currency":"EUR"}' if case == "duplicate_json" else b" " * 8193
            headers["X-TradeCred-Signature"] = base64.b64encode(
                bank_key.sign(DOMAIN + body)
            ).decode()
        elif case == "disabled":
            with Session(database) as session, session.begin():
                user = session.scalar(select(User).where(User.email == "settlement@tradecred.demo"))
                user.is_active = False
        response = client.post(URL, content=body, headers=headers)
        assert response.status_code >= 400
        assert response.json()["error"]["code"] == code, response.text
    with Session(database) as session:
        expected = "LOCKED" if case == "state" else "FINANCED"
        assert session.get(MockLedgerAsset, asset).status == expected
        assert session.scalar(select(func.count()).select_from(PaymentEvent)) == 0
        assert session.scalar(select(func.count()).select_from(SecurityEvent)) == 1


@pytest.mark.parametrize("failure", ["ledger", "drunix"])
def test_rollback_and_retry(database, storage_root, pdf_bytes, bank_key, failure, monkeypatch):
    with TestClient(create_app()) as client:
        asset, *_ = financed(client, pdf_bytes)
    body, headers = signed(bank_key, payload(asset))
    if failure == "drunix":
        monkeypatch.setenv("LEDGER_BACKEND", "drunix")
    with TestClient(create_app()) as client:
        with patch(
            "app.integrations.ledger.mock.MockLedgerClient._record",
            side_effect=APIError(503, "LEDGER_UNAVAILABLE", "Injected ledger failure"),
        ):
            response = client.post(URL, content=body, headers=headers)
            assert response.status_code == 503
    with Session(database) as session:
        assert session.get(MockLedgerAsset, asset).status == "FINANCED"
        assert session.scalar(select(func.count()).select_from(PaymentEvent)) == 0
    monkeypatch.setenv("LEDGER_BACKEND", "mock")
    with TestClient(create_app()) as client:
        assert client.post(URL, content=body, headers=headers).status_code == 200


def test_concurrent_replay(database, storage_root, pdf_bytes, bank_key):
    with TestClient(create_app()) as client:
        asset, *_ = financed(client, pdf_bytes)
    body, headers = signed(bank_key, payload(asset))

    async def race():
        engine = create_database_engine(str(Settings().database_url))
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def send():
            async with factory() as session:
                try:
                    await SettlementService(session, Settings(), "race").process(
                        body, headers["X-TradeCred-Signature"], "test-key"
                    )
                    return "accepted"
                except APIError as exc:
                    return exc.code

        try:
            results = await asyncio.gather(send(), send())
            assert sorted(results) == ["PAYMENT_EVENT_REPLAY", "accepted"]
        finally:
            await engine.dispose()

    asyncio.run(race())
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(PaymentEvent)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(LedgerTransaction)
                .where(LedgerTransaction.to_status == "PAYMENT_CONFIRMED")
            )
            == 1
        )


def test_invalid_event_does_not_consume_identifiers(database, storage_root, pdf_bytes, bank_key):
    with TestClient(create_app()) as client:
        asset, *_ = financed(client, pdf_bytes)
        event = payload(asset, amountMinor=1)
        body, headers = signed(bank_key, event)
        assert client.post(URL, content=body, headers=headers).status_code == 409
        body, headers = signed(bank_key, event | {"amountMinor": 1080000})
        assert client.post(URL, content=body, headers=headers).status_code == 200


def test_simulator_cli_over_http(database, storage_root, pdf_bytes, bank_key, tmp_path):
    import subprocess
    import sys
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    private = tmp_path / "private.pem"
    private.write_bytes(
        bank_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    saved = tmp_path / "event.json"
    with TestClient(create_app()) as client:
        asset, *_ = financed(client, pdf_bytes)

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                response = client.post(URL, content=body, headers=dict(self.headers))
                self.send_response(response.status_code)
                self.end_headers()
                self.wfile.write(response.content)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = [
            sys.executable,
            str(root / "services/bank-simulator/app.py"),
            "--url",
            f"http://127.0.0.1:{server.server_port}/",
            "--private-key",
            str(private),
            "--key-id",
            "test-key",
        ]
        event_args = [
            "--asset-id",
            asset,
            "--amount-minor",
            "1080000",
            "--currency",
            "EUR",
            "--reference",
            "IRM-CLI",
        ]
        try:
            bad = subprocess.run(
                base + event_args + ["--invalid-signature"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert bad.returncode == 1 and "INVALID_PAYMENT_SIGNATURE" in bad.stdout
            good = subprocess.run(
                base + event_args + ["--save", str(saved)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert good.returncode == 0 and "PAYMENT_CONFIRMED" in good.stdout, good.stderr
            replay = subprocess.run(
                base + ["--replay", str(saved)], capture_output=True, text=True, timeout=15
            )
            assert replay.returncode == 1 and "PAYMENT_EVENT_REPLAY" in replay.stdout
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
