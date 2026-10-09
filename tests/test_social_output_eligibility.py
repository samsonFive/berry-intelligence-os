from copy import deepcopy
from pathlib import Path
from app.services.social_intelligence.output_eligibility import exclusion_ids, eligible_records, dependencies, deleted_sources

def test_transitive_deletion_preserves_history_and_holds_mixed_support():
    receipt={'id':'ev-private','source':'linkedin','native_id':'123','mode':'live'}
    records=[{'id':'ev-published','social_observation':{'id':'ev-private','source':'linkedin','native_id':'123','mode':'imported'}},
             {'id':'fact-1','evidence_ids':['ev-published','ev-other']},
             {'id':'signal-1','fact_ids':['fact-1']},
             {'id':'brief-1','sections':[{'signal_ids':['signal-1']}]},
             {'id':'ev-other'},{'id':'unrelated','entity_ids':['ev-private']}]
    before=deepcopy(records)
    blocked=exclusion_ids(list(reversed(records)),[receipt])
    assert blocked=={'ev-private','ev-published','fact-1','signal-1','brief-1'}
    assert [r['id'] for r in eligible_records(records,blocked)]==['ev-other','unrelated']
    assert records==before

def test_fixture_deletion_and_cycles_do_not_invalidate_real_sources(tmp_path):
    records=[{'id':'a','signal_ids':['b']},{'id':'b','signal_ids':['a']}]
    assert not exclusion_ids(records,[{'id':'a','mode':'fixture'}])
    assert exclusion_ids(records,[{'id':'a','mode':'live','source':'x','native_id':'1'}])=={'a','b'}
    assert deleted_sources(tmp_path)==[]
    assert not (tmp_path/'social').exists()
    assert dependencies({'entity_ids':['a'],'sections':[{'evidence_id':'ev-1'}]})=={'ev-1'}


