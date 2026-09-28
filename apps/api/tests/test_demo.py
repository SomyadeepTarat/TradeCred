import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.models.settlement import PaymentEvent, SecurityEvent
from tests.helpers import login
from tests.test_settlement import bank_key as key_fixture
from tests.test_settlement import financed

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def signer(tmp_path, monkeypatch):
    key = key_fixture.__wrapped__(tmp_path, monkeypatch)
    private = tmp_path / "private.pem"
    private.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    monkeypatch.setenv("BANK_PRIVATE_KEY_PATH", str(private))
    monkeypatch.setenv("SIMULATOR_ENABLED", "true")
    monkeypatch.setenv("SIMULATOR_TOKEN", "sandbox-test-token-" * 3)
    monkeypatch.setenv("SIMULATOR_KEY_ID", "test-key")
    monkeypatch.syspath_prepend(str(ROOT / "services/bank-simulator"))
    spec = importlib.util.spec_from_file_location(
        "bank_server", ROOT / "services/bank-simulator/server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.ASGITransport(app=module.app)),
    )
    return module.app


def test_simulator_real_signing_security_audit_and_closure(
    database, storage_root, pdf_bytes, signer
):
    with TestClient(create_app()) as client:
        asset, draft, path, owner, bank, nbfc, admin = financed(client, pdf_bytes)
        operator = login(client, "settlement@tradecred.demo")
        payload = dict(
            asset_id=asset,
            amount_minor=1080000,
            currency="EUR",
            reference="IRM-DEMO-938291",
            mode="invalid",
        )
        for actor in (owner, bank, admin):
            assert (
                client.post("/api/v1/simulator/events", headers=actor, json=payload).status_code
                == 403
            )
        assets = client.get("/api/v1/simulator/assets", headers=operator).json()
        assert assets == [dict(asset_id=asset, currency="EUR", status="FINANCED")]
        invalid = client.post("/api/v1/simulator/events", headers=operator, json=payload)
        assert invalid.status_code == 200, invalid.text
        assert invalid.json()["code"] == "INVALID_PAYMENT_SIGNATURE"
        assert client.get(path, headers=owner).json()["status"] == "FINANCED"
        wrong = client.post(
            "/api/v1/simulator/events",
            headers=operator,
            json=payload | {"mode": "valid", "amount_minor": 1},
        ).json()
        assert wrong["code"] == "PAYMENT_AMOUNT_MISMATCH"
        valid = client.post(
            "/api/v1/simulator/events", headers=operator, json=payload | {"mode": "valid"}
        )
        assert valid.status_code == 200 and valid.json()["accepted"], valid.text
        result = valid.json()
        assert result["backend"] == "mock"
        assert "signature" not in result and "body" not in result
        replay = client.post(
            f"/api/v1/simulator/events/{result['id']}/replay", headers=operator
        ).json()
        assert replay["code"] == "PAYMENT_EVENT_REPLAY"
        for action, state in (
            ("realize", "REALIZED"),
            ("ebrc-eligible", "EBRC_ELIGIBLE"),
            ("close", "CLOSED"),
        ):
            assert client.post(path + "/" + action, headers=owner).status_code == 403
            transition = client.post(path + "/" + action, headers=admin)
            assert transition.status_code == 200, transition.text
            assert transition.json()["status"] == state
        detail = client.get(path, headers=owner).json()
        assert detail["ebrc_status"] == "SELF_CERTIFICATION_PENDING"
        assert client.post(path + "/realize", headers=admin).status_code == 409
        for actor in (owner, bank, operator):
            assert client.get("/api/v1/audit/security-events", headers=actor).status_code == 403
        events = client.get("/api/v1/audit/security-events", headers=admin).json()
        assert {e["reason"] for e in events} >= {
            "INVALID_PAYMENT_SIGNATURE",
            "PAYMENT_EVENT_REPLAY",
        }
        assert all("payload_hash" not in e for e in events)
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(PaymentEvent)) == 1
        assert session.scalar(select(func.count()).select_from(SecurityEvent)) == 3


