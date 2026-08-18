from __future__ import annotations

import json
from base64 import b64encode

import pytest
from fastapi.testclient import TestClient
from itsdangerous.timed import TimestampSigner

from app.main import app
from app.runtime_config import RemoteInteractiveMisconfigured, validate_remote_interactive_config
from app.session_auth import (
    LOGIN_FAILURE_LIMIT,
    SESSION_COOKIE_NAME,
    reset_login_failures,
    safe_next_path,
)

OPERATOR = "demo-operator"
PASSWORD = "temporary-proof-password"
SESSION_SECRET = "application-session-secret-not-the-password"


def _enable_remote(monkeypatch, **overrides: str) -> None:
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", OPERATOR)
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", PASSWORD)
    monkeypatch.setenv("BIOS_SESSION_SECRET", SESSION_SECRET)
    monkeypatch.delenv("BIOS_BASIC_AUTH", raising=False)
    for key, value in overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    reset_login_failures()


def _client() -> TestClient:
    return TestClient(app, follow_redirects=False)


def test_local_mode_does_not_require_auth() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["remote_interactive"] is False
    assert client.get("/work-queue").status_code == 200
    assert client.get("/review").status_code == 200


def test_anonymous_protected_routes_redirect_to_login(monkeypatch) -> None:
    _enable_remote(monkeypatch)
    client = _client()
    blocked = client.get("/work-queue")
    assert blocked.status_code == 302
    assert blocked.headers["location"].startswith("/login?next=")
    assert "work-queue" in blocked.headers["location"]
    assert "www-authenticate" not in {key.lower() for key in blocked.headers.keys()}
    assert client.get("/review").status_code == 302
    assert client.get("/").status_code == 302
    assert client.get("/healthz").status_code == 200
    login = client.get("/login")
    assert login.status_code == 200
    assert "Intelligence Workbench" in login.text
    assert "Private analyst workspace" in login.text
    assert "Sign in to review and curate incoming intelligence." in login.text
    assert "Scan. Review. Trust." in login.text
    assert "FastAPI" not in login.text
    assert "Docker" not in login.text
    assert "Basic Auth" not in login.text
    assert "BIOS_" not in login.text
    assert "<style>" in login.text
    assert ".login-card" in login.text
    assert "max-width: 420px" in login.text
    assert client.get("/static/app.css").status_code == 200


def test_wrong_password_is_rejected_without_leaking_which_field(monkeypatch) -> None:
    _enable_remote(monkeypatch)
    client = _client()
    response = client.post(
        "/login",
        data={"username": OPERATOR, "password": "wrong-password", "next": "/work-queue"},
    )
    assert response.status_code == 200
    assert "Username or password is incorrect." in response.text
    assert "wrong-password" not in response.text
    assert f'value="{OPERATOR}"' in response.text
    assert 'type="password"' in response.text
    assert "www-authenticate" not in {key.lower() for key in response.headers.keys()}
    assert client.get("/work-queue").status_code == 302


