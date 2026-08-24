"""Application session authentication for the remote interactive host.

Starlette ``SessionMiddleware`` (itsdangerous ``TimestampSigner``) holds the
signed HttpOnly cookie. Credentials stay in environment variables. The review
password is never used as the signing secret.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any
from urllib.parse import quote, unquote, urlparse

from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.runtime_config import (
    RemoteInteractiveMisconfigured,
    basic_auth_enabled,
    credentials_match,
    path_is_protected,
    remote_interactive_enabled,
    session_secret,
    validate_remote_interactive_config,
)

SESSION_COOKIE_NAME = "bios_session"
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60
DEFAULT_NEXT_PATH = "/today"
LOGIN_FAILURE_LIMIT = 8
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60

_failure_lock = threading.Lock()
_failures: dict[str, list[float]] = defaultdict(list)


class EnvSessionMiddleware:
    """SessionMiddleware with a request-time signing key.

    Tests monkeypatch ``BIOS_SESSION_SECRET`` on the already-built app, so the
    signer cannot be captured once at import time.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        secret = session_secret()
        if not secret:
            scope["session"] = {}
            await self.app(scope, receive, send)
            return
        middleware = SessionMiddleware(
            self.app,
            secret_key=secret,
            session_cookie=SESSION_COOKIE_NAME,
            max_age=SESSION_MAX_AGE_SECONDS,
            same_site="lax",
            https_only=_cookie_secure(scope),
        )
        await middleware(scope, receive, send)


def _cookie_secure(scope: Scope) -> bool:
    if not remote_interactive_enabled():
        return False
    headers = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }
    forwarded = headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    if forwarded == "https" or scope.get("scheme") == "https":
        return True
    return False


def display_analyst_name(username: str) -> str:
    if not username:
        return ""
    if username.islower():
        return username.title()
    return username


def auth_template_context(request: Request) -> dict[str, Any]:
    username = ""
    session = request.scope.get("session") or {}
    if isinstance(session, dict):
        username = str(session.get("user") or "")
    return {
        "analyst_username": username,
        "analyst_display_name": display_analyst_name(username),
    }


def safe_next_path(raw: str | None) -> str:
    """Allow only local absolute paths. Reject open redirects."""

    if not raw:
        return DEFAULT_NEXT_PATH
    candidate = unquote(str(raw)).strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return DEFAULT_NEXT_PATH
    if "\\" in candidate or "://" in candidate:
        return DEFAULT_NEXT_PATH
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return DEFAULT_NEXT_PATH
    path = parsed.path or "/"
    if not path.startswith("/") or path.startswith("//"):
        return DEFAULT_NEXT_PATH
    if path == "/login" or path.startswith("/login/"):
        return DEFAULT_NEXT_PATH
    if path == "/logout" or path.startswith("/logout/"):
        return DEFAULT_NEXT_PATH
    rebuilt = path
    if parsed.query:
        rebuilt = f"{path}?{parsed.query}"
    if any(ord(char) < 32 for char in rebuilt) or len(rebuilt) > 512:
        return DEFAULT_NEXT_PATH
    return rebuilt


def requested_local_path(request: Request) -> str:
    path = request.url.path or "/"
    query = request.url.query
    return f"{path}?{query}" if query else path


def login_redirect(request: Request) -> Response:
    nxt = quote(safe_next_path(requested_local_path(request)), safe="/")
    return RedirectResponse(url=f"/login?next={nxt}", status_code=302)


def session_username(request: Request) -> str:
    session = request.scope.get("session") or {}
    if not isinstance(session, dict):
        return ""
    return str(session.get("user") or "")


def establish_session(request: Request, username: str) -> None:
    request.session.clear()
    request.session["user"] = username


def clear_session(request: Request) -> None:
    request.session.clear()


def client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def reset_login_failures() -> None:
    with _failure_lock:
        _failures.clear()


def login_is_throttled(request: Request) -> bool:
    key = client_address(request)
    cutoff = time.monotonic() - LOGIN_FAILURE_WINDOW_SECONDS
    with _failure_lock:
        recent = [stamp for stamp in _failures.get(key, []) if stamp >= cutoff]
        _failures[key] = recent
        return len(recent) >= LOGIN_FAILURE_LIMIT


def record_login_failure(request: Request) -> None:
    key = client_address(request)
    now = time.monotonic()
    cutoff = now - LOGIN_FAILURE_WINDOW_SECONDS
    with _failure_lock:
        recent = [stamp for stamp in _failures.get(key, []) if stamp >= cutoff]
        recent.append(now)
        _failures[key] = recent


def clear_login_failures(request: Request) -> None:
    key = client_address(request)
    with _failure_lock:
        _failures.pop(key, None)


def _basic_credentials(request: Request) -> tuple[str, str] | None:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth is None or not auth.lower().startswith("basic "):
        return None
    try:
        import base64

        decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError, OSError):
        return None
    return username, password


def _unauthorized_basic() -> Response:
    return Response(
        content="Authentication required",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Berry Intelligence OS"'},
        media_type="text/plain",
    )


async def remote_auth_middleware(request: Request, call_next):
    path = request.url.path
    if remote_interactive_enabled() and path.rstrip("/") != "/healthz" and not path.startswith("/healthz"):
        try:
            validate_remote_interactive_config()
        except RemoteInteractiveMisconfigured:
            return Response(
                content="Remote interactive mode is misconfigured",
                status_code=503,
                media_type="text/plain",
            )

    if not path_is_protected(path, request.method):
        return await call_next(request)

    if session_username(request):
        return await call_next(request)

    if basic_auth_enabled():
        parsed = _basic_credentials(request)
        if parsed is not None and credentials_match(*parsed):
            return await call_next(request)
        return _unauthorized_basic()

    return login_redirect(request)
