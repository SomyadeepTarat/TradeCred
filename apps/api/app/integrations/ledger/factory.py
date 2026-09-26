from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import APIError
from app.integrations.ledger.base import LedgerActor, LedgerClient
from app.integrations.ledger.mock import MockLedgerClient


def create_ledger_client(
    session: AsyncSession, settings: Settings, actor: LedgerActor
) -> LedgerClient:
    if settings.ledger_backend != "mock":
        raise APIError(
            503,
            "LEDGER_UNAVAILABLE",
            "Drunix integration is not available in this milestone; no fallback was used.",
        )
    return MockLedgerClient(session, actor)
