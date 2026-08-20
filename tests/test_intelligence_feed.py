"""Live intelligence feed and inline promotion. Trust gates stay unchanged."""

from __future__ import annotations

import json
from copy import deepcopy
from html import unescape
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.intelligence_feed import (
    build_intelligence_feed,
    classify_kind,
    extract_claims_status,
    matches_filter,
)


PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")


def _publication_draft(suffix: str, **overrides) -> dict:
    draft = {
        "id": f"ev-intel-{suffix}",
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "intake_type": "article_or_url",
        "source_type": "article",
        "source_name": "Synthetic Journal",
        "source_url": f"https://example.invalid/{suffix}",
        "published_date": "2026-08-18",
        "captured_date": "2026-08-18",
        "title": f"Synthetic blueberry article {suffix}",
        "summary": "A concise blueberry supply brief for promotion tests.",
        "why_it_matters": "Peru timing still matters for blueberry buyers.",
        "submitted_by": "fixture",
        "evidence_role": "publication_artifact",
        "berry_ids": ["berry-blueberry"],
        "suggested_competitors": ["Hortifrut"],
        "suggested_varieties": [],
        "attachments": [],
        "priority": deepcopy(PRIORITY),
        "ai_enrichment": {
            "concise_summary": "Walmart blueberry merchandising is the CI point.",
            "why_it_matters": "Retail programs can move volume this season.",
            "suggested_berry_ids": ["berry-blueberry"],
            "suggested_geography_ids": [],
            "suggested_entity_ids": ["company-hortifrut"],
            "suggested_tags": ["retail"],
            "topical_relevance": "High relevance to blueberry competitive intelligence.",
            "confidence": 0.7,
            "caveats": "Show notes only.",
            "model_provenance": {
                "status": "ok",
                "provider": "perplexity-agent",
                "model": "anthropic/claude-haiku-4-5",
                "trust_state": "untrusted_suggestion",
            },
        },
    }
    draft.update(overrides)
    return draft


def _spoken_draft(suffix: str) -> dict:
    return _publication_draft(
        suffix,
        source_type="industry_podcast",
        media_format="podcast",
        title=f"Synthetic blueberry podcast {suffix}",
        source_url="https://www.youtube.com/watch?v=fixture",
        publisher_description="Long publisher dump that must not look trusted.",
    )


def _patent_draft() -> dict:
    return _publication_draft(
        "patent",
        source_type="patent_record",
        title="Red raspberry plant named ‘Finnberry’",
        summary="USPTO plant patent fixture for Finnberry.",
        patent_filing={
            "publication_number": "USPP35090P2",
            "filing_date": "2022-01-01",
            "grant_date": "2023-04-04",
            "assignees": ["United States"],
            "inventors": ["Inventor Fixture"],
            "cultivar_name": "Finnberry",
        },
        berry_ids=["berry-raspberry"],
        does_not_prove=["commercial acreage", "market success"],
        source_authority="USPTO",
        evidence_links=[{"predicate": "corroborates", "target_id": "ev-trusted-article", "status": "proposed"}],
        ai_enrichment={},
    )


def _published(record_id: str, **overrides) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "news_search",
        "source_name": "FreshPlaza",
        "source_url": "https://example.invalid/trusted",
        "title": "Trusted blueberry consumption brief",
        "published_date": "2026-08-10",
        "captured_date": "2026-08-10",
        "summary": "Trusted published article fixture.",
        "submitted_by": "reviewer",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-08-10",
        "priority": deepcopy(PRIORITY),
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-hortifrut"],
    }
    record.update(overrides)
    return record


def _seed_entities(repos) -> None:
    for entity in (
        {
            "id": "company-hortifrut",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Hortifrut",
            "status": "active",
        },
        {
            "id": "berry-blueberry",
            "record_type": "entity",
            "entity_type": "berry",
            "name": "Blueberry",
            "status": "active",
        },
        {
            "id": "berry-raspberry",
            "record_type": "entity",
            "entity_type": "berry",
            "name": "Raspberry",
            "status": "active",
        },
    ):
        repos.entities.create(entity)


