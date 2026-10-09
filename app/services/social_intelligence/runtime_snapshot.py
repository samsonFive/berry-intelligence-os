"""Explicit private social runtime snapshot. No network, secrets or destination overwrite."""
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from .profiles import saved_profiles


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_snapshot(inbox, destination):
    inbox, destination = Path(inbox).resolve(), Path(destination).resolve()
    source = inbox / "social" / "observations.sqlite3"
    if not source.is_file():
        raise ValueError("Social database missing")
    if destination == inbox or destination.is_relative_to(inbox) or inbox.is_relative_to(destination):
        raise ValueError("Snapshot must be outside source inbox")
    if destination.exists():
        raise ValueError("Destination must be new; existing runtime is never overwritten")
    profiles = saved_profiles(inbox)
    destination.mkdir(parents=True)
    target = destination / "inbox" / "social" / "observations.sqlite3"
    target.parent.mkdir(parents=True)
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Snapshot database integrity failure")
        rows = dst.execute("SELECT payload FROM observations").fetchall()
    copied = set()
    for (payload,) in rows:
        row = json.loads(payload)
        for media in row.get("media", []):
            ref = media.get("object_ref")
            if not ref:
                continue
            if not re.fullmatch(r"[a-f0-9]{64}", ref) or row["mode"] not in {"live", "imported", "manual", "fixture"}:
                raise ValueError("Invalid stored object reference")
            relative = Path("social") / "media" / row["mode"] / ref
            obj = inbox / relative
            if obj.is_symlink() or not obj.resolve().is_relative_to(inbox) or not obj.is_file() or digest(obj) != ref:
                raise ValueError("Missing or altered stored media; snapshot incomplete")
            out = destination / "inbox" / relative
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(obj.read_bytes())
            copied.add(str(relative))
    for profile in profiles:
        profile.pop("url", None)
    (destination / "inbox" / "watchlist_state.json").write_text(json.dumps({"watches": [], "social_profiles": profiles}, ensure_ascii=False), encoding="utf-8")
    files = {str(p.relative_to(destination)).replace("\\", "/"): digest(p) for p in destination.rglob("*") if p.is_file()}
    manifest = {"version": 1, "kind": "private-social-runtime", "observations": len(rows), "media_objects": len(copied), "saved_profiles": len(profiles), "files": files, "collection_enabled": False, "fixture_isolation": "Modes preserved; no conversion", "excluded": ["credentials", "raw trial receipts", "unrelated watches", "canonical data"]}
    (destination / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    verify_snapshot(destination)
    return manifest


def verify_snapshot(destination):
    destination = Path(destination).resolve()
    manifest = json.loads((destination / "MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("kind") != "private-social-runtime" or manifest.get("collection_enabled") is not False:
        raise ValueError("Unsupported snapshot")
    for relative, expected in manifest["files"].items():
        path = destination / relative
        if path.is_symlink() or not path.resolve().is_relative_to(destination) or not path.is_file() or digest(path) != expected:
            raise ValueError("Snapshot hash or path mismatch")
    with sqlite3.connect((destination / "inbox/social/observations.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Snapshot integrity failure")
    return manifest
