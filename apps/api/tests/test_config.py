import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_invalid_ledger_backend_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ledger_backend="silent-fallback")  # type: ignore[arg-type]


def test_non_postgres_database_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite:///db")  # type: ignore[arg-type]


@pytest.mark.parametrize("secret", ["", "too-short"])
def test_weak_jwt_secret_rejected(secret: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret=secret)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "url", ["http://remote.example", "https://u:p@remote.example", "https://remote.example/path"]
)
def test_gateway_rejects_unsafe_origins(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, drunix_gateway_url=url)


def test_blank_gateway_credentials_allow_explicit_mock() -> None:
    settings = Settings(
        _env_file=None, ledger_backend="mock", drunix_gateway_token="", drunix_gateway_ca_path=""
    )
    assert settings.drunix_gateway_token is None
    assert settings.drunix_gateway_ca_path is None
