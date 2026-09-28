from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.demo import router as demo_router
from app.api.routes.financing import router as financing_router
from app.api.routes.health import router
from app.api.routes.ledger import router as ledger_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.receivables import router as receivables_router
from app.api.routes.settlement import router as settlement_router
from app.core.config import Settings
from app.core.database import create_database_engine
from app.core.errors import APIError, api_error_handler
from app.core.request_id import RequestIdMiddleware
from app.core.upload_limits import UploadLimitMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(str(config.database_url))
        app.state.database = engine
        app.state.settings = config
        try:
            yield
        finally:
            await engine.dispose()

    application = FastAPI(title="TradeCred API", version="0.9.0", lifespan=lifespan)
    application.include_router(router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(organizations_router, prefix="/api/v1")
    application.include_router(receivables_router, prefix="/api/v1")
    application.add_middleware(UploadLimitMiddleware, max_bytes=config.max_upload_bytes + 65536)
    application.include_router(ledger_router, prefix="/api/v1")
    application.include_router(financing_router, prefix="/api/v1")
    application.include_router(settlement_router, prefix="/api/v1")
    application.include_router(demo_router, prefix="/api/v1")
    application.add_middleware(RequestIdMiddleware)
    application.add_exception_handler(APIError, api_error_handler)
    return application


app = create_app()
