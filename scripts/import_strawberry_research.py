"""Build or stage a hash-bound private strawberry research package. Dry-run by default."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.strawberry_research_import import build_packet, import_packet


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path, help="packet.json to import, or output directory when --build-from is used")
    parser.add_argument("--build-from", type=Path, help="Authored combined-research.json; builds only, never imports")
    parser.add_argument("--capture-root", type=Path, help="Explicit allowed root containing declared research captures")
    parser.add_argument("--batch-id")
    parser.add_argument("--berry-id", help="Explicit crop entity ID for the research package")
    parser.add_argument("--captured-at", help="ISO date or datetime; preserve research capture date")
    parser.add_argument("--extract-bodies", action="store_true", help="Extract only retained local selectable text; no network")
    parser.add_argument("--publication-source-ids", type=Path, help="Explicit JSON list of substantive cited source IDs allowed into pending publication review")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data", help="Runtime data root; active source store receives private intake on --apply")
    parser.add_argument("--inbox-dir", type=Path, help="Explicit private inbox destination")
    parser.add_argument("--apply", action="store_true", help="Stage pending private records; never approve")
    args = parser.parse_args(argv)
    try:
        if args.build_from:
            if args.apply or not args.capture_root or not args.batch_id or not args.captured_at or not args.berry_id:
                parser.error("Build requires --capture-root, --batch-id, --captured-at and --berry-id; --apply is import-only")
            result = build_packet(args.build_from, args.packet, capture_root=args.capture_root,
                                  batch_id=args.batch_id, captured_at=args.captured_at, berry_id=args.berry_id,
                                  publication_source_ids=json.loads(args.publication_source_ids.read_text(encoding="utf-8")) if args.publication_source_ids else (),
                                  extract_bodies=args.extract_bodies)
            result = {key: result[key] for key in ("version", "batch_id", "packet_sha256", "counts", "trust_effect")}
        else:
            if not args.inbox_dir:
                parser.error("Import requires --inbox-dir")
            result = import_packet(args.packet, data_dir=args.data_dir, inbox_dir=args.inbox_dir, apply=args.apply)
            result.pop("source_bindings", None)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"Research intake failed: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
