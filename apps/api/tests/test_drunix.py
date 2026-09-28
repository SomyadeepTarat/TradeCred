"""Transport-double tests; these never claim a live Drunix transaction."""

import copy
import hashlib
import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.models.drunix import LedgerArtifact
from app.models.financing import FinancingAgreement, MockDisbursement
from app.models.ledger import MockLedgerAsset
from tests.test_financing import offer, setup
from tests.test_settlement import bank_key as bank_key_fixture
from tests.test_settlement import payload, signed


@pytest.fixture
def bank_key(tmp_path, monkeypatch):
    return bank_key_fixture.__wrapped__(tmp_path, monkeypatch)


pytestmark = pytest.mark.integration


class GatewayDouble:
    def __init__(self):
        self.assets = {}
        self.operations = {}
        self.requests = []
        self.histories = {}
        self.lose_response = None
        self.unconfirmed = False
        self.counter = 0

    def response(self, request):
        p = json.loads(request.content)
        self.requests.append(copy.deepcopy(p))
        assert request.headers["Authorization"] == "Bearer " + "test-only-token-" * 3
        submit = request.url.path == "/submit"
        method = p["method"]
        args = p["arguments"]
        if not submit:
            if method == "GetOperationReceipt":
                result = self.operations.get(args[0])
                if result is None:
                    return httpx.Response(404, json={"error": "OPERATION_NOT_FOUND"})
            elif method == "GetHistory":
                result = self.histories[args[0]]
            else:
                result = (
                    self.assets.get(args[0])
                    if method == "GetReceivable"
                    else next(
                        (a for a in self.assets.values() if a["invoiceFingerprint"] == args[0]),
                        None,
                    )
                )
                if result is None:
                    return httpx.Response(404, json={"error": "ASSET_NOT_FOUND"})
        elif p["operationId"] in self.operations:
            result = copy.deepcopy(self.operations[p["operationId"]])
            result["replayed"] = True
        else:
            self.counter += 1
            txid = hashlib.sha256(str(self.counter).encode()).hexdigest()
            if method == "VerifyReceivable":
                r = json.loads(args[0])
                a = r | dict(
                    ownerOrgId="",
                    agreementHash="",
                    status="VERIFIED",
                    faceValueBucket="10000-25000",
                    revision=0,
                    registrationTransactionId="",
                )
            else:
                asset_id = (
                    json.loads(args[0])["assetId"] if method == "RegisterReceivable" else args[0]
                )
                a = self.assets[asset_id]
                a["status"] = {
                    "RegisterReceivable": "REGISTERED",
                    "OpenForFinancing": "FINANCE_AVAILABLE",
                    "LockReceivable": "LOCKED",
                    "RecordFinancing": "FINANCED",
                    "ConfirmPayment": "PAYMENT_CONFIRMED",
                    "MarkRealized": "REALIZED",
                    "MarkEbrcEligible": "EBRC_ELIGIBLE",
                    "CloseReceivable": "CLOSED",
                }[method]
                if method == "LockReceivable":
                    a["ownerOrgId"], a["agreementHash"] = args[1:]
                    agreement = json.loads(p["transient"]["agreement"])
                    assert (
                        hashlib.sha256(p["transient"]["agreement"].encode()).hexdigest() == args[2]
                    )
                    assert agreement["advanceAmountMinor"] == 975000
            a.update(
                transactionId=txid,
                updatedAt=datetime.now(UTC).isoformat(),
                actorOrgId=p["orgId"],
                revision=a["revision"] + 1,
            )
            self.assets[a["assetId"]] = copy.deepcopy(a)
            self.histories.setdefault(a["assetId"], []).append(
                {"transactionId": txid, "timestamp": a["updatedAt"], "asset": copy.deepcopy(a)}
            )
            result = dict(
                asset=copy.deepcopy(a),
                actorOrgId=p["orgId"],
                actorRole=p["role"],
                requestHash="test-double",
                replayed=False,
            )
            self.operations[p["operationId"]] = copy.deepcopy(result)
            if self.lose_response == method:
                self.lose_response = None
                raise httpx.ReadTimeout("Injected lost commit response")
        return httpx.Response(
            200,
            json={
                "backend": "drunix",
                "committed": submit and not self.unconfirmed,
                "result": copy.deepcopy(result),
            },
        )


