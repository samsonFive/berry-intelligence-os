from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import httpx
import pytest
from app.services.social_intelligence.bakeoff import (
    require_free_budget, verified_score, proportion, BoundedRead, news_feed,
    jetstream_rows, ingest_isolated, raw_metrics, AccessBlocked)

NOW=datetime(2026,10,7,13,tzinfo=timezone.utc)
MANIFEST={'version':'test','start_utc':'2026-09-07T13:00:00+00:00','end_utc':NOW.isoformat()}

def verification():
    return {'checked_at':NOW.isoformat(),'evidence_state':'actual-account',
      'evidence_reference':'private verified console receipt','free_only':True,
      'payment_method':False,'auto_recharge':False,'enforceable_no_charge_cap':True,
      'ancillary_costs_included':True,'balance':50,'initial_verified_balance':50}

@pytest.mark.parametrize('field,value',[
    ('payment_method',True),('auto_recharge',True),('free_only',False),
    ('evidence_state','documented'),('enforceable_no_charge_cap',False),
    ('ancillary_costs_included',False),('evidence_reference',''),
    ('checked_at',(NOW-timedelta(minutes=16)).isoformat()),('balance',10)])
def test_metered_run_fails_closed(field,value):
    v=verification();v[field]=value
    with pytest.raises(AccessBlocked):
        require_free_budget(v,all_in_upper_bound=5,spent=0,ceiling=20,now=NOW)

def test_free_reserve_and_all_in_ceiling():
    require_free_budget(verification(),all_in_upper_bound=20,spent=0,ceiling=20,now=NOW)
    with pytest.raises(AccessBlocked):
        require_free_budget(verification(),all_in_upper_bound=21,spent=0,ceiling=20,now=NOW)
    with pytest.raises(AccessBlocked):
        require_free_budget(verification(),all_in_upper_bound=41,spent=0,ceiling=50,now=NOW)

def test_documentation_cannot_become_verified_winner_or_renormalize():
    result=verified_score({'discovery':{'state':'documented','score':5,'n':1000},
      'cost':{'state':'live-tested','score':5,'n':2}})
    assert result['verified_points_out_of_100']==10
    assert result['tested_weight_percent']==10 and not result['renormalized']
    assert result['recommendation']=='no proven winner yet'
    with pytest.raises(ValueError):
        verified_score({'media':{'state':'live-tested','score':5,'n':0}})
    assert proportion(0,0)['estimate'] is None
    assert proportion(8,10)['wilson95'][0]<.8<proportion(8,10)['wilson95'][1]

def test_transport_disabled_errors_not_cached_as_zero_and_no_retry(tmp_path):
    calls=[]
    client=httpx.Client(transport=httpx.MockTransport(lambda request:
        calls.append(request) or httpx.Response(403)))
    reader=BoundedRead(tmp_path,client=client)
    with pytest.raises(AccessBlocked):reader.get('https://news.google.com/rss/search',{})
    assert not calls
    reader.enabled=True
    with pytest.raises(AccessBlocked,match='403'):reader.get('https://news.google.com/rss/search',{})
    assert len(calls)==1 and not list(tmp_path.glob('*.bin'))
    with pytest.raises(AccessBlocked):reader.get('https://example.org/',{})

def test_feed_long_identity_exact_dates_cache_and_pipeline_restart(tmp_path):
    xml=f'''<rss><channel><item><guid>{'long'*200}</guid><link>https://news.google.com/rss/articles/test</link><title>Blueberries sweet and crunchy</title><pubDate>Wed, 07 Oct 2026 12:00:00 GMT</pubDate><source>Publisher</source></item><item><guid>old</guid><link>https://news.google.com/rss/articles/old</link><title>Old blueberry</title><pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate></item></channel></rss>'''
    reader=BoundedRead(tmp_path/'cache',enabled=True,client=httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,text=xml))))
    query={'query':'blueberries','language':'en','feed_locale':'en-US','market':'US'}
    rows=news_feed(reader,query,MANIFEST)
    assert len(rows)==1 and len(rows[0]['native_id'])<500
    assert rows[0]['mode']=='live' and rows[0]['content_role']=='news_repost' and not rows[0]['media']
    assert 'locale' in rows[0]['language_basis'] and rows[0]['purchase_market'] is None
    assert news_feed(reader,query,MANIFEST)[0]['native_id']==rows[0]['native_id']
    assert reader.requests==1 and reader.cache_hits==1
    # Same collection timestamp comes from cached XML but normalization happens
    # again. Compare identities, not a provider repeat claim.
    first=ingest_isolated(rows,tmp_path,[])
    second=ingest_isolated(rows,tmp_path,[])
    assert first['unique']==second['unique']==len(second['store'].records(mode='live'))==1

