from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
DEAUTHORIZE_URL = "https://www.strava.com/oauth/deauthorize"
SCOPE = "read,activity:read_all"


@dataclass
class StravaToken:
    access_token: str
    refresh_token: str
    expires_at: datetime
    athlete: dict = field(default_factory=dict)


class StravaClient:
    """Thin wrapper around Strava's OAuth and API endpoints."""

    def __init__(
        self, http: httpx.Client, client_id: str, client_secret: str, redirect_uri: str
    ) -> None:
        self._http = http
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def authorize_url(self, state: str) -> str:
        """Build the Strava OAuth authorization URL with CSRF state."""
        params = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "approval_prompt": "auto",
                "scope": SCOPE,
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{params}"

    def _post_token(self, data: dict) -> StravaToken:
        response = self._http.post(TOKEN_URL, data=data)
        response.raise_for_status()
        payload = response.json()
        return StravaToken(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            expires_at=datetime.fromtimestamp(payload["expires_at"], tz=UTC),
            athlete=payload.get("athlete", {}),
        )

    def exchange_code(self, code: str) -> StravaToken:
        """Exchange an OAuth authorization code for access/refresh tokens."""
        return self._post_token(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "grant_type": "authorization_code",
            }
        )

    def refresh(self, refresh_token: str) -> StravaToken:
        """Obtain a new access token using a refresh token."""
        return self._post_token(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        )

    def deauthorize(self, access_token: str) -> None:
        """Revoke the app's access on Strava; raises on HTTP error."""
        response = self._http.post(DEAUTHORIZE_URL, data={"access_token": access_token})
        response.raise_for_status()
