from copy import deepcopy

import pytest

from app.services.presentation_memo import record_memo
from app.services.source_body import reader_content


FIELDS = ('article', 'summary', 'publisher_description', 'transcript',
          'transcript_excerpt', 'media_format', 'discovery_provenance')


@pytest.mark.parametrize('field', FIELDS)
def test_each_current_reader_input_invalidates_without_id_changes(field):
    calls = []

    @record_memo(FIELDS)
    def model(record):
        calls.append(1)
        return {'selected': deepcopy({k: record[k] for k in FIELDS if k in record})}

    record = {'id': 'unchanged', field: {'paragraphs': ['original']}}
    first = model(record)
    first['selected'][field]['paragraphs'].append('caller edit')
    assert model(record)['selected'][field]['paragraphs'] == ['original']
    assert len(calls) == 1
    record[field]['paragraphs'][0] = 'source edit'
    assert model(record)['selected'][field]['paragraphs'] == ['source edit']
    assert len(calls) == 2


def test_reader_distinguishes_list_paragraphs_from_unsupported_tuple():
    paragraph = 'Growers measured berry production over three seasons. ' * 12
    record = {'article': {'paragraphs': [paragraph]}}
    list_result = reader_content(record)
    record['article']['paragraphs'] = (paragraph,)
    tuple_result = reader_content(record)
    assert list_result == reader_content.__wrapped__({'article': {'paragraphs': [paragraph]}})
    assert tuple_result == reader_content.__wrapped__(record)
    assert list_result != tuple_result


def test_custom_reducer_never_executes_and_opaque_input_runs_uncached():
    class Extension:
        def __reduce_ex__(self, protocol):
            pytest.fail('Cache key must not execute a custom reducer')

    calls = []

    @record_memo(('article',))
    def model(record):
        calls.append(1)
        return {'available': bool(record['article'])}

    record = {'article': {'extension': Extension()}}
    assert model(record) == model(record) == {'available': True}
    assert len(calls) == 2


@pytest.mark.parametrize('text,expected_calls', [('果' * 60_000, 1), ('a' * 140_000, 2)],
                         ids=['unicode-legacy-eligible', 'ascii-too-large'])
def test_large_input_retains_legacy_admission_limits(text, expected_calls):
    calls = []

    @record_memo(('article',))
    def model(record):
        calls.append(1)
        return {'length': len(record['article']['full_text'])}

    record = {'article': {'full_text': text}}
    assert model(record) == model(record) == {'length': len(text)}
    assert len(calls) == expected_calls


def test_cyclic_input_falls_back_to_uncached_calculation():
    calls = []

    @record_memo(('article',))
    def model(record):
        calls.append(1)
        return {'available': True}

    article = []
    article.append(article)
    record = {'article': article}
    assert model(record) == model(record) == {'available': True}
    assert len(calls) == 2
