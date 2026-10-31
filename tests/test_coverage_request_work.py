"""Coverage reuses request work without hiding changed sources or human decisions."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest

from app.services import variety_portfolio_coverage as portfolios
from app.services.request_corpus import RequestCorpus, bind_request_corpus, reset_request_corpus
from app.services.variety_profile_coverage import profile_field_coverage


def source(names):
    return dict(id='portfolio-request-work', title='Literal source names',
        url='https://example.test/releases', company_ids=[], berry_ids=['berry-blueberry'],
        checked_on='2026-10-31', capture_status='names_enumerated', source_type='breeder_catalog',
        review_state='unreviewed', enumerated_scope='Named releases only', limitations='Not comprehensive',
        names=[dict(candidate_name=name, berry_id='berry-blueberry') for name in names])


def store(root, names):
    path = root/'imports/variety-portfolio-observations-2026-10-31/observations.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(kind='unreviewed_portfolio_name_observations',
                                   sources=[source(names)])), encoding='utf-8')
    return path


def in_request(root, callback):
    token = bind_request_corpus(RequestCorpus(root, root/'schemas'))
    try:
        return callback()
    finally:
        reset_request_corpus(token)


def test_source_validation_runs_once_per_request_and_next_request_sees_edits(tmp_path, monkeypatch):
    store(tmp_path, ['Before'])
    loader = portfolios._load_portfolio_observations
    calls = []
    def counted(root):
        calls.append(root)
        return loader(root)
    monkeypatch.setattr(portfolios, '_load_portfolio_observations', counted)
    def request():
        first = portfolios.load_portfolio_observations(tmp_path)
        store(tmp_path, ['After'])
        assert portfolios.load_portfolio_observations(tmp_path) == first
        assert first[0]['names'][0]['candidate_name'] == 'Before'
    in_request(tmp_path, request)
    assert len(calls) == 1
    updated = in_request(tmp_path, lambda: portfolios.load_portfolio_observations(tmp_path))
    assert len(calls) == 2
    assert updated[0]['names'][0]['candidate_name'] == 'After'
    assert updated[0]['review_state'] == 'unreviewed'


def test_invalid_then_repaired_source_is_revalidated_without_cached_success(tmp_path):
    path = store(tmp_path, ['Before'])
    in_request(tmp_path, lambda: portfolios.load_portfolio_observations(tmp_path))
    path.write_text('{"kind":"wrong"}', encoding='utf-8')
    with pytest.raises(ValueError, match='failed validation'):
        in_request(tmp_path, lambda: portfolios.load_portfolio_observations(tmp_path))
    store(tmp_path, ['Repaired'])
    assert in_request(tmp_path, lambda: portfolios.load_portfolio_observations(tmp_path))[0]['names'][0]['candidate_name'] == 'Repaired'


def test_empty_request_is_cached_but_cli_and_other_dataset_are_not(tmp_path, monkeypatch):
    empty, other = tmp_path/'empty', tmp_path/'other'
    store(other, ['Other'])
    loader = portfolios._load_portfolio_observations
    calls = []
    def counted(root):
        calls.append(root)
        return loader(root)
    monkeypatch.setattr(portfolios, '_load_portfolio_observations', counted)
    def request():
        assert portfolios.load_portfolio_observations(empty) == []
        assert portfolios.load_portfolio_observations(empty) == []
        assert portfolios.load_portfolio_observations(other)[0]['names'][0]['candidate_name'] == 'Other'
        store(other, ['Changed other dataset'])
        assert portfolios.load_portfolio_observations(other)[0]['names'][0]['candidate_name'] == 'Changed other dataset'
    in_request(empty, request)
    assert calls == [empty, other, other]
    store(empty, ['CLI first'])
    assert portfolios.load_portfolio_observations(empty)[0]['names'][0]['candidate_name'] == 'CLI first'
    store(empty, ['CLI second'])
    assert portfolios.load_portfolio_observations(empty)[0]['names'][0]['candidate_name'] == 'CLI second'


@pytest.mark.parametrize('selected', [None, {'portfolio-request-work'}])
def test_source_only_projection_keeps_conflicts_and_saved_human_decisions(selected):
    observations = source(['Rejected', 'Separate', 'Confirmed', 'Wrong crop', 'New', 'New'])
    observations['names'] += [dict(candidate_name='Shared', denomination=code,
                                  trade_name='Shared', berry_id='berry-blueberry') for code in ['CODE-1', 'CODE-2']]
    conflict = source([])
    conflict.update(id='portfolio-conflicting-pair', names=[dict(candidate_name='CODE-1',
        denomination='CODE-1', trade_name='Different label', berry_id='berry-blueberry')])
    varieties = [dict(id='variety-confirmed', entity_type='variety', name='Canonical', berry_ids=['berry-blueberry'])]
    candidates = [dict(id='candidate-'+name, candidate_name=name, berry_id='berry-blueberry',
                      status=status, identity_state=state, human_gated=True,
                      candidate_canonical_match='variety-confirmed', review_notes='Keep user decision')
        for name, status, state in [('Rejected','rejected','rejected'),
                                   ('Separate','reviewed','distinct'), ('Confirmed','reviewed','confirmed_same')]]
    candidates.append(dict(id='wrong-crop', candidate_name='Wrong crop', berry_id='berry-raspberry',
                           human_gated=True, identity_state='confirmed_same', candidate_canonical_match='variety-confirmed'))
    inputs = dict(sources=[observations, conflict], varieties=varieties, entities=varieties,
                  candidates=candidates, source_ids=selected, today=date(2026,10,31))
    before = deepcopy(inputs)
    expected, visible = portfolios.reconcile_portfolios(**inputs)
    rows, omitted = portfolios.reconcile_portfolios(**inputs, include_candidates=False)
    assert rows == expected and omitted == [] and visible
    assert inputs == before
    names = rows[0]['names']
    assert [n['status'] for n in names[:4]] == ['previously_rejected','distinct_awaiting_catalog','catalog_match','needs_review']
    assert names[4]['candidate_id'] == names[5]['candidate_id']
    assert all(n['status']=='needs_review' and n['identity_notes'] for n in names[6:])
    assert next(c for c in visible if c['id']=='candidate-Rejected')['review_notes'] == 'Keep user decision'


def test_field_inventory_keeps_complete_model_when_candidate_projection_is_omitted(monkeypatch):
    v = dict(id='variety-confirmed', entity_type='variety', name='Named cultivar', berry_ids=['berry-blueberry'],
             status='unverified', attributes={'patent_number':'US PP99,999'})
    observed = source(['Named cultivar'])
    observed['source_type'] = 'plant_patent'
    inputs = dict(varieties=[v], entities=[v], relationships=[], published_evidence=[],
                  portfolio_sources=[observed], candidates=[], profiles={v['id']:{'revision':7}})
    before = deepcopy(inputs)
    calculate = portfolios.reconcile_portfolios
    import app.services.variety_profile_coverage as fields
    # Reference behavior always builds the complete projection, as before.
    def full(**kwargs):
        kwargs.pop('include_candidates', None)
        return calculate(**kwargs)
    monkeypatch.setattr(fields, 'reconcile_portfolios', full)
    expected = profile_field_coverage(**inputs)
    monkeypatch.setattr(fields, 'reconcile_portfolios', calculate)
    actual = profile_field_coverage(**inputs)
    assert actual == expected and inputs == before
    assert actual['rows'][0]['rights_refs'] == 0
    assert actual['rows'][0]['unreviewed_rights_refs'] == 1
    assert actual['rows'][0]['status'] == 'Unverified'


def test_every_saved_source_row_is_identical_in_source_only_projection():
    root = Path(__file__).resolve().parents[1]/'data'
    sources = portfolios.load_portfolio_observations(root)
    varieties = [json.loads(p.read_text(encoding='utf-8'))
                 for p in sorted((root/'entities/varieties').glob('*.json'))]
    before = deepcopy((sources, varieties))
    expected, candidates = portfolios.reconcile_portfolios(sources=sources,
        varieties=varieties, entities=varieties, candidates=[])
    # The field inventory receives candidates already enriched by Universe.
    complete, _ = portfolios.reconcile_portfolios(sources=sources,
        varieties=varieties, entities=varieties, candidates=candidates)
    rows, omitted = portfolios.reconcile_portfolios(sources=sources,
        varieties=varieties, entities=varieties, candidates=candidates, include_candidates=False)
    assert rows == complete == expected and omitted == []
    assert len(rows) == len(sources) and len(rows) > 500
    assert (sources, varieties) == before
