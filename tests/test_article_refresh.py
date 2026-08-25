"""Tests for app/services/article_refresh.py's process_discovered_article(),
the shared per-item pipeline scripts/ingest_articles.py and the recurring
scripts/run_collection.py orchestrate() path both use for web_article
items -- one code path, not a duplicate one for each caller.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.services import article_acquisition, article_refresh, media_discovery
from app.services.article_refresh import process_discovered_article
from app.services.media_discovery import discover_source, list_discovered_items
from app.services.media_orchestration import JsonStagedTranscriptAdapter, MediaOrchestrationService
from app.services.relevance_screen import TIER_UNCERTAIN

SOURCE_ID = "source-article-refresh-test"
FEED_URL = "https://feeds.example.invalid/article-refresh-test/rss"

_RELEVANT_HTML = """
<html><head><title>Blueberry acreage grows in Peru</title></head>
<body><article>
<p>Peru's blueberry acreage expanded by 12 percent this season, according to industry group Proarandanos.
Growers cited favorable pricing and strong export demand from the United States and China this season.</p>
<p>Analysts expect the trend to continue as more growers convert land from other crops to blueberries.</p>
</article></body></html>
"""

_IRRELEVANT_HTML = """
<html><head><title>Onion exports rise in Sri Lanka</title></head>
<body><article>
<p>Sri Lanka's onion exports rose sharply this season on strong regional demand and favorable weather,
officials said, citing production gains across the growing regions this export season.</p>
<p>Traders expect continued growth as more land is converted to onion cultivation nationwide.</p>
</article></body></html>
"""


class _FakeFeedResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _FakeArticleResponse:
    def __init__(self, text: str, *, url: str = "https://example.invalid/a") -> None:
        self.text = text
        self.status_code = 200
        self.url = url

    def raise_for_status(self) -> None:
        return None


def _feed_item(*, title: str, guid: str, link: str, description: str) -> str:
    return f"""
<item>
<title>{title}</title>
<guid isPermaLink="false">{guid}</guid>
<link>{link}</link>
<pubDate>Tue, 18 Aug 2026 07:00:00 GMT</pubDate>
<description>{description}</description>
</item>"""


def _feed(items: list[str]) -> bytes:
    body = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Article Refresh Test Feed</title>
<link>https://example.invalid/</link>
<description>Test feed.</description>
{body}
</channel></rss>""".encode("utf-8")


@pytest.fixture
def repos(tmp_path: Path):
    return get_repositories(tmp_path, SCHEMAS_DIR)


@pytest.fixture
def source(repos):
    return repos.sources.create(
        {
            "id": SOURCE_ID,
            "type": "reference",
            "label": "Article Refresh Test Source",
            "value": "https://example.invalid/",
            "url": "https://example.invalid/",
            "last_checked_at": None,
            "last_status": None,
            "discovery": {"adapter": "article_rss", "feed_url": FEED_URL},
        }
    )


