from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = (Path(__file__).resolve().parent / "../../../../.env").resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    database_url: PostgresDsn = PostgresDsn(
        "postgresql+psycopg://tradecred:tradecred_local@localhost:5432/tradecred"
    )
    ledger_backend: Literal["mock", "drunix"] = "mock"

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_access_token_minutes: int = Field(default=30, ge=1, le=60)

    document_storage_path: Path = ROOT_ENV.parent / "data" / "documents"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)

    @field_validator("document_storage_path", mode="after")
    @classmethod
    def storage_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else (ROOT_ENV.parent / value).resolve()
