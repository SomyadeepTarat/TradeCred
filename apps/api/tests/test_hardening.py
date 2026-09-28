import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter, logger
from app.main import create_app


@pytest.mark.parametrize(
    "method,path,payload,status,code",
    [
        ("get", "/missing/private-token?secret=PRIVATE", None, 404, "NOT_FOUND"),
        ("put", "/api/v1/auth/login", None, 405, "METHOD_NOT_ALLOWED"),
        (
            "post",
            "/api/v1/auth/login",
            {"email": {}, "password": "PRIVATE_PASSWORD"},
            422,
            "INVALID_REQUEST",
        ),
        ("get", "/api/v1/auth/me", None, 401, "AUTHENTICATION_REQUIRED"),
    ],
)
def test_errors_are_structured_and_do_not_echo_inputs(method, path, payload, status, code):
    with TestClient(create_app()) as client:
        response = client.request(method, path, json=payload)
    assert response.status_code == status
    body = response.json()["error"]
    assert body["code"] == code and body["details"] == {}
    assert body["requestId"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE" not in response.text


def test_unexpected_failure_and_request_logs_never_expose_secrets():
    messages = []

    class Capture(logging.Handler):
        def emit(self, record):
            messages.append(JsonFormatter().format(record))

    app = create_app()

    @app.get("/test-failure/{opaque}")
    async def fail(opaque: str):
        raise RuntimeError("SQL password=PRIVATE_PASSWORD token=PRIVATE_TOKEN")

    handler = Capture()
    logger.addHandler(handler)
    try:
        with TestClient(app) as client:
            response = client.get(
                "/test-failure/PRIVATE_PATH?token=PRIVATE_QUERY",
                headers={"Authorization": "Bearer PRIVATE_TOKEN", "X-Request-ID": "forged"},
            )
            second = client.get("/api/v1/health")
    finally:
        logger.removeHandler(handler)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "PRIVATE" not in response.text + "".join(messages)
    records = [json.loads(m) for m in messages]
    completed = [r for r in records if r["event"] == "request_completed"]
    assert completed[0]["route"] == "/test-failure/{opaque}"
    assert completed[0]["request_id"] == response.headers["x-request-id"]
    assert completed[1]["request_id"] == second.headers["x-request-id"]
    assert completed[0]["request_id"] != completed[1]["request_id"]
    assert "error_code" not in completed[1]
