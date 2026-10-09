"""Recover mis-tagged report prose without admitting menus or access screens."""
import pytest

from app.services import article_acquisition as acquisition
from app.services import article_semantics
from tests.test_article_acquisition import _FakeResponse, _REAL_ARTICLE_HTML


TITLE = 'Fictional university blueberry trial report'
PROSE = '''<h2>Trial design</h2>
<p>This fictional report describes a blueberry trial planted at an experimental
station. The trial compared named selections in replicated plots during one
harvest season. The observations belong to that location and season; they do
not establish universal yield, flavor or growing-region claims.</p>
<p>The researchers recorded flowering and harvest dates for each selection.
Plants were maintained using the same irrigation schedule and soil treatment.
These details matter when comparing results, because a difference in the site
conditions can change the interpretation of the observed fruit performance.</p>
<h2>Harvest observations</h2>
<p>Blueberry varieties include Fixture Blue and Example Dawn. The researchers
weighed harvested fruit separately for each experimental plot, retaining
measurements for the individual harvest dates. Results are illustrative test
content, not real commercial intelligence or reviewed variety traits.</p>
<p>The original report includes a discussion of the limitations of its sampling
method. The next season may produce different results, and source text must
remain distinct from the analyst's interpretation. Publication review and
identity review are separate decisions that reading this text cannot make.</p>'''
REPORT = f'''<html><head><title>{TITLE}</title></head><body>
<nav><a href="/menu">Menu-only sentinel</a></nav>
<div role="main"><section><h1>{TITLE}</h1><nav class="related-links">{PROSE}</nav></section></div>
<footer>Footer-only sentinel</footer></body></html>'''


def test_mis_tagged_report_retains_paragraphs_and_headings_not_menu(monkeypatch):
    # The compact synthetic page can be recovered by trafilatura's own fallback.
    # Exercise its no-result path explicitly; use the real extractor on the
    # repaired document, retaining all body/menu/heading assertions. The full
    # live publisher response is checked separately, never committed to CI.
    extract = acquisition.trafilatura.extract
    calls=[]
    def initial_failure_then_extract(source, **kwargs):
        calls.append(source)
        return None if len(calls) == 1 else extract(source, **kwargs)
    monkeypatch.setattr(acquisition.trafilatura,'extract',initial_failure_then_extract)
    monkeypatch.setattr(acquisition.httpx,'get',lambda *args,**kwargs:_FakeResponse(REPORT))
    body=acquisition.fetch_article('https://example.invalid/report')
    assert 'Fixture Blue and Example Dawn' in body.full_text
    assert 'Menu-only sentinel' not in body.full_text and 'Footer-only sentinel' not in body.full_text
    assert {p.text for p in body.paragraphs if p.heading_level} == {'Trial design','Harvest observations'}
    assert [p.index for p in body.paragraphs] == list(range(len(body.paragraphs)))
    assert body.as_dict()['acquisition']['version'] == 'article-acquisition-v3'
    assert len(calls) == 2


@pytest.mark.parametrize('change',[
    lambda s:s.replace('role="main"','role="complementary"'),
    lambda s:s.replace(f'<title>{TITLE}</title>','<title>Unrelated directory</title>'),
    lambda s:s.replace('class="related-links"','class="related-links" hidden'),
    lambda s:s.replace('class="related-links"','class="related-links" aria-hidden="true"'),
    lambda s:s.replace('</nav></section>','<form><input name="q"></form></nav></section>'),
    lambda s:s.replace('<p>','<p><a href="/linked-menu">').replace('</p>','</a></p>'),
    lambda s:s.replace(f'<h1>{TITLE}</h1>',f'<h1>{TITLE}</h1><h1>Second unrelated article</h1>'),
    lambda s:s.replace('</nav></section>',f'</nav><nav>{PROSE}</nav></section>'),
])
def test_hidden_interactive_link_heavy_and_ambiguous_regions_are_not_repaired(change):
    assert article_semantics.prose_navigation_html(change(REPORT)) is None


def test_normal_article_does_not_invoke_semantic_fallback(monkeypatch):
    monkeypatch.setattr(acquisition.httpx,'get',lambda *args,**kwargs:_FakeResponse(_REAL_ARTICLE_HTML))
    monkeypatch.setattr(article_semantics,'prose_navigation_html',lambda *args:pytest.fail('Repaired an already readable article'))
    assert 'Peru' in acquisition.fetch_article('https://example.invalid/article').full_text


def test_paywall_still_stops_before_any_semantic_repair(monkeypatch):
    page=REPORT.replace('<body>','<body><p>Subscribe to continue reading.</p>')
    monkeypatch.setattr(acquisition.httpx,'get',lambda *args,**kwargs:_FakeResponse(page))
    monkeypatch.setattr(article_semantics,'prose_navigation_html',lambda *args:pytest.fail('Attempted repair of a paywall'))
    with pytest.raises(acquisition.ArticleAcquisitionError) as caught:
        acquisition.fetch_article('https://example.invalid/report')
    assert caught.value.category == 'paywall'
