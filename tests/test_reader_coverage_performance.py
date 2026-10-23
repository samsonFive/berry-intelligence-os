from copy import deepcopy
from datetime import UTC, datetime
import json

import httpx
import pytest

from app.services.firecrawl_reader import capture_publisher_article
from app.services import publisher_coverage as coverage
from app.services.presentation_memo import ByteMemo, json_call_memo
from app.services.source_body import reader_content

TITLE = 'Farmers publish new research on sustainable berry production'
URL = 'https://publisher.example/news/sustainable-berries'
TEXT = ('The growers measured crop production and resource use across multiple seasons. ' * 12)
BODY = '<article><h1>'+TITLE+'</h1><p>'+TEXT+'</p><h2>Field results</h2><p>Final source paragraph describes the measured field results.</p><div role="dialog"><p>Accept all cookies</p></div></article>'


def test_private_memo_is_bounded_and_returns_isolated_results():
    memo = ByteMemo(max_bytes=100, max_entries=2)
    memo.put('one', {'rows': ['original']})
    result = memo.get('one'); result['rows'].append('mutation')
    assert memo.get('one') == {'rows': ['original']}
    memo.put('two', {'rows': [2]}); memo.put('three', {'rows': [3]})
    assert memo.get('one') is None and memo.bytes <= 100


def test_read_model_invalidation_and_copy_isolation():
    calls = []
    @json_call_memo
    def model(*, rows):
        calls.append(1)
        return {'rows': deepcopy(rows)}
    first = model(rows=[{'status':'draft'}]); first['rows'][0]['status']='published'
    assert model(rows=[{'status':'draft'}])['rows'][0]['status']=='draft'
    assert len(calls)==1
    assert model(rows=[{'status':'rejected'}])['rows'][0]['status']=='rejected'
    assert len(calls)==2


def test_body_memo_never_hides_changed_source_content():
    row={'id':'same-id','article':{'full_text':TEXT},'summary':'Field research findings.'}
    assert reader_content(row)['usable_in_app']
    row['article']['full_text']='Before you continue to Google. If you choose to accept all cookies.'
    assert reader_content(row)['contaminated']
    row['article']['full_text']=TEXT
    assert reader_content(row)['usable_in_app']


@pytest.mark.parametrize('case', ['valid','wrong-title','wrong-url','wall','warning','missing-url','paywall-excerpt'])
def test_generic_reader_uses_exact_publisher_body(monkeypatch, case):
    monkeypatch.setenv('FIRECRAWL_API_KEY','fixture-only')
    calls=[]
    def handle(request):
        calls.append(json.loads(request.content))
        markup=BODY
        metadata={'statusCode':200,'sourceURL':URL}
        if case=='wrong-title':markup=markup.replace(TITLE,'An unrelated article about a different industry')
        if case=='wrong-url':metadata['sourceURL']='https://other.example/news/other'
        if case=='missing-url':metadata.pop('sourceURL')
        if case=='wall':markup='<article><h1>'+TITLE+'</h1><p>Subscribe to continue reading</p></article>'
        if case=='paywall-excerpt':markup=BODY.replace('</article>','<p>Subscribe to continue reading the complete article</p></article>')
        data={'html':markup,'metadata':metadata}
        if case=='warning':data['warning']='partial extraction'
        return httpx.Response(200,json={'success':True,'data':data})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result=capture_publisher_article({'title':TITLE,'source_url':URL},client=client)
    assert len(calls)==1
    if case in {'wrong-title','wrong-url','missing-url','wall'}:
        assert result is None
    else:
        assert result['url']==URL and 'Final source paragraph describes the measured field results.' in result['passages']
        assert 'accept all' not in ' '.join(result['passages']).lower()
        if case in {'warning','paywall-excerpt'}:assert result['availability']!='full'


@pytest.mark.parametrize('url', ['http://127.0.0.1/private','https://localhost/page','https://169.254.169.254/metadata','https://publisher.example:444/story'])
def test_generic_reader_never_sends_private_or_nonstandard_urls(monkeypatch, url):
    monkeypatch.setenv('FIRECRAWL_API_KEY','fixture-only')
    with httpx.Client(transport=httpx.MockTransport(lambda _:pytest.fail('unexpected API request'))) as client:
        assert capture_publisher_article({'title':TITLE,'source_url':url},client=client) is None


def test_google_wrapper_resolves_one_exact_publisher_headline(monkeypatch):
    monkeypatch.setenv('FIRECRAWL_API_KEY','fixture-only')
    home='https://publisher.example/'
    calls=[]
    def handle(request):
        target=json.loads(request.content)['url']; calls.append(target)
        body='<a href="'+URL+'">'+TITLE+'</a>' if target==home else BODY
        return httpx.Response(200,json={'success':True,'data':{'html':body,'metadata':{'statusCode':200,'sourceURL':target}}})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result=capture_publisher_article({'title':TITLE,'source_url':'https://news.google.com/rss/articles/opaque','origin_publisher_url':home},client=client)
    assert result['url']==URL and calls==[home,URL]


PACKER='<div class="PagePromo"><div class="PagePromo-title"><a href="https://www.thepacker.com/news/berry-research">'+TITLE+'</a></div><div class="PagePromo-date">September 29, 2026 05:43 AM</div><div class="PagePromo-description">Publisher summary</div></div>'
WATER_URL='https://watershed.com/blog/field-research'


