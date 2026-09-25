from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness does not depend on external infrastructure."""
    return {"status": "ok", "service": "tradecred-api"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    """Report readiness only after a real database query succeeds."""
    try:
        await check_database(request.app.state.database)
    except (SQLAlchemyError, OSError):
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "checks": {"database": "unavailable"}},
        )
    return JSONResponse(content={"status": "ok", "checks": {"database": "ok"}})
