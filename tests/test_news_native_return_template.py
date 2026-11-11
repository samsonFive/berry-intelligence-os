"""The legacy reading flag comes only from the validated native return value."""
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment


class Attributes(HTMLParser):
    def handle_starttag(self, tag, attrs):
        self.values = dict(attrs)


def attributes(**context):
    template = (Path(__file__).resolve().parents[1] / "app/templates/news_workspace.html").read_text(encoding="utf-8")
    start = template.index('<fieldset class="news-tags"')
    fragment = template[start:template.index('>', start) + 1]
    rendered = Environment().from_string(fragment).render(authoring_mode=True, **context)
    parser = Attributes()
    parser.feed(rendered)
    return parser.values


def test_validated_native_return_selects_reading_only_initialization():
    assert attributes(investigation_return_href="/app/briefing?ctx_v=1")["data-auto-recheck"] == "false"


def test_missing_or_raw_unvalidated_return_does_not_change_legacy_initialization():
    assert attributes()["data-auto-recheck"] == "true"
    assert attributes(investigation_return_href="", request=SimpleNamespace(query_params={"return_to": "/app/briefing"}))["data-auto-recheck"] == "true"
