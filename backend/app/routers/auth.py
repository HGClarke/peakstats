import secrets

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from supabase import Client

from app.config import Settings, get_settings
from app.cookies import (
    clear_session_cookie,
    clear_state_cookie,
    set_session_cookie,
    set_state_cookie,
)
from app.deps import get_strava, get_supabase
from app.services import auth as auth_service
from app.session import SESSION_MAX_AGE, STATE_COOKIE, sign_session
from app.strava import StravaClient

router = APIRouter()


@router.get("/strava/login")
def login(
    settings: Settings = Depends(get_settings),
    strava: StravaClient = Depends(get_strava),
) -> Response:
    """Redirect the user to Strava's OAuth authorization page and set a CSRF state cookie."""
    url, state = auth_service.start_login(strava)
    response = RedirectResponse(url, status_code=302)
    set_state_cookie(response, state, settings, max_age=600)
    return response


@router.get("/strava/callback")
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    settings: Settings = Depends(get_settings),
    supabase: Client = Depends(get_supabase),
    strava: StravaClient = Depends(get_strava),
) -> Response:
    """Handle the Strava OAuth callback: verify CSRF state, exchange code, set session cookie."""
    cookie_state = request.cookies.get(STATE_COOKIE)
    state_ok = bool(state and cookie_state and secrets.compare_digest(state, cookie_state))
    if error or not code or not state_ok:
        return RedirectResponse(f"{settings.frontend_origin}/?auth=error", status_code=302)

    athlete_id = auth_service.handle_callback(code, supabase, strava)
    response = RedirectResponse(f"{settings.frontend_origin}/home", status_code=302)
    set_session_cookie(
        response,
        sign_session(athlete_id, settings.session_secret),
        settings,
        max_age=SESSION_MAX_AGE,
    )
    clear_state_cookie(response)
    return response


@router.post("/logout", status_code=204)
def logout(settings: Settings = Depends(get_settings)) -> Response:
    """Clear the session cookie to log the athlete out."""
    response = Response(status_code=204)
    clear_session_cookie(response, settings)
    return response
