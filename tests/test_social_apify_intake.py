import pytest
from app.services.social_intelligence.apify_intake import apify_post
from app.services.social_intelligence.adapters import AccessBlocked

NOW = '2026-10-07T20:00:00+00:00'

def normalize(row, source='instagram', mode='fixture'):
    return apify_post(row, source=source, build='synthetic-test', collected_at=NOW, mode=mode)

def test_carousel_native_identity_author_dedup_and_provenance():
    row = normalize({'id':'123','url':'https://www.instagram.com/p/test/',
        'caption':'Blueberries','timestamp':NOW,'ownerUsername':'grower',
        'images':['https://cdn.example.org/1.jpg'] * 2 + ['https://cdn.example.org/2.jpg']})
    assert row['native_id'] == '123' and row['mode'] == 'fixture'
    assert row['author_handle'] == 'grower' and len(row['media']) == 2
    assert all(m['parent_native_id'] == '123' and m['storage_permission'] == 'reference_only' for m in row['media'])
    assert row['content_role'] == 'unknown' and row['language'] == 'und'
    assert row['purchase_market'] is None and row['translation'] is None

def test_linkedin_relative_date_not_promoted_and_avatar_not_media():
    row = normalize({'id':'456','linkedinUrl':'https://www.linkedin.com/posts/test/',
        'content':'Blueberry supplier','postedAt':{'date':NOW,'postedAgoShort':'1h'},
        'author':{'name':'Grower','avatar':'https://cdn.example.org/avatar.jpg'}}, 'linkedin')
    assert row['published_at'] == '2026-10-07T20:00:00Z' and row['publication_date_basis'] == 'estimated' and not row['media']
    assert row['author_name'] == 'Grower' and 'relative dates' in row['permission_basis']

@pytest.mark.parametrize('row,source',[
    ({'id':'tag','url':'https://www.instagram.com/explore/tags/blueberries/'}, 'instagram'),
    ({'id':'article','linkedinUrl':'https://www.linkedin.com/posts/article/','article':{'title':'Blueberries'}}, 'linkedin'),
    ({'id':'123','url':'https://other.example.org/post','caption':'Blueberries'}, 'instagram')])
def test_metadata_article_and_wrong_source_fail_closed(row,source):
    with pytest.raises(AccessBlocked): normalize(row,source)

def test_facebook_preserves_native_date_and_does_not_guess_photo_schema():
    row = normalize({'postId':'789','url':'https://www.facebook.com/posts/789',
        'text':'Blueberries in Madrid','time':NOW,'media':[{'avatar':'https://cdn.example.org/x.jpg'}]}, 'facebook')
    assert row['published_at'] == '2026-10-07T20:00:00Z' and not row['media']

def test_facebook_photo_variants_exclude_placeholders_and_ocr_claims():
    row = normalize({'postId':'789','url':'https://www.facebook.com/posts/789',
        'text':'Blueberries','media':[{'url':'https://www.facebook.com/posts/789'},
            {'__typename':'Photo','image':{'uri':'https://cdn.example.org/photo.jpg'},
             'ocrText':'May be an image of text'}]}, 'facebook')
    assert len(row['media']) == 1 and row['media'][0]['literal'] == []



def test_nested_and_standalone_comments_share_identity_and_replay(tmp_path):
    from app.services.social_intelligence.apify_intake import apify_dataset
    from app.services.social_intelligence.store import Store
    comment={'type':'comment','id':'comment-1','postId':'post-1',
             'linkedinUrl':'https://www.linkedin.com/feed/update/urn:li:activity:1?commentUrn=comment-1',
             'commentary':'Blueberries are crunchy','createdAt':NOW,
             'actor':{'name':'Synthetic commenter','pictureUrl':'https://cdn.example.org/avatar.jpg'},
             'engagement':{'likes':2}}
    post={'type':'post','id':'post-1','linkedinUrl':'https://www.linkedin.com/posts/test/',
          'content':'Blueberry supplier','postImages':[{'url':'https://cdn.example.org/post.jpg'}],
          'comments':[comment]}
    result=apify_dataset([comment,post],source='linkedin',build='synthetic-test',collected_at=NOW,mode='fixture')
    assert len(result['rows'])==2 and result['duplicate_copies']==1 and not result['rejected']
    reply=next(r for r in result['rows'] if r['record_role']=='reply')
    assert reply['parent_native_id']=='post-1' and reply['media']==[] and reply['language']=='und'
    assert reply['content_role']=='unknown' and reply['author_name']=='Synthetic commenter'
    store=Store(tmp_path);store.ingest(result['rows'],[],mode='fixture')
    restarted=Store(tmp_path);restarted.ingest(result['rows'],[],mode='fixture')
    assert len(restarted.records(mode='fixture'))==2
    comment_record=next(r for r in restarted.records(mode='fixture') if r['native_id']=='comment-1')
    restarted.remove(comment_record['id'])
    restarted=Store(tmp_path);restarted.ingest(result['rows'],[],mode='fixture')
    assert [r['native_id'] for r in restarted.records(mode='fixture')]==['post-1']