def test_only_deleted_receipts_persist_across_restart_and_replay(tmp_path):
    import json
    from app.services.social_intelligence.store import Store
    root=Path(__file__).resolve().parents[1]
    template=json.loads((root/'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))['records'][0]
    store=Store(tmp_path)
    def put(native,mode='live'):
        row=deepcopy(template);row.update(native_id=native,mode=mode,translation=None)
        return store.ingest([row],[],mode=mode)[0]
    unavailable=put('unavailable');store.remove(unavailable,state='unavailable')
    restricted=put('restricted');store.remove(restricted,state='restricted')
    fixture=put('fixture','fixture');store.remove(fixture)
    assert deleted_sources(tmp_path)==[]
    deleted=put('deleted');store.remove(deleted)
    receipts=deleted_sources(tmp_path)
    assert len(receipts)==1 and receipts[0]['id']==deleted
    Store(tmp_path).remove(deleted,state='unavailable')
    assert deleted_sources(tmp_path)==receipts
    store.ingest([dict(template,native_id='deleted',mode='live',translation=None)],[],mode='live')
    assert deleted_sources(tmp_path)==receipts


def test_request_and_cli_output_seams_exclude_lineage_keep_canonical_history(tmp_path,monkeypatch):
    import json
    from pathlib import Path
    from app.services.social_intelligence.store import Store
    from app.services.request_corpus import RequestCorpus
    from app.services.social_intelligence.output_eligibility import output_exclusions
    root=Path(__file__).resolve().parents[1]
    template=json.loads((root/'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))['records'][0]
    inbox=tmp_path/'inbox';data=tmp_path/'data';store=Store(inbox)
    row=dict(template,mode='live',translation=None);key=store.ingest([row],[],mode='live')[0]
    records={
        'evidence':[{'id':'ev-published','status':'published','social_observation':{'id':key,'source':row['source'],'native_id':row['native_id'],'mode':'live'}},{'id':'ev-other','status':'published'}],
        'facts':[{'id':'fact-1','evidence_ids':['ev-published']},{'id':'fact-other','evidence_ids':['ev-other']}],
        'signals':[{'id':'signal-1','evidence_ids':['ev-published']}],
        'assessments':[{'id':'assessment-1','fact_ids':['fact-1']}],
        'recommendations':[{'id':'recommendation-1','assessment_ids':['assessment-1']}],
        'relationships':[]}
    for kind,items in records.items():
        folder=data/kind;folder.mkdir(parents=True)
        for item in items:(folder/(item['id']+'.json')).write_text(json.dumps(item),encoding='utf-8')
    before={p:p.read_bytes() for p in data.rglob('*.json')}
    store.remove(key,state='unavailable')
    assert not output_exclusions(data,inbox)
    # Deleted is an irreversible output hold, not a canonical trust mutation.
    store.remove(key,state='deleted')
    corpus=RequestCorpus(data_dir=data,schemas_dir=root/'schemas',inbox_dir=inbox)
    assert {r['id'] for r in corpus.evidence}=={'ev-published','ev-other'}
    assert [r['id'] for r in corpus.published_evidence]==['ev-other']
    assert [r['id'] for r in corpus.facts]==['fact-other']
    assert not corpus.signals and not corpus.assessments and not corpus.recommendations
    from app import main
    monkeypatch.setattr(main,'DATA_DIR',data);monkeypatch.setattr(main,'INBOX_DIR',inbox)
    monkeypatch.setattr(main,'get_request_corpus',lambda:None)
    assert [r['id'] for r in main.published_evidence()]==['ev-other']
    assert [r['id'] for r in main.all_facts()]==['fact-other']
    assert not main.all_signals() and not main.all_assessments() and not main.all_recommendations()
    assert all(p.read_bytes()==body for p,body in before.items())
    import pytest
    report={'id':'rp-historical','sections':[{'citation_ids':['assessment-1'],'prose':'Retained historical interpretation'}]}
    snapshot=deepcopy(report)
    monkeypatch.setattr(main,'_load_report_or_404',lambda key:report)
    with pytest.raises(main.HTTPException) as failure:main.report_export_pdf_route(report['id'])
    assert failure.value.status_code==409 and 'deleted source' in failure.value.detail
    assert report==snapshot



def test_existing_landscape_uses_output_projection_without_contract_or_history_changes():
    from types import SimpleNamespace
    from app.services.social_intelligence.output_eligibility import OutputRepositories
    from app.services.berries.landscape import BerriesLandscapeService
    class Repository:
        def __init__(self,rows):self.rows=rows
        def list(self,**filters):return [r for r in self.rows if all(r.get(k)==v for k,v in filters.items())]
        def get(self,key):return next((r for r in self.rows if r['id']==key),None)
    rows=[{'id':'ev-deleted','status':'published','berry_ids':['berry-blueberry']},{'id':'ev-other','status':'published','berry_ids':['berry-blueberry']}]
    raw=SimpleNamespace(evidence=Repository(rows))
    view=OutputRepositories(raw,{'ev-deleted'})
    landscape=BerriesLandscapeService(view,None)
    assert [r['id'] for r in landscape.landscape_evidence('berry-blueberry')]==['ev-other']
    assert view.evidence.get('ev-deleted')==rows[0]
    assert raw.evidence.list()==rows


def test_explicit_intake_deletion_excludes_replay_preserving_bytes_and_review_audit(tmp_path):
    import json,pytest
    from tests.test_social_intelligence import sample,ENTITIES
    from app.services.social_intelligence.store import Store
    from app.services.social_intelligence.aggregate import bundle
    from app.services.social_intelligence.integration import context_links
    store=Store(tmp_path);row=sample('imported',source='facebook',media=[])
    row['media']=[{'id':'photo-one','parent_native_id':row['native_id'],'kind':'image',
        'source_url':'https://cdn.example.org/synthetic.png','mime':'image/png',
        'attribution':'Synthetic test reference','state':'available','storage_permission':'permitted_bytes','retention':'Synthetic test only'}]
    key=store.ingest([row],ENTITIES,mode='imported')[0]
    content=b'\x89PNG\r\n\x1a\nsynthetic'
    obj=store.attach_media(key,'photo-one',content,'image/png')
    path=tmp_path/'social'/'media'/'imported'/obj
    store.correct(key,store.records()[0]['analysis'],'Test reviewer')
    store.handoff(key);draft=tmp_path/'evidence'/f'{key}.json';draft_before=draft.read_bytes()
    with store.connect() as db:prior_audit=db.execute('SELECT id,event,at FROM audit ORDER BY id').fetchall()
    incoming=deepcopy(row);incoming['media'][0]['state']='deleted'
    store.ingest([incoming],ENTITIES,mode='imported')
    assert any(r['id']==key for r in deleted_sources(tmp_path))
    Store(tmp_path).ingest([row],ENTITIES,mode='imported')
    record=store.records()[0];assert record['output_excluded'] is True
    assert record['analysis']['reviewed'] is True
    assert path.read_bytes()==content and draft.read_bytes()==draft_before
    with store.connect() as db:assert db.execute('SELECT id,event,at FROM audit WHERE id<=? ORDER BY id',(prior_audit[-1][0],)).fetchall()==prior_audit
    assert bundle(store.records(),[],{'mode':'imported','berry':'all'})['count']==0
    assert context_links(store.records())==[]
    with pytest.raises(ValueError):store.handoff(key)
    with pytest.raises(ValueError):store.media(key,'photo-one')