def _discover_one(tmp_path, source, monkeypatch, *, title: str, link: str, description: str):
    feed = _feed([_feed_item(title=title, guid=link, link=link, description=description)])
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *a, **k: _FakeFeedResponse(feed))
    discover_source(SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    return list_discovered_items(tmp_path / "inbox", SOURCE_ID)[0]


def _orchestrator(repos, tmp_path: Path):
    return MediaOrchestrationService(
        repositories=repos,
        inbox_dir=tmp_path / "inbox",
        evidence_errors=lambda _record: [],
        transcript_adapter=JsonStagedTranscriptAdapter(tmp_path / "inbox"),
    )


def test_relevant_article_produces_a_review_ready_draft_with_real_body(tmp_path, repos, source, monkeypatch):
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="Blueberry acreage grows in Peru", link="https://example.invalid/peru-blueberry",
        description="Blueberry acreage update from Peru.",
    )
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *a, **k: _FakeArticleResponse(_RELEVANT_HTML))

    orchestrator = _orchestrator(repos, tmp_path)
    result, extra = process_discovered_article(item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox")

    assert result.state == "awaiting_publication_review"
    assert result.publication_draft_id is not None
    assert extra["acquired"] is True

    import json
    draft = json.loads((tmp_path / "inbox" / "evidence" / f"{result.publication_draft_id}.json").read_text(encoding="utf-8"))
    assert draft["article"]["word_count"] > 0
    assert len(draft["article"]["paragraphs"]) > 0


def test_confidently_irrelevant_article_is_skipped_before_any_acquisition(tmp_path, repos, source, monkeypatch):
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="City council approves new bridge budget", link="https://example.invalid/bridge-budget",
        description="Local municipal infrastructure spending news unrelated to farming or produce.",
    )

    def _explode(*_args, **_kwargs):
        raise AssertionError("must not acquire the article body for a confidently irrelevant item")

    monkeypatch.setattr(article_acquisition.httpx, "get", _explode)

    orchestrator = _orchestrator(repos, tmp_path)
    result, extra = process_discovered_article(item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox")

    assert result.state == "skipped_irrelevant"
    assert result.publication_draft_id is None
    assert "acquired" not in extra


def test_borderline_item_confirmed_irrelevant_after_real_body_is_skipped(tmp_path, repos, source, monkeypatch):
    """Real pilot regression shape: generic agriculture/export language with
    no berry mention must not pass, even after reading the real body."""
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="Onion exports rise in Sri Lanka", link="https://example.invalid/onion-exports",
        description="Onion production and export update from Sri Lanka this season.",
    )
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *a, **k: _FakeArticleResponse(_IRRELEVANT_HTML))

    orchestrator = _orchestrator(repos, tmp_path)
    result, extra = process_discovered_article(item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox")

    assert result.state == "skipped_irrelevant"
    assert result.publication_draft_id is None
    assert extra["acquired"] is True
    assert "relevance_screen_stage_b" in extra


def test_acquisition_failure_is_reported_as_retryable_not_operator(tmp_path, repos, source, monkeypatch):
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="Blueberry acreage grows in Peru", link="https://example.invalid/peru-blueberry-2",
        description="Blueberry acreage update from Peru.",
    )

    def _timeout(*_args, **_kwargs):
        raise httpx.TimeoutException("connect timed out")

    monkeypatch.setattr(article_acquisition.httpx, "get", _timeout)

    orchestrator = _orchestrator(repos, tmp_path)
    result, extra = process_discovered_article(item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox")

    assert result.state == "article_acquisition_failed"
    assert result.transcript_status == "acquisition_failed"
    assert result.publication_draft_id is None
    assert extra["acquisition_failure_category"]


def test_dry_run_never_acquires_the_article_body(tmp_path, repos, source, monkeypatch):
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="Blueberry acreage grows in Peru", link="https://example.invalid/peru-blueberry-3",
        description="Blueberry acreage update from Peru.",
    )

    def _explode(*_args, **_kwargs):
        raise AssertionError("dry_run must never make a network call")

    monkeypatch.setattr(article_acquisition.httpx, "get", _explode)

    orchestrator = _orchestrator(repos, tmp_path)
    result, extra = process_discovered_article(item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox", dry_run=True)

    assert result.dry_run is True
    assert extra == {}


def test_second_discovery_of_the_same_item_is_idempotent_not_duplicated(tmp_path, repos, source, monkeypatch):
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="Blueberry acreage grows in Peru", link="https://example.invalid/peru-blueberry-4",
        description="Blueberry acreage update from Peru.",
    )
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *a, **k: _FakeArticleResponse(_RELEVANT_HTML))
    orchestrator = _orchestrator(repos, tmp_path)

    first, _ = process_discovered_article(item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox")
    assert first.publication_draft_id is not None

    def _explode(*_args, **_kwargs):
        raise AssertionError("must not re-acquire an item that already has a draft")

    monkeypatch.setattr(article_acquisition.httpx, "get", _explode)
    second, extra = process_discovered_article(item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox")
    assert second.publication_draft_id == first.publication_draft_id
    assert "acquired" not in extra


def test_known_url_with_genuinely_changed_body_is_flagged_without_overwrite(tmp_path, repos, source, monkeypatch):
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="Blueberry acreage grows in Peru", link="https://example.invalid/peru-blueberry-update",
        description="Blueberry acreage update from Peru.",
    )
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *a, **k: _FakeArticleResponse(_RELEVANT_HTML))
    orchestrator = _orchestrator(repos, tmp_path)
    first, _ = process_discovered_article(item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox")
    draft_path = tmp_path / "inbox" / "evidence" / f"{first.publication_draft_id}.json"
    before = json.loads(draft_path.read_text())

    changed_html = _RELEVANT_HTML.replace(
        "Analysts expect the trend to continue as more growers convert land from other crops to blueberries.",
        "Analysts now expect acreage to contract after a severe weather event damaged fields.",
    )
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *a, **k: _FakeArticleResponse(changed_html))
    changed_item = dict(item) | {"discovery_changed_at": "2026-08-25T00:00:00+00:00"}
    result, extra = process_discovered_article(
        changed_item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox"
    )
    after = json.loads(draft_path.read_text())
    probe = json.loads(
        (tmp_path / "inbox" / "discovered_media" / f"{item['id']}.json").read_text()
    )["article_identity_probe"]
    assert result.state == "article_update_detected"
    assert extra["body_acquisition_attempted"] is True
    assert probe["status"] == "CONTENT_CHANGED"
    assert after["article"]["content_sha256"] == before["article"]["content_sha256"]


