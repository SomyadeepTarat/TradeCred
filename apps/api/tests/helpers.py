from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database import create_database_engine
from app.services.seed_service import seed_demo

PASSWORD = "TradeCred-Test-2026!"
API_ROOT = Path(__file__).resolve().parents[1]


def migration_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


async def seed(url: str, password: str = PASSWORD) -> None:
    engine = create_database_engine(url)
    try:
        async with async_sessionmaker(engine).begin() as session:
            await seed_demo(session, password)
    finally:
        await engine.dispose()


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["expires_in"] == 1800
    return {"Authorization": "Bearer " + response.json()["access_token"]}
