"""Centralized HTTP cookie helpers.

Keeps the `secure`/`samesite`/`path`/`httponly` flags in one place so routers
don't each re-specify them. Cookie *names* and signing live in `app.session`;
this module is only the HTTP mechanics of setting and clearing them.
"""

from fastapi import Response

from app.config import Settings
from app.session import SESSION_COOKIE, STATE_COOKIE


def set_session_cookie(
    response: Response, value: str, settings: Settings, max_age: int
) -> None:
    """Attach the signed session cookie with the configured security flags."""
    _set(response, SESSION_COOKIE, value, settings, max_age)


def clear_session_cookie(response: Response, settings: Settings) -> None:
    """Remove the session cookie using the same flags it was set with."""
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )


def set_state_cookie(
    response: Response, value: str, settings: Settings, max_age: int
) -> None:
    """Attach the short-lived OAuth CSRF state cookie."""
    _set(response, STATE_COOKIE, value, settings, max_age)


def clear_state_cookie(response: Response) -> None:
    """Remove the OAuth CSRF state cookie."""
    response.delete_cookie(STATE_COOKIE, path="/")


def _set(
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
