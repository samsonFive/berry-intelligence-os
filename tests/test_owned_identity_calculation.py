"""Pure calculations must retain matcher results, edits and context isolation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
from threading import Barrier

import pytest

from app.services import identity_read_model as lookup
from app.services.variety_universe import identity


def catalog():
    return [{'id':'v'+str(i),'entity_type':'variety','name':name,
             'berry_ids':['berry-blueberry'],'aliases':[],'attributes':{}}
            for i,name in enumerate(['Ocean Dawn','River Red','Pine Crown','Meadow Star'])]


@lookup.with_owned_identity_catalog
def matches(*, varieties, queries):
    return [identity.resolve_identity(query, varieties) for query in queries]


@pytest.mark.parametrize('edit', ['name','alias','berry','registration','order','remove'])
def test_next_calculation_reloads_edits_and_order(edit):
    rows = catalog()
    queries = [{'candidate_name':'Ocean Dawn'},{'registration_id':'R-12'}]
    first = matches(varieties=rows, queries=queries)
    first[0]['matches'].clear()
    if edit == 'name': rows[0]['name'] = 'Edited name'
    elif edit == 'alias':
        rows[0]['name'] = 'Edited name'
        rows[1]['aliases'].append('Ocean Dawn')
    elif edit == 'berry':
        rows[0]['berry_ids'] = ['berry-strawberry']
        queries[0]['berry_id'] = 'berry-blueberry'
    elif edit == 'registration': rows[1]['attributes']['rights_id'] = 'R-12'
    elif edit == 'order':
        rows[1]['aliases'] = ['Ocean Dawn']
        rows.reverse()
    else: rows.clear()
    before = deepcopy((rows, queries))
    assert matches(varieties=rows, queries=queries) == [identity.resolve_identity.__wrapped__(q, rows) for q in queries]
    assert (rows, queries) == before
    assert lookup._owned_catalog.get() is None and lookup._active_scope.get() is None


def test_unrelated_request_catalog_still_reads_in_place_edits():
    rows, other = catalog(), catalog()
    query = {'candidate_name':'Ocean Dawn'}
    @lookup.with_owned_identity_catalog
    def calculate(*, varieties):
        own = identity.resolve_identity(query, varieties)
        assert identity.resolve_identity(query, other) == own
        other[0]['name'] = 'Changed unrelated catalog'
        current = identity.resolve_identity(query, other)
        assert current == identity.resolve_identity.__wrapped__(query, other)
        assert not current['matches']
        return own
    assert calculate(varieties=rows)['matches']
    assert rows[0]['name'] == 'Ocean Dawn'


@pytest.mark.parametrize('unsupported', ['opaque','cycle','generator'])
def test_unsupported_input_keeps_original_objects_and_behavior(unsupported):
    class Opaque:
        def __deepcopy__(self, memo): raise AssertionError('Do not copy opaque metadata')
        def __str__(self): raise AssertionError('Do not coerce opaque metadata')
    rows = catalog()
    if unsupported == 'opaque': rows[0]['attributes']['analyst_metadata'] = Opaque()
    elif unsupported == 'cycle': rows[0]['attributes']['cycle'] = rows[0]
    original = iter(rows) if unsupported == 'generator' else rows
    consumed = []
    @lookup.with_owned_identity_catalog
    def calculate(*, varieties):
        assert varieties is original
        consumed.append(True)
        return identity.resolve_identity({'candidate_name':'Ocean Dawn'}, varieties)
    assert calculate(varieties=original)['matches'][0]['variety_id'] == 'v0'
    assert consumed == [True]


def test_opaque_query_preserves_original_coercion_count():
    class Name:
        def __init__(self): self.calls = 0
        def __str__(self):
            self.calls += 1
            return 'Ocean Dawn'
    rows = catalog()
    expected_name, current_name = Name(), Name()
    expected = identity.resolve_identity.__wrapped__({'candidate_name':expected_name}, rows)
    assert matches(varieties=rows, queries=[{'candidate_name':current_name}]) == [expected]
    assert current_name.calls == expected_name.calls == 1


@pytest.mark.parametrize('caller_edit', [False, True])
def test_unexpected_writes_cannot_return_a_stale_cached_result(caller_edit):
    rows = catalog()
    before = deepcopy(rows)
    @lookup.with_owned_identity_catalog
    def writer(*, varieties):
        result = identity.resolve_identity({'candidate_name':'Ocean Dawn'}, varieties)
        (rows if caller_edit else varieties)[0]['name'] = 'Keep actual caller edits'
        return result
    with pytest.raises(RuntimeError, match='modified its catalog'):
        writer(varieties=rows)
    if caller_edit:
        before[0]['name'] = 'Keep actual caller edits'
    assert rows == before
    assert lookup._owned_catalog.get() is None and lookup._active_scope.get() is None


def test_nested_owned_calculations_and_threads_restore_context():
    barrier = Barrier(2)
    @lookup.with_owned_identity_catalog
    def outer(*, varieties, name):
        current = lookup._owned_catalog.get()
        barrier.wait(timeout=10)
        assert matches(varieties=catalog(), queries=[{'candidate_name':'River Red'}])[0]['matches']
        assert lookup._owned_catalog.get() is current
        return identity.resolve_identity({'candidate_name':name}, varieties)
    def run(name):
        rows = catalog()
        rows[0]['name'] = name
        result = outer(varieties=rows, name=name)
        assert lookup._owned_catalog.get() is None and lookup._active_scope.get() is None
        return result['matches'][0]['variety_name']
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, ['First calculation','Second calculation'])) == ['First calculation','Second calculation']


def test_exception_restores_existing_request_scope():
    @lookup.with_owned_identity_catalog
    def fail(*, varieties): raise ValueError('Fixture failure')
    with lookup.identity_read_model_scope() as existing:
        with pytest.raises(ValueError, match='Fixture failure'): fail(varieties=catalog())
        assert lookup._active_scope.get() is existing and lookup._owned_catalog.get() is None


@pytest.mark.parametrize('decision', ['none','rejected','distinct','confirmed_same'])
@pytest.mark.parametrize('include_candidates', [False, True])
@pytest.mark.parametrize('selected', [None, {'source-first'}, {'not-selected'}])
def test_complete_portfolios_retain_human_decisions_conflicts_and_source_scope(decision, include_candidates, selected):
    from app.services import variety_portfolio_coverage as portfolio
    source = {'id':'source-first','title':'Fictional source','url':'https://example.test/portfolio',
              'company_ids':['company-first'],'berry_ids':['berry-blueberry'],
              'checked_on':'2026-11-04','observed_at':'2026-11-04T12:00:00+00:00',
              'capture_status':'names_enumerated','source_type':'breeder_catalog',
              'review_state':'unreviewed','review_warnings':['Keep this original qualification'],
              'names':[{'candidate_name':'Ocean Dawn','berry_id':'berry-blueberry'},
                       {'candidate_name':'Shared trial','denomination':'ST-1','berry_id':'berry-blueberry'}]}
    second = {**deepcopy(source),'id':'source-second',
              'names':[{'candidate_name':'Shared trial','denomination':'ST-2','berry_id':'berry-blueberry'}]}
    saved = [] if decision == 'none' else [{
        'id':'vcand-human','candidate_name':'Ocean Dawn','berry_id':'berry-blueberry',
        'status':'rejected' if decision=='rejected' else 'reviewed',
        'human_gated':True,'identity_state':decision,'candidate_canonical_match':'v0',
        'review_notes':'Keep the analyst decision','knowledge':{'notes':'Literal user edit'}}]
    values = {'sources':[source,second],'varieties':catalog(),
              'entities':[{'id':'company-first','entity_type':'company','name':'Fictional company'}],
              'candidates':saved,'today':date(2026,11,4),
              'source_ids':selected,'include_candidates':include_candidates}
    before = deepcopy(values)
    # Bypass only the pre-existing complete-input memo. The raw implementation
    # serves as the complete-value oracle for the owned pure calculation.
    owned = portfolio.reconcile_portfolios.__wrapped__
    original = owned.__wrapped__
    expected = original(**values)
    assert owned(**values) == expected
    assert values == before
    assert lookup._owned_catalog.get() is None and lookup._active_scope.get() is None
