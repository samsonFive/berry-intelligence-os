"""Print the body-free entity identity integrity report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.entity_identity import audit_entity_identity, load_identity_redirects
from app.services.variety_universe.candidates import load_variety_candidates

DATA = ROOT / "data"
INBOX = ROOT / "inbox"


def _load_folder(folder: Path) -> list[dict]:
    rows: list[dict] = []
    if not folder.is_dir():
        return rows
    for path in sorted(folder.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("id"):
            rows.append(payload)
    return rows


def main() -> None:
    report = audit_entity_identity(
        _load_folder(DATA / "entities"),
        relationships=_load_folder(DATA / "relationships"),
        candidates=load_variety_candidates(INBOX),
        redirects=load_identity_redirects(DATA),
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
