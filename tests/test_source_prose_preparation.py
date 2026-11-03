"""Short-text reuse must preserve consent gates, literal prose and edits."""
import pytest

from app.services import source_body
from app.services.variety_universe.corpus_discovery import _NAMED_TOKEN
from app.services.variety_universe.explicit_article_formats import explicit_article_formats


@pytest.mark.parametrize('text', [
    '', 'Accept all', 'We use cookies and data to maintain services.',
    'Researchers described how sites ask visitors to accept all cookies.',
    'We use cookies to make a strawberry dessert.',
    'If you choose to accept all, we will personalize ads.',
    'Please enable cookies before continuing.',
    'This is the first time you visited the website.',
    'This is the first time you visited a blueberry field.',
    'A report about blueberry cultivar development.',
    'We use cookies and data. '+ 'x'*740,
    'We use cookies and data. '+ 'x'*760,
    'Reported: “This website uses cookies.”',
])
def test_exact_text_results_match_original_predicate(text):
    assert source_body.reader_ui_message(text) == source_body._reader_ui_message(text)


def test_changed_source_text_does_not_inherit_a_cached_access_warning():
    record = {'status':'published','summary':'If you choose to accept all, we will show personalized ads.'}
    assert source_body.reader_ui_message(record['summary']) is True
    record['summary'] = 'Researchers reported new raspberry varieties after a field trial.'
    assert source_body.reader_ui_message(record['summary']) is False
    record['summary'] = 'If you choose to accept all, we will show personalized ads.'
    assert source_body.reader_ui_message(record['summary']) is True


def test_long_and_non_plain_text_inputs_do_not_enter_the_short_text_cache():
    source_body._short_reader_ui_message.cache_clear()
    try:
        source_body.reader_ui_message('Plain source paragraph.')
        before=source_body._short_reader_ui_message.cache_info()
        for text in ['x'*2000, None, ['source'], {'source':'text'}]:
            assert source_body.reader_ui_message(text) == source_body._reader_ui_message(text)
        assert source_body._short_reader_ui_message.cache_info() == before
    finally:
        source_body._short_reader_ui_message.cache_clear()


def test_short_text_retention_is_bounded_under_many_distinct_sources():
    source_body._short_reader_ui_message.cache_clear()
    try:
        for number in range(2200):
            assert source_body.reader_ui_message(f'Field report number {number}.') is False
        assert source_body._short_reader_ui_message.cache_info().currsize <= 2048
    finally:
        source_body._short_reader_ui_message.cache_clear()


@pytest.mark.parametrize('crop', ['blueberry','strawberry','raspberry','blackberry'])
def test_explicit_declaration_gate_keeps_all_four_crops_and_literal_names(crop):
    text=f"Example's 'Fixture Dawn' {crop} variety."
    leads,excluded=explicit_article_formats(text,name_token=_NAMED_TOKEN)
    assert [row['name'] for row in leads] == ['Fixture Dawn']
    assert [row['berry_id'] for row in leads] == ['berry-'+crop]
    assert excluded == []


def test_declaration_gate_keeps_an_unscoped_name_in_exclusions():
    leads,excluded=explicit_article_formats("Variety name: 'Fixture Dawn'",name_token=_NAMED_TOKEN)
    assert not leads
    assert excluded == [{'name':"'Fixture Dawn'",'reason':'berry_not_established'}]


def test_unrelated_prose_does_not_become_a_name_assertion():
    assert explicit_article_formats('Fixture Dawn is a regional marketing campaign.',name_token=_NAMED_TOKEN) == ([],[])
