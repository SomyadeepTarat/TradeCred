from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settlement import SecurityEvent
from app.schemas.demo import SecurityView


async def security_events(session: AsyncSession, limit: int, offset: int) -> list[SecurityView]:
    rows = await session.scalars(
        select(SecurityEvent)
        .order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [SecurityView.model_validate(row) for row in rows]
