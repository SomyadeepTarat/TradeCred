from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.logging import bind


class APIError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict[str, str] | None = None
    ) -> None:
        self.status_code, self.code, self.message = status_code, code, message
        self.details = details or {}


def error_response(
    request: Request, status: int, code: str, message: str, details: dict[str, str] | None = None
) -> JSONResponse:
    bind(error_code=code)
    headers = {"Cache-Control": "no-store"}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    request_id = getattr(request.state, "request_id", "")
    if request_id:
        headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=status,
        headers=headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "requestId": request_id,
            }
        },
    )


async def api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, APIError)
    return error_response(request, exc.status_code, exc.code, exc.message, exc.details)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Pydantic error inputs/context can contain passwords, tokens and private invoice data.
    return error_response(request, 422, "INVALID_REQUEST", "Request fields are invalid.")


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    code, message = {
        404: ("NOT_FOUND", "Endpoint not found."),
        405: ("METHOD_NOT_ALLOWED", "Method not allowed."),
    }.get(exc.status_code, ("HTTP_ERROR", "The request could not be processed."))
    response = error_response(request, exc.status_code, code, message)
    if exc.headers and "Allow" in exc.headers:
        response.headers["Allow"] = exc.headers["Allow"]
    return response