def test_known_google_wrapper_update_probe_stays_structurally_blocked_without_retry(tmp_path, repos, source, monkeypatch):
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="Blackberry season opens", link="https://example.invalid/blackberry-wrapper",
        description="Blackberry growers opened the season.",
    )
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *a, **k: _FakeArticleResponse(_RELEVANT_HTML))
    orchestrator = _orchestrator(repos, tmp_path)
    first, _ = process_discovered_article(item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox")

    def blocked(_url):
        raise article_acquisition.ArticleAcquisitionError(
            "Google News wrapper did not resolve", category="script_rendered"
        )

    monkeypatch.setattr(article_refresh, "fetch_article", blocked)
    result, extra = process_discovered_article(
        dict(item) | {"discovery_changed_at": "2026-08-25T00:00:00+00:00"},
        orchestrator=orchestrator,
        inbox_dir=tmp_path / "inbox",
    )
    probe = json.loads(
        (tmp_path / "inbox" / "discovered_media" / f"{item['id']}.json").read_text()
    )["article_identity_probe"]
    assert result.state == "awaiting_publication_review"
    assert result.publication_draft_id == first.publication_draft_id
    assert result.errors == []
    assert extra["article_identity_probe"] == "CHECK_BLOCKED"
    assert probe["status"] == "CHECK_BLOCKED"
    assert probe["category"] == "script_rendered"


# --- Query-provenance corroboration fallback (Relevance Screen Boundary V1)
# Real regression shape: TD-040/TD-045's own cited Unifrutti/AvoAmerica Peru
# case -- zero berry/CI signal in title/description, discovered by a
# geography+topic-scoped query, and its canonical_url is a Google News
# redirect page with no server-rendered article body (empty_body). Query
# provenance alone must never claim confident relevance -- it only reopens
# Stage B; when the body is genuinely unverifiable, this must produce an
# explicitly-labeled TIER_UNCERTAIN draft, not a confident DIRECT one and
# not a silent drop.

_PERU_MATCHER = [("geography-peru", re.compile(r"\bPeru\b", re.IGNORECASE))]


def test_query_corroborated_zero_signal_item_becomes_uncertain_draft_when_body_unverifiable(
    tmp_path, repos, source, monkeypatch
):
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU TO FURTHER STRENGTHEN ITS GLOBAL MULTI-FRUIT PLATFORM",
        link="https://example.invalid/unifrutti-peru",
        description="UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU TO FURTHER STRENGTHEN ITS GLOBAL MULTI-FRUIT PLATFORM",
    )
    # A real Google News redirect page: valid HTML, no extractable article
    # body -- article_acquisition.py's own empty_body category.
    monkeypatch.setattr(
        article_acquisition.httpx, "get",
        lambda *a, **k: _FakeArticleResponse("<html><body><div>App shell, no article</div></body></html>"),
    )

    orchestrator = _orchestrator(repos, tmp_path)
    result, extra = process_discovered_article(
        item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox",
        geo_matchers=_PERU_MATCHER, company_matchers=[],
    )

    assert result.state == "awaiting_publication_review"
    assert result.publication_draft_id is not None
    assert result.relevance_tier == TIER_UNCERTAIN
    assert "acquisition_fallback" in extra

    import json
    draft = json.loads((tmp_path / "inbox" / "evidence" / f"{result.publication_draft_id}.json").read_text(encoding="utf-8"))
    assert draft["relevance_tier"] == TIER_UNCERTAIN
    assert draft["status"] == "draft"
    assert draft["review_state"] == "in_review"


