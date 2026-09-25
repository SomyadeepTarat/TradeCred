from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import create_app


def test_liveness_does_not_require_database() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "tradecred-api"}


def test_readiness_checks_database() -> None:
    with patch("app.api.routes.health.check_database", new_callable=AsyncMock) as check:
        with TestClient(create_app()) as client:
            response = client.get("/api/v1/health/ready")
        check.assert_awaited_once()
    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"


def test_readiness_reports_failure_without_leaking_credentials() -> None:
    failure = OperationalError("SELECT 1", {}, Exception("password=secret"))
    with patch("app.api.routes.health.check_database", side_effect=failure):
        with TestClient(create_app()) as client:
            response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": {"database": "unavailable"}}
    assert "secret" not in response.text
