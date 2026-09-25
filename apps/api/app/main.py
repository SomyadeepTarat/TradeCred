from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router
from app.api.routes.auth import router as auth_router
from app.api.routes.organizations import router as organizations_router
from app.core.errors import APIError, api_error_handler
from app.core.config import Settings
from app.core.database import create_database_engine


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

    application = FastAPI(title="TradeCred API", version="0.2.0", lifespan=lifespan)
    application.include_router(router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(organizations_router, prefix="/api/v1")
    application.add_exception_handler(APIError, api_error_handler)
    return application


app = create_app()
