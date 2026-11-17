"""Confidence is accessible on each item without separating its list placement."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def _environment():
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())
    env.globals["learn_glossary_hits"] = lambda *args: []
    env.filters["us_date"] = str
    return env


def test_feed_keeps_reviewed_and_unreviewed_items_together_with_individual_details():
    records = [
        {"id": "ev-new", "title": "New source", "information": {"review_status": "unreviewed", "confidence_label": "Not assessed"}},
        {"id": "ev-reviewed", "title": "Reviewed source", "information": {"review_status": "reviewed", "confidence_label": "Medium"}},
    ]
    items = [
        {"id": row["id"], "title": row["title"], "record": row, "trust": "pending" if i == 0 else "trusted", "href": "/intelligence/" + row["id"]}
        for i, row in enumerate(records)
    ]
    html = _environment().from_string("<ul>{% for item in items %}{% include '_intelligence_card.html' %}{% endfor %}</ul>").render(items=items)
    assert html.count("data-intel-card") == 2
    assert html.count("Confidence &amp; source details") == 2
    assert "<dd>Unreviewed</dd>" in html
    assert "<dd>Reviewed</dd>" in html
    assert "<dd>Medium</dd>" in html
    assert "<dd>Not assessed</dd>" in html
    assert "v2-mark-trusted" not in html
    assert "v2-mark-pending" not in html


def test_information_details_preserve_qualifications_and_escape_source_text():
    html = _environment().get_template("_information_details.html").render(
        information_record={"information": {"review_status": "unreviewed", "confidence_label": "Low", "caveats": ["Publisher claim <unverified>"]}},
        information_ai_assisted=True,
    )
    assert "<dd>Low</dd>" in html
    assert "Publisher claim &lt;unverified&gt;" in html
    assert "AI assisted" in html
    assert " open" not in html


def test_private_review_details_are_absent_from_public_snapshot():
    html = _environment().get_template("_information_details.html").render(
        static_build=True,
        information_record={"information": {"review_status": "private reviewer note", "confidence_label": "Private confidence"}},
    )
    assert not html.strip()