def test_signer_and_simulator_fail_closed(database, signer, monkeypatch):
    with TestClient(signer) as bank:
        assert bank.post("/sign", content=b"{}").status_code == 403
        assert (
            bank.post(
                "/sign",
                content=b"{}",
                headers={"Authorization": "Bearer " + "sandbox-test-token-" * 3},
            ).status_code
            == 422
        )
    monkeypatch.setenv("SIMULATOR_ENABLED", "false")
    with TestClient(create_app()) as client:
        operator = login(client, "settlement@tradecred.demo")
        assert client.get("/api/v1/simulator/assets", headers=operator).status_code == 404
        assert (
            client.post(
                "/api/v1/receivables/00000000-0000-0000-0000-000000000000/close", headers=operator
            ).status_code
            == 403
        )


def test_demo_seed_is_idempotent_and_uses_workflows(
    database, storage_root, signer, monkeypatch, tmp_path
):
    from tests.helpers import PASSWORD

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import seed_fixtures

    monkeypatch.setattr(seed_fixtures, "ROOT", tmp_path)
    with TestClient(create_app()) as client:
        first = seed_fixtures.seed_fixtures(client, PASSWORD)
        second = seed_fixtures.seed_fixtures(client, PASSWORD)
        assert first == second and len(first) == 4
        owner = login(client, "exporter@tradecred.demo")
        rows = client.get("/api/v1/receivables", headers=owner).json()["items"]
        assert {r["status"] for r in rows} == {
            "VERIFIED",
            "FINANCE_AVAILABLE",
            "FINANCED",
            "REALIZED",
        }
        metadata = json.loads((tmp_path / "data/demo/EXP-2026-1042.json").read_text())
        pdf = (tmp_path / "data/demo/EXP-2026-1042.pdf").read_bytes()
        from io import BytesIO

        from pypdf import PdfReader

        assert "EUR 10,800.00" in PdfReader(BytesIO(pdf)).pages[0].extract_text()
        duplicate = client.post(
            "/api/v1/receivables",
            headers=owner,
            data={"metadata": json.dumps(metadata)},
            files={"document": ("changed-name.pdf", pdf, "application/pdf")},
        )
        assert duplicate.status_code == 409


def test_unknown_outcome_preserves_exact_event_for_retry(
    database, storage_root, pdf_bytes, signer, monkeypatch
):
    from app.core.errors import APIError
    from app.services.settlement_service import SettlementService

    original = SettlementService.process

    async def unavailable(self, body, signature, key_id):
        raise APIError(503, "LEDGER_UNAVAILABLE", "Injected uncertain outcome")

    with TestClient(create_app()) as client:
        asset, draft, path, owner, bank, nbfc, admin = financed(client, pdf_bytes)
        assert client.post(path + "/close", headers=admin).status_code == 409
        operator = login(client, "settlement@tradecred.demo")
        monkeypatch.setattr(SettlementService, "process", unavailable)
        response = client.post(
            "/api/v1/simulator/events",
            headers=operator,
            json={
                "asset_id": asset,
                "amount_minor": 1080000,
                "currency": "EUR",
                "reference": "IRM-RETRY",
                "mode": "valid",
            },
        )
        result = response.json()
        assert result["uncertain"] and not result["accepted"]
        assert result["code"] == "LEDGER_UNAVAILABLE"
        monkeypatch.setattr(SettlementService, "process", original)
        recovered = client.post(f"/api/v1/simulator/events/{result['id']}/replay", headers=operator)
        assert recovered.json()["accepted"], recovered.text
        assert recovered.json()["event_id"] == result["event_id"]


def test_signer_outage_never_submits_a_payment(
    database, storage_root, pdf_bytes, signer, monkeypatch
):
    async def unavailable(*args, **kwargs):
        raise httpx.ConnectError("Internal signer path must not leak")

    # Replace the constructor because the signer fixture wraps AsyncClient with ASGI transport.
    class Offline:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        post = unavailable

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Offline())
    with TestClient(create_app()) as client:
        asset, draft, path, owner, bank, nbfc, admin = financed(client, pdf_bytes)
        operator = login(client, "settlement@tradecred.demo")
        response = client.post(
            "/api/v1/simulator/events",
            headers=operator,
            json={
                "asset_id": asset,
                "amount_minor": 1080000,
                "currency": "EUR",
                "reference": "IRM-OFFLINE",
                "mode": "valid",
            },
        )
        assert response.status_code == 503 and "Internal signer" not in response.text
        assert client.get(path, headers=owner).json()["status"] == "FINANCED"
