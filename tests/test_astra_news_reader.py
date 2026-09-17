from copy import deepcopy
from datetime import UTC, datetime

from app.services.front_page import build_front_page, _normalized_source_key
from app.services.news_edition import select_edition
from app.services.source_body import reader_content, atomic_extraction_source_text, looks_like_interstitial
from app.services.publication_enrichment import enrich_publication_draft
from app.services.intelligence_feed import build_reader


NOW = datetime(2026, 9, 11, 2, tzinfo=UTC)


def story(identity, published="2026-09-10", **extra):
    return {"id": identity, "title": "Blueberry harvest reporting", "summary": "Growers report on the harvest.",
            "published_date": published, "captured_date": "2026-09-11",
            "source_name": "Publisher", "source_url": f"https://publisher.test/{identity}",
            "status": "published", "source_type": "trade_press", "berry_ids": ["berry-blueberry"],
            "entity_ids": [], "geography_ids": [], "open_reader": True, **extra}


def edition(rows, **params):
    return select_edition(rows, entities=[], relationships=[], params=params, now=NOW)


def test_today_excludes_newly_captured_old_unknown_and_future_publications():
    rows = [story("2007", "2007-01-01"), story("2017", "2017-01-01"),
            story("unknown", ""), story("future", "2026-09-12"),
            story("current", "2026-09-10", title="New blueberry report revisits a 2007 trial")]
    result = edition(rows, date="today", tz="America/Los_Angeles")
    assert [r["id"] for r in result["items"]] == ["current"]


def test_today_converts_timestamps_but_does_not_shift_date_only_reporting():
    rows = [story("timestamp", "2026-09-11T01:00:00Z"), story("date", "2026-09-10")]
    assert edition(rows, date="today", tz="America/Los_Angeles")["total"] == 2
    assert [r["id"] for r in edition(rows, date="today", tz="UTC")["items"]] == ["timestamp"]


def test_filter_pagination_preserves_scope_and_excludes_unknown_geography():
    rows = [story(str(n), entity_ids=["company-example"], geography_ids=["geography-spain"]) for n in range(40)]
    rows.append(story("unknown-geo", entity_ids=["company-example"]))
    result = edition(rows, date="archive", company="company-example", geography="geography-spain", tz="UTC")
    assert result["total"] == 40
    assert len(result["items"]) == 24
    assert "company=company-example" in result["next"]
    assert "geography=geography-spain" in result["next"]
    assert "date=archive" in result["next"]
    assert edition(rows, date="archive", page="999")["page"] == 2


def test_consent_content_is_hidden_without_changing_source_or_history(tmp_path):
    wall = "Before you continue to Google. We use cookies and data to deliver our services."
    record = story("cookie", article={"paragraphs": [{"index": 0, "text": wall}]}, summary=wall,
                   why_it_matters="Unsupported implication from the failed body.")
    original = deepcopy(record)
    view = reader_content(record)
    assert view["contaminated"] and not view["summary"]
    assert atomic_extraction_source_text(record) == ""
    reader = build_reader(record, entities=[], berry_labels={}, inbox_dir=tmp_path,
                          published=[], atomic_drafts=[])
    assert reader["paragraphs"] == []
    assert reader["item"]["summary"] == reader["item"]["why"] == ""
    assert record == original


def test_real_article_with_incidental_cookie_footer_is_usable():
    text = ("The blueberry growers announced a new packing facility serving local farms and export customers. "
            "The company says that the facility will expand its cold storage capacity ahead of the coming harvest. "
            "The release did not disclose how much it invested or identify the varieties handled at the site.\n"
            "Cookie policy")
    assert not looks_like_interstitial(text)
    assert not reader_content(story("valid", article={"paragraphs": [{"text": text}]}))["contaminated"]


def test_bot_screen_cannot_be_sent_to_enrichment():
    wall = "This website uses a security service to protect against malicious bots. This page is displayed while the website verifies you are not a bot."
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("Failed source text must never reach a model")
    result = enrich_publication_draft(story("bot"), {"description": wall}, berries=[],
                                      geographies=[], entities=[], complete_json=forbidden)
    assert not calls
    assert result["ai_enrichment"]["model_provenance"]["status"] == "skipped"


def test_distinct_query_urls_are_not_deduplicated_as_one_story():
    assert _normalized_source_key({"source_url": "https://publisher.test/story?id=1"}) != _normalized_source_key({"source_url": "https://publisher.test/story?id=2"})
    assert _normalized_source_key({"source_url": "https://publisher.test/story?id=1&utm_source=x"}) == _normalized_source_key({"source_url": "https://publisher.test/story?id=1"})


def test_news_projection_does_not_run_operational_freshness(monkeypatch, tmp_path):
    def forbidden(**kwargs):
        raise AssertionError("News page should not scan collection runtime")
    monkeypatch.setattr("app.services.front_page.build_today", forbidden)
    result = build_front_page(published=[story("news")], drafts=[], signals=[], assessments=[],
                             sources=[], entities=[], relationships=[], inbox_dir=tmp_path,
                             data_dir=tmp_path, now=NOW, news_only=True)
    assert result["items"][0]["id"] == "news"


def test_untrusted_image_schemes_are_not_rendered():
    assert not edition([story("image", image_url="javascript:alert(1)")], date="archive")["lead"]["image_url"]
