import httpx
import pytest
from app.clients import RetryTransport, build_strava, build_supabase
from app.config import Settings
from supabase import Client


def _settings() -> Settings:
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="svc",
        backend_base_url="http://localhost:8000",
        strava_client_id="cid",
        strava_client_secret="sec",
    )


class _FlakyTransport(httpx.BaseTransport):
    """Test double for the network boundary: fails the first `fail_times`
    requests with a stale-connection error, then succeeds."""

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise httpx.RemoteProtocolError("Server disconnected", request=request)
        return httpx.Response(200, text="ok")


def test_retry_transport_recovers_from_server_disconnect():
    flaky = _FlakyTransport(fail_times=1)
    transport = RetryTransport(flaky)
    request = httpx.Request("GET", "https://test.supabase.co/rest/v1/segments")

    response = transport.handle_request(request)

    assert response.status_code == 200
    assert flaky.calls == 2  # initial attempt + one retry on a fresh connection


def test_retry_transport_reraises_when_retries_exhausted():
    flaky = _FlakyTransport(fail_times=5)
    transport = RetryTransport(flaky, retries=1)
    request = httpx.Request("GET", "https://test.supabase.co/rest/v1/segments")

    with pytest.raises(httpx.RemoteProtocolError):
        transport.handle_request(request)

    assert flaky.calls == 2  # gives up rather than masking a real outage


def test_build_supabase_hardens_postgrest_transport():
    client = build_supabase(_settings())
    assert isinstance(client.postgrest.session._transport, RetryTransport)


def test_build_supabase_returns_supabase_client():
    client = build_supabase(_settings())
    assert isinstance(client, Client)
    assert callable(client.table)


def test_build_strava_returns_configured_client():
    strava = build_strava(_settings())
    try:
        url = strava.authorize_url("state123")
        assert "client_id=cid" in url
        assert "state=state123" in url
    finally:
        strava.close()
