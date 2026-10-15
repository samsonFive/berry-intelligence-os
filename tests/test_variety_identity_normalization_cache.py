from copy import deepcopy

import pytest

from app.services.variety_universe import identity


@pytest.fixture(autouse=True)
def empty_normalization_cache():
    identity._fold_short_identity.cache_clear()
    yield
    identity._fold_short_identity.cache_clear()


@pytest.mark.parametrize('text', [None, '', 'Mérida', 'Me\u0301rida', 'ABB 135',
                                   'ABB135', 'FL 95-209a', '红颜', 'Berry Blue, LLC',
                                   "'Emerald'", 'A' * 257])
def test_cached_normalization_retains_the_existing_literal_transform(text):
    assert identity.fold_identity(text) == identity._fold(text or '')


def test_repeated_short_literals_avoid_work_without_retaining_large_source_text(monkeypatch):
    original = identity._fold
    calls = []
    def counted(value):
        calls.append(value)
        return original(value)
    monkeypatch.setattr(identity, '_fold', counted)
    for _ in range(100):
        assert identity.fold_identity('Mérida') == 'merida'
    assert calls == ['Mérida']
    long_source = 'source wording ' * 100
    identity.fold_identity(long_source)
    identity.fold_identity(long_source)
    assert calls == ['Mérida', long_source, long_source]
    assert identity._fold_short_identity.cache_info().currsize == 1
    for index in range(4200):
        identity.fold_identity(f'Literal selection {index}')
    assert identity._fold_short_identity.cache_info().currsize == 4096


def test_name_alias_code_and_crop_edits_are_not_cached_as_identity_decisions():
    variety = {'id': 'variety-example', 'name': 'Mérida', 'berry_ids': ['berry-strawberry'],
               'aliases': [], 'attributes': {'breeder_code': 'ABC-12'}}
    query = {'candidate_name': 'Mérida', 'berry_id': 'berry-strawberry'}
    before = deepcopy(variety)
    match = identity.resolve_identity(query, [variety])
    assert match['candidate_canonical_match'] == variety['id']
    assert match['auto_confirmed'] is False and variety == before
    # Editing the returned result cannot poison a later result.
    match['matches'].clear()
    assert identity.resolve_identity(query, [variety])['matches']
    variety['name'] = 'Other name'
    assert not identity.resolve_identity(query, [variety])['matches']
    variety['aliases'] = ['Mérida']
    assert identity.resolve_identity(query, [variety])['matches']
    variety['berry_ids'] = ['berry-blueberry']
    assert not identity.resolve_identity(query, [variety])['matches']
    code_query = {'candidate_name': 'ABC-12', 'berry_id': 'berry-blueberry'}
    assert identity.resolve_identity(code_query, [variety])['matches']
    variety['attributes']['breeder_code'] = 'ABC-13'
    assert not identity.resolve_identity(code_query, [variety])['matches']
