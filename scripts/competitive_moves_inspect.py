"""Dump Competitive Moves derived from the current Radar cache.

Does not fetch providers. Run scripts/emerging_radar_refresh.py first.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_config import resolve_inbox_dir
from app.services.competitive_moves.board import compose_moves_board


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    inbox = args.inbox_dir or resolve_inbox_dir(ROOT)
    board = compose_moves_board(inbox_dir=inbox)
    payload = {
        "generated_at": board.generated_at,
        "freshness_label": board.freshness_label,
        "stats": board.stats,
        "moves": [row.as_dict() for row in board.moves[:40]],
        "patterns": [row.as_dict() for row in board.patterns],
        "momentum": [row.as_dict() for row in board.momentum[:12]],
        "featured_timeline": board.featured_timeline,
    }
    out = args.out or (inbox / "operations" / "radar" / "moves_inspection.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({board.stats.get('moves', 0)} moves, {board.stats.get('patterns', 0)} patterns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
