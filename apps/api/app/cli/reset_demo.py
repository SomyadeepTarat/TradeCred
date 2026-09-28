import argparse
import asyncio
import json

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.core.database import create_database_engine
from app.services.reset_service import reset_demo


async def run(apply: bool) -> None:
    settings = Settings()
    engine = create_database_engine(str(settings.database_url))
    try:
        async with async_sessionmaker(engine).begin() as session:
            plan = await reset_demo(session, settings, apply=apply)
        print(json.dumps({"applied": apply, "fixtures": plan}, indent=2))
        print("Accounts, keys, audit/security evidence and stored PDFs are retained.")
        if not apply:
            print("Preview only. Apply with make reset CONFIRM=RESET-DEMO, then make demo.")
    except (ValueError, SQLAlchemyError) as exc:
        message = (
            str(exc)
            if isinstance(exc, ValueError)
            else "Database operation failed; reset was rolled back."
        )
        raise SystemExit(message) from None
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset only the four named local mock fixtures.")
    parser.add_argument("--confirm", choices=["RESET-DEMO"])
    args = parser.parse_args()
    asyncio.run(run(args.confirm == "RESET-DEMO"))


if __name__ == "__main__":
    main()
