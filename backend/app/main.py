from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import activities, athletes, auth, health, sync, webhooks


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
    app.include_router(activities.router, prefix="/activities")
    app.include_router(sync.router, prefix="/sync")
    app.include_router(webhooks.router, prefix="/webhooks")
    return app


app = create_app()
