from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from app.core.config import Settings
from app.core.errors import APIError


def issue_access_token(user_id: UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iss": "tradecred",
            "aud": "tradecred-api",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=settings.jwt_access_token_minutes),
            "jti": str(uuid4()),
            "token_type": "access",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience="tradecred-api",
            issuer="tradecred",
            options={"require": ["sub", "exp", "iat", "nbf", "iss", "aud", "jti", "token_type"]},
        )
        if payload["token_type"] != "access":
            raise ValueError("Invalid token type")
        return UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError) as exc:
        raise APIError(401, "INVALID_TOKEN", "Invalid or expired access token.") from exc
