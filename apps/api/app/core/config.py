from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr
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
