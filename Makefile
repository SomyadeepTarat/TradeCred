API = cd apps/api && uv run --frozen
WEB = npm --prefix apps/web

.PHONY: install dev api web db test test-api test-web test-integration test-chaincode lint format build migrate seed demo reset
install:
	uv sync --frozen --project apps/api
	$(WEB) ci

dev:
	docker compose up --build --wait

db:
	docker compose up -d --wait postgres

api:
	$(API) uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

web:
	$(WEB) run dev

test: test-api test-web

test-api:
	$(API) pytest -m "not integration"

test-web:
	$(WEB) test

test-integration:
	$(API) pytest -m integration

lint:
	$(API) ruff check . ../../scripts/seed_demo.py
	$(API) ruff format --check . ../../scripts/seed_demo.py
	$(API) mypy app
	$(WEB) run lint
	$(WEB) run typecheck
	$(WEB) run format:check

format:
	$(API) ruff format . ../../scripts/seed_demo.py
	$(API) ruff check --fix . ../../scripts/seed_demo.py
	$(API) ruff format . ../../scripts/seed_demo.py
	$(WEB) run format

build:
	$(WEB) run build

migrate:
	$(API) alembic upgrade head

seed:
	uv run --frozen --project apps/api python scripts/seed_demo.py

test-chaincode demo reset:
	@echo "$@ is not available in Milestone 3; see README.md for milestone scope."
	@exit 2
