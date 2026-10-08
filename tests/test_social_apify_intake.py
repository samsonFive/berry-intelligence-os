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
