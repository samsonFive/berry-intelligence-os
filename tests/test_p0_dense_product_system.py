from pathlib import Path

from app.services.feed_first import captured_passages, parse_filters, present_card_tags
from app.services.feed_first_reader import (
    merge_capture,
    paragraphs_from_html,
    suppress_leading_boilerplate,
)


ROOT = Path(__file__).resolve().parents[1]


def test_news_defaults_to_seven_days_and_keeps_today_compatibility() -> None:
    assert parse_filters({})["window"] == "7d"
    assert parse_filters({"window": "today"})["window"] == "today"


def test_reader_projection_suppresses_only_leading_boilerplate() -> None:
    passages = suppress_leading_boilerplate(
        [
            "Please disable your ad blocker to continue reading.",
            "Planasa announced a new berry trial in Spain with growers.",
            "The article later mentions cookie preferences in its footer.",
        ]
    )
    assert len(passages) == 2
    assert passages[0].startswith("Planasa announced")
    assert "cookie preferences" in passages[-1]


def test_card_tags_dedupe_linked_and_classified_blueberry_fixture() -> None:
    tags = present_card_tags(
        entities=[
            {"id": "company-planasa", "name": "Planasa", "entity_type": "company", "profile_url": "/entities/company/company-planasa"},
            {"id": "berry-blueberry", "name": "Blueberry", "entity_type": "berry", "profile_url": "/entities/berry/berry-blueberry"},
        ],
        people=[],
        geography_chips=[{"id": "geography-spain", "name": "Spain", "href": "/geographies/geography-spain"}],
        crops=["blueberry"],
    )
    assert [tag["name"] for tag in tags] == ["Planasa", "Blueberry", "Spain"]
    assert tags[1]["href"].endswith("berry-blueberry")
    assert tags[1]["berry"] is True


def test_reader_projection_covers_ad_blocking_cached_and_existing_content() -> None:
    exact = "You are using software which is blocking our advertisements. Please disable your ad blocker."
    html = f"<p>{exact}</p><p>Planasa announced a new berry trial in Spain with growers.</p>"
    assert paragraphs_from_html(html) == ["Planasa announced a new berry trial in Spain with growers."]
    capture = {"passages": [exact, "Berry growers expanded the trial into Portugal."], "availability": "full"}
    merged = merge_capture({"id": "item-1", "summary": "Stored summary"}, capture)
    assert merged["article"]["paragraphs"][0]["text"] == "Berry growers expanded the trial into Portugal."
    existing = {"title": "Planasa berry trial", "summary": "", "article": {"paragraphs": [{"text": exact}, {"text": "Planasa berry trial later mentions cookies without being a notice."}]}}
    assert captured_passages(existing) == ["Planasa berry trial later mentions cookies without being a notice."]


def test_all_boilerplate_does_not_fall_back_to_decoded_blob() -> None:
    html = "<p>Before you continue, we use cookies.</p><p>Ad blocker detected.</p>"
    assert paragraphs_from_html(html) == []


def test_golden_news_reader_has_one_close_control_and_distinct_actions() -> None:
    template = (ROOT / "app" / "templates" / "feed_first_today.html").read_text(encoding="utf-8")
    assert template.count('data-close-reader') == 1
    assert "Collapse reader" not in template
    assert 'aria-label="Save for later"' in template
    assert "authorize extraction for confirmation" in template
    assert 'aria-label="View original"' in template


def test_shared_product_language_and_entity_index_are_present() -> None:
    today = (ROOT / "app" / "templates" / "feed_first_today.html").read_text(encoding="utf-8")
    entities = (ROOT / "app" / "templates" / "feed_first_entities.html").read_text(encoding="utf-8")
    css = (ROOT / "app" / "static" / "berry_os.css").read_text(encoding="utf-8")
    assert "News" in today
    assert "Berry" in today
    assert "Companies A to Z" in entities
    assert ".bos-az" in css
    assert ".bos-reader-close" in css
