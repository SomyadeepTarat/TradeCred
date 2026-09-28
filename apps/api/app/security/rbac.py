from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies import AuthDependency
from app.core.errors import APIError
from app.core.logging import bind
from app.models.domain import Role, User

bearer = HTTPBearer(auto_error=False)


async def current_user(
    auth: AuthDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise APIError(401, "AUTHENTICATION_REQUIRED", "A bearer access token is required.")
    user = await auth.authenticate(credentials.credentials)
    bind(user_id=str(user.id), org_id=user.organization_id)
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: Role) -> Callable[..., Awaitable[User]]:
    async def authorize(user: CurrentUser) -> User:
        if user.role not in roles:
            raise APIError(403, "UNAUTHORIZED_ROLE", "Your role cannot access this resource.")
        return user

    return authorize
