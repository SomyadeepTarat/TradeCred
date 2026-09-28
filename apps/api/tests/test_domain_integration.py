import asyncio
from datetime import date

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models.domain import Organization, Receivable, ReceivableStatus, Role, User
from app.services.seed_service import DEMO_USERS
from tests.helpers import PASSWORD, login, migration_config, seed

pytestmark = pytest.mark.integration


def test_all_demo_logins_and_admin_authorization(database: Engine) -> None:
    with TestClient(create_app()) as client:
        for email, _, role, org_id in DEMO_USERS:
            headers = login(client, "  " + email.upper() + "  ")
            response = client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 200
            assert response.json()["role"] == role
            assert response.json()["organization_id"] == org_id
            assert "password" not in response.text
            organizations = client.get("/api/v1/organizations", headers=headers)
            assert organizations.status_code == (200 if role == Role.ADMIN else 403)
            if role == Role.ADMIN:
                assert len(organizations.json()) == 6
            else:
                assert organizations.json()["error"]["code"] == "UNAUTHORIZED_ROLE"


def test_bad_credentials_disabled_users_and_current_roles(database: Engine) -> None:
    with TestClient(create_app()) as client:
        wrong = client.post(
            "/api/v1/auth/login", json={"email": DEMO_USERS[0][0], "password": "wrong"}
        )
        unknown = client.post(
            "/api/v1/auth/login", json={"email": "absent@tradecred.demo", "password": "wrong"}
        )
        assert wrong.status_code == unknown.status_code == 401

        def public_error(response):
            error = response.json()["error"]
            assert error.pop("requestId") == response.headers["X-Request-ID"]
            return error

        assert public_error(wrong) == public_error(unknown)
        assert wrong.headers["X-Request-ID"] != unknown.headers["X-Request-ID"]
        headers = login(client, "admin@tradecred.demo")
        with Session(database) as session, session.begin():
            user = session.scalar(select(User).where(User.email == "admin@tradecred.demo"))
            assert user is not None
            user.role = Role.EXPORTER
        assert client.get("/api/v1/organizations", headers=headers).status_code == 403
        with Session(database) as session, session.begin():
            user = session.scalar(select(User).where(User.email == "admin@tradecred.demo"))
            assert user is not None
            user.is_active = False
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
        inactive = client.post(
            "/api/v1/auth/login", json={"email": "admin@tradecred.demo", "password": PASSWORD}
        )
        assert public_error(inactive) == public_error(wrong)
        assert inactive.status_code == 401
        assert (
            client.get("/api/v1/auth/me", headers={"Authorization": "Bearer tampered"}).status_code
            == 401
        )


def test_seed_preserves_existing_credentials_and_creates_no_receivables(database: Engine) -> None:
    with Session(database) as session:
        before = {user.email: user.password_hash for user in session.scalars(select(User))}
    asyncio.run(seed(str(Settings().database_url), "different-demo-password"))
    with Session(database) as session:
        after = {user.email: user.password_hash for user in session.scalars(select(User))}
        assert before == after
        assert session.scalar(select(func.count()).select_from(Organization)) == 6
        assert session.scalar(select(func.count()).select_from(Receivable)) == 0


def draft(**overrides: object) -> Receivable:
    values: dict[str, object] = dict(
        exporter_org_id="ORG_EXPORTER_ALPHA",
        buyer_id="BUYER-DE-001",
        invoice_number="INV-1",
        invoice_date=date(2026, 9, 21),
        currency="EUR",
        face_value_minor=1080000,
        due_date=date(2026, 11, 25),
    )
    values.update(overrides)
    return Receivable(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"face_value_minor": 0},
        {"currency": "eur"},
        {"due_date": date(2026, 1, 1)},
        {"document_hash": "invalid"},
        {"invoice_fingerprint": "invalid"},
        {"financing_agreement_hash": "invalid"},
        {"exporter_org_id": "MISSING"},
        {"status": "FAKE_STATUS"},
    ],
)
def test_receivable_database_constraints(database: Engine, overrides: dict[str, object]) -> None:
    from sqlalchemy.exc import DataError

    with Session(database) as session, pytest.raises((IntegrityError, DataError)):
        session.add(draft(**overrides))
        session.commit()


def test_draft_defaults_unique_fingerprint_and_email(database: Engine) -> None:
    with Session(database) as session:
        asset = draft(invoice_fingerprint="a" * 64)
        session.add(asset)
        session.commit()
        assert asset.status == ReceivableStatus.DRAFT
        assert asset.id is not None and asset.created_at.tzinfo is not None
        assert asset.document_hash is None and asset.asset_id is None
        session.add(draft(invoice_fingerprint="a" * 64))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(
            User(
                email="exporter@tradecred.demo",
                display_name="Duplicate",
                password_hash="unused",
                role=Role.EXPORTER,
                organization_id="ORG_EXPORTER_ALPHA",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_migration_roundtrip_and_metadata_alignment(database: Engine) -> None:
    config = migration_config()
    command.check(config)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0
