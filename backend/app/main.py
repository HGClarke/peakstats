import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients import build_supabase
from app.config import get_settings
from app.routers import activities, athletes, auth, health, sync, webhooks


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application instance."""
    settings = get_settings()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One Supabase client for the whole process: connection pooling and
        # keep-alive, no per-request TLS handshake. Safe to share because we use a
        # single service-role key and never mutate per-request auth on the client.
        app.state.supabase = build_supabase(settings)
        try:
            yield
        finally:
            # Best-effort: release the pooled httpx connections held by the
            # postgrest sub-client. The sync supabase Client exposes no top-level
            # close(); if its internals change, the OS reclaims the sockets at
            # process exit (acceptable per the design spec).
            session = getattr(app.state.supabase.postgrest, "session", None)
            if session is not None:
                session.close()

    app = FastAPI(title="Peakstats API", lifespan=lifespan)
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
