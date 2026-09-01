"""Source Coverage Gap Closure V1.

Converts the highest-value SOURCE_UNKNOWN / SOURCE_KNOWN_NOT_COLLECTED
recall-benchmark misses into either (a) a real, modern-adapter Source
(never the legacy type:rss/keyword-without-discovery path, which
auto-publishes unreviewed Evidence), (b) a structural-collector
recognition fix in Coverage Assurance's reconciliation for hosts
already covered by a dedicated pipeline (patent_monitor, cpvo_registry)
that never registers as a generic Source, or (c) an explicit,
documented rejection/deferral in the Source Universe registry. No
Source is onboarded indiscriminately; a handful are deliberately
rejected (explicit robots.txt AI-crawler exclusions, respected) or
deferred (structured-registry work out of this mission's bounded
scope, or insufficient demonstrated value).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.coverage_assurance.reconcile import STRUCTURAL_COLLECTORS, collection_status_for_host
from app.services.coverage_assurance.statuses import COLLECTED
from app.services.coverage_assurance.yield_status import YIELD_NA, YIELD_UNKNOWN, TECHNICAL_MANUAL, yield_for_source
from app.services.media_discovery import ADAPTER_TYPES

REPO = Path(__file__).resolve().parents[1]
NEW_SOURCE_IDS = (
    "source-news-search-italian-berry",
    "source-20260901-blueberrybreeding-newsroom",
)


def _sources() -> list[dict]:
    return json.loads((REPO / "data" / "configuration" / "sources.json").read_text(encoding="utf-8"))


def _universe_entries() -> list[dict]:
    payload = json.loads((REPO / "data" / "configuration" / "source_universe.json").read_text(encoding="utf-8"))
    return payload["entries"]


# --- 1/2/3. Italian Berry / direct-feed / search-based Sources are well-formed ---


def test_all_new_sources_use_a_registered_modern_adapter():
    sources_by_id = {row["id"]: row for row in _sources()}
    for source_id in NEW_SOURCE_IDS:
        assert source_id in sources_by_id, f"{source_id} missing from sources.json"
        source = sources_by_id[source_id]
        discovery = source.get("discovery")
        assert discovery, f"{source_id} has no discovery block -- would fall through to the legacy auto-publish path"
        adapter = discovery.get("adapter")
        assert adapter in ADAPTER_TYPES, f"{source_id} uses unregistered adapter {adapter!r}"
        assert discovery.get("feed_url"), f"{source_id} discovery block has no feed_url"


def test_italian_berry_source_uses_search_based_adapter_not_bespoke_scraper():
    sources_by_id = {row["id"]: row for row in _sources()}
    source = sources_by_id["source-news-search-italian-berry"]
    assert source["discovery"]["adapter"] == "news_search_rss"
    assert "site:italianberry.it" in source["discovery"]["feed_url"]
    assert "italianberry.it" in source["url"]


def test_produce_report_already_has_a_real_eligible_source_no_duplicate_added():
    """Investigation finding: producereport.com already had a real,
    eligible, working article_rss Source (created 2026-08-06, feed
    verified 2026-08-17) before this mission started -- it was never
    actually a missing-Source gap. A duplicate Source was drafted for
    it during this mission and then removed once this was discovered;
    this test guards against silently re-adding one."""
    sources = _sources()
    matches = [row for row in sources if row.get("url", "").rstrip("/") == "https://www.producereport.com" or "producereport.com" in row.get("discovery", {}).get("feed_url", "")]
    assert len(matches) == 1, f"expected exactly one producereport.com Source, found {len(matches)}"
    source = matches[0]
    from app.services.source_lifecycle import is_collection_eligible

    assert is_collection_eligible(source), "the existing producereport.com Source should already be collection-eligible"
    assert source["id"] not in NEW_SOURCE_IDS


def test_blueberrybreeding_source_points_at_leaf_sitemap_not_the_index():
    sources_by_id = {row["id"]: row for row in _sources()}
    source = sources_by_id["source-20260901-blueberrybreeding-newsroom"]
    assert source["discovery"]["adapter"] == "sitemap_xml"
    feed_url = source["discovery"]["feed_url"]
    assert feed_url.endswith("blog-posts-sitemap.xml")
    assert "sitemap_index" not in feed_url and "sitemap-index" not in feed_url


# --- 4. Structured registry path: patents.google.com / uspto / cpvo hosts --------


def test_structural_collector_hosts_are_recognized_collected():
    for host in STRUCTURAL_COLLECTORS:
        status, reason, matched_source = collection_status_for_host(
            host, universe_by_host={}, sources_by_host={}, collected_hosts=set(), blocked_domains=set(),
        )
        assert status == COLLECTED
        assert reason is not None and "not a generic Source" in reason
        assert matched_source is None


def test_structural_collector_status_does_not_apply_to_unrelated_hosts():
    status, _reason, _source = collection_status_for_host(
        "example.invalid", universe_by_host={}, sources_by_host={}, collected_hosts=set(), blocked_domains=set(),
    )
    assert status != COLLECTED


def test_structural_collector_yield_is_internally_consistent_not_contradictory():
    """A host marked COLLECTED via a structural pipeline must not also
    report yield NOT_APPLICABLE (which would mean 'collected' but
    'collection not applicable' -- a contradiction the original
    Coverage Assurance draft would have produced for these hosts)."""
    liveness = yield_for_source(
        {},
        host="patents.google.com",
        freshness=None,
        evidence=[],
        publications=[],
        discovered_items=[],
        variety_candidates=[],
        universe_row=None,
        today=date(2026, 9, 1),
        force_collected=True,
    )
    assert liveness["technical_health"] == TECHNICAL_MANUAL
    assert liveness["yield_state"] != YIELD_NA
    assert liveness["yield_state"] == YIELD_UNKNOWN


# --- 5. Blocked/account-gated Sources remain honest, never routed around --------


def test_mountainblue_and_lens_org_are_intentionally_excluded_with_robots_reason():
    entries_by_host = {row["hostname"]: row for row in _universe_entries()}
    for host in ("mountainblue.com.au", "lens.org"):
        entry = entries_by_host[host]
        assert entry["intentionally_excluded"] is True
        assert "ClaudeBot" in entry["notes"] or "Claude" in entry["exclusion_reason"]
        assert entry["provenance"]["kind"] == "robots_txt_exclusion"

    sources_by_host_hint = " ".join(json.dumps(row) for row in _sources())
    assert "mountainblue.com.au" not in sources_by_host_hint
    assert "lens.org" not in sources_by_host_hint


def test_deferred_hosts_are_not_excluded_and_not_silently_onboarded():
    """Deferred (not rejected) hosts must be visible in the universe
    registry with a clear reason, and must NOT have a Source record --
    a deferral is not a quiet onboarding."""
    entries_by_host = {row["hostname"]: row for row in _universe_entries()}
    sources_json_text = json.dumps(_sources())
    for host in ("active.inspection.gc.ca", "fallcreekcatalogs.com", "ozblu.com", "investor.hortifrut.com"):
        entry = entries_by_host[host]
        assert entry["intentionally_excluded"] is False
        assert entry["notes"]
        assert f'"{host}"' not in sources_json_text and f"//{host}" not in sources_json_text


# --- 6. Duplicate Source avoidance -----------------------------------------------


def test_no_duplicate_source_ids():
    sources = _sources()
    ids = [row["id"] for row in sources]
    assert len(ids) == len(set(ids)), "duplicate Source id"


def test_new_sources_do_not_duplicate_any_existing_publisher_host():
    """Scoped to this mission's own additions: do the 3 new Sources
    collide with any PRE-EXISTING Source's host? (A pre-existing
    hortifrut.com host collision between two other, unrelated Sources
    was found while writing this test -- real, but out of this
    mission's bounded scope; not fixed here, noted in the completion
    report / technical debt register instead.)"""
    from app.services.recall_audit.classify import publisher_hosts

    sources = _sources()
    new_by_id = {row["id"]: row for row in sources if row["id"] in NEW_SOURCE_IDS}
    existing = [row for row in sources if row["id"] not in NEW_SOURCE_IDS]
    existing_hosts: dict[str, str] = {}
    for row in existing:
        for host in publisher_hosts(row):
            existing_hosts.setdefault(host, row["id"])
    for source_id, row in new_by_id.items():
        for host in publisher_hosts(row):
            assert host not in existing_hosts, (
                f"{source_id}'s host {host} already claimed by existing Source {existing_hosts[host]}"
            )


# --- 9. No trust promotion / no trust mutation -----------------------------------


def test_new_sources_never_use_the_legacy_auto_publish_type_without_discovery():
    """The legacy type:rss/keyword-without-discovery path
    (app.main.check_source/build_auto_evidence) auto-publishes
    Evidence with status=published and no human review step. Every new
    Source here has a discovery block, so it always goes through the
    modern discover -> screen -> acquire -> draft pipeline instead."""
    sources_by_id = {row["id"]: row for row in _sources()}
    for source_id in NEW_SOURCE_IDS:
        source = sources_by_id[source_id]
        assert source.get("discovery"), f"{source_id} would fall through to the auto-publish legacy path"


# --- 11. Benchmark classification update proof (unit-level, no LLM) -------------


def test_benchmark_scoring_still_uses_the_single_canonical_taxonomy():
    from app.services.coverage_assurance.benchmarks import score_all_benchmarks
    from app.services.recall_audit.classify import score_benchmark as canonical_score_benchmark

    benchmark = {
        "id": "bm-unit",
        "results": [
            {"url": "https://patents.google.com/patent/US1234", "domain": "patents.google.com", "qualification": "qualifying"},
        ],
    }
    scored = score_all_benchmarks([benchmark], sources=[], published_evidence=[], varieties=[], candidates=[])[0]
    canonical = canonical_score_benchmark(benchmark, sources=[], published_evidence=[], varieties=[], candidates=[])
    assert scored["counts"] == canonical["counts"]
    # patents.google.com now resolves COLLECTED via the structural fix
    # threaded through classify.collection_status_for_host's own
    # collected_hosts set -- but that set is built from Source records
    # only, so this specific low-level check documents the boundary:
    # the STRUCTURAL_COLLECTORS recognition lives in Coverage
    # Assurance's reconciliation layer (item 4 above), not inside
    # recall_audit.classify itself, which stays untouched.
