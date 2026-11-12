"""Application session authentication for the remote interactive host.

Starlette ``SessionMiddleware`` (itsdangerous ``TimestampSigner``) holds the
signed HttpOnly cookie. Credentials stay in environment variables. The review
password is never used as the signing secret.
"""

from __future__ import annotations

import threading
import time
import re
from collections import defaultdict
from typing import Any
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse

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


def is_investigation_path(path: str) -> bool:
    if path in {"/app/landscape", "/app/briefing", "/app/workspaces", "/app/learn"}:
        return True
    match = re.fullmatch(r"/app/learn/(?:concept|lesson)/([A-Za-z0-9_.-]{1,180})", path)
    return bool(match and match.group(1) not in {".", ".."})


def safe_next_path(raw: str | None) -> str:
    """Allow only local absolute paths. Reject open redirects."""

    if not raw:
        return DEFAULT_NEXT_PATH
    original_text = str(raw).strip()
    try:
        original_parts = urlparse(original_text)
    except ValueError:
        return DEFAULT_NEXT_PATH
    if (not original_parts.scheme and not original_parts.netloc and is_investigation_path(original_parts.path)):
        # Only these fixed local paths accept a larger explicit context. Query
        # text can legitimately contain a URL; it cannot change the destination.
        rebuilt = original_parts.path + ("?" + original_parts.query if original_parts.query else "")
        if len(rebuilt) > 4096 or any(ord(char) < 32 for char in unquote(original_text)):
            return DEFAULT_NEXT_PATH
        return rebuilt
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
    # The investigation URL explicitly carries its bounded cohort and nested
    # detail path. Preserve those deep links through login without expanding
    # the accepted length of unrelated legacy redirects.
    investigation_path = is_investigation_path(path)
    maximum = 4096 if investigation_path else 512
    if investigation_path:
        original = urlparse(str(raw).strip())
        if original.path == path:
            # Preserve escaped query delimiters in search text: decoding %26
            # into '&' here would change the investigation after login.
            rebuilt = path + ("?" + original.query if original.query else "")
    if any(ord(char) < 32 for char in candidate) or len(rebuilt) > maximum:
        return DEFAULT_NEXT_PATH
    return rebuilt


def requested_local_path(request: Request) -> str:
    path = request.url.path or "/"
    query = request.url.query
    return f"{path}?{query}" if query else path


def investigation_return_context(request: Request) -> dict[str, Any]:
    """A bounded explicit return from retained full dossiers/readers to React."""
    raw = request.query_params.get("return_to", "")
    candidate = safe_next_path(raw) if raw else ""
    result: dict[str, Any] = {"investigation_return_href": "", "investigation_header_links": {},
                              "investigation_header_current": ""}
    if not candidate or not is_investigation_path(urlparse(candidate).path):
        return result
    result["investigation_return_href"] = candidate
    # Header context is stronger than a safe navigation destination: it must
    # carry the supported typed selection and have no ambiguous selector values.
    from app.services.investigation_api import CONTEXT_FIELDS, context_query, normalize_context
    try:
        target = urlparse(candidate)
        pairs = parse_qsl(target.query, keep_blank_values=True, max_num_fields=80)
        selectors = {}
        for key, value in pairs:
            if key in CONTEXT_FIELDS:
                if key in selectors:
                    return result
                selectors[key] = value
        if selectors.get("ctx_v") != "1":
            return result
        context, _issues = normalize_context(selectors)
        query = context_query(context)
        native_return = target.path + "?" + query
        links = {name: "/app/" + name + "?" + query for name in ("landscape", "briefing", "learn")}
        links["workspaces"] = "/workspaces?" + urlencode({"return_to": native_return})
        links["save"] = "/app/workspaces?" + query
        if any(len(href) > 4096 for href in links.values()):
            return result
    except (TypeError, ValueError):
        return result
    result["investigation_header_links"] = links
    path = request.url.path.rstrip("/")
    if path == "/workspaces" or path.startswith("/workspaces/"):
        result["investigation_header_current"] = "workspaces"
    return result


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

    username = session_username(request)
    if username:
        from app.runtime_config import review_username
        from app import main
        from app.services.analyst_accounts import load_accounts
        account = load_accounts(main.INBOX_DIR).get(username)
        if username == review_username() or (isinstance(account, dict) and account.get("enabled") is True):
            from app.services.personal_scope import bind
            with bind(username, review_username()):
                return await call_next(request)
        clear_session(request)
        return login_redirect(request)

    if basic_auth_enabled():
        parsed = _basic_credentials(request)
        if parsed is not None and credentials_match(*parsed):
            from app.runtime_config import review_username
            from app.services.personal_scope import bind
            with bind(parsed[0], review_username()):
                return await call_next(request)
        return _unauthorized_basic()

    return login_redirect(request)
