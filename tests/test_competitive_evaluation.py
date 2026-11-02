import copy

import pytest

from app.services import competitive_evaluation as ce
from app.services.living_workspaces import Store, Conflict


@pytest.fixture
def research(tmp_path):
    entities = {'company-one': {'id': 'company-one'}, 'company-two': {'id': 'company-two'}}
    scope = {'entity_id': 'company-one', 'peer_role': 'technology_provider', 'berry_id': 'berry-strawberry',
             'capability_id': 'technology.maturity', 'destination_scope': 'unspecified', 'origin_scope': 'United Kingdom',
             'program_or_variety': 'Named platform', 'period_start': '2026', 'period_end': '2026',
             'use_system': 'fresh', 'rubric_version': ce.catalogue()['rubric_version']}
    fields = {k: v for k, v in scope.items() if k not in {'berry_id', 'rubric_version', 'use_system'}}
    fields.update(berry_scope=scope['berry_id'], source_ids='B16-S001', production_system_fresh_processing='fresh',
                  value_or_statement='Named technical design; no commercial adoption claimed')
    payload = {'records': [
        {'record_kind': 'observation', 'local_id': 'B16-O001', 'fields': fields},
        {'record_kind': 'source', 'local_id': 'B16-S001', 'fields': {'source_id': 'B16-S001',
         'original_url': 'https://example.org/design', 'source_family': 'developer'}},
    ]}
    checks = {'B16-S001': {'status': 'inspected_supports_claim', 'support': 'Original named design inspected', 'checked_at': '2026-10-30'}}
    report = ce.import_return(tmp_path, batch_id='B16', payload=payload, original_sha256='a'*64,
                              entities=entities, source_checks=checks)
    records = Store(tmp_path).rows('competitive_record')
    source_id = next(r['id'] for r in records if r['kind'] == 'source')
    observation_id = next(r['id'] for r in records if r['kind'] == 'observation')
    cap = next(c for c in ce.catalogue()['capabilities'] if c['capability_id'] == scope['capability_id'])
    proof = {'1': {'requirement': cap['anchors'][0]['requires'], 'all_conditions_supported': True,
                   'source_ids': [source_id], 'explanation': 'Named technical design is documented; no higher anchor is supported'}}
    kwargs = dict(scope=scope, observation_ids=[observation_id], checks=proof, confidence='medium',
                  rationale='Technical concept only, attributed to developer', entities=entities,
                  confidence_details={k: 'Single original, scope matched; limitations retained' for k in
                                      ['directness', 'independence', 'recency', 'scope_fit', 'methodology', 'agreement']})
    return tmp_path, entities, scope, payload, checks, report, kwargs


def test_real_return_structure_reimport_is_idempotent_and_unknown_is_unscored(research):
    inbox, entities, scope, payload, checks, report, _ = research
    repeated = ce.import_return(inbox, batch_id='B16', payload=payload, original_sha256='a'*64, entities=entities, source_checks=checks)
    assert repeated['replayed']
    assert len(Store(inbox).rows('competitive_record')) == 2
    assert Store(inbox).get(ce.scope_key(scope))['rating'] == 'unknown'
    assert not (inbox / 'evidence').exists()


def test_bad_rows_visible_without_losing_good_rows(research):
    inbox, entities, _, payload, checks, _, _ = research
    payload['records'].extend([
        {'record_kind': 'observation', 'local_id': 'bad', 'fields': {'entity_id': 'guessed', 'capability_id': 'innovation'}},
        {'record_kind': 'source', 'local_id': 'malformed', 'fields': {'original_url': 'file:///private'}},
    ])
    report = ce.import_return(inbox, batch_id='B16', payload=payload, original_sha256='b'*64, entities=entities, source_checks=checks)
    assert report['counts']['unresolved'] == 2
    assert report['counts']['accepted_structure'] == 2
    assert len(report['issues']) == 2


