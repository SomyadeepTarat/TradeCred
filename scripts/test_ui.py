"""Run browser acceptance tests against isolated PostgreSQL and temporary PDF storage."""

import asyncio
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from pypdf import PdfWriter
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps/api"
sys.path.insert(0, str(API))


def wait_ready(url: str, process: subprocess.Popen[bytes]) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Test server exited before readiness.")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.2)
    raise RuntimeError("Test server did not become ready.")


async def seed(url: str, password: str) -> None:
    from app.core.database import create_database_engine
    from app.services.seed_service import seed_demo

    engine = create_database_engine(url)
    try:
        async with async_sessionmaker(engine).begin() as session:
            await seed_demo(session, password)
    finally:
        await engine.dispose()


def main() -> int:
    # Refuse to touch a process already using either dedicated test port.
    for port in (8001, 3001):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
    settings = {**dotenv_values(ROOT / ".env"), **os.environ}
    base_url = make_url(
        settings.get("DATABASE_URL")
        or "postgresql+psycopg://tradecred:tradecred_local@localhost:5432/tradecred"
    )
    engine = create_engine(base_url)
    schema = "tc_ui_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    processes: list[subprocess.Popen[bytes]] = []
    with tempfile.TemporaryDirectory(prefix="tradecred-ui-") as directory:
        temp = Path(directory)
        env = dict(os.environ)
        env.update(
            DATABASE_URL=base_url.update_query_dict(
                {"options": f"-csearch_path={schema}"}
            ).render_as_string(hide_password=False),
            JWT_SECRET="tradecred-e2e-only-signing-key-0123456789",
            LEDGER_BACKEND="mock",
            DOCUMENT_STORAGE_PATH=str(temp / "documents"),
            E2E_PASSWORD="TradeCred-E2E-2026!",
            E2E_PDF_PATH=str(temp / "invoice.pdf"),
            API_INTERNAL_URL="http://127.0.0.1:8001",
            PORT="3001",
            HOSTNAME="127.0.0.1",
        )
        log_path = temp / "servers.log"
        try:
            original = os.environ.get("DATABASE_URL")
            os.environ["DATABASE_URL"] = env["DATABASE_URL"]
            os.environ.setdefault("JWT_SECRET", env["JWT_SECRET"])
            try:
                config = Config(str(API / "alembic.ini"))
                config.set_main_option("script_location", str(API / "migrations"))
                command.upgrade(config, "head")
            finally:
                if original is None:
                    os.environ.pop("DATABASE_URL", None)
                else:
                    os.environ["DATABASE_URL"] = original
            asyncio.run(seed(env["DATABASE_URL"], env["E2E_PASSWORD"]))
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            writer.add_metadata({"/Title": "Fictional UI acceptance invoice"})
            writer.write(env["E2E_PDF_PATH"])
            with log_path.open("wb") as log:
                api = subprocess.Popen(
                    [
                        str(API / ".venv/bin/uvicorn"),
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8001",
                    ],
                    cwd=API,
                    env=env,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
                processes.append(api)
                wait_ready("http://127.0.0.1:8001/api/v1/health/ready", api)
                web = subprocess.Popen(
                    ["node", ".next/standalone/server.js"],
                    cwd=ROOT / "apps/web",
                    env=env,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
                processes.append(web)
                wait_ready("http://127.0.0.1:3001/login", web)
                result = subprocess.run(
                    ["npx", "--no-install", "playwright", "test"],
                    cwd=ROOT / "apps/web",
                    env=env,
                    check=False,
                )
                return result.returncode
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
