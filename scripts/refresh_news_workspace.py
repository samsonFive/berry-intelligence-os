"""Refresh the actual News cache through the existing bounded keyless collector."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    from app import main as app_main
    from app.news_workspace_routes import run_refresh, refresh_state

    run_refresh(app_main.INBOX_DIR, app_main._feed_first_world(), app_main.load_sources())
    state = refresh_state(app_main.INBOX_DIR)
    errors = int(state.get("error_count") or 0)
    failed = state.get("status") == "failed"
    # Scheduler health must retain partial-source failures rather than mark a
    # useful but incomplete refresh as a full success.
    payload = {
        "state": "error" if failed else state.get("status"),
        "queried": errors + (0 if failed else 1),
        "failed": [{"reason": "News source retrieval failed"}] * errors,
        "counts": {"items_new": int(state.get("story_count") or 0), "publication_drafts_created": 0},
    }
    print(json.dumps(payload))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