def test_routine_reimport_preserves_inspection_and_source_change_flags_review(research):
    inbox, entities, _, payload, _, _, kwargs = research
    assessment = ce.apply_anchor(inbox, **kwargs)
    ce.correct_assessment(inbox, assessment_id=assessment['id'], expected_version=0, mode='reviewed',
                          rating=1, rationale='Inspected', actor='test analyst')
    ce.import_return(inbox, batch_id='B16', payload=payload, original_sha256='a'*64, entities=entities)
    source = next(r for r in Store(inbox).rows('competitive_record') if r['kind'] == 'source')
    assert source['verification']['status'] == 'inspected_supports_claim'
    source['verification']['support'] = 'Changed support requiring reconsideration'
    store = Store(inbox)
    with store.transaction() as db:
        store.put(db, 'competitive_record', source, 'test', expected=source['version'])
    effective = ce.effective_assessment(Store(inbox), Store(inbox).get(assessment['id']))
    assert effective['new_evidence'] and effective['status'] == 'reviewed'


def test_scope_correction_is_explicit_separate_and_survives_automatic_rerun(research):
    inbox, _, scope, _, _, _, kwargs = research
    auto = ce.apply_anchor(inbox, **kwargs)
    correction = {k: scope[k] for k in ('berry_id','destination_scope','origin_scope','program_or_variety','period_start','period_end','use_system')}
    correction['destination_scope'] = 'geography-united-kingdom'
    ce.correct_assessment(inbox, assessment_id=auto['id'], expected_version=0, mode='override',rating='unknown',
                          rationale='Original destination was unspecified; analyst correction requires new evidence before rating',
                          actor='test analyst',corrected_scope=correction)
    result = ce.apply_anchor(inbox, **kwargs)
    assert result['destination_scope'] == 'geography-united-kingdom' and result['rating'] == 'unknown'
    assert result['automatic']['destination_scope'] == 'unspecified'
    assert result['effective_scope_key'] != result['id']


def test_invalidated_mapping_withdraws_automatic_proposal_preserving_decision(research):
    inbox, entities, _, payload, checks, _, kwargs = research
    auto=ce.apply_anchor(inbox, **kwargs)
    ce.correct_assessment(inbox, assessment_id=auto['id'], expected_version=0, mode='override',rating='unknown',
                          rationale='Hold for identity review',actor='test analyst')
    payload['records'][0]['fields']['peer_role']='breeder'
    ce.import_return(inbox,batch_id='B16',payload=payload,original_sha256='d'*64,entities=entities,source_checks=checks)
    raw=Store(inbox).get(auto['id'])
    assert raw['rating']=='unknown' and raw['status']=='requires_resolution'
    assert ce.effective_assessment(Store(inbox),raw)['status']=='overridden'


@pytest.mark.parametrize('problem', ['uninspected', 'wrong_berry', 'wrong_destination', 'missing_requirement', 'high_without_independence'])
def test_anchor_requires_exact_scope_and_inspected_support(research, problem):
    inbox, _, _, _, _, _, kwargs = research
    if problem == 'uninspected':
        store = Store(inbox)
        record = next(r for r in store.rows('competitive_record') if r['kind'] == 'source')
        record['verification'] = {'status': 'inaccessible'}
        with store.transaction() as db:
            store.put(db, 'competitive_record', record, 'test', expected=record['version'])
    elif problem == 'wrong_berry':
        kwargs['scope']['berry_id'] = 'berry-raspberry'
    elif problem == 'wrong_destination':
        kwargs['scope']['destination_scope'] = 'Europe'
    elif problem == 'missing_requirement':
        kwargs['checks']['1']['requirement'] = 'Vague innovation'
    else:
        kwargs['confidence'] = 'high'
    with pytest.raises(ValueError):
        ce.apply_anchor(inbox, **kwargs)


def test_override_survives_later_import_and_rescore_with_revision_guard(research):
    inbox, entities, scope, payload, checks, _, kwargs = research
    automatic = ce.apply_anchor(inbox, **kwargs)
    assert automatic['rating'] == 1 and automatic['status'] == 'provisional'
    decision = ce.correct_assessment(inbox, assessment_id=automatic['id'], expected_version=0,
                                     mode='override', rating='unknown', rationale='Insufficient method for my decision', actor='analyst')
    with pytest.raises(Conflict):
        ce.correct_assessment(inbox, assessment_id=automatic['id'], expected_version=0,
                               mode='override', rating=2, rationale='Stale form', actor='analyst')
    payload['records'][0]['fields']['value_or_statement'] += '; new evidence context'
    ce.import_return(inbox, batch_id='B16', payload=payload, original_sha256='b'*64, entities=entities, source_checks=checks)
    store = Store(inbox)
    effective = ce.effective_assessment(store, store.get(automatic['id']))
    assert effective['rating'] == 'unknown' and effective['new_evidence']
    rerun = ce.apply_anchor(inbox, **kwargs)
    assert rerun['rating'] == 'unknown' and rerun['decision']['version'] == decision['version']


