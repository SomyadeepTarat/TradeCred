from app.core.config import Settings
from app.core.errors import APIError
from app.models.domain import Receivable


def require_ledger_mode(row: Receivable, settings: Settings) -> None:
    # Existing registered records before migration 0006 belong to mock mode.
    backend = row.ledger_backend or ("mock" if row.asset_id else None)
    if backend and (
        backend != settings.ledger_backend
        or (backend == "drunix" and row.ledger_network != settings.drunix_network_id)
    ):
        raise APIError(
            503,
            "LEDGER_BACKEND_MISMATCH",
            "This asset belongs to another ledger backend or network.",
        )


def bind_ledger(row: Receivable, settings: Settings) -> None:
    row.ledger_backend = settings.ledger_backend
    row.ledger_network = settings.drunix_network_id if settings.ledger_backend == "drunix" else None
