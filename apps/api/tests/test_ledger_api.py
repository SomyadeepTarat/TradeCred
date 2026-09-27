from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.main import create_app
from app.models.domain import Receivable
from app.models.ledger import AuditEvent, LedgerTransaction, MockLedgerAsset, MockLedgerPrivate
from tests.helpers import login
from tests.test_document_integration import upload

pytestmark = pytest.mark.integration
REGISTRY = dict(
    exporterId="ORG_EXPORTER_ALPHA",
    buyerId="BUYER-DE-001",
    invoiceNumber="EXP-2026-1042",
    currency="EUR",
    amountMinor=1080000,
    invoiceDate="2026-09-21",
)


def prepared(client, pdf_bytes):
    owner = login(client, "exporter@tradecred.demo")
    admin = login(client, "admin@tradecred.demo")
    response = upload(client, owner, pdf_bytes)
    assert response.status_code == 201, response.text
    draft = response.json()
    path = f"/api/v1/receivables/{draft['id']}"
    assert client.post(path + "/submit", headers=owner).status_code == 200
    assert client.post(path + "/verify", headers=admin).status_code == 200
    return owner, admin, draft, path


def test_registration_registry_history_and_retry(database: Engine, storage_root: Path, pdf_bytes):
    with TestClient(create_app()) as client:
        owner, admin, draft, path = prepared(client, pdf_bytes)
        bank = login(client, "bank@tradecred.demo")
        absent = client.post("/api/v1/registry/check", json=REGISTRY, headers=bank).json()
        assert absent["exists"] is False and absent["eligible"] is True
        response = client.post(path + "/register", headers=owner)
        assert response.status_code == 200, response.text
        registered = response.json()
        assert registered["status"] == "REGISTERED" and registered["backend"] == "mock"
        assert registered["transaction_id"].startswith("MOCK-")
        lookup = client.post("/api/v1/registry/check", json=REGISTRY, headers=bank).json()
        assert lookup["exists"] is True and lookup["eligible"] is False
        assert lookup["assetId"] == registered["asset_id"]
        assert set(lookup) <= {
            "fingerprint",
            "exists",
            "eligible",
            "assetId",
            "status",
            "reason",
            "locked",
            "financed",
            "backend",
        }
        assert (
            client.post(path + "/open-financing", headers=owner).json()["status"]
            == "FINANCE_AVAILABLE"
        )
        retry = client.post(path + "/register", headers=owner).json()
        assert retry["replayed"] is True and retry["status"] == "FINANCE_AVAILABLE"
        assert retry["transaction_id"] == registered["transaction_id"]
        found = client.get(
            "/api/v1/registry/fingerprint/" + draft["invoice_fingerprint"], headers=bank
        )
        assert found.json()["eligible"] is True
        assert upload(client, owner, pdf_bytes + b"\n").status_code == 409
        history = client.get(path + "/history", headers=owner).json()
        assert [e["event_type"] for e in history["events"]] == [
            "RECEIVABLE_CREATED",
            "RECEIVABLE_SUBMITTED",
            "RECEIVABLE_VERIFIED",
            "RECEIVABLE_REGISTERED",
            "RECEIVABLE_OPENED",
        ]
        assert [e["to_status"] for e in history["ledger"]] == ["REGISTERED", "FINANCE_AVAILABLE"]
        assert history["events"][3]["request_id"] == response.headers["x-request-id"]
        assert client.get(path + "/history", headers=bank).json()["events"] == []
        assert client.get("/api/v1/audit/events", headers=owner).status_code == 403
        audit = client.get("/api/v1/audit/events", headers=admin).json()
        assert any(e["event_type"] == "DUPLICATE_REJECTED" for e in audit)
        assert client.post("/api/v1/registry/check", json=REGISTRY).status_code == 401
        assert (
            client.post(
                "/api/v1/registry/check", json=REGISTRY | {"amountMinor": 1.2}, headers=bank
            ).status_code
            == 422
        )
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(MockLedgerAsset)) == 1
        assert session.scalar(select(func.count()).select_from(LedgerTransaction)) == 2
        assert session.scalar(select(MockLedgerPrivate.face_value_minor)) == 1080000