@pytest.fixture
def gateway(monkeypatch):
    double = GatewayDouble()
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(double.response)),
    )
    monkeypatch.setenv("LEDGER_BACKEND", "drunix")
    monkeypatch.setenv("DRUNIX_GATEWAY_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("DRUNIX_GATEWAY_TOKEN", "test-only-token-" * 3)
    monkeypatch.setenv("DRUNIX_NETWORK_ID", "isolated-test-network")
    monkeypatch.setenv("DRUNIX_CHANNEL", "tradecred")
    return double


def test_gateway_workflow_and_commit_response_recovery(
    database, storage_root, pdf_bytes, gateway, bank_key
):
    with TestClient(create_app()) as client:
        owner, admin, bank, nbfc, draft, path = setup(client, pdf_bytes)
        first = offer(client, path, bank)
        offer(client, path, nbfc)
        gateway.lose_response = "LockReceivable"
        failed = client.post(f"/api/v1/offers/{first}/accept", headers=owner)
        assert failed.status_code == 503, failed.text
        with Session(database) as session:
            assert session.scalar(select(func.count()).select_from(FinancingAgreement)) == 0
            assert session.scalar(select(func.count()).select_from(LedgerArtifact)) > 0
        recovered = client.post(f"/api/v1/offers/{first}/accept", headers=owner)
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["backend"] == "drunix" and recovered.json()["status"] == "LOCKED"
        assert client.post(path + "/disbursement/mock", headers=nbfc).status_code == 403
        gateway.lose_response = "RecordFinancing"
        assert client.post(path + "/disbursement/mock", headers=bank).status_code == 503
        with Session(database) as session:
            assert session.scalar(select(func.count()).select_from(MockDisbursement)) == 0
        paid = client.post(path + "/disbursement/mock", headers=bank)
        assert paid.status_code == 200, paid.text
        assert paid.json()["backend"] == "drunix"
        assert paid.json()["payment"]["backend"] == "mock"
        asset = client.get(path, headers=owner).json()["asset_id"]
        gateway.lose_response = "ConfirmPayment"
        body, headers = signed(bank_key, payload(asset))
        assert (
            client.post("/api/v1/settlement/events", content=body, headers=headers).status_code
            == 503
        )
        settled = client.post("/api/v1/settlement/events", content=body, headers=headers)
        assert settled.status_code == 200, settled.text
        assert settled.json()["backend"] == "drunix"
        assert (
            client.post("/api/v1/settlement/events", content=body, headers=headers).status_code
            == 409
        )
        # Registration retry must not rewind settled state using the old operation snapshot.
        again = client.post(path + "/register", headers=owner)
        assert again.status_code == 200, again.text
        assert again.json()["status"] == "PAYMENT_CONFIRMED" and again.json()["replayed"]
        history = client.get(path + "/history", headers=owner).json()["ledger"]
        assert len(history) == 6 and all(item["backend"] == "drunix" for item in history)
        assert gateway.counter == 6  # Every lost response recovered without a second transition.
        for request in gateway.requests:
            serialized = json.dumps(request["arguments"])
            assert "amountMinor" not in serialized and "975000" not in serialized
            if request["method"] == "LockReceivable":
                assert request["endorserOrgs"] == ["ORG_EXPORTER_ALPHA", "ORG_BANK_CITI_DEMO"]
        gateway.lose_response = "MarkRealized"
        assert client.post(path + "/realize", headers=admin).status_code == 503
        for action, state in (
            ("realize", "REALIZED"),
            ("ebrc-eligible", "EBRC_ELIGIBLE"),
            ("close", "CLOSED"),
        ):
            advanced = client.post(path + "/" + action, headers=admin)
            assert advanced.status_code == 200, advanced.text
            assert advanced.json()["status"] == state
            assert advanced.json()["backend"] == "drunix"
        assert gateway.counter == 9
        assert client.get(path, headers=owner).json()["ebrc_status"] == "SELF_CERTIFICATION_PENDING"
        audit = client.get(path + "/history", headers=admin).json()["events"]
        assert sum(e["event_type"] == "RECEIVABLE_REALIZED" for e in audit) == 1
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(MockLedgerAsset)) == 0


def test_unconfirmed_gateway_response_never_advances(database, storage_root, pdf_bytes, gateway):
    from tests.helpers import login
    from tests.test_document_integration import upload

    gateway.unconfirmed = True
    with TestClient(create_app()) as client:
        owner = login(client, "exporter@tradecred.demo")
        admin = login(client, "admin@tradecred.demo")
        draft = upload(client, owner, pdf_bytes).json()
        path = "/api/v1/receivables/" + draft["id"]
        assert client.post(path + "/submit", headers=owner).status_code == 200
        assert client.post(path + "/verify", headers=admin).status_code == 503
        assert client.get(path, headers=owner).json()["status"] == "SUBMITTED"
        gateway.unconfirmed = False
        assert client.post(path + "/verify", headers=admin).status_code == 200
        assert gateway.counter == 1


def test_backend_switch_does_not_migrate_existing_assets(
    database, storage_root, pdf_bytes, gateway, monkeypatch
):
    monkeypatch.setenv("LEDGER_BACKEND", "mock")
    with TestClient(create_app()) as client:
        owner, admin, bank, nbfc, draft, path = setup(client, pdf_bytes)
    monkeypatch.setenv("LEDGER_BACKEND", "drunix")
    with TestClient(create_app()) as client:
        result = client.post(path + "/register", headers=owner)
        assert result.status_code == 503
        assert result.json()["error"]["code"] == "LEDGER_BACKEND_MISMATCH"
        assert gateway.requests == []


def test_projection_commit_failure_recovers_original_agreement(
    database, storage_root, pdf_bytes, gateway, monkeypatch
):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.ext.asyncio import AsyncSession

    original = AsyncSession.commit
    failed = False

    async def fail_once(session):
        nonlocal failed
        if gateway.counter == 4 and not failed:
            failed = True
            raise SQLAlchemyError("Injected projection commit failure")
        return await original(session)

    with TestClient(create_app()) as client:
        owner, admin, bank, nbfc, draft, path = setup(client, pdf_bytes)
        first = offer(client, path, bank)
        monkeypatch.setattr(AsyncSession, "commit", fail_once)
        response = client.post(f"/api/v1/offers/{first}/accept", headers=owner)
        assert response.status_code == 503 and failed
        with Session(database) as session:
            assert session.scalar(select(func.count()).select_from(FinancingAgreement)) == 0
        recovered = client.post(f"/api/v1/offers/{first}/accept", headers=owner)
        assert recovered.status_code == 200, recovered.text
        requests = [r for r in gateway.requests if r["method"] == "LockReceivable"]
        assert len(requests) == 2 and requests[0] == requests[1]
        assert gateway.counter == 4
        with Session(database) as session:
            assert session.scalar(select(func.count()).select_from(FinancingAgreement)) == 1
