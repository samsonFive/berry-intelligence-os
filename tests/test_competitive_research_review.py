from copy import deepcopy
import pytest

from app.services import competitive_evaluation as ce
from app.services.competitive_research_review import reviewed_payload, context_review_usable
from app.services.living_workspaces import Store,digest


def packet():
    return {'records':[
        {'record_kind':'source','local_id':'B01-S001','fields':{'source_id':'B01-S001','original_url':'https://example.org/original'}},
        {'record_kind':'observation','local_id':'B01-O001','fields':{'entity_id':'company-one','peer_role':'grower; marketer',
            'capability_id':'grower.production','berry_scope':'berry-strawberry','source_ids':'B01-S001','value_or_statement':'Reported completed harvest'}}]}


def review(payload, disposition='corrected'):
    row=payload['records'][1]
    return {'batch_id':'B01','record_kind':row['record_kind'],'local_id':row['local_id'],
            'expected_fields_sha256':digest(row['fields']),'disposition':disposition,'reviewed_at':'2026-11-02',
            'rationale':'Explicit grower role retained; marketing role separate. This is mapping review, not claim verification.',
            'source_urls':['https://example.org/original'],'field_updates':{'peer_role':'grower'} if disposition=='corrected' else {}}


def test_correction_keeps_exact_original_and_replays_without_duplicate_or_analyst_decision(tmp_path):
    raw=packet();before=deepcopy(raw)
    cooked=reviewed_payload('B01',raw,[review(raw)])
    assert raw==before
    assert cooked['records'][1]['returned_fields']==raw['records'][1]['fields']
    kwargs=dict(batch_id='B01',payload=cooked,original_sha256='a'*64,entities={'company-one':{}})
    first=ce.import_return(tmp_path,**kwargs)
    assert first['counts']=={'accepted_structure':2}
    assert ce.import_return(tmp_path,**kwargs)['replayed']
    records=Store(tmp_path).rows('competitive_record')
    observation=next(r for r in records if r['kind']=='observation')
    assert observation['original_row']['returned_fields']['peer_role']=='grower; marketer'
    assert observation['fields']['peer_role']=='grower'
    assert len(records)==2 and Store(tmp_path).rows('capability_decision')==[]
    assert Store(tmp_path).rows('capability_automatic')[0]['rating']=='unknown'


def test_context_decision_closes_non_peer_mapping_without_creating_a_rated_cell(tmp_path):
    raw=packet();raw['records'][1]['fields']['peer_role']='retailer'
    cooked=reviewed_payload('B01',raw,[review(raw,'context_only')])
    result=ce.import_return(tmp_path,batch_id='B01',payload=cooked,original_sha256='b'*64,entities={'company-one':{}})
    assert result['counts']=={'accepted_structure':1,'context_only':1}
    assert Store(tmp_path).rows('capability_automatic')==[]
    row=next(r for r in Store(tmp_path).rows('competitive_record') if r['kind']=='observation')
    assert row['context_boundaries'] and row['fields']==row['original_row']['returned_fields']


@pytest.mark.parametrize('mutation',[lambda p:p['records'][1]['fields'].update(value_or_statement='Changed original'),
                                   lambda p:p['records'].append(deepcopy(p['records'][1]))])
def test_changed_or_ambiguous_original_rejects_old_review(mutation):
    raw=packet();decision=review(raw);mutation(raw)
    with pytest.raises(ValueError,match='stale or ambiguous'): reviewed_payload('B01',raw,[decision])


@pytest.mark.parametrize('kind,reason',[('observation','Entity identity requires resolution; no name or multi-entity merge inferred'),
                                      ('profile','Canonical placeholder has an unresolved legal identity; no commercial identity inferred'),
                                      ('source','Original HTTP(S) source URL missing')])
def test_context_does_not_mask_identity_or_source_integrity(kind,reason):
    raw=packet();raw['records'][1]['record_kind']=kind
    cooked=reviewed_payload('B01',raw,[review(raw,'context_only')])
    assert not context_review_usable(cooked['records'][1],[reason],{})


def test_group_gap_retains_separate_known_entities_without_name_merging():
    raw=packet();row=raw['records'][1];row['record_kind']='gap';row['fields']={'entity_id':'company-one; company-two','issue':'Shared search gap'}
    decision=review(raw,'context_only');decision['context_entity_ids']=['company-one','company-two']
    cooked=reviewed_payload('B01',raw,[decision])['records'][1]
    reason=['Entity identity requires resolution; no name or multi-entity merge inferred']
    assert context_review_usable(cooked,reason,{'company-one':{},'company-two':{}})
    assert not context_review_usable(cooked,reason,{'company-one':{}})
    assert cooked['fields']['entity_id']=='company-one; company-two'


@pytest.mark.parametrize('binding',[{'original_url':'https://example.org/different'}, {'reviewed_fields_sha256':'b'*64}])
def test_source_inspection_for_another_url_or_original_is_not_usable(tmp_path,binding):
    raw=packet();raw['records'][1]['fields']['peer_role']='grower'
    check={'status':'inspected_supports_claim','checked_at':'2026-11-02','support':'Original inspected',**binding}
    ce.import_return(tmp_path,batch_id='B01',payload=raw,original_sha256='c'*64,entities={'company-one':{}},source_checks={'B01-S001':check})
    source=next(r for r in Store(tmp_path).rows('competitive_record') if r['kind']=='source')
    assert source['verification']['status']=='source_changed_requires_reinspection'
    assert not ce.source_check_usable(source['verification'])


def test_stale_review_in_later_batch_is_rejected_before_any_import(tmp_path,monkeypatch):
    from scripts import import_competitive_research as importer
    raw=packet();decision=review(raw)
    bad=deepcopy(decision);bad.update(batch_id='B02',expected_fields_sha256='f'*64)
    monkeypatch.setattr(importer,'inputs',lambda:iter([('B01',raw,'a'*64,'first'),('B02',raw,'b'*64,'second')]))
    with pytest.raises(ValueError,match='stale or ambiguous'):
        importer.run(apply=True,inbox_dir=tmp_path/'private',reviews=[decision,bad])
    assert not (tmp_path/'private').exists()
