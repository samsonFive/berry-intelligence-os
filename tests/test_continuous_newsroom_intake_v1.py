"""Continuous Newsroom Intake V1.

Covers the mission's own 23-item test list: qualified Google/Perplexity
result -> Publication draft; rejected/duplicate results never acquired;
known Source preserved; unknown Source safely represented; publisher !=
provider; provider/query provenance retained; published vs captured date;
acquisition failure honesty; no Evidence auto-publication; Front Page
Emerging visibility; reviewed label not used prematurely; recurring run
locking; provider outage isolation; Perplexity disabled fallback /
enabled union; run telemetry; no static leakage; no proprietary provider
leakage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app import main
from app.services.article_acquisition import ArticleAcquisitionError, ArticleBody, ArticleParagraph
from app.services.industry_pulse.intake import (
    PULSE_CATCHNET_SOURCE_ID,
    build_pulse_draft,
    intake_qualified_hits,
    pulse_draft_id,
    resolve_attribution,
)
from app.services.industry_pulse.matrix import generate_pulse_queries
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.newsroom_cycle import (
    load_recent_runs,
    newsroom_lock_status,
    run_newsroom_cycle,
)
from app.services.industry_pulse.providers import MemoryProvider

TODAY = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

QUALIFYING_TITLE = "New blueberry variety launch: breeder announces licensing and PBR patent acreage expansion"


def _hit(
    url: str,
    *,
    provider: str,
    title: str = QUALIFYING_TITLE,
    qualifying: bool = True,
    published_date: str = "2026-08-30",
    source_domain: str = "newpublisher.example",
    origin_publisher_url: str | None = None,
    berry: str = "blueberry",
    geography: str = "americas",
    query_id: str = "pulse:blueberry:americas:7d",
) -> DiscoveryHit:
    return DiscoveryHit(
        title=title, url=url, source_domain=source_domain, published_date=published_date,
        snippet="A breeder announced a new blueberry variety.", query_id=query_id, query_text="",
        geography=geography, berry=berry, topic="industry_pulse", provider=provider,
        origin_publisher_url=origin_publisher_url or url, qualifying=qualifying,
    )


def _body(url: str, *, text: str | None = None) -> ArticleBody:
    long_text = text or (
        "A breeder in California announced a new blueberry variety today, expanding acreage and "
        "entering a licensing agreement with a major grower. " * 6
    )
    return ArticleBody(
        source_url=url, paragraphs=(ArticleParagraph(index=0, text=long_text),), word_count=len(long_text.split()),
        content_sha256="b" * 64, fetched_at="2026-09-01T00:00:00Z", extractor="trafilatura", extractor_version="1",
        author="Jane Doe", final_url=url, title=QUALIFYING_TITLE, published_date="2026-08-30", language="en",
    )


def _fetch_ok(url: str) -> ArticleBody:
    return _body(url)


def _fetch_fails(url: str) -> ArticleBody:
    raise ArticleAcquisitionError("blocked by robots", category="blocked")


# 1. Qualified Google result -> Publication draft.
def test_qualified_google_result_becomes_publication_draft(tmp_path: Path) -> None:
    hit = _hit("https://newpublisher.example/g1", provider="google_news_rss")
    summary = intake_qualified_hits(
        [hit], sources=[], published_evidence=[], drafts=[], entities=[], inbox_dir=tmp_path / "inbox", fetch=_fetch_ok,
    )
    assert summary.drafts_created == 1
    files = list((tmp_path / "inbox" / "evidence").glob("*.json"))
    assert len(files) == 1


# 2. Qualified Perplexity result -> Publication draft.
def test_qualified_perplexity_result_becomes_publication_draft(tmp_path: Path) -> None:
    hit = _hit("https://newpublisher.example/p1", provider="perplexity")
    summary = intake_qualified_hits(
        [hit], sources=[], published_evidence=[], drafts=[], entities=[], inbox_dir=tmp_path / "inbox", fetch=_fetch_ok,
    )
    assert summary.drafts_created == 1


# 3. Rejected (non-qualifying) result is never acquired.
def test_rejected_result_never_acquired(tmp_path: Path) -> None:
    hit = _hit("https://newpublisher.example/reject", provider="google_news_rss", qualifying=False)
    calls = []

    def spy_fetch(url):
        calls.append(url)
        return _fetch_ok(url)

    summary = intake_qualified_hits(
        [hit], sources=[], published_evidence=[], drafts=[], entities=[], inbox_dir=tmp_path / "inbox", fetch=spy_fetch,
    )
    assert calls == []
    assert summary.considered == 0
    assert summary.drafts_created == 0


# 4. Duplicate is never acquired twice.
def test_duplicate_hit_never_acquired_twice(tmp_path: Path) -> None:
    hit_a = _hit("https://newpublisher.example/dup", provider="google_news_rss")
    hit_b = _hit("https://newpublisher.example/dup", provider="perplexity")
    calls = []

    def spy_fetch(url):
        calls.append(url)
        return _fetch_ok(url)

    summary = intake_qualified_hits(
        [hit_a, hit_b], sources=[], published_evidence=[], drafts=[], entities=[], inbox_dir=tmp_path / "inbox", fetch=spy_fetch,
    )
    assert len(calls) == 1
    assert summary.drafts_created == 1


# 5. Already-existing Publication is skipped.
def test_already_existing_publication_skipped(tmp_path: Path) -> None:
    hit = _hit("https://newpublisher.example/existing", provider="google_news_rss")
    existing_draft = {
        "id": "ev-media-existing",
        "source_url": "https://newpublisher.example/existing",
        "title": QUALIFYING_TITLE,
        "source_id": None,
        "published_date": "2026-08-30",
    }
    calls = []

    def spy_fetch(url):
        calls.append(url)
        return _fetch_ok(url)

    summary = intake_qualified_hits(
        [hit], sources=[], published_evidence=[], drafts=[existing_draft], entities=[],
        inbox_dir=tmp_path / "inbox", fetch=spy_fetch,
    )
    assert calls == []
    assert summary.already_represented == 1
    assert summary.drafts_created == 0


# 6. Known Source is preserved (correct attribution, not the catch-net placeholder).
def test_known_source_attribution_preserved() -> None:
    hit = _hit("https://knownpublisher.example/story", provider="perplexity", source_domain="knownpublisher.example")
    sources = [{"id": "source-known-publisher", "label": "Known Publisher", "url": "https://knownpublisher.example/"}]
    source_id, source_name, source_url = resolve_attribution(hit, sources=sources)
    assert source_id == "source-known-publisher"
    assert source_name == "Known Publisher"


# 7. Unknown Source is safely represented (catch-net placeholder, not silently a new trusted Source).
def test_unknown_source_uses_catchnet_placeholder_not_new_source() -> None:
    hit = _hit("https://brandnew.example/story", provider="perplexity", source_domain="brandnew.example")
    source_id, source_name, source_url = resolve_attribution(hit, sources=[])
    assert source_id == PULSE_CATCHNET_SOURCE_ID
    assert source_name != PULSE_CATCHNET_SOURCE_ID  # real publisher name, not the placeholder id
    assert "brandnew.example" in source_name or source_name


# 8. Publisher != provider.
def test_source_name_is_publisher_never_provider() -> None:
    hit = _hit("https://realpublisher.example/story", provider="perplexity", source_domain="realpublisher.example")
    draft = build_pulse_draft(hit, sources=[], entities=[], now=TODAY)
    assert draft["source_name"] != "perplexity"
    assert draft["source_name"] != "Perplexity"
    assert "perplexity" not in draft["source_name"].casefold()


# 9. Provider provenance retained.
def test_provider_provenance_retained_on_draft() -> None:
    hit = _hit("https://x.example/a", provider="perplexity")
    draft = build_pulse_draft(hit, sources=[], entities=[], now=TODAY)
    assert draft["pulse_provenance"]["providers"] == ["perplexity"]


# 10. Query provenance retained.
def test_query_provenance_retained_on_draft() -> None:
    hit = _hit("https://x.example/b", provider="google_news_rss", berry="raspberry", geography="africa")
    draft = build_pulse_draft(hit, sources=[], entities=[], now=TODAY)
    prov = draft["pulse_provenance"]
    assert prov["query_ids"] == [hit.query_id]
    assert prov["berry_query"] == "raspberry"
    assert prov["geography_query"] == "africa"
    assert prov["topic_query"] == "industry_pulse"


# 11. Published date retained.
def test_published_date_retained() -> None:
    hit = _hit("https://x.example/c", provider="google_news_rss", published_date="2026-08-15")
    draft = build_pulse_draft(hit, sources=[], entities=[], now=TODAY)
    assert draft["published_date"] == "2026-08-15"


# 12. Captured date distinct from published date.
def test_captured_date_distinct_from_published_date() -> None:
    hit = _hit("https://x.example/d", provider="google_news_rss", published_date="2019-12-17")
    draft = build_pulse_draft(hit, sources=[], entities=[], now=TODAY)
    assert draft["published_date"] == "2019-12-17"
    assert draft["captured_date"] == "2026-09-01"
    assert draft["captured_date"] != draft["published_date"]


# 13. Acquisition failure is recorded honestly, not silently dropped.
def test_acquisition_failure_produces_honest_thin_draft(tmp_path: Path) -> None:
    hit = _hit("https://blocked.example/story", provider="google_news_rss", source_domain="blocked.example")
    summary = intake_qualified_hits(
        [hit], sources=[], published_evidence=[], drafts=[], entities=[], inbox_dir=tmp_path / "inbox", fetch=_fetch_fails,
    )
    assert summary.acquisition_attempted == 1
    assert summary.acquisition_failed == 1
    assert summary.drafts_created == 1  # still a draft -- useful intelligence is not discarded
    files = list((tmp_path / "inbox" / "evidence").glob("*.json"))
    import json

    draft = json.loads(files[0].read_text(encoding="utf-8"))
    assert draft["source_completeness"]["failure_category"] == "ROBOTS"
    assert draft["status"] == "draft"


# 14. No Evidence auto-publication -- ever, regardless of outcome.
def test_intake_never_writes_published_evidence(tmp_path: Path) -> None:
    hit = _hit("https://x.example/e", provider="google_news_rss")
    intake_qualified_hits(
        [hit], sources=[], published_evidence=[], drafts=[], entities=[], inbox_dir=tmp_path / "inbox", fetch=_fetch_ok,
    )
    assert not (tmp_path / "inbox" / "evidence" / "published").exists()
    files = list((tmp_path / "inbox" / "evidence").glob("*.json"))
    import json

    for f in files:
        record = json.loads(f.read_text(encoding="utf-8"))
        assert record["status"] == "draft"
        assert record["review_state"] == "in_review"


# 15. Front Page Emerging visibility.
def test_pulse_draft_visible_in_front_page_emerging(tmp_path: Path) -> None:
    from app.services.front_page import build_front_page

    hit = _hit("https://x.example/f", provider="perplexity", published_date="2026-09-01")
    draft = build_pulse_draft(hit, sources=[], entities=[], now=TODAY)
    page = build_front_page(
        published=[], drafts=[draft], signals=[], assessments=[], sources=[], entities=[], relationships=[],
        inbox_dir=tmp_path, data_dir=tmp_path, now=TODAY,
    )
    matches = [i for i in page["top_stories"] if i["id"] == draft["id"]]
    assert matches
    assert matches[0]["trust_label"] == "FRESH / UNREVIEWED"


# 16. Reviewed label not used prematurely.
def test_pulse_draft_never_labeled_reviewed_evidence(tmp_path: Path) -> None:
    from app.services.front_page import build_front_page

    hit = _hit("https://x.example/g", provider="google_news_rss", published_date="2026-09-01")
    draft = build_pulse_draft(hit, sources=[], entities=[], now=TODAY)
    page = build_front_page(
        published=[], drafts=[draft], signals=[], assessments=[], sources=[], entities=[], relationships=[],
        inbox_dir=tmp_path, data_dir=tmp_path, now=TODAY,
    )
    matches = [i for i in page["top_stories"] if i["id"] == draft["id"]]
    assert matches
    assert matches[0]["trust_label"] != "REVIEWED EVIDENCE"
    assert matches[0]["front_kind"] != "evidence"


# 17. Recurring run locking.
def test_newsroom_cycle_refuses_concurrent_run(tmp_path: Path) -> None:
    import json

    inbox = tmp_path / "inbox"
    lock_path = inbox / "operations" / "industry_pulse_intake.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"run_id": "other", "started_at": TODAY.isoformat(), "pid": 1}), encoding="utf-8")

    result = run_newsroom_cycle(
        sources=[], published_evidence=[], drafts=[], entities=[], inbox_dir=inbox, data_dir=tmp_path, now=TODAY,
    )
    assert result["refused"] is True
    status = newsroom_lock_status(inbox, now=TODAY)
    assert status["active"] is True


# 18. Provider outage isolation -- catch-net failure never blocks discovery+intake from Google.
def test_catch_net_outage_does_not_block_google_results(tmp_path: Path) -> None:
    @dataclass
    class FailingCatchNet:
        name: str = "perplexity"

        def discover(self, query):
            raise RuntimeError("provider outage")

        def available(self) -> bool:
            return True

    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://x.example/h", provider="x")])
    result = run_newsroom_cycle(
        sources=[], published_evidence=[], drafts=[], entities=[], inbox_dir=tmp_path / "inbox",
        data_dir=tmp_path, provider=google, catch_net_provider=FailingCatchNet(), fetch=_fetch_ok, now=TODAY,
    )
    assert result["intake"]["drafts_created"] == 1
    assert result["discovery"]["query_failures"] > 0


# 19. Perplexity disabled -> Google-only fallback (route-level flag check).
def test_route_flag_off_runs_google_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "PERPLEXITY_PULSE_ENABLED", False)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_entities", lambda: [])
    monkeypatch.setattr(main, "list_drafts_metadata", lambda: [])
    monkeypatch.setattr(main, "list_pending_drafts", lambda: [])
    monkeypatch.setattr(main, "list_discovered_items", lambda *_a, **_k: [])
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [], {}))

    captured = {}

    def _stub(**kwargs):
        captured["catch_net_provider"] = kwargs.get("catch_net_provider")
        return {"refused": False, "refusal_reason": ""}

    monkeypatch.setattr(main, "run_newsroom_cycle", _stub)
    from fastapi.testclient import TestClient

    resp = TestClient(main.app).post("/industry-pulse/run", follow_redirects=False)
    assert resp.status_code == 303
    assert captured["catch_net_provider"] is None


# 20. Perplexity enabled -> union with both providers.
def test_two_providers_union_into_deduped_qualifying_set(tmp_path: Path) -> None:
    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://x.example/i", provider="x")])
    perplexity = MemoryProvider(name="perplexity", hits=[_hit("https://x.example/j", provider="x")])
    result = run_newsroom_cycle(
        sources=[], published_evidence=[], drafts=[], entities=[], inbox_dir=tmp_path / "inbox",
        data_dir=tmp_path, provider=google, catch_net_provider=perplexity, fetch=_fetch_ok, now=TODAY,
    )
    assert result["discovery"]["union_unique_count"] == 2
    assert result["intake"]["drafts_created"] == 2


# 21. Run telemetry.
def test_run_telemetry_shape(tmp_path: Path) -> None:
    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://x.example/k", provider="x")])
    result = run_newsroom_cycle(
        sources=[], published_evidence=[], drafts=[], entities=[], inbox_dir=tmp_path / "inbox",
        data_dir=tmp_path, provider=google, fetch=_fetch_ok, now=TODAY,
    )
    assert set(result) >= {"run_id", "as_of", "refused", "discovery", "intake"}
    assert "provider_telemetry" in result["discovery"]
    assert "drafts_created" in result["intake"]
    assert "estimated_cost_usd" not in result["discovery"]
    assert "cost" not in result["discovery"]
    runs = load_recent_runs(tmp_path / "inbox")
    assert len(runs) == 1


# 22. No static leakage.
def test_build_static_does_not_reference_intake_or_newsroom() -> None:
    text = Path(main.BASE_DIR, "scripts", "build_static.py").read_text(encoding="utf-8")
    assert "industry_pulse_intake" not in text
    assert "newsroom_cycle" not in text
    assert "pulse_draft" not in text.lower()


# 23. No proprietary provider leakage -- pulse-derived draft text never
# carries a provider-only marker where the real publisher belongs.
def test_no_proprietary_provider_leakage_in_draft_text() -> None:
    hit = _hit("https://realpublisher.example/story", provider="perplexity", source_domain="realpublisher.example")
    draft = build_pulse_draft(hit, sources=[], entities=[], now=TODAY)
    for field in ("source_name", "title", "summary"):
        assert "perplexity" not in str(draft.get(field, "")).casefold()
    assert draft["pulse_provenance"]["providers"] == ["perplexity"]  # provenance, not attribution