@pytest.mark.parametrize("failure", ["drunix", "write", "tamper"])
def test_registration_failure_is_atomic(database, storage_root, pdf_bytes, monkeypatch, failure):
    with TestClient(create_app()) as client:
        owner, admin, draft, path = prepared(client, pdf_bytes)
    if failure == "drunix":
        monkeypatch.setenv("LEDGER_BACKEND", "drunix")
    if failure == "tamper":
        next(storage_root.iterdir()).write_bytes(pdf_bytes + b"changed")
    with TestClient(create_app()) as client:
        if failure == "write":
            with patch(
                "app.integrations.ledger.mock.MockLedgerClient._record",
                side_effect=APIError(503, "LEDGER_UNAVAILABLE", "Injected ledger failure"),
            ):
                response = client.post(path + "/register", headers=owner)
        else:
            response = client.post(path + "/register", headers=owner)
        assert response.status_code == (409 if failure == "tamper" else 503), response.text
        if failure == "drunix":
            assert (
                client.post("/api/v1/registry/check", json=REGISTRY, headers=owner).status_code
                == 503
            )
    with Session(database) as session:
        row = session.get(Receivable, UUID(draft["id"]))
        assert row.status == "VERIFIED" and row.asset_id is None
        assert session.scalar(select(func.count()).select_from(MockLedgerAsset)) == 0
        assert session.scalar(select(func.count()).select_from(LedgerTransaction)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "RECEIVABLE_REGISTERED")
            )
            == 0
        )


def test_roles_and_invalid_transitions(database, storage_root, pdf_bytes):
    with TestClient(create_app()) as client:
        owner = login(client, "exporter@tradecred.demo")
        admin = login(client, "admin@tradecred.demo")
        bank = login(client, "bank@tradecred.demo")
        draft = upload(client, owner, pdf_bytes).json()
        path = f"/api/v1/receivables/{draft['id']}"
        assert client.post(path + "/register", headers=owner).status_code == 409
        assert client.post(path + "/verify", headers=owner).status_code == 403
        assert client.post(path + "/submit", headers=admin).status_code == 403
        assert client.post(path + "/register", headers=bank).status_code == 404
        assert client.post(path + "/submit", headers=owner).status_code == 200
        assert client.post(path + "/submit", headers=owner).status_code == 409
        assert client.post(path + "/verify", headers=admin).status_code == 200
        assert client.post(path + "/open-financing", headers=owner).status_code == 409
        assert client.get(path + "/document", headers=admin).status_code == 403


def test_existing_ledger_fingerprint_blocks_registration(database, storage_root, pdf_bytes):
    import asyncio
    from datetime import date
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.config import Settings
    from app.core.database import create_database_engine
    from app.integrations.ledger.base import LedgerActor, Registration
    from app.integrations.ledger.mock import MockLedgerClient
    from app.models.domain import Role

    with TestClient(create_app()) as client:
        owner, admin, draft, path = prepared(client, pdf_bytes)

        async def external_registration():
            engine = create_database_engine(str(Settings().database_url))
            try:
                async with async_sessionmaker(engine).begin() as session:
                    ledger = MockLedgerClient(
                        session,
                        LedgerActor(
                            user_id=uuid4(),
                            organization_id="ORG_EXPORTER_ALPHA",
                            role=Role.EXPORTER,
                        ),
                    )
                    await ledger.register_receivable(
                        Registration(
                            asset_id="TC-already-registered",
                            invoice_fingerprint=draft["invoice_fingerprint"],
                            document_hash=draft["document_hash"],
                            exporter_org_id="ORG_EXPORTER_ALPHA",
                            currency="EUR",
                            face_value_minor=1080000,
                            due_date=date(2026, 11, 25),
                        )
                    )
            finally:
                await engine.dispose()

        asyncio.run(external_registration())
        response = client.post(path + "/register", headers=owner)
        assert response.status_code == 409, response.text
        assert response.json()["error"]["details"]["assetId"] == "TC-already-registered"
        assert response.json()["error"]["code"] == "DUPLICATE_RECEIVABLE"
        audit = client.get("/api/v1/audit/events", headers=admin).json()
        assert any(
            e["event_type"] == "DUPLICATE_REJECTED"
            and e["request_id"] == response.headers["x-request-id"]
            for e in audit
        )
    with Session(database) as session:
        row = session.get(Receivable, UUID(draft["id"]))
        assert row.status == "VERIFIED" and row.asset_id is None
        assert session.scalar(select(func.count()).select_from(MockLedgerAsset)) == 1
