from app.services.social_intelligence.sociavault_normalize import normalize

def test_real_shape_tiktok_dict_arrays_no_language_or_geography_from_query():
    payload={'success':True,'data':{'search_item_list':{'0':{'aweme_info':{
       'aweme_id':'123','url':'https://www.tiktok.com/@sample/video/123','desc':'Blueberries crunchy',
       'desc_language':'en','create_time':1791370000,'video':{'cover':{'url_list':{'0':'https://example.org/cover.jpg'}}}}}}}}
    result=normalize(payload,'tiktok-search');row=result['rows'][0]
    assert result['mapped_items']==1 and row['language']=='en' and row['purchase_market'] is None
    assert row['media'][0]['parent_native_id']=='123' and row['media'][0]['kind']=='thumbnail'
    assert row['translation'] is None and row['mode']=='live'

def test_reddit_comment_images_html_never_rendered_or_avatar_used_and_replies_linked():
    post={'name':'t1_parent','id':'parent','body':'Blueberries','parent_id':'t3_post',
          'permalink':'/r/berries/comments/post/example/parent','created_utc':1791370000,
          'body_html':'<script>alert(1)</script><img src="https://example.org/comment.png">',
          'author_avatar':'https://example.org/avatar.png','replies':{'items':{'0':{
             'name':'t1_child','id':'child','body':'Crunchy','parent_id':'t1_parent',
             'permalink':'/r/berries/comments/post/example/child','created_utc':1791370001}}}}
    result=normalize({'success':True,'data':{'comments':{'0':post}}},'reddit-comments')
    assert result['returned_items']==2 and len(result['rows'])==2
    parent,child=result['rows'];assert parent['media'][0]['source_url']=='https://example.org/comment.png'
    assert len(parent['media'])==1 and parent['media'][0]['parent_native_id']=='t1_parent'
    assert child['parent_native_id']=='t1_parent' and child['record_role']=='reply'
    assert '<script>' not in parent['text']

def test_instagram_original_details_nested_envelope_and_numeric_comment_parent():
    post={'id':'12345','shortcode':'AbCd','display_url':'https://example.org/post.jpg',
          'edge_media_to_caption':{'edges':{'0':{'node':{'text':'Arándanos'}}}},'taken_at_timestamp':1791370000}
    result=normalize({'success':True,'data':{'data':{'xdt_shortcode_media':post}}},'instagram-post')
    assert result['rows'][0]['text']=='Arándanos' and result['rows'][0]['language']=='und'
    payload={'success':True,'data':{'comments':{'0':{'id':'comment123','text':'sweet','created_at':1791370001}}}}
    assert normalize(payload,'instagram-comments',supplied_url='https://www.instagram.com/p/AbCd/')['mapped_items']==0
    row=normalize(payload,'instagram-comments',supplied_url='https://www.instagram.com/p/AbCd/',supplied_parent_id='12345')['rows'][0]
    assert row['parent_native_id']=='12345' and row['native_id']=='comment123'

def test_youtube_undated_shorts_not_given_query_date_or_language():
    result=normalize({'success':True,'data':{'videos':{},'shorts':{'0':{
        'id':'video123','url':'https://www.youtube.com/watch?v=video123','title':'ブルーベリー'}},'lives':{}}},'youtube-search')
    row=result['rows'][0];assert row['published_at'] is None and row['language']=='und'
    comment=normalize({'success':True,'data':{'comments':{'0':{'id':'c1','content':'sweet',
         'publishedTime':'2026-10-07T10:00:00Z'}}}},'youtube-comments',
         supplied_url='https://www.youtube.com/watch?v=video123',supplied_parent_id='video123')['rows'][0]
    assert comment['text']=='sweet' and comment['parent_native_id']=='video123'
