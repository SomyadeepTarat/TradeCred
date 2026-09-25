from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.repositories.users import UserRepository
from app.services.auth_service import AuthService


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(request.app.state.database, expire_on_commit=False)
    async with factory() as session:
        yield session


SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_auth_service(session: SessionDependency, settings: SettingsDependency) -> AuthService:
    return AuthService(UserRepository(session), settings)


AuthDependency = Annotated[AuthService, Depends(get_auth_service)]