def test_classify_kind_and_filters_use_stored_fields_only() -> None:
    assert classify_kind({"source_type": "news_search"}) == "article"
    assert classify_kind({"media_format": "podcast"}) == "spoken"
    assert classify_kind({"patent_filing": {"publication_number": "USPP1"}}) == "patent"
    article = {"kind": "article", "tags": ["retail"], "entities": [{"entity_type": "company"}]}
    spoken = {"kind": "spoken", "tags": ["shopper"], "entities": []}
    patent = {"kind": "patent", "tags": [], "entities": [{"entity_type": "variety"}]}
    assert matches_filter(article, "articles")
    assert matches_filter(spoken, "spoken")
    assert matches_filter(patent, "patents") and matches_filter(patent, "genetics")
    assert matches_filter(article, "markets")
    assert matches_filter(spoken, "consumer")
    assert extract_claims_status()["runnable"] is False
    assert "unqualified" in extract_claims_status()["detail"].casefold()


def test_feed_ranks_high_relevance_above_generic_and_keeps_trusted(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    high = _spoken_draft("high")
    low = _spoken_draft("low")
    low["title"] = "How DNA Technology Is Transforming Agriculture"
    low["ai_enrichment"]["topical_relevance"] = "Low to moderate. Not berry-specific."
    low["berry_ids"] = []
    low["ai_enrichment"]["suggested_berry_ids"] = []
    patents = [
        _patent_draft() | {"id": f"ev-intel-patent-{index}", "title": f"Raspberry plant {index}"}
        for index in range(20)
    ]
    for draft in [high, low, *patents]:
        main.save_draft(draft)
    repos.evidence.create(_published("ev-trusted-article"))
    repos.evidence.create(
        _published(
            "ev-trusted-podcast",
            source_type="industry_podcast",
            media_format="podcast",
            title="Scaling the Blueberry Industry fixture",
            published_date="2025-10-28",
        )
    )
    feed = build_intelligence_feed(
        drafts=main.list_drafts(),
        published=repos.evidence.list(),
        entities=repos.entities.list(),
        berry_labels=main.BERRIES,
        limit=24,
    )
    titles = [item["title"] for item in feed["entries"]]
    assert titles.index("Synthetic blueberry podcast high") < titles.index(
        "How DNA Technology Is Transforming Agriculture"
    )
    assert any(item["trust"] == "trusted" and item["kind"] == "article" for item in feed["entries"])
    assert any(item["id"] == "ev-trusted-podcast" for item in feed["entries"])
    spoken = build_intelligence_feed(
        drafts=main.list_drafts(),
        published=repos.evidence.list(),
        entities=repos.entities.list(),
        berry_labels=main.BERRIES,
        filter_key="spoken",
        limit=24,
    )
    assert {item["kind"] for item in spoken["entries"]} == {"spoken"}


def test_feed_ranks_direct_relevance_tier_above_adjacent_at_equal_band_and_date(monkeypatch, tmp_path: Path) -> None:
    """Continuous Intelligence Refresh requirement: an Aug-17 direct
    blueberry-market-access story must generally outrank an Aug-17
    pear-solar (adjacent) story -- relevance_tier is the primary rank,
    ahead of relevance_band/berry_direct, which don't capture the same
    distinction (see app/services/intelligence_feed.py's _feed_sort_key)."""
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    direct = _publication_draft(
        "direct-tier",
        media_format="web_article",
        title="Fresh Peruvian blueberries gain access to Egypt",
        relevance_tier="direct",
        published_date="2026-08-17",
    )
    adjacent = _publication_draft(
        "adjacent-tier",
        media_format="web_article",
        title="Solar panels above pear trees provide effective heat protection",
        relevance_tier="adjacent",
        published_date="2026-08-17",
    )
    for draft in [direct, adjacent]:
        main.save_draft(draft)
    feed = build_intelligence_feed(
        drafts=main.list_drafts(),
        published=repos.evidence.list(),
        entities=repos.entities.list(),
        berry_labels=main.BERRIES,
        limit=24,
    )
    titles = [item["title"] for item in feed["entries"]]
    assert titles.index("Fresh Peruvian blueberries gain access to Egypt") < titles.index(
        "Solar panels above pear trees provide effective heat protection"
    )


def test_adjacent_filter_surfaces_adjacent_signals_without_hiding_them(monkeypatch, tmp_path: Path) -> None:
    """Do not hide adjacent signals -- give them their own filter."""
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    direct = _publication_draft("direct-only", media_format="web_article", relevance_tier="direct")
    adjacent = _publication_draft(
        "adjacent-only",
        media_format="web_article",
        title="Adjacent agtech story",
        relevance_tier="adjacent",
    )
    for draft in [direct, adjacent]:
        main.save_draft(draft)
    feed = build_intelligence_feed(
        drafts=main.list_drafts(),
        published=repos.evidence.list(),
        entities=repos.entities.list(),
        berry_labels=main.BERRIES,
        filter_key="adjacent",
        limit=24,
    )
    assert feed["filter"] == "adjacent"
    assert {item["id"] for item in feed["entries"]} == {"ev-intel-adjacent-only"}
    assert any(option["key"] == "adjacent" for option in feed["filters"])


def test_feed_promote_save_reject_use_existing_review_paths(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    promote = _publication_draft("feed-promote")
    save = _publication_draft("feed-save")
    reject = _publication_draft("feed-reject")
    for draft in (promote, save, reject):
        main.save_draft(draft)
    client = TestClient(app)

    page = client.get("/work-queue")
    assert page.status_code == 200
    assert 'name="review_values"' not in page.text
    assert f'value="{promote["title"]}"' in unescape(page.text)
    assert "event.key === \"j\"" in page.text

    saved = client.post(
        f"/review/{save['id']}/save",
        data={
            "title": save["title"],
            "summary": save["summary"],
            "why_it_matters": save["why_it_matters"],
            "return_to": "/work-queue?saved=1",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    assert saved.headers["location"] == "/work-queue?saved=1"
    saved_page = client.get("/work-queue?saved=1")
    assert "Pending item saved" in saved_page.text
    assert main.get_draft(save["id"])["status"] == "draft"

    promoted = client.post(
        f"/review/{promote['id']}/publish",
        data={
            "title": promote["title"],
            "source_type": promote["source_type"],
            "source_name": promote["source_name"],
            "source_url": promote["source_url"],
            "published_date": promote["published_date"],
            "captured_date": promote["captured_date"],
            "summary": promote["summary"],
            "why_it_matters": promote["why_it_matters"],
            "tags": "retail",
            "reviewer": "analyst-fixture",
            "return_to": f"/work-queue?promoted={promote['id']}",
        },
        follow_redirects=False,
    )
    assert promoted.status_code == 303
    assert promoted.headers["location"] == f"/work-queue?promoted={promote['id']}"
    feed = client.get(promoted.headers["location"])
    assert "Promoted to trusted intelligence" in feed.text
    assert f'href="/intelligence/{promote["id"]}"' in feed.text
    assert repos.evidence.get(promote["id"])["status"] == "published"
    assert main.get_draft(promote["id"]) is None

    rejected = client.post(
        f"/review/{reject['id']}/reject",
        data={
            "reviewer": "analyst-fixture",
            "rejection_reason": "Rejected from intelligence feed",
            "rejection_category": "other",
            "return_to": "/work-queue",
        },
        follow_redirects=False,
    )
    assert rejected.status_code == 303
    assert rejected.headers["location"] == "/work-queue"
    assert main.get_draft(reject["id"])["status"] == "rejected"
    after = client.get("/work-queue")
    assert "Synthetic blueberry article feed-reject" not in after.text


def test_tier_absent_items_are_not_penalized_below_direct(monkeypatch, tmp_path: Path) -> None:
    """Podcasts/videos/pre-fix drafts carry no relevance_tier at all --
    they must rank with direct items, not be treated as adjacent."""
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    spoken = _spoken_draft("no-tier")
    adjacent = _publication_draft(
        "adjacent-vs-notier",
        media_format="web_article",
        title="Adjacent agtech story two",
        relevance_tier="adjacent",
    )
    for draft in [spoken, adjacent]:
        main.save_draft(draft)
    feed = build_intelligence_feed(
        drafts=main.list_drafts(),
        published=repos.evidence.list(),
        entities=repos.entities.list(),
        berry_labels=main.BERRIES,
        limit=24,
    )
    titles = [item["title"] for item in feed["entries"]]
    assert titles.index("Synthetic blueberry podcast no-tier") < titles.index("Adjacent agtech story two")


def test_reader_promote_save_and_trusted_feedback(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    draft = _publication_draft("promote")
    draft["article"] = {
        "paragraphs": [
            {"locator": "p1", "text": "Exact acquired paragraph one."},
            {"locator": "p2", "text": "Exact acquired paragraph two."},
        ]
    }
    main.save_draft(draft)
    client = TestClient(app)
    feed = client.get("/work-queue")
    assert feed.status_code == 200
    assert "LIVE INTELLIGENCE" in feed.text
    assert "Synthetic blueberry article promote" in feed.text
    assert "Pending" in feed.text
    assert "AI-assisted · pending analyst review" in feed.text
    assert f'href="/intelligence/{draft["id"]}"' in feed.text
    assert "/entities/company/company-hortifrut" in feed.text

    reader = client.get(f"/intelligence/{draft['id']}")
    assert reader.status_code == 200
    assert "INTELLIGENCE READER" in reader.text
    assert "Exact acquired paragraph one." in reader.text
    assert "p1" in reader.text
    assert "Promote publication" in reader.text
    assert "Save pending" in reader.text
    assert "Ignore / reject" in reader.text
    assert "HUMAN PUBLICATION REVIEW" not in reader.text
    assert "Read original" in reader.text
    assert "No qualified extraction model" in reader.text
    assert 'action="/review/%s/publish"' % draft["id"] in reader.text

    saved = client.post(
        f"/review/{draft['id']}/save",
        data={
            "title": draft["title"],
            "summary": draft["summary"],
            "why_it_matters": draft["why_it_matters"],
            "return_to": f"/intelligence/{draft['id']}?saved=1",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    assert saved.headers["location"] == f"/intelligence/{draft['id']}?saved=1"

    promoted = client.post(
        f"/review/{draft['id']}/publish",
        data={
            "title": draft["title"],
            "source_type": draft["source_type"],
            "source_name": draft["source_name"],
            "source_url": draft["source_url"],
            "published_date": draft["published_date"],
            "captured_date": draft["captured_date"],
            "summary": draft["summary"],
            "why_it_matters": draft["why_it_matters"],
            "tags": "retail",
            "reviewer": "analyst-fixture",
            "return_to": f"/intelligence/{draft['id']}?promoted=1",
        },
        follow_redirects=False,
    )
    assert promoted.status_code == 303
    assert promoted.headers["location"] == f"/intelligence/{draft['id']}?promoted=1"
    trusted = client.get(promoted.headers["location"])
    assert trusted.status_code == 200
    assert "Promoted to trusted intelligence" in trusted.text
    assert ">Trusted<" in trusted.text
    assert "Promote publication" not in trusted.text
    assert repos.evidence.get(draft["id"])["status"] == "published"
    assert main.get_draft(draft["id"]) is None


def test_spoken_and_patent_reader_shell(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    spoken = _spoken_draft("spoken")
    spoken["discovered_item_id"] = "discovered-spoken-fixture"
    main.save_draft(spoken)
    _write(
        tmp_path / "inbox" / "discovered_media" / "_normalized_transcripts" / "discovered-spoken-fixture.json",
        {
            "segments": [
                {
                    "text": "Exact transcript sentence about blueberries.",
                    "start_seconds": 125,
                    "end_seconds": 140,
                    "speaker_label": "Host",
                }
            ]
        },
    )
    main.save_draft(_patent_draft())
    repos.evidence.create(_published("ev-trusted-article"))
    client = TestClient(app)
    spoken_page = client.get(f"/intelligence/{spoken['id']}")
    assert spoken_page.status_code == 200
    assert "Exact transcript sentence about blueberries." in spoken_page.text
    assert "2:05" in spoken_page.text
    assert "Transcript quality depends" in spoken_page.text
    assert "t=125" in spoken_page.text
    patent_page = client.get("/intelligence/ev-intel-patent")
    assert patent_page.status_code == 200
    assert "USPP35090P2" in patent_page.text
    assert "Finnberry" in patent_page.text
    assert "Does not prove" in patent_page.text
    assert "Open filing" in patent_page.text
    trusted_page = client.get("/intelligence/ev-trusted-article")
    assert trusted_page.status_code == 200
    assert ">Trusted<" in trusted_page.text
    assert "Trusted blueberry consumption brief" in trusted_page.text


def test_inline_atomic_accept_uses_existing_publish_path(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    parent = _published(
        "ev-intel-parent",
        source_type="industry_podcast",
        media_format="podcast",
        title="Trusted spoken parent",
        source_url="https://www.youtube.com/watch?v=fixture",
    )
    repos.evidence.create(parent)
    proposal = {
        "id": "ev-intel-claim",
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "intake_type": "article_or_url",
        "source_type": "industry_podcast",
        "source_name": "Synthetic Podcast",
        "source_url": parent["source_url"],
        "published_date": "2026-08-10",
        "captured_date": "2026-08-10",
        "title": "Normalized blueberry claim.",
        "summary": "Normalized blueberry claim.",
        "why_it_matters": "",
        "submitted_by": "synthetic extractor",
        "evidence_role": "atomic_evidence",
        "parent_evidence_id": parent["id"],
        "artifact_locator": {"start_seconds": 180, "end_seconds": 200, "speaker_label": "Speaker A"},
        "transcript_excerpt": "Exact synthetic transcript support.",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-hortifrut"],
        "suggested_competitors": [],
        "suggested_varieties": [],
        "attachments": [],
        "priority": deepcopy(PRIORITY),
        "extraction_provenance": {
            "method": "ai_assisted",
            "extracted_by": "synthetic-provider",
            "extracted_at": "2026-08-10",
        },
    }
    main.save_draft(proposal)
    client = TestClient(app)
    reader = client.get(f"/intelligence/{parent['id']}")
    assert reader.status_code == 200
    assert "Normalized blueberry claim." in reader.text
    assert "Exact synthetic transcript support." in reader.text
    assert 'action="/review/ev-intel-claim/approve-atomic"' in reader.text
    accepted = client.post(
        "/review/ev-intel-claim/approve-atomic",
        data={
            "reviewer": "analyst-fixture",
            "confirm_individual_review": "true",
            "return_to": f"/intelligence/{parent['id']}",
        },
        follow_redirects=False,
    )
    assert accepted.status_code == 303
    assert accepted.headers["location"] == f"/intelligence/{parent['id']}"
    trusted = repos.evidence.get("ev-intel-claim")
    assert trusted["status"] == "published"
    assert trusted["evidence_role"] == "atomic_evidence"
    assert trusted["transcript_excerpt"] == "Exact synthetic transcript support."
    after = client.get(f"/intelligence/{parent['id']}")
    assert 'action="/review/ev-intel-claim/approve-atomic"' not in after.text


def test_evil_return_to_still_rejected(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    draft = _publication_draft("reject")
    main.save_draft(draft)
    client = TestClient(app)
    rejected = client.post(
        f"/review/{draft['id']}/reject",
        data={
            "reviewer": "analyst-fixture",
            "rejection_reason": "Not relevant.",
            "return_to": "https://evil.invalid/",
        },
        follow_redirects=False,
    )
    assert rejected.status_code == 303
    assert rejected.headers["location"] == "/review"


def test_runtime_feed_uses_real_records_when_present() -> None:
    inbox = Path("inbox/evidence")
    data = Path("data/evidence")
    if not inbox.is_dir() or not data.is_dir():
        return
    client = TestClient(app)
    page = client.get("/work-queue")
    assert page.status_code == 200
    spoken = client.get("/work-queue?filter=spoken")
    patents = client.get("/work-queue?filter=patents")
    articles = client.get("/work-queue?filter=articles")
    assert spoken.status_code == articles.status_code == patents.status_code == 200
    # The "ev-media-" id prefix is shared by media_discovery.py's whole
    # adapter family (podcast_rss/youtube_feed *and* article_rss), so it is
    # not itself proof of spoken media -- classify_kind() on the record's
    # own media_format is the same check the real /work-queue route uses.
    has_spoken_draft = any(
        classify_kind(json.loads(path.read_text(encoding="utf-8"))) == "spoken"
        for path in inbox.glob("ev-media-*.json")
    )
    if has_spoken_draft:
        assert "Spoken media" in spoken.text
        assert "Pending" in spoken.text
    if any("lucentlands" in path.name for path in data.glob("*.json")):
        trusted = client.get("/intelligence/ev-lucentlands-scaling-blueberry-industry-2025")
        assert trusted.status_code == 200
        assert "Trusted" in trusted.text
        assert "Open source" in trusted.text
    sample_article = next(
        (
            path
            for path in sorted(data.glob("*.json"))
            if json.loads(path.read_text(encoding="utf-8")).get("source_type") == "news_search"
        ),
        None,
    )
    if sample_article is not None:
        record = json.loads(sample_article.read_text(encoding="utf-8"))
        detail = client.get(f"/intelligence/{record['id']}")
        if detail.status_code == 200:
            text = unescape(detail.text)
            assert record["title"] in text
            assert "Read original" in text or "Open filing" in text or "Open source" in text
