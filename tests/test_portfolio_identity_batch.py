"""Matching reuse must never retain human decisions or miss edited identities."""
from copy import deepcopy
from datetime import date

import pytest

from app.services import variety_portfolio_coverage as portfolio
from app.services.presentation_memo import json_call_memo


@pytest.fixture
def isolated_batch(monkeypatch):
    original = portfolio._portfolio_identity_results.__wrapped__
    monkeypatch.setattr(portfolio, '_portfolio_identity_results', json_call_memo(original))


def inputs():
    return {
        'sources': [{'id': 'portfolio-offline-batch', 'title': 'Offline test portfolio',
            'url': 'https://example.test/batch', 'company_ids': [],
            'berry_ids': ['berry-blueberry'], 'checked_on': '2026-11-03',
            'capture_status': 'names_enumerated', 'source_type': 'breeder_catalog',
            'review_state': 'unreviewed', 'names': [
                {'candidate_name': 'Offline Match', 'berry_id': 'berry-blueberry'}]}],
        'varieties': [{'id': 'variety-offline-batch', 'entity_type': 'variety',
            'name': 'Offline Match', 'aliases': [], 'berry_ids': ['berry-blueberry']}],
        'entities': [], 'candidates': [], 'today': date(2026, 11, 3),
    }


def rebuild(values, **changes):
    # Exercise a real outer-cache miss without resetting the inner match memo.
    return portfolio.reconcile_portfolios.__wrapped__(**{**values, **changes})


def test_reused_match_reapplies_rejection_confirmation_and_user_notes(isolated_batch, monkeypatch):
    values = inputs()
    calls = []
    from app.services import identity_read_model
    original = identity_read_model.resolve_identity_batch
    def observed(queries, varieties):
        calls.append(deepcopy(queries))
        return original(queries, varieties)
    monkeypatch.setattr(identity_read_model, 'resolve_identity_batch', observed)
    initial = rebuild(values)
    assert initial[0][0]['names'][0]['catalog_id'] == 'variety-offline-batch'
    saved = {'id': 'vcand-offline-saved', 'candidate_name': 'Offline Match',
        'berry_id': 'berry-blueberry', 'status': 'rejected', 'human_gated': True,
        'identity_state': 'rejected', 'review_notes': 'Keep my decision',
        'knowledge': {'notes': 'An analyst edit'}}
    before = deepcopy(saved)
    rejected = rebuild(values, candidates=[saved])
    assert len(calls) == 1
    assert rejected[0][0]['names'][0]['status'] == 'previously_rejected'
    assert rejected[0][0]['names'][0]['catalog_id'] is None
    assert rejected[1][0]['review_notes'] == saved['review_notes']
    assert saved == before
    confirmed = {**saved, 'status': 'reviewed', 'identity_state': 'confirmed_same',
                 'candidate_canonical_match': 'variety-offline-batch'}
    assert rebuild(values, candidates=[confirmed])[0][0]['names'][0]['catalog_id'] == 'variety-offline-batch'
    assert len(calls) == 1


@pytest.mark.parametrize('edit', ['name', 'alias', 'berry', 'denomination', 'registration', 'order', 'remove'])
def test_current_catalog_and_query_edits_match_uncached_resolver(isolated_batch, edit):
    values = inputs()
    query = {key: values['sources'][0]['names'][0].get(key, '') for key in
             ('candidate_name', 'denomination', 'breeder_code', 'berry_id')}
    arguments = {'queries': [[query]], 'varieties': values['varieties']}
    first = portfolio._portfolio_identity_results(**arguments)
    # Mutate both returned nested graphs and the original catalog/query in place.
    first[0][0]['matches'].clear()
    catalog = values['varieties']
    if edit == 'name':
        catalog[0]['name'] = 'Different'
    elif edit == 'alias':
        catalog[0]['name'] = 'Different'
        catalog[0]['aliases'].append('Offline Match')
    elif edit == 'berry':
        catalog[0]['berry_ids'][:] = ['berry-strawberry']
    elif edit == 'denomination':
        query['candidate_name'] = 'Different'
        query['denomination'] = 'Offline Match'
    elif edit == 'registration':
        catalog[0]['attributes'] = {'application_number': 'Offline 101'}
        query['breeder_code'] = 'Offline 101'
    elif edit == 'order':
        catalog.insert(0, {**deepcopy(catalog[0]), 'id': 'variety-offline-second'})
    else:
        catalog.clear()
    current = portfolio._portfolio_identity_results(**arguments)
    assert current == portfolio._portfolio_identity_results.__wrapped__(**arguments)


