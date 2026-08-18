from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runtime_config import RemoteInteractiveMisconfigured, validate_remote_interactive_config


def test_local_mode_does_not_require_auth() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["remote_interactive"] is False
    assert client.get("/work-queue").status_code == 200
    assert client.get("/review").status_code == 200


def test_remote_interactive_requires_auth(monkeypatch) -> None:
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "demo-operator")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "temporary-proof-password")
    client = TestClient(app)
    blocked = client.get("/work-queue")
    assert blocked.status_code == 401
    assert blocked.headers.get("www-authenticate", "").lower().startswith("basic")
    assert client.get("/review").status_code == 401
    assert client.get("/").status_code == 401
    assert client.get("/healthz").status_code == 200

    allowed = client.get("/work-queue", auth=("demo-operator", "temporary-proof-password"))
    assert allowed.status_code == 200
    assert "Scanner" in allowed.text
    assert client.get("/work-queue", auth=("demo-operator", "wrong-password")).status_code == 401


def test_remote_interactive_missing_credentials_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.delenv("BIOS_REVIEW_USERNAME", raising=False)
    monkeypatch.delenv("BIOS_REVIEW_PASSWORD", raising=False)
    with pytest.raises(RemoteInteractiveMisconfigured):
        validate_remote_interactive_config()
    client = TestClient(app)
    response = client.get("/work-queue")
    assert response.status_code == 503
    assert "password" not in response.text.casefold()
