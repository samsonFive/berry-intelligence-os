"""Original source structure survives acquisition and selected reading."""
from copy import deepcopy

import httpx
import pytest

from app.services import article_acquisition as acquisition, feed_first_reader as reader
from app.services.article_structure import publisher_heading_levels, display_article_blocks
from tests.test_personal_digest import article, workspace


HTML = """<html><head><title>New raspberry programme</title></head><body>
<nav><h2>Navigation headline</h2></nav><article>
<h1>New raspberry programme</h1>
<p>A nursery has introduced a new raspberry selection after several seasons
of grower trials. The company describes its results as preliminary and says
that production trials will continue with growers next season.</p>
<h2>Growing results</h2>
<p>The trial compared fruit quality, storage and harvest timing under the
same field conditions. These observations do not establish broader commercial
performance in other climates or at different grower locations.</p>
<h4>What comes next?</h4>
<p>The next stage will test the selection in additional growing regions.
The nursery says that independent results will be shared when those trials
have been completed, rather than treating a release announcement as proof.</p>
</article><footer><h3>Related stories</h3></footer></body></html>"""
URL = "https://publisher.example/article"


def test_acquisition_keeps_original_words_indexes_and_hash_with_source_headings(monkeypatch):
    from tests.test_article_acquisition import _FakeResponse
    monkeypatch.setattr(acquisition.httpx, "get", lambda *args, **kwargs: _FakeResponse(HTML, url=URL))
    body = acquisition.fetch_article(URL)
    headings = {row.text: row.heading_level for row in body.paragraphs if row.heading_level}
    assert headings == {"Growing results": 2, "What comes next?": 4}
    monkeypatch.setattr("app.services.article_structure.publisher_heading_levels", lambda *args: {})
    plain = acquisition.fetch_article(URL)
    assert [(row.index, row.text) for row in body.paragraphs] == [(row.index, row.text) for row in plain.paragraphs]
    assert body.content_sha256 == plain.content_sha256 and body.word_count == plain.word_count
    assert body.full_text == plain.full_text
    assert all("heading_level" not in row for row in plain.as_dict()["paragraphs"])


def test_exact_source_heading_matching_excludes_chrome_hidden_and_ambiguous_text():
    html = '<h2>Real <em>section</em></h2><nav><h2>Menu</h2></nav><aside><h2>Aside</h2></aside><h3 hidden>Hidden</h3><div aria-hidden="true"><h2>Invisible</h2></div><h4>Duplicate</h4><h5>Duplicate</h5><p>Ordinary question?</p>'
    passages = ["Real section", "Menu", "Aside", "Hidden", "Invisible", "Duplicate", "Ordinary question?"]
    assert publisher_heading_levels(html, passages) == {0: 2}
    assert publisher_heading_levels('<h2>Duplicate</h2>', ['Duplicate', 'Duplicate']) == {}
    assert publisher_heading_levels('<h2>Real section</h2>', ['Real section: revised by operator']) == {}
    assert publisher_heading_levels('<h2>Unrelated</h2><article><p>Unrelated</p><h3>Real</h3></article>', ['Unrelated', 'Real']) == {1: 3}


def test_bounded_capture_retains_heading_order_and_metadata_without_html():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=HTML))) as client:
        captured = reader.fetch_public_article(URL, client=client)
    assert captured['ok'] and captured['content_kind'] == 'article'
    assert captured['heading_levels'] == {'1': 2, '3': 4}
    assert captured['passages'][1] == 'Growing results' and captured['passages'][3] == 'What comes next?'
    assert 'Navigation headline' not in captured['passages'] and 'Related stories' not in captured['passages']
    original = deepcopy(captured)
    merged = reader.merge_capture({'source_url': URL}, captured)
    assert merged['article']['paragraphs'][3] == {'text': 'What comes next?', 'heading_level': 4}
    assert captured == original
    record = {'source_url': URL, 'article': {'paragraphs': [{'text': 'Operator text'}]}}
    assert reader.merge_capture(record, captured)['article'] == record['article']
    assert reader.merge_capture({'source_url': URL + '/different'}, captured) == {'source_url': URL + '/different'}


def test_capture_reports_passage_limit_instead_of_claiming_full_article():
    html = '<article>' + ''.join(f'<p>Paragraph {index}: ' + 'Original publisher words. ' * 8 + '</p>' for index in range(30)) + '</article>'
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=html))) as client:
        captured = reader.fetch_public_article(URL, client=client)
    assert len(captured['passages']) == 24 and captured['truncated']
    assert captured['availability'] == 'partial' and captured['reason'] == 'article-text-limit'


def test_heading_only_shell_cannot_become_full_article():
    html = '<article>' + ''.join('<h2>' + 'Navigation section words. ' * 10 + '</h2>' for _ in range(5)) + '</article>'
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=html))) as client:
        captured = reader.fetch_public_article(URL, client=client)
    assert captured['availability'] != 'full' and captured['heading_levels'] == {}


@pytest.mark.parametrize('level', [None, True, 1, 7, '2'])
def test_invalid_hint_cannot_turn_text_into_a_heading(level):
    record = {'article': {'paragraphs': [{'text': 'Original words?', 'heading_level': level}]}}
    assert display_article_blocks(record, ['Original words?'])[0]['heading'] is False


def test_reader_renders_source_titles_with_hierarchy_and_escapes_source_html(workspace):
    client, repos = workspace
    record = article('ev-headings', article={'paragraphs': [
        {'index': 0, 'text': 'Introductory publisher paragraph.'},
        {'index': 1, 'text': 'Growing results', 'heading_level': 2},
        {'index': 2, 'text': 'Publisher answer. An ordinary question? remains prose.'},
        {'index': 3, 'text': 'What comes next?', 'heading_level': 4},
        {'index': 4, 'text': '<script>alert("source")</script>', 'heading_level': 4}]})
    repos.evidence.create(record)
    response = client.get('/api/intelligence/ev-headings/reader?personal=1')
    assert response.status_code == 200
    assert '<h3 class="publisher-heading">Growing results</h3>' in response.text
    assert '<h4 class="publisher-heading">What comes next?</h4>' in response.text
    assert '<p>Publisher answer. An ordinary question? remains prose.</p>' in response.text
    assert '&lt;script&gt;' in response.text and '<script>alert("source")</script>' not in response.text
    ordinary = client.get('/intelligence/ev-headings')
    assert ordinary.status_code == 200
    assert 'class="publisher-heading" id="p2"' in ordinary.text
    assert 'id="p3"' in ordinary.text and 'Publisher answer.' in ordinary.text
