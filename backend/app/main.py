from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import athletes, auth, health, sync


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application instance."""
    settings = get_settings()
    app = FastAPI(title="Peakstats API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/auth")
    app.include_router(athletes.router, prefix="/athlete")
    app.include_router(sync.router, prefix="/sync")
    return app


app = create_app()