def test_stream_comment_blob_not_fabricated_working_media(tmp_path):
    event={'did':'did:plc:test','collection':'app.bsky.feed.post','rkey':'abc','operation':'create',
      'record':{'text':'ブルーベリー 甘い','langs':['ja'],'createdAt':NOW.isoformat(),
        'reply':{'parent':{'uri':'at://did:plc:parent/app.bsky.feed.post/p'}},
        'embed':{'images':[{'image':{'ref':{'$link':'cid'}}}]}}}
    rows=jetstream_rows({'matched_events':[event]},MANIFEST)
    assert rows[0]['record_role']=='reply' and rows[0]['media'][0]['parent_native_id']==rows[0]['native_id']
    assert rows[0]['media'][0]['state']=='unsupported' and rows[0]['media'][0]['source_url'] is None
    assert rows[0]['language']=='ja' and rows[0]['purchase_market'] is None
    metrics=raw_metrics(rows+rows,1)
    assert metrics['comments']==1 and metrics['unique']==1 and metrics['duplicates']==1
    assert metrics['media_references']==metrics['downloaded_media_bytes']==0

def test_publisher_name_is_not_fruit_freshness(tmp_path):
    from app.services.social_intelligence.extraction import analyze
    xml='<rss><channel><item><guid>x</guid><link>https://news.google.com/rss/articles/test</link><title>Blueberry trials - Fresh Plaza</title><pubDate>Wed, 07 Oct 2026 12:00:00 GMT</pubDate><source>Fresh Plaza</source></item></channel></rss>'
    reader=BoundedRead(tmp_path,enabled=True,client=httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,text=xml))))
    row=news_feed(reader,{'query':'blueberry','language':'en','market':'US','feed_locale':'en-US'},MANIFEST)[0]
    assert row['text']=='Blueberry trials' and 'Fresh Plaza' in row['attribution']
    assert analyze(row,[])['aspects']==[]

