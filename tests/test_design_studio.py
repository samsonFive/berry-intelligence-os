"""The local design Reader cannot become an arbitrary outbound fetch proxy."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import serve_design_studio as studio


def request(path, **headers):
    handler = object.__new__(studio.Handler)
    handler.path = path
    handler.headers = {"Host": "127.0.0.1:18322", **headers}
    handler.send_json = Mock()
    return handler


@pytest.mark.parametrize("headers", [
    {"Host": "external.example"},
    {"Sec-Fetch-Site": "cross-site"},
])
def test_reader_rejects_external_context_before_fetch(monkeypatch, headers):
    fetch = Mock()
    monkeypatch.setattr(studio, "fetch_article", fetch)
    handler = request("/__reader/article?id=" + next(iter(studio.RECORDS)), **headers)
    handler.do_GET()
    assert handler.send_json.call_args.args[0] == 403
    fetch.assert_not_called()


def test_reader_cannot_fetch_an_arbitrary_url(monkeypatch):
    fetch = Mock()
    monkeypatch.setattr(studio, "fetch_article", fetch)
    handler = request("/__reader/article?id=https://example.com/private&url=http://127.0.0.1/")
    handler.do_GET()
    assert handler.send_json.call_args.args[0] == 404
    fetch.assert_not_called()


def test_reader_returns_only_allowlisted_article_and_reuses_memory_cache(monkeypatch):
    monkeypatch.setattr(studio, "CACHE", {})
    article = SimpleNamespace(paragraphs=[SimpleNamespace(text="Publisher paragraph.")], author="Writer", fetched_at="2026-09-30")
    fetch = Mock(return_value=article)
    monkeypatch.setattr(studio, "fetch_article", fetch)
    item_id = next(iter(studio.RECORDS))
    handler = request("/__reader/article?id=" + item_id)
    handler.do_GET()
    handler.do_GET()
    fetch.assert_called_once_with(studio.RECORDS[item_id]["url"], timeout=12)
    response = handler.send_json.call_args.args[1]
    assert response["paragraphs"] == ["Publisher paragraph."]
    assert response["url"] == studio.RECORDS[item_id]["url"]


def test_reader_failure_does_not_leak_exception_or_cache_a_false_article(monkeypatch):
    monkeypatch.setattr(studio, "CACHE", {})
    monkeypatch.setattr(studio, "fetch_article", Mock(side_effect=RuntimeError("private diagnostic")))
    item_id = next(iter(studio.RECORDS))
    handler = request("/__reader/article?id=" + item_id)
    handler.do_GET()
    assert handler.send_json.call_args.args == (200, {"state": "unavailable", "reason": "reader-unavailable"})
    assert item_id not in studio.CACHE