@pytest.mark.parametrize('change',[{'postId':'other-parent'},{'commentary':'Conflicting body'}])
def test_conflicting_comment_duplicates_fail_batch(change):
    from app.services.social_intelligence.apify_intake import apify_dataset
    comment={'type':'comment','id':'comment-1','postId':'post-1',
             'linkedinUrl':'https://www.linkedin.com/feed/update/urn:li:activity:1',
             'commentary':'Blueberries','createdAt':NOW}
    with pytest.raises(AccessBlocked):
        apify_dataset([comment,{**comment,**change}],source='linkedin',build='synthetic-test',collected_at=NOW,mode='fixture')


def test_nested_parent_mismatch_and_metadata_not_silent_success():
    from app.services.social_intelligence.apify_intake import apify_dataset
    post={'id':'post-1','linkedinUrl':'https://www.linkedin.com/posts/test/','content':'Blueberries',
          'comments':[{'id':'comment-1','postId':'other-parent','commentary':'Blueberries',
                       'linkedinUrl':'https://www.linkedin.com/feed/update/urn:li:activity:1'}]}
    with pytest.raises(AccessBlocked,match='parent conflicts'):
        apify_dataset([post],source='linkedin',build='synthetic-test',collected_at=NOW,mode='fixture')
    result=apify_dataset([{'id':'article','article':{'title':'Blueberries'}}],source='linkedin',build='synthetic-test',collected_at=NOW,mode='fixture')
    assert not result['rows'] and len(result['rejected'])==1


def test_x_inspected_identity_language_date_media_and_replay(tmp_path):
    from app.services.social_intelligence.apify_intake import apify_dataset
    from app.services.social_intelligence.store import Store
    item={'tweet_id':'123456','url':'https://x.com/demo/status/123456','text':'Blueberries today','created_at':'Wed Oct 07 09:01:34 +0000 2026','lang':'en','author':{'screen_name':'demo','avatar':'https://example.org/avatar.jpg'},'media':[{'image_url':'https://example.org/post.jpg','video_url':None}]}
    result=apify_dataset([item,item],source='x',build='1.0.45',collected_at='2026-10-08T00:00:00+00:00',mode='imported')
    assert len(result['rows'])==1 and result['duplicate_copies']==1 and not result['rejected']
    row=result['rows'][0]
    assert row['language']=='en' and row['published_at']=='2026-10-07T09:01:34Z'
    assert len(row['media'])==1 and row['content_role']=='unknown' and row['author_handle']=='demo'
    assert row.get('author_geography') is None and row.get('purchase_market') is None
    store=Store(tmp_path);store.ingest(result['rows'],[],mode='imported');Store(tmp_path).ingest(result['rows'],[],mode='imported')
    assert len(store.records(mode='imported'))==1 and not store.records(mode='live')
    item['url']='https://x.com/demo/status/999999'
    bad=apify_dataset([item],source='x',build='1.0.45',collected_at='2026-10-08T00:00:00+00:00')
    assert not bad['rows'] and len(bad['rejected'])==1


def test_x_reply_without_parent_stays_reply_and_quoted_media_is_not_attachment(tmp_path):
    from app.services.social_intelligence.apify_intake import apify_dataset
    from app.services.social_intelligence.store import Store
    item={'tweet_id':'777777','url':'https://x.com/demo/status/777777','text':'My blueberries','created_at':'Wed Oct 07 09:01:34 +0000 2026','lang':'en','is_reply':True,'quoted_tweet':{'media':[{'image_url':'https://example.org/quote.jpg'}]},'author':{'avatar':'https://example.org/avatar.jpg'},'media':[{'image_url':'https://example.org/own.jpg'}]}
    result=apify_dataset([item],source='x',build='1.0.45',collected_at='2026-10-08T00:00:00Z',mode='imported')
    row=result['rows'][0]
    assert row['record_role']=='reply' and row['parent_native_id'] is None and len(row['media'])==1
    store=Store(tmp_path);key=store.ingest([row],[],mode='imported')[0]
    store.remove(key,media_id=row['media'][0]['id']);Store(tmp_path).ingest([row],[],mode='imported')
    assert store.records(mode='imported')[0]['media'][0]['state']=='deleted'
    item['in_reply_to_status_id']='888888'
    linked=apify_dataset([item],source='x',build='1.0.45',collected_at='2026-10-08T00:00:00Z')['rows'][0]
    assert linked['parent_native_id']=='888888'


@pytest.mark.parametrize('bad',[{'url':[]},{'created_at':7},{'author':['bad']},{'media':[{'image_url':{'bad':'value'}}]},{'is_reply':True,'in_reply_to_status_id':'not-a-native-id'}])
def test_x_malformed_records_are_explicit_rejects(bad):
    from app.services.social_intelligence.apify_intake import apify_dataset
    item={'tweet_id':'123456','url':'https://x.com/demo/status/123456','text':'Blueberries','created_at':'Wed Oct 07 09:01:34 +0000 2026',**bad}
    result=apify_dataset([item],source='x',build='1.0.45',collected_at='2026-10-08T00:00:00Z')
    assert not result['rows'] and len(result['rejected'])==1
