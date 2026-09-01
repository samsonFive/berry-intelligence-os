"""Independent recall benchmark store and scoring.

Benchmarks come from two places: private, analyst-run ad-hoc benchmarks
under inbox/coverage_assurance/benchmarks/, and committed, versioned
benchmark files under data/imports/*/benchmark.json (e.g. the output of
Independent Missed Intelligence Discovery + Recall Audit V1). Both are
coverage tests, not trusted Evidence -- loading never writes data/evidence
or Sources.

Scoring delegates entirely to app.services.recall_audit.classify, the
one taxonomy this codebase uses for miss classification -- this module
never reimplements that logic, only loads/persists/aggregates around it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.recall_audit.classify import MISS_CLASSES, score_benchmark as classify_score_benchmark

HIDDEN_REASONING_KEYS = (
    "reasoning",
    "hidden_reasoning",
    "provider_reasoning",
    "raw_model_output",
    "raw_model_outputs",
    "thinking",
    "chain_of_thought",
)


def benchmarks_dir(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / "coverage_assurance" / "benchmarks"


def _strip_hidden(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _strip_hidden(value) for key, value in payload.items() if key not in HIDDEN_REASONING_KEYS}
    if isinstance(payload, list):
        return [_strip_hidden(item) for item in payload]
    return payload


def _load_json_files(folder: Path) -> list[dict[str, Any]]:
    if not folder.is_dir():
        return []
    loaded: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        loaded.append(_strip_hidden(payload))
    return loaded


def load_benchmarks(inbox_dir: Path | None, *, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Private inbox benchmarks plus committed data/imports/*/benchmark.json
    files -- so a real audit's output (e.g. Independent Missed Intelligence
    Discovery + Recall Audit V1's benchmark.json) is picked up automatically
    once it lands, with no code change here."""
    loaded: list[dict[str, Any]] = []
    if inbox_dir is not None:
        loaded.extend(_load_json_files(benchmarks_dir(inbox_dir)))
    if data_dir is not None:
        imports_dir = Path(data_dir) / "imports"
        if imports_dir.is_dir():
            for benchmark_path in sorted(imports_dir.glob("*/benchmark.json")):
                try:
                    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(payload, dict):
                    loaded.append(_strip_hidden(payload))
    return loaded


def score_all_benchmarks(
    benchmarks: list[dict[str, Any]],
    *,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    varieties: list[dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    return [
        classify_score_benchmark(
            benchmark,
            sources=sources,
            published_evidence=published_evidence,
            varieties=varieties or [],
            candidates=candidates,
        )
        for benchmark in benchmarks
    ]


def miss_totals(scored: list[dict[str, Any]]) -> dict[str, int]:
    totals = {key: 0 for key in MISS_CLASSES}
    for benchmark in scored:
        for key in MISS_CLASSES:
            totals[key] += int((benchmark.get("counts") or {}).get(key) or 0)
    return totals
