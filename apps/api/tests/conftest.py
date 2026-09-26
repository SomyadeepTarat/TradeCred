import asyncio
import os
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from pypdf import PdfWriter
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from tests.helpers import migration_config, seed

# Explicit test-only key; never use a developer's JWT secret in tests.
os.environ["JWT_SECRET"] = "tradecred-test-only-signing-key-0123456789"


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    base_url = make_url(str(Settings().database_url))
    admin = create_engine(base_url)
    schema = "tc_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = base_url.update_query_dict({"options": f"-csearch_path={schema}"})
    monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    engine = create_engine(url)
    try:
        command.upgrade(migration_config(), "head")
        asyncio.run(seed(url.render_as_string(hide_password=False)))
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_metadata({"/Title": "Fictional TradeCred test invoice"})
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def storage_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "private-documents"
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(root))
    return root
