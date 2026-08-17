"""Integration tests for the article ingestion vertical slice: article_rss
discovery -> orchestration (transcription-skip guard, draft creation,
dedup, no-auto-trust) -> review-workbench presentation. Entirely offline
-- every network call is mocked, and every fixture is built through
get_repositories() pointed at tmp_path, per this project's existing
media-discovery test discipline (see tests/test_media_discovery.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.services import article_acquisition, media_discovery
from app.services.media_discovery import TRANSCRIPT_NOT_APPLICABLE, discover_source, list_discovered_items
from app.services.media_orchestration import JsonStagedTranscriptAdapter, MediaOrchestrationService
from app.services.review_workbench import _readiness_for_item

SOURCE_ID = "source-article-ingestion-test"
FEED_URL = "https://feeds.example.invalid/article-ingestion-test/rss"


class _FakeHttpResponse:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.text = content.decode("utf-8")
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


class _FakeArticleResponse:
    def __init__(self, text: str, *, status: int = 200, url: str = "https://example.invalid/a") -> None:
        self.text = text
        self.status_code = status
        self.url = url


_ARTICLE_HTML = """
<html><head><title>Blueberry acreage grows in Peru</title></head>
<body><article>
<p>Peru's blueberry acreage expanded by 12 percent this season, according to industry group Proarándanos.
Growers cited favorable pricing and strong export demand from the United States and China.</p>
<p>Analysts expect the trend to continue as more growers convert land from other crops to blueberries.</p>
</article></body></html>
"""


def _feed_item(*, title: str, guid: str, link: str, description: str) -> str:
    return f"""
