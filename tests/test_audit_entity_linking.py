from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_internal_audit_is_canonical_only_and_meets_sample_floor() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/audit_entity_linking.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)

    assert report["scope"] == "canonical trusted data only; inbox not read"
    assert report["reviewed_sample"]["companies"] >= 10
    assert report["reviewed_sample"]["varieties"] >= 20
    assert report["reviewed_sample"]["berries"] == [
        "berry-blackberry",
        "berry-blueberry",
        "berry-raspberry",
        "berry-strawberry",
    ]
    assert report["reviewed_sample"]["after"]["precision"] >= report["reviewed_sample"]["before"]["precision"]
    assert report["reviewed_sample"]["after"]["recall"] >= 0.95
