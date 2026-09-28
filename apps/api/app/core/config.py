from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = (Path(__file__).resolve().parent / "../../../../.env").resolve()


class TrustedBankKey(BaseModel):
    bank_id: str
    organization_id: str
    public_key_path: Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    database_url: PostgresDsn = PostgresDsn(
        "postgresql+psycopg://tradecred:tradecred_local@localhost:5432/tradecred"
    )
    bank_trusted_keys: dict[str, TrustedBankKey] = Field(default_factory=dict)
    payment_timestamp_tolerance_seconds: int = Field(default=300, ge=1, le=300)

    ledger_backend: Literal["mock", "drunix"] = "mock"

    drunix_gateway_url: str = ""
    drunix_gateway_token: SecretStr | None = Field(default=None, min_length=32)
    drunix_gateway_ca_path: Path | None = None
    drunix_network_id: str = ""
    drunix_channel: str = ""
    drunix_chaincode_name: str = "tradecred"
    drunix_timeout_seconds: int = Field(default=55, ge=50, le=120)

    @field_validator("drunix_gateway_token", "drunix_gateway_ca_path", mode="before")
    @classmethod
    def empty_optional(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("drunix_gateway_url")
    @classmethod
    def gateway_url(cls, value: str) -> str:
        if not value:
            return value
        url = urlparse(value)
        if url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
            raise ValueError("Gateway URL must be an origin without credentials")
        if url.scheme != "https" and not (
            url.scheme == "http"
            and url.hostname in {"127.0.0.1", "localhost", "::1", "drunix-gateway"}
        ):
            raise ValueError("Remote gateway connections require HTTPS")
        return value

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_access_token_minutes: int = Field(default=30, ge=1, le=60)

    document_storage_path: Path = ROOT_ENV.parent / "data" / "documents"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)

    @field_validator("document_storage_path", mode="after")
    @classmethod
    def storage_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else (ROOT_ENV.parent / value).resolve()
