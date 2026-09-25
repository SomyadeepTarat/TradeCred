# Bootstrap API

Interactive schema: `http://localhost:8000/docs`.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/v1/health` | 200 with `status: ok`, `service: tradecred-api`; process liveness |
| GET | `/api/v1/health/ready` | Real `SELECT 1`; 200 with database `ok`, or 503 with database `unavailable` |

Health endpoints are public and return no secrets or exception details. Authentication
and all domain endpoints in PRD section 23 are deferred to their respective milestones.
No health response asserts Drunix availability.
