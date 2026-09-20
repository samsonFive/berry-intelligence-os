"""Analyst-managed company logo presentation overrides."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.entity_logo_overrides import (
    LogoOverrideError,
    clear_logo_override,
    load_logo_overrides,
    logo_file,
    set_logo_upload,
    set_logo_url,
    validate_logo_url,
)


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
)


def test_url_override_persists_and_rejects_non_public_hosts(tmp_path: Path):
    row = set_logo_url(tmp_path, "company-test", "https://cdn.example.com/company.png")
    assert row["kind"] == "url"
    assert load_logo_overrides(tmp_path)["company-test"]["url"].endswith("company.png")
    with pytest.raises(LogoOverrideError):
        validate_logo_url("javascript:alert(1)")
    with pytest.raises(LogoOverrideError):
        validate_logo_url("http://127.0.0.1/logo.png")


def test_upload_override_is_validated_and_served_from_safe_path(tmp_path: Path):
    row = set_logo_upload(tmp_path, "company-test", PNG_1X1)
    assert row["url"].startswith("/entity-logos/company-test/logo-")
    path, media_type = logo_file(tmp_path, "company-test", row["filename"])
    assert path.read_bytes() == PNG_1X1
    assert media_type == "image/png"
    with pytest.raises(LogoOverrideError):
        set_logo_upload(tmp_path, "company-test", b"<svg onload=alert(1)>")
    clear_logo_override(tmp_path, "company-test")
    assert "company-test" not in load_logo_overrides(tmp_path)


def test_company_logo_url_and_upload_flow_updates_profile_and_roster(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main.INBOX_DIR", tmp_path)
    client = TestClient(app)
    entity_id = "seed-org-0018"

    pasted = client.post(
        f"/entities/company/{entity_id}/logo",
        data={"action": "save", "logo_url": "https://cdn.example.com/abz-logo.png"},
        follow_redirects=False,
    )
    assert pasted.status_code == 303
    profile = client.get(f"/entities/company/{entity_id}")
    assert "https://cdn.example.com/abz-logo.png" in profile.text
    following = client.get("/following")
    assert "https://cdn.example.com/abz-logo.png" in following.text

    uploaded = client.post(
        f"/entities/company/{entity_id}/logo",
        data={"action": "save", "logo_url": ""},
        files={"logo_file_upload": ("abz.png", PNG_1X1, "image/png")},
        follow_redirects=False,
    )
    assert uploaded.status_code == 303
    override = load_logo_overrides(tmp_path)[entity_id]
    asset = client.get(override["url"])
    assert asset.status_code == 200
    assert asset.headers["content-type"].startswith("image/png")
    assert asset.content == PNG_1X1

    cleared = client.post(
        f"/entities/company/{entity_id}/logo",
        data={"action": "clear", "logo_url": ""},
        follow_redirects=False,
    )
    assert cleared.status_code == 303
    assert entity_id not in load_logo_overrides(tmp_path)
