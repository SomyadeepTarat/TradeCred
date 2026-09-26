"""Seed only Milestone 1 identities. Run using `make seed`."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.core.database import create_database_engine  # noqa: E402
from app.services.seed_service import seed_demo  # noqa: E402


async def main() -> None:
    load_dotenv(ROOT / ".env")
    password = os.environ.get("DEMO_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Set DEMO_PASSWORD to at least 12 characters before seeding.")
    engine = create_database_engine(str(Settings().database_url))
    try:
        async with async_sessionmaker(engine).begin() as session:
            await seed_demo(session, password)
    finally:
        await engine.dispose()
    print("Demo organizations and users are present; existing credentials were preserved.")


if __name__ == "__main__":
    asyncio.run(main())
