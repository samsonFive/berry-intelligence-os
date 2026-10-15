"""Exact publisher identity, bounded API capture, and reader-cache integration."""
from copy import deepcopy
import json

import httpx
import pytest

from app.services import feed_first_reader as reader
from app.services.firecrawl_reader import capture_packer_article, PACKER_SECTION

TITLE = 'Retailers use sustainable sourcing to protect supply reliability'
URL = 'https://www.thepacker.com/news/retailers-sustainable-sourcing'
WRAPPER = 'https://news.google.com/rss/articles/opaque-test-token'
HTML = '<main><h1>' + TITLE + '</h1><div class="RichTextArticleBody">' + ''.join(
    '<h2>Source section '+str(i)+'</h2><p>'+('Retailers discuss sustainable packaging, supply reliability and emissions. ' * 6)+'</p>'
    for i in range(4)) + '</div><aside><p>Related stories and newsletter signup.</p></aside></main>'


def record(url=URL):
    return {'id':'live-packer-api-proof', 'title':TITLE+' - The Packer',
            'source_url':url, 'origin_publisher_url':'https://www.thepacker.com', 'status':'unreviewed'}


def page(url=URL, html=HTML):
    return {'success':True, 'data':{'html':html,'metadata':{'title':TITLE+' - The Packer','statusCode':200,'sourceURL':url}}}


def test_exact_publisher_html_preserves_sections_and_stays_private(monkeypatch):
    monkeypatch.setenv('FIRECRAWL_API_KEY','fixture-key-not-real')
    calls=[]
    def handle(request):
        calls.append(json.loads(request.content))
        assert request.url.host == 'api.firecrawl.dev'
        assert request.headers['authorization']=='Bearer fixture-key-not-real'
        return httpx.Response(200,json=page())
    original=record();before=deepcopy(original)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result=capture_packer_article(original,client=client)
    assert result['ok'] and result['availability']=='full' and result['method']=='firecrawl'
    assert result['url']==URL and len(result['passages'])==8
    assert len(result['heading_levels'])==4 and not result['frame_allowed']
    assert not any('Related stories' in p for p in result['passages'])
    assert original==before and calls[0]['formats']==['html']
    assert 'onlyCleanContent' not in calls[0]  # no generated cleanup/model text


def test_google_wrapper_uses_one_explicit_listing_then_exact_article(monkeypatch):
    monkeypatch.setenv('FIRECRAWL_API_KEY','fixture-key-not-real')
    calls=[]
    def handle(request):
        body=json.loads(request.content);calls.append(body)
        if body['url']==PACKER_SECTION:
            return httpx.Response(200,json=page(PACKER_SECTION,'<a href="'+URL+'">'+TITLE+'</a>'))
        return httpx.Response(200,json=page())
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result=capture_packer_article(record(WRAPPER),client=client,refresh=True)
    assert result['url']==URL
    assert [c['url'] for c in calls]==[PACKER_SECTION,URL]
    assert all(c['maxAge']==0 for c in calls)


@pytest.mark.parametrize('variation',['wrong-title','wrong-url','missing-url','google-consent','publisher-error','cookie-only','malformed','oversized','api-error','ambiguous-listing'])
def test_failures_never_replace_selected_story_with_another_body(monkeypatch,variation):
    monkeypatch.setenv('FIRECRAWL_API_KEY','fixture-key-not-real')
    response=page()
    if variation=='wrong-title':response['data']['html']=HTML.replace(TITLE,'A different older article about retailer sustainability')
    if variation=='wrong-url':response['data']['metadata']['sourceURL']='https://www.thepacker.com/news/another-article'
    if variation=='missing-url':response['data']['metadata'].pop('sourceURL')
    if variation=='google-consent':response['data']['metadata']['sourceURL']='https://consent.google.com/m'
    if variation=='publisher-error':response['data']['metadata']['statusCode']=403
    if variation=='cookie-only':response['data']['html']='<h1>'+TITLE+'</h1><p>If you choose to accept all cookies, we will use them for personalization.</p>'
    if variation=='ambiguous-listing':response=page(PACKER_SECTION,'<a href="'+URL+'">'+TITLE+'</a><a href="https://www.thepacker.com/news/different">'+TITLE+'</a>')
    def handle(request):
        if variation=='api-error':return httpx.Response(401,json={'error':'not authorized'})
        if variation=='malformed':return httpx.Response(200,content=b'not JSON')
        if variation=='oversized':return httpx.Response(200,content=b'x'*1_000_001)
        return httpx.Response(200,json=response)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert capture_packer_article(record(WRAPPER if variation=='ambiguous-listing' else URL),client=client) is None


def test_absent_key_and_unrequested_publishers_never_call_api(monkeypatch):
    def forbidden(request):raise AssertionError('unexpected network')
    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        monkeypatch.delenv('FIRECRAWL_API_KEY',raising=False)
        assert capture_packer_article(record(),client=client) is None
        monkeypatch.setenv('FIRECRAWL_API_KEY','fixture-key-not-real')
        assert capture_packer_article(record('https://other.example/news/story'),client=client) is None


def test_reader_uses_fallback_once_and_reuses_exact_source_cache(monkeypatch,tmp_path):
    from app.services import firecrawl_reader
    calls=[]
    def recover(row,**kwargs):
        calls.append(row['source_url'])
        return {'url':URL,'ok':True,'availability':'full','passages':['Source article text. '*80],
                'method':'firecrawl','retrieved_at':'2026-10-15T00:00:00+00:00'}
    monkeypatch.setattr(firecrawl_reader,'capture_packer_article',recover)
    def blocked(request):return httpx.Response(403,content=b'blocked')
    row=record()
    with httpx.Client(transport=httpx.MockTransport(blocked)) as client:
        first=reader.capture_item(tmp_path,row,client=client)
        again=reader.capture_item(tmp_path,row,client=client)
    assert first==again and calls==[URL]
    assert first['requested_url']==URL and first['capture_version']==reader.CAPTURE_VERSION
    assert row.get('article') is None and row['status']=='unreviewed'
