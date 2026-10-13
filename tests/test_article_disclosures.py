"""Collapsed public lists cannot disappear while navigation stays excluded."""
import json

import pytest

from app.services.article_disclosures import retained_disclosure_passages
from app.services import article_acquisition as acquisition


LEAD = ('This blueberry programme provides commercial growers with plant material, '
        'technical support and distinct purchasing options for different markets.')
ENDING = ('The following programme has its own selections and conditions. '
          'Its commercial offering does not establish universal performance or growing regions.')


def disclosure(panel_id, title_id, text, *, label='Varieties', attributes=''):
    return (f'<div role="button" id="{title_id}" aria-controls="{panel_id}" '
            f'aria-expanded="false">{label}</div><div role="region" id="{panel_id}" '
            f'aria-labelledby="{title_id}" {attributes}><p>{text}</p></div>')


def test_multiple_link_heavy_sections_keep_names_codes_breaks_and_order():
    first = disclosure('a', 'ta', 'HIGH CHILL</p><p><a href="/one">Goldenstar ‘FC-123’</a><br>'
                       '<a href="/two">Morningstar ‘FC-456’</a>')
    second = disclosure('b', 'tb', 'HIGH CHILL</p><p><a href="/three">Eveningstar ‘FC-789’</a>')
    source = f'<body><section><p>{LEAD}</p>{first}<p>{ENDING}</p>{second}</section></body>'
    rows = retained_disclosure_passages(source, [LEAD, ENDING])
    assert rows == [LEAD, 'Varieties', 'HIGH CHILL',
                    'Goldenstar ‘FC-123’\nMorningstar ‘FC-456’', ENDING,
                    'Varieties', 'HIGH CHILL', 'Eveningstar ‘FC-789’']


@pytest.mark.parametrize('wrapper', ['nav', 'aside', 'footer', 'header', 'template', 'form'])
def test_navigation_and_template_panels_never_become_source_text(wrapper):
    panel = disclosure('a', 'ta', 'Navigation cultivar ‘FAKE-1’')
    source = f'<section><p>{LEAD}</p><{wrapper}>{panel}</{wrapper}></section>'
    assert retained_disclosure_passages(source, [LEAD]) == [LEAD]


@pytest.mark.parametrize('attrs', ['hidden', 'aria-hidden="true"'])
def test_hard_hidden_ancestors_are_not_public_disclosures(attrs):
    panel = disclosure('a', 'ta', 'Hidden cultivar ‘FAKE-1’')
    source = f'<section><p>{LEAD}</p><div {attrs}>{panel}</div></section>'
    assert retained_disclosure_passages(source, [LEAD]) == [LEAD]


def test_duplicate_ids_broken_pairs_and_unanchored_widgets_stay_excluded():
    panel = disclosure('a', 'ta', 'Not anchored ‘FAKE-1’')
    for source in (
        f'<section><p>{LEAD}</p>{panel}<span id="a"></span></section>',
        f'<section><p>{LEAD}</p>{panel.replace("aria-controls=\"a\"", "aria-controls=\"wrong\"")}</section>',
        f'<article><p>{LEAD}</p><section>{panel}</section></article>',
    ):
        assert retained_disclosure_passages(source, [LEAD]) == [LEAD]


def test_native_details_preserve_content_without_duplicate_extracted_paragraphs():
    source = f'<article><p>{LEAD}</p><details><summary>Named selections</summary><p>Goldenstar ‘FC-123’</p></details></article>'
    assert retained_disclosure_passages(source, [LEAD]) == [LEAD, 'Named selections', 'Goldenstar ‘FC-123’']
    assert retained_disclosure_passages(source, [LEAD, 'Goldenstar ‘FC-123’']) == [LEAD, 'Goldenstar ‘FC-123’']


def test_list_already_retained_as_separate_lines_is_not_duplicated():
    source = f'<section><p>{LEAD}</p>{disclosure("a", "ta", "Goldenstar ‘FC-123’<br>Morningstar ‘FC-456’")}</section>'
    rows = [LEAD, 'Goldenstar ‘FC-123’', 'Morningstar ‘FC-456’']
    assert retained_disclosure_passages(source, rows) == rows


def test_partially_retained_panel_keeps_list_after_its_existing_prose():
    panel = disclosure('a', 'ta', LEAD + '</p><p>Goldenstar ‘FC-123’</p><p>' + ENDING)
    source = f'<section>{panel}</section>'
    assert retained_disclosure_passages(source, [LEAD, ENDING]) == [
        'Varieties', LEAD, 'Goldenstar ‘FC-123’', ENDING]


def test_hidden_and_script_descendants_cannot_supply_false_cultivar_names():
    content = ('Goldenstar ‘FC-123’<script>Scriptstar FAKE-1</script>'
               '<style>Stylestar FAKE-2</style><template>Templatestar FAKE-3</template>'
               '<span hidden>Hiddenstar FAKE-4</span>'
               '<span aria-hidden="true">Ariahiddenstar FAKE-5</span>'
               '<br>Morningstar ‘FC-456’')
    source = f'<section><p>{LEAD}</p>{disclosure("a", "ta", content)}</section>'
    assert retained_disclosure_passages(source, [LEAD]) == [
        LEAD, 'Varieties', 'Goldenstar ‘FC-123’\nMorningstar ‘FC-456’']


def test_unbounded_disclosure_fails_instead_of_silently_dropping_text():
    source = f'<section><p>{LEAD}</p>{disclosure("a", "ta", "x" * 100001)}</section>'
    with pytest.raises(ValueError, match='bounded capture limit'):
        retained_disclosure_passages(source, [LEAD])


def test_acquisition_indexes_and_hash_include_retained_disclosure(monkeypatch):
    source = f'<html><head><title>Blueberry selections</title></head><body><section><p>{LEAD}</p>{disclosure("a", "ta", "Goldenstar ‘FC-123’")}</section></body></html>'
    class Response:
        text = source
        status_code = 200
        url = 'https://example.invalid/blueberry'
    monkeypatch.setattr(acquisition.httpx, 'get', lambda *args, **kwargs: Response())
    monkeypatch.setattr(acquisition.trafilatura, 'extract', lambda *args, **kwargs: json.dumps({'text': LEAD + '\n\n' + ENDING, 'title': 'Blueberry selections'}))
    body = acquisition.fetch_article(str(Response.url))
    assert 'Goldenstar ‘FC-123’' in body.full_text
    assert [p.index for p in body.paragraphs] == list(range(len(body.paragraphs)))
    assert body.as_dict()['acquisition']['version'] == 'article-acquisition-v4'
    assert body.word_count == len(body.full_text.split())
    import hashlib
    assert body.content_sha256 == hashlib.sha256(body.full_text.encode()).hexdigest()
