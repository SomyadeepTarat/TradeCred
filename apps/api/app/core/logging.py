"""Allowlisted operational logging. Never serialize request bodies or exception text."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

context: ContextVar[dict[str, str] | None] = ContextVar("request_context", default=None)
logger = logging.getLogger("tradecred")
FIELDS = {
    "request_id",
    "user_id",
    "org_id",
    "asset_id",
    "transaction_id",
    "event_id",
    "method",
    "route",
    "status",
    "duration_ms",
    "error_code",
    "exception_type",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "event": record.getMessage(),
                **getattr(record, "fields", {}),
            }
        )


def configure_logging() -> None:
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def bind(**fields: str) -> None:
    context.set((context.get() or {}) | {k: v for k, v in fields.items() if k in FIELDS})


def log_event(event: str, **fields: Any) -> None:
    safe = (context.get() or {}) | {k: v for k, v in fields.items() if k in FIELDS}
    logger.info(event, extra={"fields": safe})