def test_query_corroborated_item_still_lets_stage_b_decide_when_body_is_fetchable(
    tmp_path, repos, source, monkeypatch
):
    """When the body IS fetchable, query provenance never short-circuits
    Stage B -- real body content remains the sole arbiter, exactly as for
    any other borderline item."""
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU TO FURTHER STRENGTHEN ITS GLOBAL MULTI-FRUIT PLATFORM",
        link="https://example.invalid/unifrutti-peru-2",
        description="UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU TO FURTHER STRENGTHEN ITS GLOBAL MULTI-FRUIT PLATFORM",
    )
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *a, **k: _FakeArticleResponse(_RELEVANT_HTML))

    orchestrator = _orchestrator(repos, tmp_path)
    result, extra = process_discovered_article(
        item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox",
        geo_matchers=_PERU_MATCHER, company_matchers=[],
    )

    assert result.state == "awaiting_publication_review"
    assert extra["relevance_screen_stage_b"]["relevant"] is True

    import json
    draft = json.loads((tmp_path / "inbox" / "evidence" / f"{result.publication_draft_id}.json").read_text(encoding="utf-8"))
    assert draft["relevance_tier"] == "direct"  # Stage B's real body content decided this, not query provenance


def test_query_corroboration_does_not_apply_without_matchers_passed(tmp_path, repos, source, monkeypatch):
    """No regression for existing callers that don't pass matchers at all
    (e.g. any test or script not yet updated) -- exact prior behavior."""
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU TO FURTHER STRENGTHEN ITS GLOBAL MULTI-FRUIT PLATFORM",
        link="https://example.invalid/unifrutti-peru-3",
        description="UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU TO FURTHER STRENGTHEN ITS GLOBAL MULTI-FRUIT PLATFORM",
    )

    def _explode(*_args, **_kwargs):
        raise AssertionError("must not acquire the body without corroboration matchers")

    monkeypatch.setattr(article_acquisition.httpx, "get", _explode)

    orchestrator = _orchestrator(repos, tmp_path)
    result, extra = process_discovered_article(item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox")

    assert result.state == "skipped_irrelevant"
    assert result.publication_draft_id is None


# --- always_body_check + zero-signal + access-limited fallback (Unknown-Event
# Discovery + Query Coverage V3) -----------------------------------------
# Real regression shape: a CIK-scoped SEC EDGAR search item ("Mission
# Produce, Inc. 8-K filing (EX-99.1)") carries no berry species word in its
# own synthesized title -- Stage A is CONFIDENT-irrelevant on metadata
# alone. The source is pre-scoped (always_body_check=True, same signal as a
# Federal Register/openFDA/UK FSA source), but the filing's own raw
# SGML-wrapped document is not extractable by trafilatura (empty_body) --
# a real, structural dead end distinct from the query-corroboration case
# above, but deserving the identical honest TIER_UNCERTAIN treatment
# rather than a silent article_acquisition_failed with no draft at all.

def test_always_body_check_source_zero_signal_item_becomes_uncertain_draft_when_body_unverifiable(
    tmp_path, repos, source, monkeypatch
):
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="Mission Produce, Inc.  (AVO)  (CIK 0001802974) 8-K filing (EX-99.1)",
        link="https://example.invalid/sec-8k-mission-produce",
        description="SEC 8-K exhibit, items 2.02, 8.01, 9.01.",
    )
    monkeypatch.setattr(
        article_acquisition.httpx, "get",
        lambda *a, **k: _FakeArticleResponse("<html><body><div>Raw SGML-wrapped filing, no extractable article</div></body></html>"),
    )

    orchestrator = _orchestrator(repos, tmp_path)
    result, extra = process_discovered_article(
        item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox", always_body_check=True,
    )

    assert result.state == "awaiting_publication_review"
    assert result.publication_draft_id is not None
    assert result.relevance_tier == TIER_UNCERTAIN

    import json
    draft = json.loads((tmp_path / "inbox" / "evidence" / f"{result.publication_draft_id}.json").read_text(encoding="utf-8"))
    assert draft["relevance_tier"] == TIER_UNCERTAIN


def test_always_body_check_without_access_limitation_still_lets_stage_b_decide(
    tmp_path, repos, source, monkeypatch
):
    """When always_body_check forces a real body fetch that succeeds, real
    content -- not the pre-scoped-source signal -- decides the outcome,
    exactly as the existing always_body_check contract already promises."""
    item = _discover_one(
        tmp_path, source, monkeypatch,
        title="Mission Produce, Inc.  (AVO)  (CIK 0001802974) 8-K filing (EX-99.1)",
        link="https://example.invalid/sec-8k-mission-produce-2",
        description="SEC 8-K exhibit, items 2.02, 8.01, 9.01.",
    )
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *a, **k: _FakeArticleResponse(_IRRELEVANT_HTML))

    orchestrator = _orchestrator(repos, tmp_path)
    result, extra = process_discovered_article(
        item, orchestrator=orchestrator, inbox_dir=tmp_path / "inbox", always_body_check=True,
    )

    assert result.state == "skipped_irrelevant"
    assert result.publication_draft_id is None
