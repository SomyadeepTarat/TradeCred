import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.models.domain import Document, Receivable, Role, User
from app.security.passwords import hash_password
from app.services.fingerprint_service import document_hash
from tests.helpers import PASSWORD, login

pytestmark = pytest.mark.integration
METADATA = dict(
    buyerId="BUYER-DE-001",
    invoiceNumber="EXP-2026-1042",
    invoiceDate="2026-09-21",
    currency="EUR",
    amount="10800.00",
    dueDate="2026-11-25",
)


def upload(client: TestClient, headers: dict[str, str], data: bytes, **changes: object):
    return client.post(
        "/api/v1/receivables",
        headers=headers,
        data={"metadata": json.dumps(METADATA | changes)},
        files={"document": ("../../untrusted.pdf", data, "application/pdf")},
    )


def test_upload_persists_draft_and_original_pdf(
    database: Engine, storage_root: Path, pdf_bytes: bytes
) -> None:
    with TestClient(create_app()) as client:
        headers = login(client, "exporter@tradecred.demo")
        response = upload(client, headers, pdf_bytes)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "DRAFT" and body["face_value_minor"] == 1080000
        assert body["document_hash"] == document_hash(pdf_bytes)
        assert (
            body["invoice_fingerprint"]
            == "febfe7ea6bba251d86dcbc6444a714a1da9e2797ec8959f5ae910a3d2140453b"
        )
        path = f"/api/v1/receivables/{body['id']}/document"
        downloaded = client.get(path, headers=headers)
        assert downloaded.content == pdf_bytes
        assert downloaded.headers["content-disposition"].startswith("attachment;")
        assert downloaded.headers["cache-control"] == "no-store"
        assert client.get(path + "/integrity", headers=headers).json()["verified"] is True
    with Session(database) as session:
        document = session.scalar(select(Document))
        receivable = session.scalar(select(Receivable))
        assert document is not None and receivable is not None
        assert document.document_hash == receivable.document_hash == body["document_hash"]
        assert document.size_bytes == len(pdf_bytes)
        assert document.storage_key == body["document_id"].replace("-", "") + ".pdf"
        assert receivable.asset_id is None
    assert len(list(storage_root.iterdir())) == 1