def test_peer_cohort_does_not_change_underlying_assessment(research):
    inbox, _, _, _, _, _, kwargs = research
    a = ce.apply_anchor(inbox, **kwargs)
    b = {**a, 'id': 'other', 'entity_id': 'company-two', 'rating': 1}
    before = copy.deepcopy(a)
    cohort = ce.peer_positions([a, b], 3)
    assert cohort[a['id']]['ties'] == 2 and cohort[a['id']]['size'] == 2
    assert cohort[a['id']]['percentile'] is None
    assert a == before
    b['destination_scope'] = 'different market'
    assert ce.peer_positions([a, b], 3)[a['id']]['size'] == 1


def test_job_reposts_keep_history_and_do_not_infer_hire():
    records = [{'id': str(i), 'kind': 'job', 'resolution': 'accepted_structure', 'entity_id': 'company-one', 'version': i,
                'fields': {'requisition_id': '123', 'original_url': 'https://example.org/job',
                           'observed_status': status, 'last_observed_date': day}}
               for i, status, day in [(1, 'open', '2026-10-01'), (2, 'unavailable', '2026-10-30')]]
    groups = ce.job_groups(records)
    assert len(groups) == 1 and len(groups[0]['observations']) == 2
    assert groups[0]['latest']['fields']['observed_status'] == 'unavailable'
    assert 'no hire' in groups[0]['interpretation']
    undated=copy.deepcopy(records[0]);undated.update(id='undated',version=99)
    undated['fields']['last_observed_date']='Unknown'
    assert ce.job_groups([*records,undated])[0]['latest']['id']=='2'


def test_later_requisition_reconciles_url_only_history_without_merging_reused_urls():
    def job(key, req, title='Research technician'):
        return {'id':key,'kind':'job','resolution':'accepted_structure','entity_id':'company-one','version':1,
                'fields':{'title':title,'requisition_id':req,'original_url':'https://example.org/job','last_observed_date':'2026-10-30'}}
    rows=[job('first','Unknown'),job('later','req123')]
    assert len(ce.job_groups(rows))==1
    rows.append(job('new requisition','req456'))
    groups=ce.job_groups(rows)
    assert len(groups)==3 and any(g.get('identity_issue') for g in groups)
    assert ce.job_groups([job('gap','Unknown','Unknown')])==[]


def test_malformed_row_types_are_retained_without_corrupting_good_rows(research):
    inbox, entities, _, payload, checks, _, _=research
    payload['records'].extend([None,{'record_kind':[], 'fields':[]},
        {'record_kind':'observation','fields':{'entity_id':['company-one'],'capability_id':{}}}])
    report=ce.import_return(inbox,batch_id='B16',payload=payload,original_sha256='e'*64,entities=entities,source_checks=checks)
    assert report['counts']=={'accepted_structure':2,'unresolved':3}


def test_unresolved_canonical_placeholder_cannot_receive_rating(research):
    _, entities, scope, _, _, _, kwargs=research
    entities[scope['entity_id']]['attributes']={'identity_review_required':True}
    with pytest.raises(ValueError,match='Resolve the canonical entity identity'):
        ce.apply_anchor(research[0],**kwargs)


def test_changed_observation_scope_withdraws_old_automatic_rating(research):
    inbox, entities, scope, payload, checks, _, kwargs=research
    auto=ce.apply_anchor(inbox,**kwargs)
    payload['records'][0]['fields']['berry_scope']='berry-raspberry'
    ce.import_return(inbox,batch_id='B16',payload=payload,original_sha256='f'*64,entities=entities,source_checks=checks)
    old=Store(inbox).get(auto['id'])
    assert old['rating']=='unknown' and old['status']=='requires_resolution'
    changed={**scope,'berry_id':'berry-raspberry'}
    assert Store(inbox).get(ce.scope_key(changed))['rating']=='unknown'
