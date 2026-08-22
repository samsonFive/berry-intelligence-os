from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from app.services.review_capacity import build_review_capacity_report


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def _source(source_id: str, *, adapter: str = "news_search_rss", priority: str = "medium") -> dict:
    return {
        "id": source_id,
        "label": source_id,
        "enabled": True,
        "monitoring_priority": priority,
        "discovery": {"adapter": adapter},
    }


def _draft(
    draft_id: str,
    *,
    source_id: str = "source-a",
    tier: str = "adjacent",
    title: str | None = None,
    first_seen: str = "2026-08-20T12:00:00+00:00",
    source_url: str | None = None,
) -> dict:
    return {
        "id": draft_id,
        "evidence_role": "publication_artifact",
        "status": "draft",
        "review_state": "in_review",
        "title": title or draft_id,
        "source_id": source_id,
        "source_url": source_url or f"https://example.test/{draft_id}",
        "published_date": "2026-08-19",
        "captured_date": "2026-08-20",
        "discovery_provenance": {"first_seen_at": first_seen},
        "relevance_tier": tier,
        "berry_ids": ["berry-blueberry"],
        "geography_ids": ["geo-us"],
        "media_format": "web_article",
        "article": {"paragraphs": ["body"]},
        "entity_ids": [],
        "priority": {},
    }


def _report(**overrides) -> dict:
    values = {
        "drafts": [],
        "sources": [_source("source-a")],
        "entities": [],
        "trusted": [],
        "run_records": [],
        "analyst_state": {},
        "now": NOW,
    }
    values.update(overrides)
    return build_review_capacity_report(**values)


def test_unreviewed_backlog_never_becomes_fabricated_yield() -> None:
    report = _report(drafts=[_draft(f"draft-{index}") for index in range(20)])

    observed = report["observed_review_events"]
    economics = report["derived_operational_metrics"]["source_economics"][0]
    assert observed["published"] == observed["rejected"] == 0
    assert observed["publish_rate"] is None
    assert observed["reject_rate"] is None
    assert observed["rates_measurable"] is False
    assert economics["pending_backlog"] == 20
    assert economics["publish_rate"] is None
    assert economics["yield_measurable"] is False


def test_only_real_recorded_actions_are_observed() -> None:
    rejected = _draft("rejected")
    rejected["review_state"] = "rejected"
    rejected["reviewed_at"] = "2026-08-21T10:00:00+00:00"
    published = _draft("published")
    published.update({"status": "published", "reviewed_at": "2026-08-21T11:00:00+00:00"})
    state = {
        "pending": {"pending-1": {"state": "dismissed", "updated_at": "2026-08-21T12:00:00"}},
        "testing": {
            "test-pass": {"state": "pass", "updated_at": "2026-08-21T12:00:00"},
            "test-fail": {"state": "fail", "updated_at": "2026-08-21T12:00:00"},
            "test-defer": {"state": "defer", "updated_at": "2026-08-21T12:00:00"},
        },
    }
    observed = _report(drafts=[rejected], trusted=[published], analyst_state=state)["observed_review_events"]
    assert observed["published"] == 1
    assert observed["rejected"] == 1
    assert observed["dismissed_from_triage"] == 1
    assert observed["pass"] == 1 and observed["fail"] == 1 and observed["deferred"] == 1
    assert observed["rates_measurable"] is False


def test_operational_metrics_cover_age_arrivals_duplicates_and_load() -> None:
    drafts = [
        _draft("one", title="Same headline", first_seen="2026-06-01T00:00:00+00:00"),
        _draft("two", title="Same headline", source_url="https://example.test/one"),
    ]
    for row in drafts:
        row["published_date"] = "2026-08-19"
    runs = [{
        "pipeline": "unified_collection",
        "completed_at": "2026-08-20T12:00:00+00:00",
        "counts": {"publication_drafts_created": 2, "publication_awaiting_review": 1},
    }, {
        "completed_at": "2026-08-20T12:01:00+00:00",
        "counts": {"publication_drafts_created": 2, "publication_awaiting_review": 1},
    }]
    derived = _report(drafts=drafts, run_records=runs)["derived_operational_metrics"]
    assert derived["backlog_total"] == 2
    assert derived["oldest_open_item"]["id"] == "one"
    assert derived["new_since_last_run"] == 2
    assert derived["arrival"]["mean_drafts_per_run"] == 2
    assert derived["arrival"]["runs_observed"] == 1
    assert derived["duplicate_reprint"]["excess_items"] == 1
    assert derived["source_economics"][0]["pending_backlog"] == 2


def test_simulation_is_deterministic_read_only_and_preserves_protected_unique_items() -> None:
    sources = [
        _source("government", adapter="government_rss"),
        _source("search-a"),
        _source("search-b"),
        _source("search-c"),
    ]
    drafts = [_draft("protected", source_id="government", tier="direct")]
    drafts.extend(_draft(f"adjacent-{index:02}", source_id="search-a", tier="adjacent") for index in range(13))
    before = deepcopy(drafts)
    report = _report(drafts=drafts, sources=sources)
    simulation = report["simulated_policy_effect"]
    assert simulation["automatic_throttling_enabled"] is False
    assert simulation["would_defer"] == 3
    assert simulation["protected_items_surface"] >= 1
    assert simulation["direct_or_uncertain_unique_events_lost"] == 0
    assert report["policy"]["automatic_throttling_enabled"] is False
    assert drafts == before


def test_item_audit_labels_simulated_actions_without_mutation() -> None:
    drafts = [_draft(f"adjacent-{index:02}") for index in range(12)]
    report = _report(
        drafts=drafts,
        sources=[_source("source-a"), _source("source-b"), _source("source-c")],
        include_items=True,
    )
    actions = [row["simulated_action"] for row in report["simulated_policy_effect"]["items"]]
    assert actions.count("defer_adjacent_source_overflow") == 2
    assert actions.count("surface") == 10
