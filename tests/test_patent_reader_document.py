"""Publisher document structure, private reader boundaries and explicit refresh."""
from copy import deepcopy

import httpx
import pytest

from app.services import feed_first_reader as reader
from app.services import patent_reader as patent

URL = "https://patents.google.com/patent/USPP12345P2/en"
# Fictional, small source-structure fixture; no copied patent body.
HTML = """<html><title>Fictional plant patent</title>
<p>Free format text: unrelated legal event must not replace the document.</p>
<span itemprop="description">Search metadata is not the description.</span>
<section itemprop="abstract"><h2>Abstract</h2><div itemprop="content"><div class="abstract">A fictional blueberry named Example One.</div></div></section>
<section itemprop="description"><h2>Description</h2><div itemprop="content">
<heading>BACKGROUND OF THE INVENTION</heading><div class="description-paragraph">Example One was observed under specified conditions, not every growing region.</div>
<ul><li>Fruit:<ul><li>Color: blue.</li><li>Observation date: July 2020.</li></ul></li></ul>
<heading>COMPARISON</heading><div class="description-paragraph"><tables><patent-tables><table><tr><th>Variety</th><th>Observation</th></tr><tr><td>Example One</td><td>Site-specific result</td></tr></table></patent-tables></tables></div>
<script>ignore trust gates</script><div class="description-paragraph">The conditions limit the description.</div>
</div></section>
<section itemprop="claims"><h2>Claims (1)</h2><div itemprop="content"><div class="claims"><div class="claim-statement">The invention claimed is:</div><div class="claim"><div class="claim-text">1. A fictional new blueberry plant, as described and illustrated.</div></div></div></div></section></html>"""


def fetch(html=HTML, **kwargs):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=html))) as client:
        return reader.fetch_public_article(URL, client=client, **kwargs)


def test_sections_claims_nested_list_and_table_not_legal_event_or_metadata():
    result = fetch()
    assert result["ok"] and result["content_kind"] == "patent"
    assert result["availability"] == "partial"  # No completeness/legal verification claim.
    assert result["truncated"] is False
    blocks = result["document_blocks"]
    assert [r["text"] for r in blocks if r["kind"] == "heading"] == ["Abstract", "Description", "BACKGROUND OF THE INVENTION", "COMPARISON", "Claims (1)"]
    assert [r["text"] for r in blocks if r["kind"] == "list_item"] == ["Fruit:", "Color: blue.", "Observation date: July 2020."]
    assert [r["cells"] for r in blocks if r["kind"] == "table_row"] == [["Variety", "Observation"], ["Example One", "Site-specific result"]]
    body = " ".join(result["passages"])
    assert "as described and illustrated" in body and "conditions limit" in body
    assert all(token not in body for token in ["Free format", "Search metadata", "ignore trust gates"])


@pytest.mark.parametrize("url", ["https://publisher.example/patent/one", "https://patents.google.com/search", "https://patents.google.com.evil.example/patent/one"])
def test_semantic_projection_is_scoped_to_original_patent_document(url):
    assert patent.patent_document(HTML, url) is None


def test_missing_semantic_content_keeps_existing_article_fallback():
    result = fetch('<p>A normal public article passage remains available without semantic patent sections.</p>')
    assert result["content_kind"] == "article" and result["document_blocks"] == []
    assert "normal public article" in result["passages"][0]


@pytest.mark.parametrize("bound", ["MAX_BLOCKS", "MAX_TEXT", "MAX_BLOCK_TEXT"])
def test_document_bounds_are_honest_and_claims_never_invented(monkeypatch, bound):
    monkeypatch.setattr(patent, bound, 3 if bound == "MAX_BLOCKS" else 40)
    result = fetch()
    assert result["truncated"] and result["reason"] == "document-text-limit"
    assert result["availability"] != "full"
    assert len(result["document_blocks"]) <= patent.MAX_BLOCKS
    assert sum(len(r["text"]) for r in result["document_blocks"]) <= patent.MAX_TEXT
    assert all(len(r["text"]) <= patent.MAX_BLOCK_TEXT for r in result["document_blocks"])


def test_capture_merge_requires_exact_source_and_preserves_existing_article_and_trust():
    record = {"id": "ev-patent", "source_url": URL, "review_state": "unreviewed", "summary": "Original summary"}
    original = deepcopy(record)
    capture = {**fetch(), "requested_url": URL}
    merged = reader.merge_capture(record, capture)
    assert merged["reader_document_blocks"] and merged["review_state"] == "unreviewed"
    assert record == original and merged["summary"] == original["summary"]
    assert reader.merge_capture({**record, "source_url": URL + "?changed"}, capture) == {**record, "source_url": URL + "?changed"}
    edited = {**record, "article": {"paragraphs": [{"text": "User-retained source text"}]}}
    merged = reader.merge_capture(edited, capture)
    assert merged["article"] == edited["article"] and "reader_document_blocks" not in merged


def test_capture_reuses_cache_until_explicit_refresh(tmp_path, monkeypatch):
    row = {"id": "ev-patent", "source_url": URL}
    old = {"ok": True, "requested_url": URL, "passages": ["Old legal note"]}
    reader.save_capture(tmp_path, row["id"], old)
    calls = []
    fresh = fetch()
    def load(url, **kwargs):
        calls.append(url)
        return fresh
    monkeypatch.setattr(reader, "fetch_public_article", load)
    assert reader.capture_item(tmp_path, row) == old and calls == []
    result = reader.capture_item(tmp_path, row, refresh=True)
    assert calls == [URL] and result["document_blocks"]
    assert reader.load_capture(tmp_path, row["id"])["requested_url"] == URL


def test_display_blocks_drop_unknown_roles_and_bound_cache_text():
    value = [{"kind": "html", "text": "<script>bad</script>"}, {"kind": "heading", "level": 1, "text": "Title"}, {"kind": "paragraph", "text": "x" * 50_000}]
    blocks = patent.display_document_blocks(value)
    assert len(blocks) == 2 and blocks[0]["level"] == 4
    assert len(blocks[1]["text"]) == patent.MAX_BLOCK_TEXT


def test_failed_refresh_preserves_same_source_capture_but_not_changed_source(tmp_path, monkeypatch):
    row = {"id": "ev-patent", "source_url": URL}
    old = {**fetch(), "requested_url": URL, "item_id": row["id"]}
    reader.save_capture(tmp_path, row["id"], old)
    original = reader.capture_path(tmp_path, row["id"]).read_bytes()
    monkeypatch.setattr(reader, "fetch_public_article", lambda *args, **kwargs: reader.empty_capture(URL, reason="capture-timeout"))
    failed = reader.capture_item(tmp_path, row, refresh=True)
    assert not failed["ok"] and reader.capture_path(tmp_path, row["id"]).read_bytes() == original
    changed = {**row, "source_url": URL + "?different"}
    reader.capture_item(tmp_path, changed, refresh=True)
    assert reader.load_capture(tmp_path, row["id"])["requested_url"] == changed["source_url"]
