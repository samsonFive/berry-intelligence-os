"""Run one full newsroom-intake cycle: Industry Pulse discovery+
qualification, then the pulse-to-Publication intake bridge.

Writes only inbox/evidence/*.json Publication drafts (status=draft,
evidence_role=publication_artifact) and an inbox/operations/
industry_pulse_runs/*.json run record. Never writes trusted Evidence,
never onboards a Source, never bypasses Publication Review. Lock-
protected: refuses immediately if another newsroom-intake cycle is
already active rather than running two at once.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Same single activation switch app/main.py's routes read -- ENABLE_PERPLEXITY_PULSE
# set in the deployment environment is the one place this gets turned on,
# consistently for both the manual "Run newsroom cycle" button and this
# scheduled CLI. --enable-perplexity below is an explicit CLI override for
# ad hoc use (e.g. a one-off manual acceptance run) on top of that default.
PERPLEXITY_PULSE_ENABLED = os.environ.get("ENABLE_PERPLEXITY_PULSE", "").lower() in {"1", "true", "yes"}

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.industry_pulse.credentials import has_perplexity
from app.services.industry_pulse.newsroom_cycle import run_newsroom_cycle
from app.services.industry_pulse.perplexity_provider import PerplexitySearchProvider
from app.services.industry_pulse.providers import GoogleNewsRssProvider
from app.services.media_discovery import list_discovered_items


def _load_drafts(inbox_dir: Path) -> list[dict]:
    folder = inbox_dir / "evidence"
    if not folder.is_dir():
        return []
    drafts = []
    for path in folder.glob("*.json"):
        try:
            drafts.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return drafts


def _ops_compatible(result: dict) -> dict:
    """Layer top-level fields app.services.pipeline_health.build_pipeline_health()
    already knows how to read (outcome, drafts_created, counts, failure_count)
    onto the full detailed result, so run_due_pipelines.py's generic --json
    stdout capture makes this pipeline observable on /collection-ops without
    a special case there -- the full nested discovery/intake detail stays
    available underneath for anyone reading the raw run record."""

    out = dict(result)
    if result.get("refused"):
        out["outcome"] = "FAILED"
        out["failure_count"] = 1
        out["drafts_created"] = 0
        out["counts"] = {}
        return out
    intake = result.get("intake") or {}
    discovery = result.get("discovery") or {}
    errors = int(intake.get("errors") or 0) + int(discovery.get("query_failures") or 0)
    out["outcome"] = "FAILED" if errors and not intake.get("drafts_created") else ("PARTIAL" if errors else "SUCCESS")
    out["failure_count"] = errors
    out["drafts_created"] = intake.get("drafts_created") or 0
    out["counts"] = {
        "considered": intake.get("considered"),
        "already_represented": intake.get("already_represented"),
        "acquisition_attempted": intake.get("acquisition_attempted"),
        "acquisition_succeeded": intake.get("acquisition_succeeded"),
        "acquisition_failed": intake.get("acquisition_failed"),
        "publication_drafts_created": intake.get("drafts_created"),
        "union_unique": discovery.get("union_unique_count"),
    }
    return out


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the run result as JSON")
    parser.add_argument("--no-persist", action="store_true", help="Dry run: no drafts written, no run record")
    parser.add_argument("--max-acquisitions", type=int, default=20, help="Bounded body-fetch attempts per run")
    parser.add_argument(
        "--enable-perplexity",
        action="store_true",
        help="Run the optional Perplexity semantic catch-net alongside Google News RSS. Falls back to Google-only if PERPLEXITY_API_KEY is unset.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir = resolve_data_dir(ROOT)
    inbox_dir = resolve_inbox_dir(ROOT)
    repos = get_repositories(data_dir, SCHEMAS_DIR)

    sources = repos.sources.list()
    published = [row for row in repos.evidence.list() if row.get("status") == "published"]
    all_drafts = _load_drafts(inbox_dir)
    drafts = [row for row in all_drafts if row.get("evidence_role") == "publication_artifact"]
    entities = repos.entities.list()
    varieties = [row for row in entities if row.get("entity_type") == "variety"]
    publications = list(drafts)
    discovered_items = list_discovered_items(inbox_dir)

    want_perplexity = args.enable_perplexity or PERPLEXITY_PULSE_ENABLED
    catch_net = PerplexitySearchProvider() if (want_perplexity and has_perplexity()) else None
    if want_perplexity and catch_net is None:
        print("Perplexity requested but PERPLEXITY_API_KEY is not set; running Google-only.", file=sys.stderr)

    result = run_newsroom_cycle(
        sources=sources,
        published_evidence=published,
        drafts=drafts,
        entities=entities,
        varieties=varieties,
        publications=publications,
        discovered_items=discovered_items,
        inbox_dir=inbox_dir,
        data_dir=data_dir,
        provider=GoogleNewsRssProvider(),
        catch_net_provider=catch_net,
        max_acquisitions=args.max_acquisitions,
        now=datetime.now(timezone.utc),
        persist=not args.no_persist,
    )

    if args.json:
        print(json.dumps(_ops_compatible(result), indent=2, ensure_ascii=False))
        return 0

    if result["refused"]:
        print(f"refused: {result['refusal_reason']}")
        return 1

    d = result["discovery"]
    i = result["intake"]
    print(f"run_id={result['run_id']}")
    print(f"provider={d['provider']} catch_net_provider={d['catch_net_provider']}")
    for name, stats in d["provider_telemetry"].items():
        print(f"  {name}: queries={stats['queries_issued']} hits={stats['hits_returned']} errors={stats['errors']} unique_qualifying={stats['unique_qualifying']}")
    print(f"union_unique={d['union_unique_count']} overlap_qualifying={d['overlap_qualifying_count']}")
    for window in ("24h", "3d", "7d"):
        w = d["windows"][window]
        print(f"{window}: discovered={w['discovered']} qualifying={w['qualifying']} novel={w['novel']}")
    print(
        f"intake: considered={i['considered']} already_represented={i['already_represented']} "
        f"acquisition_attempted={i['acquisition_attempted']} acquisition_succeeded={i['acquisition_succeeded']} "
        f"acquisition_failed={i['acquisition_failed']} drafts_created={i['drafts_created']} errors={i['errors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
