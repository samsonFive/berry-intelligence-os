"""Shared runtime lease used by every collector writing the same inbox."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.services.collection_runner import CollectionRunLock


def pipeline_lock(inbox_dir: Path, pipeline: str) -> CollectionRunLock:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return CollectionRunLock(
        inbox_dir / "operations" / "collection.lock",
        run_id=f"{pipeline}-{stamp}",
    )
