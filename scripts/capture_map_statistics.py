"""Capture bounded official Map references for review; never overwrite data.

Run manually: python scripts/capture_map_statistics.py
Keeps original Eurostat payload and derived references in a new ignored capture.
An operator reviews the capture/diff before updating the public reference file.
Opening Map/Snapshot never runs this script. No paid research or trusted writes.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.market_reality.eurostat_apro import fetch_apro_cpsh1
from app.services.market_statistics_reference import GEOS, eurostat_groups


def capture(*, output_dir, fetch=fetch_apro_cpsh1, now=None):
    stamp = now or datetime.now(timezone.utc)
    payload = fetch(crops=["S0000"], geos=list(GEOS), since_year=stamp.year - 3)
    groups = eurostat_groups(payload, captured_at=stamp.isoformat(timespec="seconds"))
    envelope = {"version": 1, "state": "reference_capture_for_review", "captured_at": stamp.isoformat(timespec="seconds"),
                "scope": {"crops": ["S0000"], "geos": list(GEOS), "since_year": stamp.year - 3},
                "payload": payload, "groups": groups}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / (stamp.strftime("eurostat-%Y%m%dT%H%M%SZ-") + uuid4().hex[:12] + ".json")
    with path.open("x", encoding="utf-8") as stream:
        json.dump(envelope, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return path, groups


if __name__ == "__main__":
    path, groups = capture(output_dir=ROOT / "inbox" / "market_statistics_captures")
    print(f"Saved {len(groups)} country references for review: {path}")
    print("Existing public references and reviewed intelligence are unchanged.")
