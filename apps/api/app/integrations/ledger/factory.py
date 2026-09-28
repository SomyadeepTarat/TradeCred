from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.ledger.base import LedgerActor, LedgerClient
from app.integrations.ledger.drunix import DrunixLedgerClient
from app.integrations.ledger.mock import MockLedgerClient


def create_ledger_client(
    session: AsyncSession, settings: Settings, actor: LedgerActor
) -> LedgerClient:
    if settings.ledger_backend == "drunix":
        return DrunixLedgerClient(session, settings, actor)
    return MockLedgerClient(session, actor)
