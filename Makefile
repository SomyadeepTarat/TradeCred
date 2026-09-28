API = cd apps/api && uv run --frozen
WEB = npm --prefix apps/web

.PHONY: install dev api web db test test-api test-web test-integration test-e2e test-chaincode lint format build migrate seed demo reset
install:
	uv sync --frozen --project apps/api
	$(WEB) ci

dev:
	docker compose up --build --wait

db:
	docker compose up -d --wait postgres

api:
	$(API) uvicorn app.main:app --no-access-log --reload --host 127.0.0.1 --port 8000

web:
	$(WEB) run dev

test: test-api test-web test-chaincode test-gateway

test-api:
	$(API) pytest -m "not integration"

test-web:
	$(WEB) test

test-integration:
	$(API) pytest -m integration

lint: lint-chaincode lint-gateway
	$(API) ruff check . ../../scripts/test_setup.py ../../scripts/seed_demo.py ../../scripts/seed_fixtures.py ../../scripts/test_ui.py ../../scripts/generate_keys.py ../../services/bank-simulator
	$(API) ruff format --check . ../../scripts/test_setup.py ../../scripts/seed_demo.py ../../scripts/seed_fixtures.py ../../scripts/test_ui.py ../../scripts/generate_keys.py ../../services/bank-simulator
	$(API) mypy app
	$(WEB) run lint
	$(WEB) run typecheck
	$(WEB) run format:check

format: format-chaincode format-gateway
	$(API) ruff format . ../../scripts/test_setup.py ../../scripts/seed_demo.py ../../scripts/seed_fixtures.py ../../scripts/test_ui.py ../../scripts/generate_keys.py ../../services/bank-simulator
	$(API) ruff check --fix . ../../scripts/test_setup.py ../../scripts/seed_demo.py ../../scripts/seed_fixtures.py ../../scripts/test_ui.py ../../scripts/generate_keys.py ../../services/bank-simulator
	$(API) ruff format . ../../scripts/test_setup.py ../../scripts/seed_demo.py ../../scripts/seed_fixtures.py ../../scripts/test_ui.py ../../scripts/generate_keys.py ../../services/bank-simulator
	$(WEB) run format

build:
	$(WEB) run build

migrate:
	$(API) alembic upgrade head

seed:
	uv run --frozen --project apps/api python scripts/seed_demo.py

demo:
	bash scripts/run_demo.sh

seed-fixtures:
	uv run --frozen --project apps/api python scripts/seed_fixtures.py

reset:
	CONFIRM="$(CONFIRM)" bash scripts/reset_demo.sh

test-e2e: build
	uv run --frozen --project apps/api python scripts/test_ui.py

.PHONY: keys bank-event
keys:
	uv run --frozen --project apps/api python scripts/generate_keys.py

bank-event:
	uv run --frozen --project apps/api python services/bank-simulator/app.py $(ARGS)

.PHONY: lint-chaincode format-chaincode build-chaincode
test-chaincode:
	bash scripts/chaincode.sh go test -mod=readonly -race -cover ./...

lint-chaincode:
	bash scripts/chaincode.sh sh -c 'test -z "$$(gofmt -l .)" && go vet -mod=readonly ./...'

format-chaincode:
	bash scripts/chaincode.sh gofmt -w .

build-chaincode:
	bash scripts/chaincode.sh go build -mod=readonly -o build/tradecred .


.PHONY: test-gateway lint-gateway format-gateway build-gateway drunix-preflight drunix-package
test-gateway:
	bash scripts/gateway.sh go test -mod=readonly -race -cover ./...

lint-gateway:
	bash scripts/gateway.sh sh -c 'test -z "$$(gofmt -l .)" && go vet -mod=readonly ./...'

format-gateway:
	bash scripts/gateway.sh gofmt -w .

build-gateway:
	bash scripts/gateway.sh go build -mod=readonly -o build/gateway .

drunix-preflight:
	bash blockchain/network/scripts/preflight.sh

drunix-package:
	bash blockchain/network/scripts/package.sh

.PHONY: test-setup seed-fixtures
test-setup:
	uv run --frozen --project apps/api python scripts/test_setup.py
