from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Organization, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def organizations(self) -> list[Organization]:
        return list(await self.session.scalars(select(Organization).order_by(Organization.id)))
