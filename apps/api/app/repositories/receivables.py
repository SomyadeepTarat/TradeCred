from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Document, Receivable


class ReceivableRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_draft(self, receivable: Receivable, document: Document) -> None:
        self.session.add(receivable)
        await self.session.flush()
        self.session.add(document)
        await self.session.flush()

    async def owned_document(self, receivable_id: UUID, organization_id: str) -> Document | None:
        return await self.session.scalar(
            select(Document)
            .join(Receivable, Document.receivable_id == Receivable.id)
            .where(
                Receivable.id == receivable_id,
                Receivable.exporter_org_id == organization_id,
            )
        )
