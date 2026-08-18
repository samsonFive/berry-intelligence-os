"""Prepare a bounded, secret-free demo runtime for remote interactive review.

Copies trusted published `data/` plus selected inbox drafts, discovered-media
records, and normalized transcripts. Never copies API keys, qualification
files, audio/video caches, or unrelated backlog.

Usage:
    python scripts/export_demo_runtime.py --output /path/to/demo-runtime
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import BASE_DIR, DATA_DIR, INBOX_DIR  # noqa: E402

SPECIMEN_DRAFT_IDS = (
    "ev-media-cfc3cc9f97414c09c483",  # Peru El Niño
    "ev-media-40026e5b188a12e695ed",  # Michigan Blueberry Legacy
    "ev-media-6b00e9da4ab8b0740ec7",  # Click to Cart
    "ev-media-5f3abbf5a900546806a4",  # Florida Perspective (backup)
)

SECRET_PATTERNS = (
    re.compile(r"PERPLEXITY_API_KEY\s*="),
    re.compile(r"Authorization:\s*Bearer\s+\S+", re.I),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bpplx-[A-Za-z0-9]{16,}\b"),
    re.compile(r"BEGIN (RSA |OPENSSH )?PRIVATE KEY"),
)

SKIP_DIR_NAMES = {
    "_media",
    "qualification",
    "qualifications",
    "operations",
    "__pycache__",
}
SKIP_SUFFIXES = {
    ".mp3",
    ".wav",
    ".m4a",
    ".mp4",
    ".webm",
    ".ogg",
    ".flac",
    ".aac",
    ".env",
    ".pem",
    ".key",
}


class ExportError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExportError(f"not a JSON object: {path}")
    return payload


def _secret_hits(text: str) -> list[str]:
    hits = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def _copy_json(source: Path, dest: Path) -> None:
    text = source.read_text(encoding="utf-8")
    hits = _secret_hits(text)
    if hits:
        raise ExportError(f"refusing to export secret-bearing file {source}: {hits}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def _should_skip(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def selected_draft_ids(inbox_dir: Path, *, include_all_pending: bool) -> list[str]:
    ids = list(SPECIMEN_DRAFT_IDS)
    evidence_dir = inbox_dir / "evidence"
    if include_all_pending and evidence_dir.is_dir():
        for path in sorted(evidence_dir.glob("*.json")):
            record = _load_json(path)
            record_id = record.get("id")
            if not isinstance(record_id, str):
                continue
            if record.get("evidence_role") == "publication_artifact" and record.get("status") != "rejected":
                if record_id not in ids:
                    ids.append(record_id)
    return ids


def collect_discovered_ids(drafts: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for draft in drafts:
        item_id = draft.get("discovered_item_id")
        if isinstance(item_id, str) and item_id and item_id not in ids:
            ids.append(item_id)
    return ids


def copy_trusted_data(source: Path, dest_data: Path) -> int:
    if not source.is_dir():
        raise ExportError(f"trusted data directory missing: {source}")
    if dest_data.exists():
        shutil.rmtree(dest_data)
    file_count = 0
    for path in source.rglob("*"):
        if path.is_dir() or _should_skip(path):
            continue
        relative = path.relative_to(source)
        target = dest_data / relative
        if path.suffix.lower() == ".json":
            _copy_json(path, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        file_count += 1
    return file_count


def export_demo_runtime(
    output: Path,
    *,
    include_all_pending: bool = True,
    data_dir: Path | None = None,
    inbox_dir: Path | None = None,
) -> dict[str, Any]:
    data_dir = Path(data_dir or DATA_DIR)
    inbox_dir = Path(inbox_dir or INBOX_DIR)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    dest_data = output / "data"
    dest_inbox = output / "inbox"
    if dest_inbox.exists():
        shutil.rmtree(dest_inbox)
    dest_inbox.mkdir(parents=True, exist_ok=True)

    wanted_ids = selected_draft_ids(inbox_dir, include_all_pending=include_all_pending)
    drafts: list[dict[str, Any]] = []
    missing_drafts: list[str] = []
    for draft_id in wanted_ids:
        path = inbox_dir / "evidence" / f"{draft_id}.json"
        if not path.is_file():
            missing_drafts.append(draft_id)
            continue
        record = _load_json(path)
        drafts.append(record)
        _copy_json(path, dest_inbox / "evidence" / path.name)

    discovered_ids = collect_discovered_ids(drafts)
    copied_discovered: list[str] = []
    missing_discovered: list[str] = []
    for item_id in discovered_ids:
        path = inbox_dir / "discovered_media" / f"{item_id}.json"
        if not path.is_file():
            missing_discovered.append(item_id)
            continue
        _copy_json(path, dest_inbox / "discovered_media" / path.name)
        copied_discovered.append(item_id)
        transcript = inbox_dir / "discovered_media" / "_normalized_transcripts" / f"{item_id}.json"
        if transcript.is_file():
            _copy_json(
                transcript,
                dest_inbox / "discovered_media" / "_normalized_transcripts" / transcript.name,
            )

    data_files = copy_trusted_data(data_dir, dest_data)
    (dest_inbox / "evidence").mkdir(parents=True, exist_ok=True)
    (dest_inbox / "discovered_media").mkdir(parents=True, exist_ok=True)

    manifest = {
        "kind": "berry-intelligence-os-demo-runtime",
        "source_repo": str(BASE_DIR),
        "draft_ids": [d["id"] for d in drafts],
        "missing_draft_ids": missing_drafts,
        "discovered_item_ids": copied_discovered,
        "missing_discovered_item_ids": missing_discovered,
        "trusted_data_files": data_files,
        "specimens": {
            "peru_el_nino": "ev-media-cfc3cc9f97414c09c483" in {d["id"] for d in drafts},
            "michigan_blueberry_legacy": "ev-media-40026e5b188a12e695ed" in {d["id"] for d in drafts},
            "click_to_cart": "ev-media-6b00e9da4ab8b0740ec7" in {d["id"] for d in drafts},
        },
        "excluded": [
            "inbox audio/video caches (_media/)",
            "qualification credentials and runs",
            "operations scratch",
            "API keys and Authorization headers",
            "unrelated discovered-media backlog",
        ],
    }
    (output / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="Destination runtime directory (not committed)")
    parser.add_argument(
        "--specimens-only",
        action="store_true",
        help="Export only the named demo specimens, not the rest of the pending publication queue",
    )
    args = parser.parse_args()
    manifest = export_demo_runtime(args.output, include_all_pending=not args.specimens_only)
    print(f"Wrote demo runtime to {args.output.resolve()}")
    print(f"Drafts: {len(manifest['draft_ids'])}  discovered: {len(manifest['discovered_item_ids'])}  data files: {manifest['trusted_data_files']}")
    if manifest["missing_draft_ids"]:
        print("Missing specimen drafts (safe to continue if this machine has no inbox):")
        for draft_id in manifest["missing_draft_ids"]:
            print(f"  - {draft_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