def test_pack_and_candidates_are_bounded_and_china_explicit():
    pack=Path(__file__).resolve().parents[1]/'benchmarks/social-bakeoff'
    manifest=json.loads((pack/'manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['queries'])==20 and sum(q['group']=='blueberry' for q in manifest['queries'])==12
    assert {'en','es','pt','zh','ja'} <= {q['language'] for q in manifest['queries']}
    assert manifest['caps']=={'results_per_query':10,'reference_urls_per_provider':5,'pages':1,'retries':0}
    candidates=json.loads((pack/'candidates.json').read_text(encoding='utf-8'))['candidates']
    assert {'weibo','douyin','red','bilibili'} <= {c['platform'] for c in candidates}
    assert all(c.get('blocker') for c in candidates)

def test_vendor_comment_image_parent_and_null_sample_not_proof():
    from app.services.social_intelligence.bakeoff_vendors import sociavault_tiktok_rows
    base={'cid':'123','aweme_id':'456','reply_id':'0','text':'Blueberries crunchy but bland',
          'comment_language':'en','create_time':1791370000,'image_list':None}
    payload={'success':True,'data':{'comments':{'0':base}}}
    rows=sociavault_tiktok_rows(payload,task='comments',manifest=MANIFEST,
                              supplied_url='https://www.tiktok.com/@sample/video/456')
    assert rows[0]['native_id']=='123' and rows[0]['parent_native_id']=='456'
    assert rows[0]['media']==[]
    base['image_list']=[{'url_list':['https://example.org/comment-only.png']}]
    rows=sociavault_tiktok_rows(payload,task='comments',manifest=MANIFEST,supplied_url='https://www.tiktok.com/@sample/video/456')
    assert rows[0]['media'][0]['parent_native_id']=='123'
    assert rows[0]['media'][0]['storage_permission']=='reference_only'
    with pytest.raises(AccessBlocked):
        sociavault_tiktok_rows({'success':True,'data':{}},task='search',manifest=MANIFEST)

def test_vendor_opt_in_credential_and_fresh_budget_each_call(tmp_path,monkeypatch):
    from app.services.social_intelligence.bakeoff_vendors import SociaVaultPilot
    calls=[]
    client=httpx.Client(transport=httpx.MockTransport(lambda request:
        calls.append(request) or httpx.Response(200,json={'success':True,'data':{'comments':[]},'credits_used':1})))
    pilot=SociaVaultPilot(tmp_path,client=client)
    monkeypatch.setenv('SOCIAVAULT_API_KEY','synthetic-not-a-real-token')
    v=verification();v['checked_at']=datetime.now(timezone.utc).isoformat()
    v.update(task_pricing_verified=True,endpoint_maximum_credits=1)
    with pytest.raises(AccessBlocked):pilot.fetch(task='comments',value='https://www.tiktok.com/@x/video/456',verification=v)
    assert not calls
    pilot.enabled=True
    data,cached=pilot.fetch(task='comments',value='https://www.tiktok.com/@x/video/456',verification=v)
    assert not cached and len(calls)==1 and calls[0].headers['X-API-Key']=='synthetic-not-a-real-token'
    assert 'synthetic-not-a-real-token' not in str(calls[0].url)
    assert pilot.fetch(task='comments',value='https://www.tiktok.com/@x/video/456',verification=v)[1]
    with pytest.raises(AccessBlocked,match='again'):
        pilot.fetch(task='comments',value='https://www.tiktok.com/@x/video/999',verification=v)
    assert len(calls)==1

def test_apify_cannot_launch_from_marketplace_claim():
    from app.services.social_intelligence.bakeoff_vendors import apify_launch_plan
    v=verification();v.update(checked_at=datetime.now(timezone.utc).isoformat(),
                             actor_input_schema_verified=True,task_pricing_verified=True)
    plan=apify_launch_plan('atomus/weibo-scraper',build='pinned-build-id',
                           actor_input={'searchType':'search','keywords':['蓝莓'],'maxItems':10},verification=v)
    assert not plan['launch_enabled'] and plan['params']['maxTotalChargeUsd']==.25
    with pytest.raises(AccessBlocked):
        apify_launch_plan('atomus/weibo-scraper',build='latest',actor_input={},verification=v)

def test_facebook_multiple_images_dedupe_and_engagement():
    from app.services.social_intelligence.sociavault_normalize import normalize
    result=normalize({'success':True,'data':{'posts':{'0':{'id':'123','url':'https://www.facebook.com/example/posts/123','text':'Blueberries','publishTime':1791370000,'image':'https://scontent.example.fbcdn.net/a.jpg?thumbnail=1','images':{'0':'https://scontent.example.fbcdn.net/a.jpg?full=1','1':'https://scontent.example.fbcdn.net/b.jpg'},'reactionCount':12,'commentCount':3,'videoDetails':{}}}}},'facebook-posts')
    assert result['mapping_errors']==[]
    assert len(result['rows'][0]['media'])==2
    assert result['rows'][0]['engagement']=={'likes':12,'comments':3}
    assert result['rows'][0]['language']=='und'


def test_native_author_identity_is_preserved_without_search_target_inference():
    from app.services.social_intelligence.sociavault_normalize import normalize
    tweet={'__typename':'Tweet','rest_id':'123','legacy':{'full_text':'Blueberries','lang':'en'},'core':{'user_results':{'result':{'legacy':{'screen_name':'actual_author','name':'Actual Author'}}}}}
    result=normalize({'success':True,'data':{'result':{'tweets':[tweet]}}},'x-search')
    assert result['rows'][0]['author_handle']=='actual_author'
    assert result['rows'][0]['content_role']=='unknown'
    post={'id':'123','url':'https://www.facebook.com/example/posts/123','text':'Blueberries','author':{'name':'Supplied Page'}}
    result=normalize({'success':True,'data':{'posts':[post]}},'facebook-posts')
    assert result['rows'][0]['author_name']=='Supplied Page'
    assert result['rows'][0]['author_handle'] is None


def test_verified_consumption_and_attempt_cap_are_separate(tmp_path):
    from app.services.social_intelligence.sociavault_pilot import MultiPlatformPilot
    calls=[];balances=iter([12,11,11])
    def handler(request):
        if request.url.path=='/v1/credits':return httpx.Response(200,json={'credits':next(balances),'subscriptionStatus':'free','subscriptionId':None})
        calls.append(request);return httpx.Response(200,json={'success':True,'data':{'comments':[]},'credits_used':1})
    pilot=MultiPlatformPilot(tmp_path,enabled=True,key='synthetic-test-key',ceiling=41,client=httpx.Client(transport=httpx.MockTransport(handler)))
    pilot.ledger={'initial_balance':50,'attempts':[{'id':str(i),'state':'provider-error'} for i in range(40)]}
    pilot.fetch('reddit-comments',{'url':'https://www.reddit.com/r/berries/comments/photo/example/'},case_id='requested-picture')
    assert len(calls)==1 and len(pilot.ledger['attempts'])==41 and pilot.ledger['attempts'][-1]['observed_credit_delta']==1
    with pytest.raises(AccessBlocked,match='attempt ceiling'):
        pilot.fetch('reddit-comments',{'url':'https://www.reddit.com/r/berries/comments/another/example/'},case_id='not-authorized')
    assert len(calls)==1


def test_reddit_direct_gallery_and_inline_photos_are_references():
    from app.services.social_intelligence.sociavault_normalize import normalize
    post={'id':'gallery','permalink':'/r/berries/comments/gallery/example/','title':'Strawberries',
      'gallery_data':{'items':[{'media_id':'b'},{'media_id':'a'}]},
      'media_metadata':{'a':{'s':{'u':'https://i.redd.it/a.jpg'}},'b':{'s':{'u':'https://i.redd.it/b.jpg'}}},
      'selftext_html':'<img src="https://i.redd.it/inline.jpg"><script>alert(1)</script>'}
    row=normalize({'success':True,'data':{'post':post}},'reddit-post')['rows'][0]
    assert [m['source_url'] for m in row['media']]==['https://i.redd.it/b.jpg','https://i.redd.it/a.jpg','https://i.redd.it/inline.jpg']
    assert all(m['parent_native_id']=='t3_gallery' and m['storage_permission']=='reference_only' for m in row['media'])
    assert 'alert' not in row['text'] and not row['language']=='en'