def test_duplicate_pdf_variant_does_not_create_second_file(
    database: Engine, storage_root: Path, pdf_bytes: bytes
) -> None:
    with TestClient(create_app()) as client:
        headers = login(client, "exporter@tradecred.demo")
        assert upload(client, headers, pdf_bytes).status_code == 201
        duplicate = upload(
            client,
            headers,
            pdf_bytes + b"\n",
            invoiceNumber=" exp - 2026 - 1042 ",
            currency=" eur ",
            amount="10800",
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "DUPLICATE_RECEIVABLE"
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 1
        assert session.scalar(select(func.count()).select_from(Receivable)) == 1
    assert len(list(storage_root.iterdir())) == 1


def test_private_document_authorization(
    database: Engine, storage_root: Path, pdf_bytes: bytes
) -> None:
    with Session(database) as session, session.begin():
        session.add(
            User(
                email="beta@tradecred.demo",
                display_name="Other exporter",
                role=Role.EXPORTER,
                organization_id="ORG_EXPORTER_BETA",
                password_hash=hash_password(PASSWORD),
            )
        )
    with TestClient(create_app()) as client:
        owner = login(client, "exporter@tradecred.demo")
        body = upload(client, owner, pdf_bytes).json()
        path = f"/api/v1/receivables/{body['id']}/document"
        assert upload(client, {}, pdf_bytes).status_code == 401
        assert client.get(path).status_code == 401
        for email in ("bank@tradecred.demo", "settlement@tradecred.demo", "admin@tradecred.demo"):
            headers = login(client, email)
            assert upload(client, headers, pdf_bytes).status_code == 403
            assert client.get(path, headers=headers).status_code == 403
            assert client.get(path + "/integrity", headers=headers).status_code == 403
        other = login(client, "beta@tradecred.demo")
        for suffix in ("", "/integrity"):
            assert client.get(path + suffix, headers=other).status_code == 404
            assert (
                client.get(
                    f"/api/v1/receivables/{uuid4()}/document" + suffix, headers=owner
                ).status_code
                == 404
            )


def test_tamper_and_missing_document_never_report_integrity_success(
    database: Engine, storage_root: Path, pdf_bytes: bytes
) -> None:
    with TestClient(create_app()) as client:
        headers = login(client, "exporter@tradecred.demo")
        body = upload(client, headers, pdf_bytes).json()
        path = f"/api/v1/receivables/{body['id']}/document"
        file = next(storage_root.iterdir())
        file.write_bytes(pdf_bytes + b"changed")
        assert client.get(path + "/integrity", headers=headers).json()["verified"] is False
        assert client.get(path, headers=headers).status_code == 409
        file.unlink()
        assert client.get(path + "/integrity", headers=headers).status_code == 503
        assert client.get(path, headers=headers).status_code == 503


def test_invalid_inputs_leave_no_rows_or_files(
    database: Engine, storage_root: Path, pdf_bytes: bytes
) -> None:
    with TestClient(create_app()) as client:
        headers = login(client, "exporter@tradecred.demo")
        for changes in (
            {"amount": 10800.0},
            {"amount": "10800.001"},
            {"currency": "ZZZ"},
            {"exporterId": "ORG_EXPORTER_BETA"},
            {"invoiceDate": "2026-02-30"},
            {"dueDate": "2026-01-01"},
            {"invoiceNumber": "***"},
        ):
            assert upload(client, headers, pdf_bytes, **changes).status_code == 422
        assert upload(client, headers, b"%PDF-1.7\ninvalid\n%%EOF").status_code == 422
        bad_type = client.post(
            "/api/v1/receivables",
            headers=headers,
            data={"metadata": json.dumps(METADATA)},
            files={"document": ("file.pdf", pdf_bytes, "text/plain")},
        )
        assert bad_type.status_code == 415
        bad_json = client.post(
            "/api/v1/receivables",
            headers=headers,
            data={"metadata": "{"},
            files={"document": ("file.pdf", pdf_bytes, "application/pdf")},
        )
        assert bad_json.status_code == 422
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 0
        assert session.scalar(select(func.count()).select_from(Receivable)) == 0
    assert not storage_root.exists()


def test_storage_failure_rolls_back_database(
    database: Engine, storage_root: Path, pdf_bytes: bytes
) -> None:
    with TestClient(create_app()) as client:
        headers = login(client, "exporter@tradecred.demo")
        with patch(
            "app.integrations.storage.local.LocalDocumentStorage.write",
            side_effect=OSError("private path"),
        ):
            response = upload(client, headers, pdf_bytes)
        assert response.status_code == 503
        assert "private path" not in response.text
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 0
        assert session.scalar(select(func.count()).select_from(Receivable)) == 0


def test_file_and_chunked_request_size_limits(
    database: Engine, storage_root: Path, pdf_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1024")
    with TestClient(create_app()) as client:
        headers = login(client, "exporter@tradecred.demo")
        assert upload(client, headers, pdf_bytes + b" " * 2048).status_code == 413
        boundary = "tradecred-test-boundary"
        body = (
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="document"; filename="file.pdf"\r\n'
                "Content-Type: application/pdf\r\n\r\n"
            ).encode()
            + b"x" * 70000
            + f"\r\n--{boundary}--\r\n".encode()
        )
        chunked = client.post(
            "/api/v1/receivables",
            headers=headers | {"Content-Type": f"multipart/form-data; boundary={boundary}"},
            content=iter([body[:1024], body[1024:]]),
        )
        assert chunked.status_code == 413, chunked.text
        assert chunked.json()["error"]["code"] == "UPLOAD_TOO_LARGE"
    assert not storage_root.exists()
