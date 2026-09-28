"""Verify fresh setup/reset in a disposable checkout, Compose project and database."""

import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="tradecred-acceptance-") as directory:
        checkout = Path(directory)
        files = (
            subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
            )
            .decode()
            .split("\0")
        )
        for name in files:
            source = ROOT / name
            if name and source.is_file() and not source.is_symlink():
                target = checkout / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        ports = [free_port() for _ in range(4)]
        password = "Acceptance-" + secrets.token_hex(16)
        project = "tc_accept_" + uuid4().hex[:12]
        env = {
            key: value
            for key, value in os.environ.items()
            if key
            in {
                "PATH",
                "HOME",
                "USER",
                "LOGNAME",
                "TMPDIR",
                "LANG",
                "LC_ALL",
                "CI",
                "DOCKER_HOST",
                "DOCKER_CONTEXT",
                "DOCKER_CONFIG",
                "SSH_AUTH_SOCK",
                "UV_CACHE_DIR",
                "UV_PYTHON_INSTALL_DIR",
                "NPM_CONFIG_CACHE",
            }
        }
        # Override inherited application settings so no developer resources are selected.
        env.update(
            COMPOSE_PROJECT_NAME=project,
            LEDGER_BACKEND="mock",
            POSTGRES_USER="tradecred",
            POSTGRES_PASSWORD="tradecred_local",
            POSTGRES_DB="tradecred",
            POSTGRES_PORT=str(ports[0]),
            API_PORT=str(ports[1]),
            WEB_PORT=str(ports[2]),
            SIMULATOR_PORT=str(ports[3]),
            DATABASE_URL=f"postgresql+psycopg://tradecred:tradecred_local@127.0.0.1:{ports[0]}/tradecred",
            JWT_SECRET=secrets.token_hex(32),
            DEMO_PASSWORD=password,
            DEMO_API_URL=f"http://127.0.0.1:{ports[1]}",
            CONFIRM="",
        )
        env.pop("SIMULATOR_TOKEN", None)
        (checkout / ".env").write_text((checkout / ".env.example").read_text())
        (checkout / ".env").chmod(0o600)

        def run(*command: str) -> None:
            subprocess.run(command, cwd=checkout, env=env, check=True)

        def assets() -> set[str]:
            with httpx.Client(base_url=env["DEMO_API_URL"], trust_env=False, timeout=10) as client:
                response = client.post(
                    "/api/v1/auth/login",
                    json={"email": "exporter@tradecred.demo", "password": password},
                )
                response.raise_for_status()
                token = response.json()["access_token"]
                response = client.get(
                    "/api/v1/receivables", headers={"Authorization": "Bearer " + token}
                )
                response.raise_for_status()
                data = response.json()
                assert data["total"] == 4, "Expected four demo fixtures"
                assert {row["status"] for row in data["items"]} == {
                    "VERIFIED",
                    "FINANCE_AVAILABLE",
                    "FINANCED",
                    "REALIZED",
                }
                return {row["id"] for row in data["items"]}

        try:
            run("make", "install")
            run("make", "demo")
            first = assets()
            run("make", "reset")
            assert assets() == first, "Reset preview changed fixtures"
            run("make", "reset", "CONFIRM=RESET-DEMO")
            run("make", "demo")
            second = assets()
            assert first.isdisjoint(second), "Reset failed to recreate fixtures"
            run("make", "seed-fixtures")
            assert assets() == second, "Seeding duplicated fixtures"
            print(
                json.dumps(
                    {"fresh_setup": "passed", "reset_reseed": "passed", "idempotent_seed": "passed"}
                )
            )
        finally:
            # Only resources of the randomly named disposable acceptance project are removed.
            subprocess.run(
                ["docker", "compose", "--profile", "demo", "down", "--volumes", "--remove-orphans"],
                cwd=checkout,
                env=env,
                check=True,
            )


if __name__ == "__main__":
    main()
