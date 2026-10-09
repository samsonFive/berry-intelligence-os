"""Inspect the selected collection route; never sends requests."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.social_intelligence.provider_routing import route
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("task", choices=["discovery", "detail"])
    parser.add_argument("--already-captured", action="store_true")
    args = parser.parse_args()
    print(json.dumps({**route(args.source, args.task, already_captured=args.already_captured), "collection_enabled": False, "execution": "Use the existing explicit provider runner after fresh free-access/budget checks"}))
