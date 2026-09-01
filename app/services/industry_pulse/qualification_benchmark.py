"""Score the frozen qualification benchmark. Does not mutate trust."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import qualify_hit
from app.services.industry_pulse.qualify_legacy import qualify_hit_legacy

BENCHMARK_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "imports"
    / "industry-pulse-qualification-v1"
    / "qualification_benchmark.json"
)


def load_benchmark(path: Path | None = None) -> dict[str, Any]:
    target = path or BENCHMARK_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def _hit_from_entry(entry: dict[str, Any]) -> DiscoveryHit:
    return DiscoveryHit(
        title=str(entry.get("title") or ""),
        url=str(entry.get("url") or ""),
        source_domain=str(entry.get("source_domain") or ""),
        published_date=None,
        snippet=str(entry.get("snippet") or ""),
        query_id=f"benchmark:{entry.get('id')}",
        query_text="",
        geography=str(entry.get("geography") or "global"),
        berry=entry.get("berry"),
        topic="industry_pulse",
        provider=str(entry.get("provider") or "memory"),
        origin_publisher_url=entry.get("url"),
    )


def score_benchmark(path: Path | None = None) -> dict[str, Any]:
    payload = load_benchmark(path)
    entries = list(payload.get("entries") or [])
    before = {"total": len(entries), "qualifying": 0, "false_positives": 0, "false_negatives": 0}
    after = {"total": len(entries), "qualifying": 0, "false_positives": 0, "false_negatives": 0}
    losses: list[dict[str, Any]] = []
    residual_fp: list[str] = []
    before_fps: list[str] = []
    for entry in entries:
        expected = entry.get("expected") == "qualify"
        legacy = qualify_hit_legacy(deepcopy(_hit_from_entry(entry)))
        current = qualify_hit(deepcopy(_hit_from_entry(entry)))
        if legacy.qualifying:
            before["qualifying"] += 1
        if current.qualifying:
            after["qualifying"] += 1
        if legacy.qualifying and not expected:
            before["false_positives"] += 1
            before_fps.append(str(entry.get("id")))
        if not legacy.qualifying and expected:
            before["false_negatives"] += 1
        if current.qualifying and not expected:
            after["false_positives"] += 1
            residual_fp.append(str(entry.get("id")))
        if not current.qualifying and expected:
            after["false_negatives"] += 1
            losses.append(
                {
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "reason": current.qualify_reason,
                }
            )
    before_precision = (
        round((before["qualifying"] - before["false_positives"]) / before["qualifying"], 3)
        if before["qualifying"]
        else None
    )
    after_precision = (
        round((after["qualifying"] - after["false_positives"]) / after["qualifying"], 3)
        if after["qualifying"]
        else None
    )
    return {
        "id": payload.get("id"),
        "entry_count": len(entries),
        "before": {**before, "precision": before_precision},
        "after": {**after, "precision": after_precision},
        "recall_losses": losses,
        "residual_false_positives": residual_fp,
        "before_false_positive_ids": before_fps,
    }
