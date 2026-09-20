"""Analyst-managed company logo presentation overrides.

Overrides live in ``inbox/`` and never rewrite trusted entity or seed data.
Only public http(s) URLs or validated local raster images are accepted.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SUBDIR = "entity_logos"
INDEX_NAME = "overrides.json"
MAX_LOGO_BYTES = 2 * 1024 * 1024
_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]+$")
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}


class LogoOverrideError(ValueError):
    pass


def safe_entity_id(entity_id: str) -> str:
    value = str(entity_id or "").strip()
    if not value or not _SAFE_ID.fullmatch(value):
        raise LogoOverrideError("invalid entity id")
    return value


def _root(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / SUBDIR


def _index_path(inbox_dir: Path) -> Path:
    return _root(inbox_dir) / INDEX_NAME


def load_logo_overrides(inbox_dir: Path) -> dict[str, dict[str, Any]]:
    path = _index_path(inbox_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(key): dict(value)
        for key, value in payload.items()
        if isinstance(value, dict) and value.get("url")
    } if isinstance(payload, dict) else {}


def _save(inbox_dir: Path, payload: dict[str, dict[str, Any]]) -> None:
    root = _root(inbox_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = _index_path(inbox_dir)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)


def validate_logo_url(raw: str) -> str:
    value = str(raw or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise LogoOverrideError("logo URL must be a public http(s) URL")
    host = parsed.hostname.casefold()
    if host in _BLOCKED_HOSTS or host.endswith((".local", ".internal", ".localhost")):
        raise LogoOverrideError("logo URL host is not public")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return value
    if not address.is_global:
        raise LogoOverrideError("logo URL host is not public")
    return value


def _image_type(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif", "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp", "image/webp"
    raise LogoOverrideError("logo must be PNG, JPEG, GIF, or WebP")


def set_logo_url(inbox_dir: Path, entity_id: str, url: str) -> dict[str, Any]:
    entity_id = safe_entity_id(entity_id)
    url = validate_logo_url(url)
    payload = load_logo_overrides(inbox_dir)
    row = {
        "url": url,
        "kind": "url",
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    payload[entity_id] = row
    _save(inbox_dir, payload)
    return row


def set_logo_upload(inbox_dir: Path, entity_id: str, data: bytes) -> dict[str, Any]:
    entity_id = safe_entity_id(entity_id)
    if not data:
        raise LogoOverrideError("choose an image to upload")
    if len(data) > MAX_LOGO_BYTES:
        raise LogoOverrideError("logo image must be 2 MB or smaller")
    extension, media_type = _image_type(data)
    digest = hashlib.sha256(data).hexdigest()[:16]
    entity_dir = _root(inbox_dir) / entity_id
    entity_dir.mkdir(parents=True, exist_ok=True)
    filename = f"logo-{digest}{extension}"
    target = entity_dir / filename
    target.write_bytes(data)
    payload = load_logo_overrides(inbox_dir)
    row = {
        "url": f"/entity-logos/{entity_id}/{filename}",
        "kind": "upload",
        "filename": filename,
        "media_type": media_type,
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    payload[entity_id] = row
    _save(inbox_dir, payload)
    return row


def clear_logo_override(inbox_dir: Path, entity_id: str) -> None:
    entity_id = safe_entity_id(entity_id)
    payload = load_logo_overrides(inbox_dir)
    payload.pop(entity_id, None)
    _save(inbox_dir, payload)
    entity_dir = _root(inbox_dir) / entity_id
    if entity_dir.exists():
        shutil.rmtree(entity_dir)


def logo_override_url(inbox_dir: Path, entity_id: str) -> str:
    try:
        entity_id = safe_entity_id(entity_id)
    except LogoOverrideError:
        return ""
    return str((load_logo_overrides(inbox_dir).get(entity_id) or {}).get("url") or "")


def logo_file(inbox_dir: Path, entity_id: str, filename: str) -> tuple[Path, str]:
    entity_id = safe_entity_id(entity_id)
    if not re.fullmatch(r"logo-[a-f0-9]{16}\.(?:png|jpg|gif|webp)", str(filename or "")):
        raise LogoOverrideError("invalid logo filename")
    entity_dir = (_root(inbox_dir) / entity_id).resolve()
    target = (entity_dir / filename).resolve()
    if target.parent != entity_dir or not target.is_file():
        raise LogoOverrideError("logo not found")
    row = load_logo_overrides(inbox_dir).get(entity_id) or {}
    if row.get("filename") != filename:
        raise LogoOverrideError("logo not found")
    return target, str(row.get("media_type") or "application/octet-stream")
