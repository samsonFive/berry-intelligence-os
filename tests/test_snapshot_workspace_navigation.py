"""The snapshot must retain the originating workspace's navigation and scope."""
from html import unescape
import re

from fastapi.testclient import TestClient
import pytest

from app import main


def primary_links(html):
    nav = re.search(r'<nav class="glass-primary"[^>]*>(.*?)</nav>', html, re.S)
    assert nav, "The shared primary navigation must remain available"
    return [unescape(href) for href in re.findall(r'<a\b[^>]*href="([^"]+)"', nav.group(1))]


@pytest.mark.parametrize("authoring", [True, False])
def test_map_and_snapshot_keep_the_same_primary_links_and_fresh_news_action(monkeypatch, tmp_path, authoring):
    monkeypatch.setattr(main, "AUTHORING_MODE", authoring)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    query = {"countries": "iso:FR", "berry": "berry-strawberry", "company": "company-perfection-fresh"}
    before = sorted(tmp_path.rglob("*"))
    map_page = client.get("/explorer", params=query)
    snapshot = client.get("/explorer/snapshot", params={**query, "sections": "statistics"})
    assert map_page.status_code == snapshot.status_code == 200
    assert snapshot.context["authoring_mode"] is authoring
    assert primary_links(snapshot.text) == primary_links(map_page.text)
    links = set(primary_links(snapshot.text))
    assert ("/today?refresh=1" if authoring else "/today") in links
    for href in ("/workspaces", "/social", "/landscapes/explorer"):
        assert (href in links) is authoring
    assert ('href="/social?view=atlas"' in snapshot.text) is authoring
    assert snapshot.context["query"].params()["countries"] == "iso:FR"
    assert snapshot.context["query"].params()["berry"] == "berry-strawberry"
    assert "company=company-perfection-fresh" in snapshot.context["explorer_href"]
    assert 'name="countries" value="iso:FR"' in snapshot.text
    assert 'name="berry" value="berry-strawberry"' in snapshot.text
    assert 'formaction="/explorer/snapshot.pdf"' in snapshot.text
    assert sorted(tmp_path.rglob("*")) == before, "Opening either view must not write workspace state"
