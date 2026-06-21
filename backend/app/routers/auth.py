import secrets

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from app.config import Settings, get_settings
from app.deps import get_strava, get_supabase
from app.services import auth as auth_service
from app.session import SESSION_COOKIE, SESSION_MAX_AGE, STATE_COOKIE, sign_session

router = APIRouter()


def _set_cookie(
    response: Response, name: str, value: str, settings: Settings, max_age: int
) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


@router.get("/strava/login")
def login(
    settings: Settings = Depends(get_settings),
    strava=Depends(get_strava),
) -> Response:
    url, state = auth_service.start_login(strava)
    response = RedirectResponse(url, status_code=302)
    _set_cookie(response, STATE_COOKIE, state, settings, max_age=600)
    return response


@router.get("/strava/callback")
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    settings: Settings = Depends(get_settings),
    supabase=Depends(get_supabase),
    strava=Depends(get_strava),
) -> Response:
    cookie_state = request.cookies.get(STATE_COOKIE)
    state_ok = bool(state and cookie_state and secrets.compare_digest(state, cookie_state))
    if error or not code or not state_ok:
        return RedirectResponse(f"{settings.frontend_origin}/?auth=error", status_code=302)

    athlete_id = auth_service.handle_callback(code, supabase, strava)
    response = RedirectResponse(f"{settings.frontend_origin}/app", status_code=302)
    _set_cookie(
        response,
        SESSION_COOKIE,
        sign_session(athlete_id, settings.session_secret),
        settings,
        max_age=SESSION_MAX_AGE,
    )
    response.delete_cookie(STATE_COOKIE, path="/")
    return response


@router.post("/logout", status_code=204)
def logout(settings: Settings = Depends(get_settings)) -> Response:
    response = Response(status_code=204)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )
    return response
