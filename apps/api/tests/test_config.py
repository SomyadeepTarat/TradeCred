import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_invalid_ledger_backend_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ledger_backend="silent-fallback")  # type: ignore[arg-type]


def test_non_postgres_database_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite:///db")  # type: ignore[arg-type]