def test_successful_login_creates_session_and_reaches_scanner(monkeypatch) -> None:
    _enable_remote(monkeypatch)
    client = _client()
    response = client.post(
        "/login",
        data={"username": OPERATOR, "password": PASSWORD, "next": "/work-queue"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/work-queue"
    cookie = response.headers.get("set-cookie", "")
    assert SESSION_COOKIE_NAME in cookie
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()
    assert PASSWORD not in cookie
    scanner = client.get("/work-queue")
    assert scanner.status_code == 200
    assert "Scanner" in scanner.text
    assert "Sign out" in scanner.text
    assert "Demo-Operator" in scanner.text or "demo-operator" in scanner.text


def test_https_session_cookie_is_secure(monkeypatch) -> None:
    _enable_remote(monkeypatch)
    client = TestClient(app, base_url="https://testserver", follow_redirects=False)
    response = client.post(
        "/login",
        data={"username": OPERATOR, "password": PASSWORD, "next": "/work-queue"},
    )
    cookie = response.headers.get("set-cookie", "").lower()
    assert "secure" in cookie
    assert "httponly" in cookie


def test_logout_clears_authentication(monkeypatch) -> None:
    _enable_remote(monkeypatch)
    client = _client()
    client.post("/login", data={"username": OPERATOR, "password": PASSWORD, "next": "/work-queue"})
    assert client.get("/work-queue").status_code == 200
    logged_out = client.post("/logout")
    assert logged_out.status_code == 303
    assert logged_out.headers["location"] == "/login"
    blocked = client.get("/work-queue")
    assert blocked.status_code == 302
    assert "/login" in blocked.headers["location"]


def test_tampered_cookie_is_rejected(monkeypatch) -> None:
    _enable_remote(monkeypatch)
    client = _client()
    forged = TimestampSigner("forged-signing-key-that-is-not-valid-xxx").sign(
        b64encode(json.dumps({"user": OPERATOR}).encode("utf-8"))
    ).decode("utf-8")
    client.cookies.set(SESSION_COOKIE_NAME, forged)
    blocked = client.get("/work-queue")
    assert blocked.status_code == 302
    assert "/login" in blocked.headers["location"]


def test_unsafe_next_cannot_redirect_externally(monkeypatch) -> None:
    _enable_remote(monkeypatch)
    assert safe_next_path("https://evil.example/phish") == "/work-queue"
    assert safe_next_path("//evil.example") == "/work-queue"
    assert safe_next_path("/\\evil.example") == "/work-queue"
    assert safe_next_path("/work-queue") == "/work-queue"
    assert safe_next_path("/review?kind=publication") == "/review?kind=publication"
    client = _client()
    response = client.post(
        "/login",
        data={
            "username": OPERATOR,
            "password": PASSWORD,
            "next": "https://evil.example/phish",
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/work-queue"


def test_missing_session_secret_fails_closed(monkeypatch) -> None:
    _enable_remote(monkeypatch)
    monkeypatch.delenv("BIOS_SESSION_SECRET", raising=False)
    with pytest.raises(RemoteInteractiveMisconfigured):
        validate_remote_interactive_config()
    client = _client()
    response = client.get("/work-queue")
    assert response.status_code == 503
    assert "password" not in response.text.casefold()
    assert "BIOS_" not in response.text


def test_session_secret_cannot_be_the_review_password(monkeypatch) -> None:
    long_password = "temporary-proof-password-long-enough-secret"
    _enable_remote(
        monkeypatch,
        BIOS_REVIEW_PASSWORD=long_password,
        BIOS_SESSION_SECRET=long_password,
    )
    with pytest.raises(RemoteInteractiveMisconfigured):
        validate_remote_interactive_config()


def test_remote_interactive_missing_credentials_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.delenv("BIOS_REVIEW_USERNAME", raising=False)
    monkeypatch.delenv("BIOS_REVIEW_PASSWORD", raising=False)
    monkeypatch.setenv("BIOS_SESSION_SECRET", SESSION_SECRET)
    with pytest.raises(RemoteInteractiveMisconfigured):
        validate_remote_interactive_config()
    client = _client()
    response = client.get("/work-queue")
    assert response.status_code == 503
    assert "password" not in response.text.casefold()


def test_basic_auth_is_opt_in_emergency_only(monkeypatch) -> None:
    _enable_remote(monkeypatch, BIOS_BASIC_AUTH="true")
    client = _client()
    login = client.get("/login")
    assert login.status_code == 200
    assert "www-authenticate" not in {key.lower() for key in login.headers.keys()}
    blocked = client.get("/work-queue")
    assert blocked.status_code == 401
    assert blocked.headers.get("www-authenticate", "").lower().startswith("basic")
    allowed = client.get("/work-queue", auth=(OPERATOR, PASSWORD))
    assert allowed.status_code == 200


def test_login_throttling_uses_generic_error(monkeypatch) -> None:
    _enable_remote(monkeypatch)
    client = _client()
    for _ in range(LOGIN_FAILURE_LIMIT):
        failed = client.post(
            "/login",
            data={"username": OPERATOR, "password": "wrong-password"},
        )
        assert failed.status_code == 200
        assert "Username or password is incorrect." in failed.text
    throttled = client.post(
        "/login",
        data={"username": OPERATOR, "password": "wrong-password"},
    )
    assert throttled.status_code == 200
    assert "Too many sign-in attempts" in throttled.text
    assert PASSWORD not in throttled.text
