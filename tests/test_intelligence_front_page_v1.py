"""Intelligence Front Page V1.

Covers the mission's own test list: newest-first freshness, fresh
unreviewed Publication visibility, trusted Evidence visibility, correct
trust labels, published-vs-captured date honesty, Europe includes
descendants, a country excludes siblings, berry filters, what-changed-
since-yesterday, deduplication, empty/stale explanation, no GET mutation,
no trust promotion, no static leak, no article-body persistence
duplication, links into graph objects, and deterministic fallback.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.front_page import build_front_page
from app.services.stakeholder_ui import brief_handoff_query_string

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _draft(draft_id: str, *, captured: str, completeness_class: str | None = None, **extra) -> dict:
    record = {
        "id": draft_id,
        "record_type": "evidence",
        "status": "draft",
        "evidence_role": "publication_artifact",
        "title": f"Draft {draft_id}",
        "captured_date": captured,
        "source_name": "Italian Berry",
        "source_type": "news_search",
        "source_url": f"https://italianberry.it/{draft_id}",
        "berry_ids": ["berry-blueberry"],
        "publisher_description": "A short publisher-provided description, never the full article body.",
    }
    if completeness_class:
        record["source_completeness"] = {
            "version": "source-completeness-v1",
            "class": completeness_class,
            "failure_category": None,
            "retryable": False,
            "content_sha256": None,
            "operator_accepted_thin": False,
        }
    record.update(extra)
    return record


def _evidence(evidence_id: str, *, published: str | None, captured: str, **extra) -> dict:
    record = {
        "id": evidence_id,
        "status": "published",
        "title": f"Evidence {evidence_id}",
        "published_date": published,
        "captured_date": captured,
        "source_name": "Fresh Fruit Portal",
        "source_type": "trade_press",
        "source_url": f"https://freshfruitportal.com/{evidence_id}",
        "berry_ids": ["berry-blueberry"],
        "card": {"summary": "A short editorial summary."},
    }
    record.update(extra)
    return record


def _signal(signal_id: str, *, first_seen: str, evidence_ids: list[str] | None = None, **extra) -> dict:
    record = {
        "id": signal_id,
        "record_type": "signal",
        "title": f"Signal {signal_id}",
        "status": "proposed",
        "first_seen": first_seen,
        "berry_ids": ["berry-blueberry"],
        "evidence_ids": evidence_ids or [],
        "entity_ids": [],
        "observation": "A short analyst observation.",
    }
    record.update(extra)
    return record


def _assessment(assessment_id: str, *, created_at: str, evidence_ids: list[str] | None = None, **extra) -> dict:
    record = {
        "id": assessment_id,
        "record_type": "assessment",
        "title": f"Assessment {assessment_id}",
        "created_at": created_at,
        "market_ids": ["berry-blueberry"],
        "evidence_ids": evidence_ids or [],
        "entity_ids": [],
        "rationale": "A short analyst rationale.",
    }
    record.update(extra)
    return record


def _geography(gid: str, name: str) -> dict:
    return {"id": gid, "entity_type": "geography", "name": name, "berry_ids": [], "evidence_ids": []}


def _rel(subject: str, obj: str) -> dict:
    return {
        "id": f"rel-{subject}-part-of-{obj}",
        "predicate": "part_of",
        "subject_id": subject,
        "object_id": obj,
        "status": "active",
    }


def _base_kwargs(tmp_path: Path, **overrides) -> dict:
    kwargs = dict(
        published=[],
        drafts=[],
        signals=[],
        assessments=[],
        sources=[],
        entities=[],
        relationships=[],
        inbox_dir=tmp_path / "inbox",
        data_dir=tmp_path / "data",
        now=NOW,
    )
    kwargs.update(overrides)
    return kwargs


# 1. Newest-first freshness behavior.
def test_top_stories_ranks_newer_recency_band_above_older(tmp_path: Path) -> None:
    older = _evidence("ev-older", published="2026-08-20", captured="2026-08-20")
    newer = _evidence("ev-newer", published="2026-08-31", captured="2026-08-31")
    page = build_front_page(**_base_kwargs(tmp_path, published=[older, newer]))
    ids = [item["id"] for item in page["top_stories"]]
    assert ids.index("ev-newer") < ids.index("ev-older")


# 2. Fresh unreviewed Publication visible.
def test_fresh_unreviewed_publication_is_visible(tmp_path: Path) -> None:
    draft = _draft("ev-draft-fresh", captured="2026-08-31")
    page = build_front_page(**_base_kwargs(tmp_path, drafts=[draft]))
    assert page["trust_counts"]["publication_fresh"] == 1
    matches = [item for item in page["top_stories"] if item["id"] == "ev-draft-fresh"]
    assert matches and matches[0]["trust_label"] == "FRESH / UNREVIEWED"


# 2b. Source-backed (review-ready) Publication is a distinct kind.
def test_source_backed_publication_is_awaiting_review(tmp_path: Path) -> None:
    draft = _draft("ev-draft-ready", captured="2026-08-31", completeness_class="FULL_ARTICLE")
    page = build_front_page(**_base_kwargs(tmp_path, drafts=[draft]))
    assert page["trust_counts"]["publication_pending"] == 1
    matches = [item for item in page["top_stories"] if item["id"] == "ev-draft-ready"]
    assert matches and matches[0]["trust_label"] == "SOURCE-BACKED / AWAITING REVIEW"


# 3. Trusted Evidence visible.
def test_trusted_evidence_is_visible(tmp_path: Path) -> None:
    evidence = _evidence("ev-trusted", published="2026-08-31", captured="2026-08-31")
    page = build_front_page(**_base_kwargs(tmp_path, published=[evidence]))
    matches = [item for item in page["top_stories"] if item["id"] == "ev-trusted"]
    assert matches and matches[0]["trust_label"] == "REVIEWED EVIDENCE"


# 3b. A real production case: a historical-backfill Publication (old real
# published_date, captured today) must appear in Emerging/Unreviewed
# (pipeline just brought it in) but must NOT appear in Top Stories/By
# Region/By Berry (those are about world-time news, not system capture
# time -- captured must never masquerade as published/breaking).
def test_historical_backfill_draft_appears_in_emerging_not_top_stories(tmp_path: Path) -> None:
    draft = _draft(
        "ev-media-historical",
        captured="2026-09-01",
        published_date="2019-12-17",
        entity_ids=[],
    )
    page = build_front_page(**_base_kwargs(tmp_path, drafts=[draft]))
    top_story_ids = [i["id"] for i in page["top_stories"]]
    assert "ev-media-historical" not in top_story_ids

    emerging = next(s for s in page["sections"] if s["key"] == "emerging_unreviewed")
    emerging_ids = [i["id"] for i in emerging["rows"]]
    assert "ev-media-historical" in emerging_ids
    item = next(i for i in emerging["rows"] if i["id"] == "ev-media-historical")
    assert item["captured_band"] == "today"
    assert item["band"] is None
    assert item["date_basis_label"] == "Published"
    assert item["exact_date"] == "Dec 17, 2019"


# 4. Trust labels correct for all five kinds.
def test_all_five_trust_labels_are_exact(tmp_path: Path) -> None:
    draft_fresh = _draft("ev-d1", captured="2026-08-31")
    draft_ready = _draft("ev-d2", captured="2026-08-31", completeness_class="STRUCTURED_REGISTRY")
    evidence = _evidence("ev-e1", published="2026-08-31", captured="2026-08-31")
    signal = _signal("sig-1", first_seen="2026-08-31")
    assessment = _assessment("assessment-1", created_at="2026-08-31")
    page = build_front_page(
        **_base_kwargs(
            tmp_path,
            drafts=[draft_fresh, draft_ready],
            published=[evidence],
            signals=[signal],
            assessments=[assessment],
        )
    )
    labels = {item["id"]: item["trust_label"] for item in page["top_stories"]}
    assert labels["ev-d1"] == "FRESH / UNREVIEWED"
    assert labels["ev-d2"] == "SOURCE-BACKED / AWAITING REVIEW"
    assert labels["ev-e1"] == "REVIEWED EVIDENCE"
    assert labels["sig-1"] == "SIGNAL"
    assert labels["assessment-1"] == "ASSESSMENT"


# 5. Published vs captured date correctness -- capture never masquerades as published.
def test_captured_only_is_never_shown_as_published(tmp_path: Path) -> None:
    evidence = _evidence("ev-captured-only", published=None, captured="2026-08-31")
    page = build_front_page(**_base_kwargs(tmp_path, published=[evidence]))
    item = next(i for i in page["top_stories"] if i["id"] == "ev-captured-only")
    assert item["captured_only"] is True
    assert item["date_basis_label"] == "Captured"

    published = _evidence("ev-published", published="2026-08-30", captured="2026-08-31")
    page2 = build_front_page(**_base_kwargs(tmp_path, published=[published]))
    item2 = next(i for i in page2["top_stories"] if i["id"] == "ev-published")
    assert item2["captured_only"] is False
    assert item2["date_basis_label"] == "Published"


# 6. Europe includes descendants.
def test_europe_region_includes_descendant_country(tmp_path: Path) -> None:
    spain = _geography("geography-spain", "Spain")
    europe = _geography("geography-europe", "Europe")
    evidence = _evidence(
        "ev-spain", published="2026-08-31", captured="2026-08-31", geography_ids=["geography-spain"]
    )
    page = build_front_page(
        **_base_kwargs(
            tmp_path,
            published=[evidence],
            entities=[spain, europe],
            relationships=[_rel("geography-spain", "geography-europe")],
        )
    )
    europe_ids = [item["id"] for item in page["by_region"]["geography-europe"]["rows"]]
    assert "ev-spain" in europe_ids


# 7. A country excludes siblings.
def test_country_region_would_not_include_unrelated_sibling(tmp_path: Path) -> None:
    from app.services.geography_hierarchy import resolve_geography_scope

    spain = _geography("geography-spain", "Spain")
    portugal = _geography("geography-portugal", "Portugal")
    europe = _geography("geography-europe", "Europe")
    relationships = [_rel("geography-spain", "geography-europe"), _rel("geography-portugal", "geography-europe")]
    scope = resolve_geography_scope("geography-spain", relationships=relationships)
    assert "geography-portugal" not in scope.all_ids
    assert "geography-spain" in scope.all_ids


# 8. Berry filters.
def test_berry_filter_excludes_other_berries(tmp_path: Path) -> None:
    blueberry = _evidence("ev-blue", published="2026-08-31", captured="2026-08-31", berry_ids=["berry-blueberry"])
    strawberry = _evidence("ev-straw", published="2026-08-31", captured="2026-08-31", berry_ids=["berry-strawberry"])
    page = build_front_page(
        **_base_kwargs(tmp_path, published=[blueberry, strawberry], berry_id="berry-blueberry")
    )
    ids = [item["id"] for item in page["top_stories"]]
    assert "ev-blue" in ids
    assert "ev-straw" not in ids


# 9. What changed since yesterday.
def test_since_yesterday_counts_only_last_24_hours(tmp_path: Path) -> None:
    recent = _evidence("ev-recent", published="2026-09-01T06:00:00+00:00", captured="2026-09-01T06:00:00+00:00")
    old = _evidence("ev-old", published="2026-08-20", captured="2026-08-20")
    page = build_front_page(**_base_kwargs(tmp_path, published=[recent, old]))
    assert page["since_yesterday"]["total"] == 1
    assert page["since_yesterday"]["newly_reviewed_evidence"][0]["id"] == "ev-recent"


# 10. Deduplication -- an Assessment citing Evidence absorbs it into `underlying`.
def test_dedup_folds_evidence_into_citing_assessment(tmp_path: Path) -> None:
    evidence = _evidence("ev-cited", published="2026-08-31", captured="2026-08-31")
    assessment = _assessment("assessment-cites", created_at="2026-08-31", evidence_ids=["ev-cited"])
    page = build_front_page(**_base_kwargs(tmp_path, published=[evidence], assessments=[assessment]))
    ids = [item["id"] for item in page["top_stories"]]
    assert "assessment-cites" in ids
    assert "ev-cited" not in ids
    representative = next(i for i in page["top_stories"] if i["id"] == "assessment-cites")
    assert any(u["id"] == "ev-cited" for u in representative["underlying"])


# 11. Empty/stale explanation.
def test_stale_state_reports_why(tmp_path: Path) -> None:
    old = _evidence("ev-old", published="2026-07-01", captured="2026-07-01")
    page = build_front_page(**_base_kwargs(tmp_path, published=[old]))
    assert page["quiet"] is True
    assert page["stale_reason"]
    assert "14 days" in page["stale_reason"]
    assert page["top_stories"] == []


# 12. No GET mutation.
def test_today_route_get_never_mutates_inbox(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_signals", lambda: [])
    monkeypatch.setattr(main, "all_assessments", lambda: [])
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "pending_publication_drafts", lambda: [])
    monkeypatch.setattr(main, "all_entities", lambda: [])
    monkeypatch.setattr(main, "all_relationships", lambda: [])
    before = list((tmp_path / "inbox").rglob("*")) if (tmp_path / "inbox").exists() else []
    page = TestClient(main.app).get("/today")
    assert page.status_code == 200
    after = list((tmp_path / "inbox").rglob("*")) if (tmp_path / "inbox").exists() else []
    assert before == after


# 13. No trust promotion -- a fresh draft never renders with a trusted/reviewed label.
def test_fresh_draft_never_labeled_as_reviewed_evidence(tmp_path: Path) -> None:
    draft = _draft("ev-never-promoted", captured="2026-08-31")
    page = build_front_page(**_base_kwargs(tmp_path, drafts=[draft]))
    item = next(i for i in page["top_stories"] if i["id"] == "ev-never-promoted")
    assert item["trust_label"] != "REVIEWED EVIDENCE"
    assert item["front_kind"] != "evidence"


# 14. No static leak -- build_static.py never touches the front page composer.
def test_build_static_does_not_reference_front_page(tmp_path: Path) -> None:
    text = Path(main.BASE_DIR, "scripts", "build_static.py").read_text(encoding="utf-8")
    assert "front_page" not in text
    assert "pending_publication_drafts" not in text
    assert "build_front_page" not in text


# 15. No article-body persistence duplication -- only the short publisher
# description is copied onto the projected item, never full article/raw HTML.
def test_publication_summary_never_carries_full_article_body(tmp_path: Path) -> None:
    long_body = "word " * 500
    draft = _draft(
        "ev-body",
        captured="2026-08-31",
        publisher_description="Short description.",
        article={"paragraphs": [{"text": long_body}]},
        raw_html="<html>" + long_body + "</html>",
    )
    page = build_front_page(**_base_kwargs(tmp_path, drafts=[draft]))
    item = next(i for i in page["top_stories"] if i["id"] == "ev-body")
    assert "article" not in item
    assert "raw_html" not in item
    assert long_body not in item["summary"]


# 16. Links into graph objects.
def test_items_link_to_their_canonical_detail_pages(tmp_path: Path) -> None:
    draft = _draft("ev-link-draft", captured="2026-08-31")
    evidence = _evidence("ev-link-evidence", published="2026-08-31", captured="2026-08-31")
    signal = _signal("sig-link", first_seen="2026-08-31")
    assessment = _assessment("assessment-link", created_at="2026-08-31")
    page = build_front_page(
        **_base_kwargs(
            tmp_path, drafts=[draft], published=[evidence], signals=[signal], assessments=[assessment]
        )
    )
    hrefs = {item["id"]: item["href"] for item in page["top_stories"]}
    assert hrefs["ev-link-draft"] == "/intelligence/ev-link-draft"
    assert hrefs["ev-link-evidence"] == "/evidence/ev-link-evidence"
    assert hrefs["sig-link"] == "/signals/sig-link"
    assert hrefs["assessment-link"] == "/assessments/assessment-link"


# 17. Deterministic fallback -- identical input always produces identical ranking.
def test_ranking_is_deterministic_across_repeated_calls(tmp_path: Path) -> None:
    published = [
        _evidence(f"ev-{i}", published="2026-08-31", captured="2026-08-31", entity_ids=[])
        for i in range(5)
    ]
    kwargs = _base_kwargs(tmp_path, published=list(published))
    first = [item["id"] for item in build_front_page(**kwargs)["top_stories"]]
    second = [item["id"] for item in build_front_page(**kwargs)["top_stories"]]
    assert first == second


# --- Morning Intelligence Edition V1 additions ---


class _FakeMarketRepo:
    """Minimal stand-in for MarketObservationRepository.latest_by_key()."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def latest_by_key(self, **filters) -> list[dict]:
        rows = self._rows
        for field, value in filters.items():
            rows = [r for r in rows if r.get(field) == value]
        return sorted(rows, key=lambda r: r.get("period", ""))