def test_publisher_discovery_dates_cache_bounds_and_index_outage(monkeypatch,tmp_path):
    monkeypatch.setenv('FIRECRAWL_API_KEY','fixture-only')
    calls=[]
    def handle(request):
        calls.append(str(request.url))
        if request.method=='POST':
            target=json.loads(request.content)['url']
            return httpx.Response(200,json={'success':True,'data':{'html':PACKER,'metadata':{'sourceURL':target,'statusCode':200}}})
        if str(request.url)=='https://watershed.com/blog':
            return httpx.Response(200,text='<a href="'+WATER_URL+'"><h2>'+TITLE+'</h2></a><a href="https://other.example/blog/no"><h2>Other</h2></a>')
        assert str(request.url)==WATER_URL
        return httpx.Response(200,text='<script type="application/ld+json">'+json.dumps({'@type':'BlogPosting','url':WATER_URL,'headline':TITLE,'datePublished':'2025-09-01','dateModified':'2026-10-22'})+'</script>')
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        reports=coverage.refresh_publisher_coverage(tmp_path,client=client)
        assert all(r['status']=='ready' for r in reports)
        assert coverage.cached_articles(tmp_path,'feed:watershed-blog')[0]['published_date']=='2025-09-01'
        assert coverage.cached_articles(tmp_path,'feed:packer-sustainability-insights')[0]['published_date']=='2026-09-29'
        count=len(calls);coverage.refresh_publisher_coverage(tmp_path,client=client)
        assert len(calls)==count
    from app.services.industry_pulse.specialist_feeds import SpecialistRssProvider, week_specialist_feed_queries
    query=next(q for q in week_specialist_feed_queries() if q.id=='feed:packer-sustainability-insights')
    def failed(_):raise httpx.ConnectError('fixture index outage')
    hits=SpecialistRssProvider(fetch=failed,coverage_dir=tmp_path).discover(query)
    assert len(hits)==1 and hits[0].title==TITLE
    assert hits[0].provider_metadata['date_basis']=='publisher_section_display_date'
    record={'title':TITLE+' - The Packer','source_url':'https://news.google.com/rss/articles/opaque','origin_publisher_url':'https://www.thepacker.com/'}
    assert coverage.cached_publisher_target(tmp_path,record)=='https://www.thepacker.com/news/berry-research'
    record['origin_publisher_url']='https://other.example'
    assert not coverage.cached_publisher_target(tmp_path,record)


def test_watershed_listing_is_bounded_and_excludes_non_blog():
    markup=''.join('<a href="/blog/story-'+str(i)+'"><h2>Title</h2></a>' for i in range(100))
    assert len(coverage.watershed_links(markup))==24
    assert coverage.article_metadata('<script type="application/ld+json">'+json.dumps({'@type':'BlogPosting','url':WATER_URL,'headline':TITLE,'dateModified':'2026-10-22'})+'</script>',WATER_URL) is None


def test_file_collection_memo_detects_writes_deletes_and_repairs(tmp_path):
    from app.services.review_workbench import _safe_runtime_objects
    folder=tmp_path/'files';folder.mkdir();path=folder/'one.json'
    path.write_text(json.dumps({'id':'one','status':'draft'}))
    first,issues=_safe_runtime_objects(folder);first[0]['status']='published'
    assert not issues and _safe_runtime_objects(folder)[0][0]['status']=='draft'
    path.write_text(json.dumps({'id':'one','status':'rejected'}))
    assert _safe_runtime_objects(folder)[0][0]['status']=='rejected'
    path.write_text('{broken')
    assert _safe_runtime_objects(folder)==([],{'one'})
    path.write_text(json.dumps({'id':'one','status':'draft'}))
    assert _safe_runtime_objects(folder)[1]==set()
    path.unlink()
    assert _safe_runtime_objects(folder)==([],set())


def test_discovery_cache_keeps_source_filters_and_current_inventory(tmp_path):
    from app.services.media_discovery import list_discovered_items, staging_dir
    folder=staging_dir(tmp_path);folder.mkdir(parents=True)
    for source in ('a','b'):
        (folder/(source+'.json')).write_text(json.dumps({'id':source,'source_id':source}))
    assert [r['id'] for r in list_discovered_items(tmp_path,'a')]==['a']
    assert [r['id'] for r in list_discovered_items(tmp_path,'b')]==['b']
    (folder/'b.json').unlink()
    assert list_discovered_items(tmp_path,'b')==[]


def test_failed_publisher_refresh_retains_last_good_articles(monkeypatch,tmp_path):
    stamp=datetime.now(UTC).isoformat()
    for query_id in coverage.CONFIG:
        path=coverage.cache_path(tmp_path,query_id);path.parent.mkdir(parents=True,exist_ok=True)
        host=coverage.CONFIG[query_id][0]
        path.write_text(json.dumps({'version':1,'last_success_at':stamp,'articles':[{'url':'https://'+host+'/news/article','title':TITLE,'published_date':'2026-10-20','date_basis':'publisher'}]}))
    monkeypatch.delenv('FIRECRAWL_API_KEY',raising=False)
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(503))) as client:
        reports=coverage.refresh_publisher_coverage(tmp_path,client=client,force=True)
    assert all(r['status']=='failed' for r in reports)
    assert all(coverage.cached_articles(tmp_path,q) for q in coverage.CONFIG)

