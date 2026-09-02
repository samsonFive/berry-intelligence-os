"""Bounded Eurostat apro_cpsh1 ingestion (Market Reality Data Layer V1).

Fetches EU strawberry ("S0000") and other-berry ("F3000") production,
acreage, and yield for a small, explicit set of countries with existing
geography entities, and writes market_observation records directly to
data/market_observations/ (trusted structured data, not a review-queue
draft -- see docs/v2/MARKET-REALITY-DATA-LAYER-V1.md for why).

Bounded by construction: crops/geos are a fixed, small, explicit list --
never "all crops, all countries." Re-running does not overwrite prior
captures (MarketObservationRepository.create() rejects a duplicate id,
and id includes captured_at) -- it adds a new capture, so a genuine
Eurostat revision is preserved alongside the earlier value rather than
silently replacing it.

Usage:
    python scripts/ingest_market_reality_eurostat.py --json
    python scripts/ingest_market_reality_eurostat.py --dry-run --json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.base import DuplicateRecord
from app.runtime_config import resolve_data_dir
from app.services.market_reality.eurostat_apro import build_observations, decode_jsonstat, fetch_apro_cpsh1

CROPS = ["S0000", "F3000"]
GEOS = ["ES", "DE", "NL", "PT", "EU27_2020"]
YEARS_OF_HISTORY = 10


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)

    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    since_year = datetime.now(timezone.utc).year - YEARS_OF_HISTORY
    payload = fetch_apro_cpsh1(crops=CROPS, geos=GEOS, since_year=since_year)
    rows = decode_jsonstat(payload)
    observations = build_observations(rows, captured_at=captured_at)

    created = 0
    skipped_duplicate = 0
    if not args.dry_run:
        repo = get_repositories(data_dir).market_observations
        for obs in observations:
            try:
                repo.create(obs)
                created += 1
            except DuplicateRecord:
                skipped_duplicate += 1

    report = {
        "state": "dry_run" if args.dry_run else "ok",
        "source": "eurostat",
        "source_dataset": "apro_cpsh1",
        "crops": CROPS,
        "geos": GEOS,
        "since_year": since_year,
        "rows_decoded": len(rows),
        "observations_built": len(observations),
        "observations_created": created,
        "observations_skipped_duplicate": skipped_duplicate,
        "captured_at": captured_at,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(
            f"eurostat apro_cpsh1: rows={report['rows_decoded']} "
            f"observations={report['observations_built']} "
            f"created={report['observations_created']} "
            f"skipped_duplicate={report['observations_skipped_duplicate']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
