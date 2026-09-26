from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pypdf import PdfWriter
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers, UploadFile

from app.core.config import Settings
from app.core.errors import APIError
from app.integrations.storage.local import LocalDocumentStorage
from app.models.domain import User
from app.services.document_service import validate_pdf
from app.services.receivable_service import ReceivableService

METADATA = (
    '{"buyerId":"BUYER-DE-001","invoiceNumber":"INV-001","invoiceDate":"2026-09-21",'
    '"currency":"EUR","amount":"10800.00","dueDate":"2026-11-25"}'
)


def test_pdf_validation_and_private_immutable_storage(tmp_path: Path, pdf_bytes: bytes) -> None:
    validate_pdf(pdf_bytes)
    storage = LocalDocumentStorage(tmp_path / "documents")
    key = uuid4().hex + ".pdf"
    storage.write(key, pdf_bytes)
    assert storage.read(key, 10000) == pdf_bytes
    assert (storage.root / key).stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        storage.write(key, b"replacement")
    assert storage.read(key, 10000) == pdf_bytes


@pytest.mark.parametrize(
    "key", ["../secret.pdf", "/tmp/private.pdf", "..", "a/b.pdf", "invoice.pdf"]
)
def test_storage_rejects_untrusted_paths(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError):
        LocalDocumentStorage(tmp_path).write(key, b"data")


def test_storage_refuses_symlinks(tmp_path: Path) -> None:
    private = tmp_path / "secret"
    private.write_bytes(b"secret")
    key = uuid4().hex + ".pdf"
    (tmp_path / key).symlink_to(private)
    with pytest.raises(OSError):
        LocalDocumentStorage(tmp_path).read(key, 100)


def test_failed_storage_write_removes_partial_file(tmp_path: Path) -> None:
    with patch("app.integrations.storage.local.os.fsync", side_effect=OSError("disk failure")):
        with pytest.raises(OSError):
            LocalDocumentStorage(tmp_path).write(uuid4().hex + ".pdf", b"data")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("data", [b"", b"not pdf", b"%PDF-1.7\ninvalid objects\n%%EOF"])
def test_invalid_pdf_rejected(data: bytes) -> None:
    with pytest.raises(APIError) as error:
        validate_pdf(data)
    assert error.value.code == "INVALID_PDF"


def test_encrypted_pdf_rejected() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("private-password")
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(APIError):
        validate_pdf(stream.getvalue())


@pytest.mark.parametrize("failure", ["storage", "commit"])
async def test_no_false_success_on_storage_or_commit_failure(
    tmp_path: Path, pdf_bytes: bytes, failure: str
) -> None:
    session = AsyncMock(spec=AsyncSession)
    storage = LocalDocumentStorage(tmp_path)
    service = ReceivableService(session, storage, Settings())
    service.repository.add_draft = AsyncMock()
    user = User(id=uuid4(), organization_id="ORG_EXPORTER_ALPHA")
    if failure == "storage":
        error = OSError("cannot write")
        context = patch.object(storage, "write", side_effect=error)
    else:
        error = OperationalError("commit", {}, Exception("database unavailable"))
        context = patch.object(session, "commit", side_effect=error)
    with context, pytest.raises(APIError) as caught:
        await service.create_draft(
            METADATA,
            UploadFile(BytesIO(pdf_bytes), headers=Headers({"content-type": "application/pdf"})),
            user,
        )
    assert caught.value.status_code == 503
    session.rollback.assert_awaited_once()
    assert await run_in_threadpool(lambda: len(list(tmp_path.glob("*.pdf")))) == (
        1 if failure == "commit" else 0
    )
    if failure == "storage":
        session.commit.assert_not_awaited()
