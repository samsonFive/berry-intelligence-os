"""Background refresh for the Emerging Developments Radar cache.

Usage:
    python scripts/emerging_radar_refresh.py --json
    python scripts/emerging_radar_refresh.py --json --inbox-dir PATH

Never writes Evidence. Without EXA_API_KEY the run still executes Google
+ specialist RSS and succeeds. Live CatchAll submit is never started.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_config import resolve_inbox_dir
from app.services.pipeline_lock import pipeline_lock

ALLOWED_ENV = {
    "EXA_API_KEY",
    "PERPLEXITY_API_KEY",
    "ENABLE_PERPLEXITY_PULSE",
}


def _load_operator_env() -> None:
    """Presence-only. Never prints values."""
    candidates = [ROOT / "deploy" / ".env", ROOT.parent.parent / "deploy" / ".env"]
    parent = ROOT.parent
    if parent.name == ".worktrees":
        candidates.append(parent.parent / "deploy" / ".env")
    for path in candidates:
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.strip()
            if name not in ALLOWED_ENV or os.environ.get(name):
                continue
            os.environ[name] = value.strip().strip('"').strip("'")
        break


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    _load_operator_env()

    from app.composition import get_repositories
    from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
    from app.services.emerging_radar.run import run_radar_intelligence
    from app.services.industry_pulse.live_stack import radar_discovery_stack, week_background_hits
    from app.services.industry_pulse.credentials import has_exa, has_perplexity

    inbox = args.inbox_dir or resolve_inbox_dir(ROOT)
    data_dir = args.data_dir or DEFAULT_DATA_DIR
    repos = get_repositories(data_dir, SCHEMAS_DIR)
    entities = repos.entities.list()
    evidence = [row for row in repos.evidence.list() if row.get("status") == "published"]
    assessments = repos.assessments.list()
    sources = repos.sources.list() if hasattr(repos.sources, "list") else []
    perplexity_enabled = os.environ.get("ENABLE_PERPLEXITY_PULSE", "").lower() in {"1", "true", "yes"}
    providers, catch_net, specialist = radar_discovery_stack(perplexity_enabled=perplexity_enabled)
    with pipeline_lock(inbox, "emerging_radar"):
        edition = run_radar_intelligence(
            providers=providers,
            catch_net_provider=catch_net,
            specialist_provider=specialist,
            entities=entities,
            sources=sources,
            evidence=evidence,
            assessments=assessments,
            background_hits=week_background_hits(inbox_dir=inbox),
            market_repo=repos.market_observations,
            inbox_dir=inbox,
            persist=True,
        )
    payload = {
        "state": "ok",
        "developments": edition.stats.get("developments"),
        "qualifying": edition.stats.get("qualifying"),
        "raw_discovered": edition.stats.get("raw_discovered"),
        "latency_seconds": edition.latency_seconds,
        "generated_at": edition.generated_at,
        "exa_configured": has_exa(),
        "perplexity_configured": has_perplexity() and perplexity_enabled,
        "failures": len(edition.query_failures),
        "sections": [section["key"] for section in edition.sections],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"Radar refresh: {payload['developments']} developments "
            f"in {payload['latency_seconds']}s (exa={payload['exa_configured']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