def _market_obs(period: str, value: float, **overrides) -> dict:
    row = {
        "id": f"mkt-{period}-{value}",
        "record_type": "market_observation",
        "metric": "PRODUCTION",
        "berry_id": "berry-blueberry",
        "source_commodity_label": "Fresh Blueberries",
        "source_commodity_code": "081040",
        "form": "unspecified",
        "geography": "PE",
        "geography_id": "geography-peru",
        "period": period,
        "period_type": "year",
        "unit": "MT",
        "value": value,
        "source": "usda_fas",
        "source_dataset": "PE2025-0010",
        "source_url": "https://example.invalid/fas.pdf",
        "captured_at": "2026-09-02T00:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_front_page_includes_market_reality_cards_when_repo_given(tmp_path: Path) -> None:
    repo = _FakeMarketRepo([_market_obs("2023/24", 242000.0), _market_obs("2024/25e", 320000.0)])
    page = build_front_page(**_base_kwargs(tmp_path, market_observations_repo=repo))
    assert page["market_reality"]
    card = page["market_reality"][0]
    assert card["metric"] == "PRODUCTION"
    assert card["direction"] == "up"
    assert card["pct_change"] > 0
    assert card["source"] == "usda_fas"


def test_front_page_omits_market_reality_when_no_repo(tmp_path: Path) -> None:
    page = build_front_page(**_base_kwargs(tmp_path))
    assert page["market_reality"] == []


def test_front_page_market_reality_skips_forecast_vs_forecast(tmp_path: Path) -> None:
    repo = _FakeMarketRepo([_market_obs("2025/26f", 355000.0), _market_obs("2026/27f", 365000.0)])
    page = build_front_page(**_base_kwargs(tmp_path, market_observations_repo=repo))
    assert page["market_reality"] == []  # both periods are forecast -- not a real "change"


def test_front_page_trusted_intelligence_key_present_and_populated(tmp_path: Path) -> None:
    evidence = _evidence("ev-trusted", published="2026-08-31", captured="2026-08-31")
    page = build_front_page(**_base_kwargs(tmp_path, published=[evidence]))
    assert any(row["id"] == "ev-trusted" for row in page["trusted_intelligence"])


def test_front_page_watchlist_match_surfaced_and_tagged(tmp_path: Path) -> None:
    evidence = _evidence(
        "ev-watched", published="2026-08-31", captured="2026-08-31", entity_ids=["company-driscolls"]
    )
    other = _evidence("ev-unwatched", published="2026-08-31", captured="2026-08-31")
    watches = [{"watch_type": "company", "object_id": "company-driscolls"}]
    page = build_front_page(**_base_kwargs(tmp_path, published=[evidence, other], watches=watches))
    watched_ids = {row["id"] for row in page["watchlist_matches"]}
    assert "ev-watched" in watched_ids
    assert "ev-unwatched" not in watched_ids
    matched_item = next(i for i in page["top_stories"] if i["id"] == "ev-watched")
    assert matched_item["is_watched"] is True


def test_front_page_no_watches_gives_empty_watchlist_matches_not_error(tmp_path: Path) -> None:
    evidence = _evidence("ev-a", published="2026-08-31", captured="2026-08-31")
    page = build_front_page(**_base_kwargs(tmp_path, published=[evidence]))
    assert page["watchlist_matches"] == []


def test_front_page_item_carries_strategic_question_ids(tmp_path: Path) -> None:
    evidence = _evidence(
        "ev-sq", published="2026-08-31", captured="2026-08-31", strategic_question_ids=["sq-001"]
    )
    page = build_front_page(**_base_kwargs(tmp_path, published=[evidence]))
    item = next(i for i in page["top_stories"] if i["id"] == "ev-sq")
    assert item["strategic_question_ids"] == ["sq-001"]


def test_brief_handoff_query_string_derives_from_top_stories(tmp_path: Path) -> None:
    evidence = _evidence(
        "ev-handoff",
        published="2026-08-31",
        captured="2026-08-31",
        entity_ids=["company-driscolls", "variety-legacy"],
        geography_ids=["geography-peru"],
    )
    page = build_front_page(**_base_kwargs(tmp_path, published=[evidence], berry_id="berry-blueberry"))
    query = brief_handoff_query_string(page)
    assert "company_ids=company-driscolls" in query
    assert "variety_ids=variety-legacy" in query
    assert "geography_ids=geography-peru" in query
    assert "berry=blueberry" in query


def test_brief_handoff_query_string_empty_when_no_top_stories(tmp_path: Path) -> None:
    page = build_front_page(**_base_kwargs(tmp_path))
    assert brief_handoff_query_string(page) == ""


def test_front_page_route_smoke(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "published_evidence", lambda: [_evidence("ev-smoke", published="2026-08-31", captured="2026-08-31")])
    monkeypatch.setattr(main, "all_signals", lambda: [])
    monkeypatch.setattr(main, "all_assessments", lambda: [])
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "pending_publication_drafts", lambda: [_draft("ev-smoke-draft", captured="2026-08-31")])
    monkeypatch.setattr(main, "all_entities", lambda: [])
    monkeypatch.setattr(main, "all_relationships", lambda: [])
    page = TestClient(main.app).get("/today")
    assert page.status_code == 200
    assert "FRESH / UNREVIEWED" in page.text
    assert "REVIEWED EVIDENCE" in page.text