<item>
<title>{title}</title>
<guid isPermaLink="false">{guid}</guid>
<link>{link}</link>
<pubDate>Wed, 28 Oct 2025 07:00:00 GMT</pubDate>
<description>{description}</description>
</item>"""


def _feed(items: list[str]) -> bytes:
    body = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Article Ingestion Test Feed</title>
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
            "label": "Article Ingestion Test Source",
            "value": "https://example.invalid/",
            "url": "https://example.invalid/",
            "last_checked_at": None,
            "last_status": None,
            "discovery": {"adapter": "article_rss", "feed_url": FEED_URL},
        }
    )


def _discover(tmp_path: Path, source, monkeypatch, feed_bytes: bytes):
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *a, **k: _FakeHttpResponse(feed_bytes))
    return discover_source(SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)


def _orchestrator(repos, tmp_path: Path):
    return MediaOrchestrationService(
        repositories=repos,
        inbox_dir=tmp_path / "inbox",
        evidence_errors=lambda _record: [],
        transcript_adapter=JsonStagedTranscriptAdapter(tmp_path / "inbox"),
    )


def test_article_rss_discovery_normalizes_to_web_article_with_no_transcript_concept(tmp_path, source, monkeypatch):
    feed = _feed([_feed_item(
        title="Blueberry acreage grows in Peru", guid="guid-1",
        link="https://example.invalid/peru-blueberry-acreage",
        description="Original publisher description about Peru blueberry acreage.",
    )])
    result = _discover(tmp_path, source, monkeypatch, feed)
    assert result.status == "ok" and result.found == 1

    items = list_discovered_items(tmp_path / "inbox", SOURCE_ID)
    assert len(items) == 1
    item = items[0]
    assert item["media_format"] == "web_article"
    assert item["duration_seconds"] is None
    assert item["transcript_availability"]["status"] == TRANSCRIPT_NOT_APPLICABLE


def test_orchestration_skips_transcription_and_never_touches_transcript_adapter(tmp_path, repos, source, monkeypatch):
    feed = _feed([_feed_item(
        title="Blueberry acreage grows in Peru", guid="guid-1",
        link="https://example.invalid/peru-blueberry-acreage",
        description="Original publisher description.",
    )])
    _discover(tmp_path, source, monkeypatch, feed)
    item_id = list_discovered_items(tmp_path / "inbox", SOURCE_ID)[0]["id"]

    class _ExplodingTranscriptAdapter:
        def load(self, discovered_item):
            raise AssertionError("transcript adapter must never be called for a web_article item")

    orchestrator = MediaOrchestrationService(
        repositories=repos,
        inbox_dir=tmp_path / "inbox",
        evidence_errors=lambda _record: [],
        transcript_adapter=_ExplodingTranscriptAdapter(),
    )
    result = orchestrator.process(item_id, dry_run=False)
    assert result.transcript_status == "not_applicable"
    assert result.errors == []
    assert result.state == "awaiting_publication_review"
    assert result.publication_draft_id is not None


def test_draft_creation_preserves_publisher_description_and_never_auto_trusts(tmp_path, repos, source, monkeypatch):
    feed = _feed([_feed_item(
        title="Blueberry acreage grows in Peru", guid="guid-1",
        link="https://example.invalid/peru-blueberry-acreage",
        description="Original publisher description, verbatim.",
    )])
    _discover(tmp_path, source, monkeypatch, feed)
    item_id = list_discovered_items(tmp_path / "inbox", SOURCE_ID)[0]["id"]

    orchestrator = _orchestrator(repos, tmp_path)
    result = orchestrator.process(item_id, dry_run=False)
    draft_path = tmp_path / "inbox" / "evidence" / f"{result.publication_draft_id}.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))

    assert draft["summary"] == "Original publisher description, verbatim."
    assert draft["status"] == "draft"
    assert draft["review_state"] == "in_review"
    assert "article" not in draft  # not yet acquired at this stage
    assert repos.evidence.list() == []  # nothing trusted


def test_same_article_discovered_twice_is_idempotent_not_a_duplicate_draft(tmp_path, repos, source, monkeypatch):
    feed = _feed([_feed_item(
        title="Blueberry acreage grows in Peru", guid="guid-1",
        link="https://example.invalid/peru-blueberry-acreage",
        description="Original publisher description.",
    )])
    _discover(tmp_path, source, monkeypatch, feed)
    item_id = list_discovered_items(tmp_path / "inbox", SOURCE_ID)[0]["id"]

    orchestrator = _orchestrator(repos, tmp_path)
    first = orchestrator.process(item_id, dry_run=False)
    second_resolution = orchestrator.resolve_publication_artifact(orchestrator.load_item(item_id))

    assert second_resolution.status == "pending_draft"
    assert second_resolution.draft_id == first.publication_draft_id
    drafts = list((tmp_path / "inbox" / "evidence").glob("*.json"))
    assert len(drafts) == 1  # no second draft was created


def test_acquisition_attaches_article_body_and_content_provenance(tmp_path, repos, source, monkeypatch):
    feed = _feed([_feed_item(
        title="Blueberry acreage grows in Peru", guid="guid-1",
        link="https://example.invalid/peru-blueberry-acreage",
        description="Original publisher description.",
    )])
    _discover(tmp_path, source, monkeypatch, feed)
    item_id = list_discovered_items(tmp_path / "inbox", SOURCE_ID)[0]["id"]

    orchestrator = _orchestrator(repos, tmp_path)
    result = orchestrator.process(item_id, dry_run=False)

    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *a, **k: _FakeArticleResponse(_ARTICLE_HTML))
    body = article_acquisition.fetch_article("https://example.invalid/peru-blueberry-acreage")

    draft_path = tmp_path / "inbox" / "evidence" / f"{result.publication_draft_id}.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft["article"] = body.as_dict()
    draft_path.write_text(json.dumps(draft), encoding="utf-8")

    reloaded = json.loads(draft_path.read_text(encoding="utf-8"))
    assert reloaded["summary"] == "Original publisher description."  # still untouched
    assert len(reloaded["article"]["paragraphs"]) >= 2
    assert reloaded["article"]["content_sha256"]
    assert reloaded["article"]["acquisition"]["extractor"] == "trafilatura"


def test_acquisition_failure_on_one_item_does_not_prevent_processing_others(tmp_path, repos, source, monkeypatch):
    feed = _feed([
        _feed_item(title="Good article", guid="guid-good", link="https://example.invalid/good", description="Real content."),
        _feed_item(title="Blocked article", guid="guid-blocked", link="https://example.invalid/blocked", description="Real content."),
    ])
    _discover(tmp_path, source, monkeypatch, feed)
    items = {item["canonical_url"]: item["id"] for item in list_discovered_items(tmp_path / "inbox", SOURCE_ID)}

    def _fake_get(url, **kwargs):
        if "blocked" in url:
            return _FakeArticleResponse("blocked", status=403)
        return _FakeArticleResponse(_ARTICLE_HTML)

    monkeypatch.setattr(article_acquisition.httpx, "get", _fake_get)

    outcomes = {}
    for url, item_id in items.items():
        try:
            article_acquisition.fetch_article(url)
            outcomes[item_id] = "ok"
        except article_acquisition.ArticleAcquisitionError as exc:
            outcomes[item_id] = exc.category

    assert "ok" in outcomes.values()
    assert "blocked" in outcomes.values()


def test_review_workbench_shows_not_applicable_not_unknown_for_articles():
    readiness = _readiness_for_item(
        transcript=None,
        transcript_unreadable=False,
        operation={},
        operation_unreadable=False,
        run_item={"transcript_status": "not_applicable"},
    )
    assert readiness["state"] == "not_applicable"
    assert "unknown" not in readiness["state_label"].lower()
