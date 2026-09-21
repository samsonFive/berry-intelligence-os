from pathlib import Path

from app.services.feed_first import parse_filters
from app.services.feed_first_reader import suppress_leading_boilerplate


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
