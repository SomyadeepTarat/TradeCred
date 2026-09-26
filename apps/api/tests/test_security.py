from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.config import Settings
from app.core.errors import APIError
from app.models.domain import Role, User
from app.security.passwords import hash_password, verify_password
from app.security.rbac import require_roles
from app.security.tokens import decode_access_token, issue_access_token


def test_password_hash_is_salted_and_verifiable() -> None:
    password = "unit-test-password"
    first, second = hash_password(password), hash_password(password)
    assert first != second
    assert password not in first
    assert verify_password(password, first)
    assert not verify_password("wrong-password", first)
    assert not verify_password(password, "corrupt-hash")


def test_access_token_roundtrip() -> None:
    settings = Settings()
    user_id = uuid4()
    assert decode_access_token(issue_access_token(user_id, settings), settings) == user_id


@pytest.mark.parametrize(
    "mutation", ["expired", "future", "issuer", "audience", "type", "subject", "missing"]
)
def test_rejects_invalid_token_claims(mutation: str) -> None:
    settings = Settings()
    key = settings.jwt_secret.get_secret_value()
    token = issue_access_token(uuid4(), settings)
    payload = jwt.decode(token, key, algorithms=["HS256"], audience="tradecred-api")
    if mutation == "expired":
        payload["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    elif mutation == "future":
        payload["nbf"] = datetime.now(UTC) + timedelta(hours=1)
    elif mutation == "issuer":
        payload["iss"] = "other-app"
    elif mutation == "audience":
        payload["aud"] = "other-api"
    elif mutation == "type":
        payload["token_type"] = "refresh"
    elif mutation == "subject":
        payload["sub"] = "not-a-uuid"
    else:
        del payload["exp"]
    with pytest.raises(APIError) as exc:
        decode_access_token(jwt.encode(payload, key, algorithm="HS256"), settings)
    assert exc.value.status_code == 401


@pytest.mark.parametrize(
    "algorithm,key",
    [
        ("HS256", "wrong-signing-key-0123456789abcdef"),
        ("HS384", "tradecred-test-only-signing-key-0123456789-extra-long"),
        ("none", ""),
    ],
)
def test_rejects_wrong_signature_or_algorithm(algorithm: str, key: str) -> None:
    settings = Settings()
    original = issue_access_token(uuid4(), settings)
    payload = jwt.decode(original, options={"verify_signature": False})
    with pytest.raises(APIError):
        decode_access_token(jwt.encode(payload, key, algorithm=algorithm), settings)


@pytest.mark.parametrize("actual", list(Role))
@pytest.mark.parametrize("allowed", list(Role))
async def test_role_matrix(actual: Role, allowed: Role) -> None:
    user = User(role=actual)
    guard = require_roles(allowed)
    if actual == allowed:
        assert await guard(user) is user
    else:
        with pytest.raises(APIError) as exc:
            await guard(user)
        assert exc.value.status_code == 403
