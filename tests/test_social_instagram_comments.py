import hashlib
import json
import pytest
from app.services.social_intelligence.apify_intake import apify_dataset
from app.services.social_intelligence.apify_jobs import ApifyJobs
from app.services.social_intelligence.adapters import AccessBlocked
from app.services.social_intelligence.store import Store

NOW='2026-10-08T00:00:00Z'
PARENT={'native_id':'12345','canonical_url':'https://www.instagram.com/p/SyntheticPost/'}
COMMENT={'id':'67890','postUrl':PARENT['canonical_url'],
         'commentUrl':PARENT['canonical_url']+'c/67890', 'text':'Blueberries are crunchy',
         'timestamp':NOW,'ownerUsername':'synthetic_consumer','likesCount':2,
         'ownerProfilePicUrl':'https://example.org/avatar.jpg',
         'owner':{'full_name':'Synthetic consumer','profile_pic_url':'https://example.org/avatar.jpg'}}


def normalize(items,context=PARENT):
    return apify_dataset(items,source='instagram',build='synthetic-test',collected_at=NOW,mode='fixture',parent_context=context)


def test_comment_identity_parent_provenance_no_avatar_and_restart(tmp_path):
    result=normalize([COMMENT,COMMENT])
    assert result['duplicate_copies']==1 and len(result['rows'])==1 and not result['rejected']
    row=result['rows'][0]
    assert row['native_id']=='67890' and row['parent_native_id']=='12345' and row['record_role']=='reply'
    assert row['mode']=='fixture' and row['language']=='und' and row['content_role']=='unknown'
    assert row['engagement']=={'likes':2} and row['media']==[] and row['translation'] is None
    assert row['author_handle']=='synthetic_consumer' and row['purchase_market'] is None
    store=Store(tmp_path);key=store.ingest(result['rows'],[],mode='fixture')[0]
    Store(tmp_path).ingest(result['rows'],[],mode='fixture')
    assert len(store.records())==1
    store.remove(key);Store(tmp_path).ingest(result['rows'],[],mode='fixture')
    assert store.records()==[]


@pytest.mark.parametrize('change',[{'postUrl':'https://www.instagram.com/p/Other/'},
    {'commentUrl':PARENT['canonical_url']+'c/999'}, {'commentUrl':'https://evil.example.org/c/67890'},
    {'id':True},{'id':'１２３'},{'timestamp':True},{'text':''},{'owner':['not-an-owner-object']}])
def test_malformed_comments_are_rejected_not_successful_posts(change):
    result=normalize([{**COMMENT,**change}])
    assert result['rows']==[] and len(result['rejected'])==1


def test_missing_or_conflicting_parent_and_same_id_body_fail():
    result=normalize([COMMENT],None)
    assert not result['rows'] and len(result['rejected'])==1
    with pytest.raises(AccessBlocked,match='Conflicting'):
        normalize([COMMENT,{**COMMENT,'text':'Changed body'}])
    result=normalize([COMMENT],{'native_id':'bad','canonical_url':PARENT['canonical_url']})
    assert not result['rows']


@pytest.mark.parametrize('context,change',[(None,{}),(PARENT,{'resultsLimit':6}),
    (PARENT,{'directUrls':['https://www.instagram.com/p/Other/']}),
    (PARENT,{'search':'blueberries'})])
def test_comment_launch_guard_blocks_before_any_http(tmp_path,context,change):
    class NoRequests(ApifyJobs):
        def _request(self,*args,**kwargs):raise AssertionError('Guard must precede network')
    jobs=NoRequests(tmp_path)
    with pytest.raises(AccessBlocked):
        jobs.launch('comment-test','apify/instagram-scraper',build_id='Build12345',build_number='0.0.803',
                    actor_input={'directUrls':[PARENT['canonical_url']],'resultsType':'comments','resultsLimit':3,**change},parent_context=context)
    assert not jobs.ledger_path.exists()


def test_cached_comment_export_preserves_parent_binding_and_blocks_drift(tmp_path):
    actor='apify/instagram-scraper';build='Build12345';version='0.0.803';case='comment-test'
    actor_input={'directUrls':[PARENT['canonical_url']],'resultsType':'comments','resultsLimit':3}
    fingerprint=hashlib.sha256(json.dumps([actor,build,version,actor_input,PARENT],sort_keys=True).encode()).hexdigest()
    entry={'case':case,'actor':actor,'build_id':build,'build_number':version,'run_id':'Run12345',
           'cap_usd':.1,'state':'SUCCEEDED','input':actor_input,'parent_context':PARENT,
           'fingerprint':fingerprint,'data_observed_at':NOW}
    ledger={'ceiling_free_credit_usd':1,'cash_spend':0,'attempts':[entry]}
    (tmp_path/'ledger.json').write_text(json.dumps(ledger),encoding='utf-8')
    (tmp_path/(case+'-items.json')).write_text(json.dumps([COMMENT]),encoding='utf-8')
    jobs=ApifyJobs(tmp_path)
    assert jobs.launch(case,actor,build_id=build,build_number=version,actor_input=actor_input,parent_context=PARENT)['reused']
    receipt=jobs.normalize_cached(case)
    assert receipt['normalized']==1 and receipt['mode']=='imported' and receipt['ingested'] is False
    exported=tmp_path/(case+'-normalized-import.json');before=exported.read_bytes()
    assert json.loads(before)[0]['parent_native_id']=='12345'
    assert jobs.cached_status()['jobs'][0]['observed_volume']==1
    entry['parent_context']={**PARENT,'native_id':'99999'}
    (tmp_path/'ledger.json').write_text(json.dumps(ledger),encoding='utf-8')
    with pytest.raises(AccessBlocked,match='Existing case input differs'):
        jobs.launch(case,actor,build_id=build,build_number=version,actor_input=actor_input,parent_context=PARENT)
    with pytest.raises(AccessBlocked,match='context changed'):
        jobs.normalize_cached(case)
    assert exported.read_bytes()==before
    status=jobs.cached_status()['jobs'][0]
    assert status['status']=='unknown' and status['observed_volume'] is None
