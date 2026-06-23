import httpx
from supabase import Client, ClientOptions, create_client

from app.config import Settings
from app.strava import StravaClient


class RetryTransport(httpx.BaseTransport):
    """Wrap an httpx transport and retry a request when the pooled keep-alive
    connection has been closed server-side.

    Supabase's gateway drops idle HTTP/2 connections, so the long-lived shared
    client eventually reuses a dead socket and raises ``RemoteProtocolError``
    ("Server disconnected") — or ``ConnectError`` on a cold start. httpx evicts
    the failed connection, so a single retry lands on a fresh one. Our DB calls
    (selects + idempotent upserts/updates) are safe to replay.
    """

    _RETRYABLE = (httpx.RemoteProtocolError, httpx.ConnectError)

    def __init__(self, wrapped: httpx.BaseTransport, retries: int = 1) -> None:
        self._wrapped = wrapped
        self._retries = retries

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        for attempt in range(self._retries + 1):
            try:
                return self._wrapped.handle_request(request)
            except self._RETRYABLE:
                if attempt == self._retries:
                    raise
        raise RuntimeError("unreachable")  # pragma: no cover

    def close(self) -> None:
        self._wrapped.close()


def build_supabase(settings: Settings) -> Client:
    """A Supabase client configured with the service-role key.

    `create_client` performs no network I/O, so this is safe to call at startup.
    The client wraps a synchronous httpx session (connection pooling + keep-alive);
    share one instance for the app's lifetime (see app.main lifespan).

    The PostgREST session's transport is wrapped in `RetryTransport` so a stale
    keep-alive connection (Supabase drops idle HTTP/2 conns) is retried on a
    fresh connection instead of surfacing as a 500.
    """
    client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(postgrest_client_timeout=10),
    )
    session = client.postgrest.session
    session._transport = RetryTransport(session._transport)
    return client


def build_strava(settings: Settings) -> StravaClient:
    """A StravaClient backed by a short-lived httpx session."""
    redirect_uri = f"{settings.backend_base_url}/auth/strava/callback"
    http = httpx.Client(timeout=10)
    return StravaClient(
        http, settings.strava_client_id, settings.strava_client_secret, redirect_uri
    )
