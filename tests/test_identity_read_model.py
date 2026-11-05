"""Indexing must preserve every matcher decision, order and current edit."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from itertools import product
from threading import Barrier

import pytest

from app.services import identity_read_model as lookup
from app.services.variety_universe import identity


def variety(key, name, berry='berry-blueberry', **attrs):
    return {'id': key, 'entity_type': 'variety', 'name': name,
            'berry_ids': [berry], 'aliases': [], 'attributes': attrs}


def catalog():
    rows = [variety('blue-a', 'Mérida Dawn', breeder_code='AA-12', patent_number='PP12'),
            variety('blue-b', 'Merida Dawn'),
            variety('straw', 'Victoria', 'berry-strawberry'),
            variety('black', 'Victoria', 'berry-blackberry'),
            variety('blue-c', 'Example Tide', trade_name='Trial Star', rights_id='right-7'),
            variety('ignored', 'Mérida Dawn')]
    rows[0]['aliases'] = ['Dawn', 'Sky Harbour']
    rows[5]['entity_type'] = 'company'
    return rows


QUERIES = [
    {'candidate_name': name} for name in ['', 'AB', 'Mérida Dawn', 'Me\u0301rida Dawn',
                                         'Victoria', 'Sky Harbour', 'Trial Star', 'AA-12',
                                         'Report on Sky Harbour planting', 'Harbour Sky', 'Unknown']
] + [
    {'candidate_name': 'Trial Star', 'registration_id': 'PP12'},
    {'candidate_name': 'Other', 'registration': {'grant_number': 'right-7'}},
    {'candidate_name': 'Other', 'aliases': ['Trial Star', 'Mérida Dawn']},
    {'denomination': 'Trial Star', 'trade_name': 'Mérida Dawn', 'breeder_code': 'AA-12'},
    {'registration_id': 'PP12'}, {},
]


@pytest.mark.parametrize('query,berry,order', list(product(QUERIES,
    ['', 'berry-blueberry', 'berry-strawberry', 'berry-blackberry', 'berry-raspberry'],
    ['normal', 'reversed', 'duplicate'])))
@pytest.mark.parametrize('calculation', [False, True])
def test_complete_results_match_unindexed_oracle(query, berry, order, calculation):
    rows = catalog()
    if order == 'reversed':
        rows.reverse()
    elif order == 'duplicate':
        rows.insert(1, deepcopy(rows[0]))
    query = {**query, 'berry_id': berry}
    before = deepcopy(rows)
    expected = identity.resolve_identity.__wrapped__(query, rows)
    if calculation:
        @lookup.with_owned_identity_catalog
        def calculate(*, varieties):
            return identity.resolve_identity(query, varieties)
        actual = calculate(varieties=rows)
    else:
        with lookup.identity_read_model_scope():
            actual = identity.resolve_identity(query, rows)
    assert actual == expected
    assert lookup.resolve_identity_batch([query], rows) == [expected]
    assert actual['auto_confirmed'] is False
    assert rows == before


def test_wrong_crop_exact_does_not_hide_valid_contiguous_overlap():
    rows = [variety('wrong', 'Field Trial Red', 'berry-strawberry'),
            variety('right', 'Trial Red'), *catalog()]
    query = {'candidate_name': 'Field Trial Red', 'berry_id': 'berry-blueberry'}
    with lookup.identity_read_model_scope():
        result = identity.resolve_identity(query, rows)
    assert result['identity_state'] == identity.STATE_UNKNOWN
    assert result['matches'] == identity.resolve_identity.__wrapped__(query, rows)['matches']
    assert result['matches'][0]['variety_id'] == 'right'


@pytest.mark.parametrize('field,role', identity._IDENTITY_ATTRIBUTE_ROLES)
def test_all_identity_attribute_roles_retain_original_result(field, role):
    rows = [variety('target', 'Other', **{field: 'Fixture identity'}), *catalog()]
    with lookup.identity_read_model_scope():
        result = identity.resolve_identity({'candidate_name': 'Fixture identity'}, rows)
    assert result['matches'][0]['matched_on'] == 'candidate_name->' + role


def test_all_registration_fields_retain_precedence_and_sorted_identifier():
    rows = [variety('target', 'Other', **{field: 'B 22' for field in identity._REGISTRATION_ATTRIBUTES}),
            variety('name', 'Candidate Name'), *catalog()]
    query = {'candidate_name': 'Candidate Name', 'registration_id': 'B 22'}
    with lookup.identity_read_model_scope():
        result = identity.resolve_identity(query, rows)
    assert result == identity.resolve_identity.__wrapped__(query, rows)
    assert result['matches'][0]['reason'] == 'same_registration_identifier'
    assert result['candidate_canonical_match'] == 'target'


def test_same_scope_in_place_edits_are_visible_and_results_are_not_shared():
    rows = catalog()
    query = {'candidate_name': 'Mérida Dawn', 'berry_id': 'berry-blueberry'}
    with lookup.identity_read_model_scope() as scope:
        first = identity.resolve_identity(query, rows)
        first['matches'].clear()
        assert identity.resolve_identity(query, rows)['matches']
        rows[0]['name'] = 'Updated cultivar'
        rows[1]['name'] = 'Changed name'
        assert not identity.resolve_identity(query, rows)['matches']
        rows[0]['aliases'].append('Mérida Dawn')
        assert identity.resolve_identity(query, rows)['matches'][0]['matched_on'].endswith('alias')
        rows[0]['berry_ids'][:] = ['berry-strawberry']
        assert not identity.resolve_identity(query, rows)['matches']
        rows[0]['berry_ids'][:] = ['berry-blueberry']
        code = {'registration_id': 'PP12', 'berry_id': 'berry-blueberry'}
        assert identity.resolve_identity(code, rows)['matches']
        rows[0]['attributes']['patent_number'] = 'PP13'
        assert not identity.resolve_identity(code, rows)['matches']
        assert scope.catalog_count == 1


def test_whitespace_in_display_name_and_input_order_remain_exact():
    rows = [variety('target', '  Example Name  '), *catalog()]
    query = {'candidate_name': 'Example Name'}
    with lookup.identity_read_model_scope():
        assert identity.resolve_identity(query, rows)['matches'][0]['variety_name'] == '  Example Name  '
        rows.reverse()
        assert identity.resolve_identity(query, rows) == identity.resolve_identity.__wrapped__(query, rows)


def test_next_request_reusing_the_same_objects_rebuilds_from_current_data():
    rows = catalog()
    with lookup.identity_read_model_scope() as first:
        assert identity.resolve_identity({'candidate_name': 'Mérida Dawn'}, rows)['matches']
    rows[0]['name'] = rows[1]['name'] = 'New shared edit'
    with lookup.identity_read_model_scope() as second:
        assert not identity.resolve_identity({'candidate_name': 'Mérida Dawn'}, rows)['matches']
        assert identity.resolve_identity({'candidate_name': 'New shared edit'}, rows)['matches']
        assert second is not first


def test_catalog_limit_falls_back_without_omitting_results(monkeypatch):
    monkeypatch.setattr(lookup, '_MAX_CATALOGS', 1)
    first, second = catalog(), catalog()
    second[0]['name'] = 'Different input'
    with lookup.identity_read_model_scope() as scope:
        identity.resolve_identity({'candidate_name': 'Dawn'}, first)
        result = identity.resolve_identity({'candidate_name': 'Different input'}, second)
        assert result == identity.resolve_identity.__wrapped__({'candidate_name': 'Different input'}, second)
        assert scope.catalog_count == 1


def test_small_catalog_and_non_list_input_keep_original_path():
    query = {'candidate_name': 'Mérida Dawn'}
    with lookup.identity_read_model_scope() as scope:
        assert identity.resolve_identity(query, catalog()[:2]) == identity.resolve_identity.__wrapped__(query, catalog()[:2])
        assert identity.resolve_identity(query, iter(catalog())) == identity.resolve_identity.__wrapped__(query, iter(catalog()))
        assert scope.catalog_count == 0


def test_unsupported_wrong_crop_record_does_not_create_a_new_error():
    rows = catalog()
    rows.append({'id': 'bad', 'name': 'Bad record', 'berry_ids': ['berry-strawberry'], 'attributes': 'unsupported'})
    query = {'candidate_name': 'Mérida Dawn', 'berry_id': 'berry-blueberry'}
    with lookup.identity_read_model_scope() as scope:
        assert identity.resolve_identity(query, rows) == identity.resolve_identity.__wrapped__(query, rows)
        assert scope.catalog_count == 0


def test_unsupported_name_keeps_original_object_and_coercion_count():
    class Name:
        calls = 0
        def __str__(self):
            self.calls += 1
            return 'Opaque name'
    name = Name()
    rows = [variety('opaque', name), *catalog()]
    with lookup.identity_read_model_scope():
        result = identity.resolve_identity({'candidate_name': 'Opaque name'}, rows)
    assert result['matches'][0]['variety_name'] is name
    assert name.calls == 1


def test_thread_scopes_are_separate_and_nested_scope_is_reused():
    barrier = Barrier(2)
    def run(name):
        rows = [variety('same-id', name), *catalog()]
        with lookup.identity_read_model_scope() as outer:
            with lookup.identity_read_model_scope() as inner:
                assert inner is outer
                barrier.wait(timeout=10)
                result = identity.resolve_identity({'candidate_name': name}, rows)
                return id(outer), result['matches'][0]['variety_name']
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = list(pool.map(run, ['First analyst input', 'Second analyst input']))
    assert a[0] != b[0]
    assert [a[1], b[1]] == ['First analyst input', 'Second analyst input']
    assert lookup._active_scope.get() is None


def test_candidate_alias_iterator_is_consumed_only_by_original_matcher():
    rows = catalog()
    query = {'aliases': iter(['Mérida Dawn'])}
    expected = identity.resolve_identity.__wrapped__({'aliases': iter(['Mérida Dawn'])}, rows)
    with lookup.identity_read_model_scope() as scope:
        assert identity.resolve_identity(query, rows) == expected
        assert scope.catalog_count == 0


def test_opaque_candidate_name_is_coerced_only_once():
    class Name:
        calls = 0
        def __str__(self):
            self.calls += 1
            return 'Mérida Dawn'
    name = Name()
    with lookup.identity_read_model_scope() as scope:
        result = identity.resolve_identity({'candidate_name': name}, catalog())
        assert scope.catalog_count == 0
    assert result['matches']
    assert name.calls == 1


def test_equal_numbers_of_different_types_keep_original_identity_strings():
    rows = catalog()
    rows[0]['aliases'] = [1]
    with lookup.identity_read_model_scope() as scope:
        for value in (1, True, 1.0):
            rows[0]['aliases'][0] = value
            query = {'candidate_name': str(value)}
            assert identity.resolve_identity(query, rows) == identity.resolve_identity.__wrapped__(query, rows)
        assert scope.catalog_count == 0
