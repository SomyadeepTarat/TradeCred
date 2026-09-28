from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import APIError
from app.core.logging import bind
from app.models.domain import User
from app.repositories.users import UserRepository
from app.schemas.auth import TokenResponse
from app.security.passwords import DUMMY_PASSWORD_HASH, verify_password
from app.security.tokens import decode_access_token, issue_access_token


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self.users = users
        self.settings = settings

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.users.by_email(email)
        encoded = user.password_hash if user else DUMMY_PASSWORD_HASH
        valid = await run_in_threadpool(verify_password, password, encoded)
        if user is None or not valid or not user.is_active:
            raise APIError(401, "INVALID_CREDENTIALS", "Invalid email or password.")
        bind(user_id=str(user.id), org_id=user.organization_id)
        return TokenResponse(
            access_token=issue_access_token(user.id, self.settings),
            expires_in=self.settings.jwt_access_token_minutes * 60,
        )

    async def authenticate(self, token: str) -> User:
        user_id = decode_access_token(token, self.settings)
        user = await self.users.by_id(user_id)
        if user is None or not user.is_active:
            raise APIError(401, "INVALID_TOKEN", "Invalid or expired access token.")
        return user
