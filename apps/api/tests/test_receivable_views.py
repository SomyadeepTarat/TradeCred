from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from app.models.domain import Role, User
from app.security.passwords import hash_password
from tests.helpers import PASSWORD, login
from tests.test_document_integration import upload
from tests.test_domain_integration import draft

pytestmark = pytest.mark.integration


def test_scoped_list_detail_summary_and_pagination(database, storage_root, pdf_bytes):
    with Session(database) as session, session.begin():
        session.add(
            User(
                email="beta@tradecred.demo",
                display_name="Other exporter",
                organization_id="ORG_EXPORTER_BETA",
                role=Role.EXPORTER,
                password_hash=hash_password(PASSWORD),
            )
        )
        session.add(draft(exporter_org_id="ORG_EXPORTER_BETA", invoice_number="PRIVATE-BETA"))
        for status in ("FINANCE_AVAILABLE", "FINANCED", "PAYMENT_CONFIRMED", "CLOSED"):
            session.add(
                draft(status=status, invoice_number=status, face_value_minor=9223372036854775807)
            )
    with TestClient(create_app()) as client:
        owner = login(client, "exporter@tradecred.demo")
        body = upload(client, owner, pdf_bytes).json()
        response = client.get("/api/v1/receivables?limit=2", headers=owner)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        page = response.json()
        assert page["summary"] == dict(total=5, available=1, financed=1, settled=2)
        assert page["total"] == 5 and len(page["items"]) == 2
        assert "PRIVATE-BETA" not in response.text
        assert len(page["recent_activity"]) == 1
        filtered = client.get("/api/v1/receivables?status=CLOSED", headers=owner).json()
        assert filtered["total"] == 1 and filtered["summary"]["total"] == 5
        assert filtered["items"][0]["face_value"] == "92233720368547758.07"
        assert client.get("/api/v1/receivables?offset=100", headers=owner).json()["items"] == []
        assert client.get("/api/v1/receivables?limit=0", headers=owner).status_code == 422
        path = f"/api/v1/receivables/{body['id']}"
        detail = client.get(path, headers=owner).json()
        assert detail["available_actions"] == ["submit"]
        assert detail["face_value"] == "10800.00"
        assert detail["document_available"] is True
        assert detail["ledger_backend"] == "mock"
        assert "storage_key" not in detail and "settlement_reference" not in detail
        beta = login(client, "beta@tradecred.demo")
        assert client.get(path, headers=beta).status_code == 404
        assert client.get("/api/v1/receivables", headers=beta).json()["recent_activity"] == []
        assert client.get(f"/api/v1/receivables/{uuid4()}", headers=owner).status_code == 404
        assert client.get("/api/v1/receivables").status_code == 401
        for email in ("settlement@tradecred.demo",):
            headers = login(client, email)
            assert client.get("/api/v1/receivables", headers=headers).status_code == 403
            assert client.get(path, headers=headers).status_code == 403
        bank = login(client, "bank@tradecred.demo")
        assert client.get("/api/v1/receivables", headers=bank).status_code == 200
        assert client.get(path, headers=bank).status_code == 404


def test_admin_sanitization_and_role_specific_actions(database, storage_root, pdf_bytes):
    with TestClient(create_app()) as client:
        owner = login(client, "exporter@tradecred.demo")
        admin = login(client, "admin@tradecred.demo")
        body = upload(client, owner, pdf_bytes).json()
        path = f"/api/v1/receivables/{body['id']}"
        response = client.get(path, headers=admin)
        assert response.status_code == 200
        detail = response.json()
        assert (
            detail["face_value"] is None
            and detail["buyer_id"] is None
            and detail["invoice_number"] is None
        )
        assert detail["document_available"] is False and detail["available_actions"] == []
        page = client.get("/api/v1/receivables", headers=admin).json()
        assert page["items"][0]["face_value"] is None
        assert client.post(path + "/submit", headers=owner).status_code == 200
        assert client.get(path, headers=owner).json()["available_actions"] == []
        assert client.get(path, headers=admin).json()["available_actions"] == ["verify"]
        assert client.post(path + "/verify", headers=admin).status_code == 200
        assert client.get(path, headers=owner).json()["available_actions"] == ["register"]
        assert client.post(path + "/register", headers=owner).status_code == 200
        assert client.get(path, headers=owner).json()["available_actions"] == ["open-financing"]
        assert client.get(path, headers=admin).json()["available_actions"] == []