def test_reused_matches_keep_current_warnings_company_context_and_selection(isolated_batch):
    values = inputs()
    original = deepcopy(values)
    rebuild(values)
    changed = deepcopy(values['sources'])
    changed[0]['review_warnings'] = ['Current attribution needs review']
    changed[0]['names'][0]['portfolio_context'] = 'Current source wording'
    changed[0]['names'][0]['source_company_ids'] = ['company-offline']
    changed[0]['names'][0]['source_company_context'] = 'Printed association only'
    entities = [{'id': 'company-offline', 'name': 'Current company name', 'entity_type': 'company'}]
    result = rebuild(values, sources=changed, entities=entities)
    assert result[0][0]['review_warnings'] == ['Current attribution needs review']
    assert result[0][0]['names'][0]['portfolio_context'] == 'Current source wording'
    assert result[0][0]['companies'][0]['name'] == 'Current company name'
    assert rebuild(values, source_ids={'different-source'}) == ([], [])
    assert rebuild(values, include_candidates=False)[1] == []
    assert values == original


def test_returned_match_edit_does_not_poison_later_rebuild(isolated_batch):
    values = inputs()
    query = {'candidate_name': 'Offline Match', 'denomination': '', 'breeder_code': '', 'berry_id': 'berry-blueberry'}
    arguments = {'queries': [[query]], 'varieties': values['varieties']}
    first = portfolio._portfolio_identity_results(**arguments)
    first[0][0]['matches'][0]['variety_id'] = 'caller-edit'
    current = portfolio._portfolio_identity_results(**arguments)
    assert current[0][0]['matches'][0]['variety_id'] == 'variety-offline-batch'
    assert rebuild(values)[0][0]['names'][0]['catalog_id'] == 'variety-offline-batch'


def test_owned_batch_reads_next_edits_and_preserves_query_order():
    from app.services.identity_read_model import resolve_identity_batch
    from app.services.variety_universe.identity import resolve_identity
    catalog = [
        {'id': 'v' + str(i), 'name': name, 'entity_type': 'variety', 'berry_ids': ['berry-blueberry']}
        for i, name in enumerate(['First', 'Second', 'Third', 'Fourth'])]
    queries = [{'candidate_name': name} for name in ['Second', 'First', 'Second']]
    before = deepcopy((queries, catalog))
    assert resolve_identity_batch(queries, catalog) == [resolve_identity.__wrapped__(q, catalog) for q in queries]
    assert (queries, catalog) == before
    catalog[1]['name'] = 'Edited'
    catalog[0]['aliases'] = ['Second']
    queries.reverse()
    assert resolve_identity_batch(queries, catalog) == [resolve_identity.__wrapped__(q, catalog) for q in queries]


def test_batch_opaque_values_keep_original_coercion_and_errors():
    from app.services.identity_read_model import resolve_identity_batch
    from app.services.variety_universe.identity import resolve_identity
    class Opaque:
        def __init__(self): self.calls = 0
        def __str__(self):
            self.calls += 1
            return 'Opaque match'
    catalog = [{'id': str(i), 'name': 'Opaque match', 'berry_ids': ['berry-blueberry']} for i in range(4)]
    original, current = Opaque(), Opaque()
    expected = resolve_identity.__wrapped__({'candidate_name': original}, catalog)
    assert resolve_identity_batch([{'candidate_name': current}], catalog) == [expected]
    assert current.calls == original.calls
