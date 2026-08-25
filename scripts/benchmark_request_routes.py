#!/usr/bin/env python3
"""Cold + warm route timing harness for performance hardening.

Reports only timings and counts — no body text. Uses the local trusted
data/ corpus with a temporary empty inbox so inbox volume does not skew
trusted-path measurements.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app import main as application


ROUTES = (
    ("/healthz", False),
    ("/login", False),
    ("/work-queue", True),
    ("/brief", True),
    ("/review-ops", True),
    ("/geographies", True),
    ("/landscapes/berries/blueberry", True),
    ("/entities/company", True),
    ("/search?q=planasa", True),
)


def _timed(client: TestClient, path: str) -> tuple[int, float]:
    started = perf_counter()
    response = client.get(path, follow_redirects=False)
    elapsed = perf_counter() - started
    return response.status_code, elapsed


def run(*, warm_runs: int, out: Path | None) -> dict:
    with TemporaryDirectory(prefix="bios-perf-inbox-") as raw:
        inbox = Path(raw)
        (inbox / "evidence").mkdir(parents=True)
        application.INBOX_DIR = inbox
        client = TestClient(application.app)
        cold: dict[str, dict[str, float | int]] = {}
        warm: dict[str, list[float]] = {}
        for path, _needs_auth in ROUTES:
            status, elapsed = _timed(client, path)
            cold[path] = {"status": status, "seconds": round(elapsed, 4)}
            warm[path] = []
        for _ in range(max(1, warm_runs)):
            for path, _needs_auth in ROUTES:
                _status, elapsed = _timed(client, path)
                warm[path].append(round(elapsed, 4))
        summary = {
            "cold": cold,
            "warm_runs": warm_runs,
            "warm": {
                path: {
                    "samples": samples,
                    "median_seconds": sorted(samples)[len(samples) // 2] if samples else None,
                    "min_seconds": min(samples) if samples else None,
                    "max_seconds": max(samples) if samples else None,
                }
                for path, samples in warm.items()
            },
            "evidence_count": len(application.published_evidence()),
            "entity_count": len(application.all_entities()),
        }
        text = json.dumps(summary, indent=2)
        print(text)
        if out:
            out.write_text(text + "\n", encoding="utf-8")
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warm-runs", type=int, default=5)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    run(warm_runs=args.warm_runs, out=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
