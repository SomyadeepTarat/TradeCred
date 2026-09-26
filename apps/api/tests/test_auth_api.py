from fastapi.testclient import TestClient

from app.main import create_app


def test_anonymous_cannot_read_identity_or_organizations() -> None:
    with TestClient(create_app()) as client:
        for path in ("/api/v1/auth/me", "/api/v1/organizations"):
            response = client.get(path)
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer"
            assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_login_rejects_overposting() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "exporter@tradecred.demo",
                "password": "some-password",
                "role": "ADMIN",
            },
        )
    assert response.status_code == 422
