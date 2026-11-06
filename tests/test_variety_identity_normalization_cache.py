from copy import deepcopy
from hashlib import sha256

import pytest

from app.services.variety_universe import identity, registry_import
from app.services.variety_universe.candidates import apply_identity_decision, persist_variety_candidates


@pytest.fixture(autouse=True)
def empty_normalization_cache():
    identity._fold_short_identity.cache_clear()
    yield
    identity._fold_short_identity.cache_clear()


@pytest.mark.parametrize('text', [None, '', 'Mérida', 'Me\u0301rida', 'ABB 135',
                                   'ABB135', 'FL 95-209a', 'Berry Blue, LLC',
                                   "'Emerald'", 'A' * 257])
def test_cached_normalization_retains_the_existing_literal_transform(text):
    assert identity.fold_identity(text) == identity._fold(text or '')


def test_original_script_survives_exact_matching_without_transliteration():
    assert identity.fold_identity('蓝闺蜜') == '蓝闺蜜'
    assert identity.fold_identity('蓝闺蜜 １') == '蓝闺蜜 1'
    assert identity.fold_identity('北斗星 １') == '北斗星 1'
    variety = {'id': 'variety-literal', 'name': '蓝闺蜜', 'berry_ids': ['berry-blueberry'], 'aliases': []}
    result = identity.resolve_identity({'candidate_name': '蓝闺蜜', 'berry_id': 'berry-blueberry'}, [variety])
    assert result['candidate_canonical_match'] == variety['id'] and not result['auto_confirmed']
    for name, berry in [('北斗星', 'berry-blueberry'), ('Lan Guimi', 'berry-blueberry'), ('蓝闺蜜', 'berry-strawberry')]:
        assert not identity.resolve_identity({'candidate_name': name, 'berry_id': berry}, [variety])['matches']


def test_registry_replay_keeps_saved_legacy_id_and_separates_a_former_collision(tmp_path):
    first = {'candidate_name': '蓝闺蜜 1', 'berry_id': 'berry-blueberry', 'source_id': 'fixture-register',
             'source_url': 'https://example.test/registry', 'jurisdiction': 'CN'}
    second = {**first, 'candidate_name': '北斗星 1'}
    legacy_seed = 'cn||1|berry blueberry|fixture register'
    legacy_id = 'vcand-' + sha256(legacy_seed.encode()).hexdigest()[:12]
    saved = registry_import.build_candidate({**first, 'id': legacy_id}, varieties=[])
    saved = apply_identity_decision(saved, decision='distinct', reviewer='Fixture reviewer', notes='Preserve my edit')
    path, = persist_variety_candidates([saved], inbox_dir=tmp_path)
    original = path.read_bytes()
    incoming = registry_import.import_registry_rows([first, second], varieties=[], inbox_dir=tmp_path)
    assert incoming['candidates'][0]['id'] == legacy_id and path.read_bytes() == original
    assert incoming['written_ids'] == [registry_import.candidate_id_for(second)]
    assert incoming['written_ids'][0] != legacy_id
    again = registry_import.import_registry_rows([first, second], varieties=[], inbox_dir=tmp_path)
    assert again['written_count'] == 0 and path.read_bytes() == original


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
