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
	$(API) uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

web:
	$(WEB) run dev

test: test-api test-web test-chaincode

test-api:
	$(API) pytest -m "not integration"

test-web:
	$(WEB) test

test-integration:
	$(API) pytest -m integration

lint: lint-chaincode
	$(API) ruff check . ../../scripts/seed_demo.py ../../scripts/test_ui.py ../../scripts/generate_keys.py ../../services/bank-simulator
	$(API) ruff format --check . ../../scripts/seed_demo.py ../../scripts/test_ui.py ../../scripts/generate_keys.py ../../services/bank-simulator
	$(API) mypy app
	$(WEB) run lint
	$(WEB) run typecheck
	$(WEB) run format:check

format: format-chaincode
	$(API) ruff format . ../../scripts/seed_demo.py ../../scripts/test_ui.py ../../scripts/generate_keys.py ../../services/bank-simulator
	$(API) ruff check --fix . ../../scripts/seed_demo.py ../../scripts/test_ui.py ../../scripts/generate_keys.py ../../services/bank-simulator
	$(API) ruff format . ../../scripts/seed_demo.py ../../scripts/test_ui.py ../../scripts/generate_keys.py ../../services/bank-simulator
	$(WEB) run format

build:
	$(WEB) run build

migrate:
	$(API) alembic upgrade head

seed:
	uv run --frozen --project apps/api python scripts/seed_demo.py

demo reset:
	@echo "$@ is not available in Milestone 7; see README.md for milestone scope."
	@exit 2

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
