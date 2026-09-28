import asyncio
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_database_engine
from app.main import create_app
from app.models.domain import Receivable, User
from app.models.drunix import LedgerArtifact
from app.models.ledger import AuditEvent, MockLedgerAsset
from app.services.reset_service import reset_demo
from tests.helpers import PASSWORD, login
from tests.test_demo import ROOT, signer  # noqa: F401
from tests.test_document_integration import upload

pytestmark = pytest.mark.integration


async def reset(*, apply=False, fail=False):
    settings = Settings()
    engine = create_database_engine(str(settings.database_url))
    try:
        async with async_sessionmaker(engine).begin() as session:
            plan = await reset_demo(session, settings, apply=apply)
            if fail:
                raise RuntimeError("Injected failure before commit")
            return plan
    finally:
        await engine.dispose()


@pytest.mark.usefixtures("signer")
def test_reset_preview_rollback_apply_and_reseed_preserve_other_data(
    database, storage_root, monkeypatch, tmp_path, pdf_bytes
):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import seed_fixtures

    monkeypatch.setattr(seed_fixtures, "ROOT", tmp_path)
    with TestClient(create_app()) as client:
        manifest = seed_fixtures.seed_fixtures(client, PASSWORD)
        owner = login(client, "exporter@tradecred.demo")
        other = upload(client, owner, pdf_bytes, invoiceNumber="USER-KEEP-001").json()["id"]
        with Session(database) as session:
            credentials = list(session.execute(select(User.id, User.password_hash)))
            audits = session.scalar(select(func.count()).select_from(AuditEvent))
        plan = asyncio.run(reset())
        assert len(plan) == 4
        assert client.get("/api/v1/receivables", headers=owner).json()["total"] == 5
        with pytest.raises(RuntimeError):
            asyncio.run(reset(apply=True, fail=True))
        assert client.get("/api/v1/receivables", headers=owner).json()["total"] == 5
        asyncio.run(reset(apply=True))
        with Session(database) as session:
            assert session.scalar(select(func.count()).select_from(MockLedgerAsset)) == 0
            assert session.get(Receivable, UUID(other)) is not None
            assert list(session.execute(select(User.id, User.password_hash))) == credentials
            assert session.scalar(select(func.count()).select_from(AuditEvent)) == audits
        assert asyncio.run(reset(apply=True)) == []
        reseeded = seed_fixtures.seed_fixtures(client, PASSWORD)
        assert set(reseeded) == set(manifest)
        assert set(reseeded.values()).isdisjoint(manifest.values())
        assert client.get("/api/v1/receivables", headers=owner).json()["total"] == 5


def test_reset_refuses_real_ledger_and_durable_recovery_inputs(database, monkeypatch):
    monkeypatch.setenv("LEDGER_BACKEND", "drunix")
    with pytest.raises(ValueError, match="mock mode"):
        asyncio.run(reset(apply=True))
    monkeypatch.setenv("LEDGER_BACKEND", "mock")
    with Session(database) as session:
        session.add(LedgerArtifact(key="a" * 64, payload={"pending": True}))
        session.commit()
    with pytest.raises(ValueError, match="Drunix recovery"):
        asyncio.run(reset(apply=True))
