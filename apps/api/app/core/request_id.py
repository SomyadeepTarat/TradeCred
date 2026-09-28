from time import perf_counter
from uuid import uuid4

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response
from app.core.logging import context, log_event


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = context.set({"request_id": request_id})
        started, status, sent = perf_counter(), 500, False

        async def with_id(message: Message) -> None:
            nonlocal status, sent
            if message["type"] == "http.response.start":
                status, sent = message["status"], True
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, with_id)
        except Exception as exc:
            # No raw exception, SQL, URI or traceback in responses or logs.
            log_event("request_failed", exception_type=type(exc).__name__)
            if not sent:
                response = error_response(
                    Request(scope), 500, "INTERNAL_ERROR", "The request could not be completed."
                )
                await response(scope, receive, with_id)
            else:
                raise RuntimeError("Response stream failed") from None
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            log_event(
                "request_completed",
                method=scope["method"],
                route=route,
                status=status,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            context.reset(token)
