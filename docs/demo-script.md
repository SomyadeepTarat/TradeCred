# Milestone 0 walkthrough

1. Copy `.env.example` to `.env`, run `make install`, then `make dev`.
2. Open `http://localhost:3000`; verify the bootstrap scope and prototype boundaries.
3. Open `http://localhost:8000/docs` and execute both health requests.
4. Run `make test`, `make lint`, `make test-integration`, and `make build`.
5. Run `docker compose down` to stop without deleting database data.

The three PRD business demos are not yet implemented. Demo users, receivables,
settlement events, and seed/reset scripts must arrive in the specified milestone order.
