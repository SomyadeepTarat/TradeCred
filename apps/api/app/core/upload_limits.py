from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import APIError


class UploadLimitMiddleware:
    """Bound multipart bodies before parsing/spooling, including chunked requests."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != "/api/v1/receivables"
        ):
            await self.app(scope, receive, send)
            return
        size = Headers(scope=scope).get("content-length")
        if size is not None and (not size.isdecimal() or int(size) > self.max_bytes):
            response = JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "UPLOAD_TOO_LARGE",
                        "message": "Upload exceeds the request size limit.",
                        "details": {},
                    }
                },
            )
            await response(scope, receive, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise APIError(
                        413, "UPLOAD_TOO_LARGE", "Upload exceeds the request size limit."
                    )
            return message

        await self.app(scope, limited_receive, send)
