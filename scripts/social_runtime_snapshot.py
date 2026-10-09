"""Local private snapshot preparation only; does not deploy or activate collection."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.social_intelligence.runtime_snapshot import export_snapshot, verify_snapshot
if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("destination", type=Path)
    p.add_argument("--inbox", type=Path)
    args = p.parse_args()
    result = export_snapshot(args.inbox, args.destination) if args.inbox else verify_snapshot(args.destination)
    print(json.dumps({k: result[k] for k in ["kind", "observations", "media_objects", "saved_profiles", "collection_enabled"]}))
