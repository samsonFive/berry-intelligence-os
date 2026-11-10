import hashlib
from dataclasses import dataclass
from copy import deepcopy

from app.services.research_source_cache import remember_sources,cached_sources
from app.services.topic_retrieval import plan_query,match_record
from app.services.ai_gateway.results import SearchHit,SearchResponse
from app.services.topic_discovery import discover_topic


def source():
    body='A floricane blackberry field trial compared pruning and crop yield.'
    return {'id':'web-fixture','title':'Blackberry pruning research','source_url':'https://publisher.example/trial',
            'article':{'paragraphs':[{'index':0,'text':body,'private_annotation':'Do not retain'}],'analyst_note':'Do not retain'},
            'source_version':hashlib.sha256(body.encode()).hexdigest(),'capture_status':'full',
            'published_date':'2025-03-01','capture_provenance':{'method':'direct_http'},'private_note':'Do not retain'}


def test_reusable_public_body_is_unreviewed_and_cannot_persist_private_annotations(tmp_path):
    original=source();before=deepcopy(original)
    assert remember_sources(tmp_path,[original])=={'status':'ready','stored':1}
    assert remember_sources(tmp_path,[original])=={'status':'ready','stored':0}
    rows,status=cached_sources(tmp_path,plan_query('blackberry floricane pruning'))
    assert status=='ready'and len(rows)==1 and rows[0]['trust_class']=='LIVE / UNREVIEWED'
    assert 'private'not in str(rows) and rows[0]['source_version']==original['source_version']
    assert match_record(rows[0],plan_query('blackberry floricane trial'))['support_status']=='body_supported'
    assert not match_record(rows[0],plan_query('blackberry floricane pruning 2026-01-01 through 2026-11-03'))
    assert original==before


def test_cache_rejects_unverified_bytes_private_urls_and_metadata_only(tmp_path):
    for damage in ['hash','url','metadata']:
        row=source()
        if damage=='hash':row['source_version']='wrong'
        elif damage=='url':row['source_url']='http://127.0.0.1/private'
        else:row['capture_status']='metadata_only'
        assert remember_sources(tmp_path,[row])['stored']==0
    assert cached_sources(tmp_path,plan_query('blackberry'))==([],'empty')


def test_new_query_reuses_captured_body_but_still_searches_public_sources(tmp_path):
    calls=[]
    class Client:
        def search(self,query,**kwargs):
            calls.append(query)
            return SearchResponse('fixture',query,(SearchHit('Blackberry trial','https://publisher.example/trial',''),)if len(calls)==1 else(),0.01)
    row=source();fetches=[]
    def fetch(url):
        fetches.append(url)
        return {'ok':True,'headline':row['title'],'passages':[row['article']['paragraphs'][0]['text']],
                'published_date':row['published_date'],'published_date_basis':'publisher_date','availability':'full'}
    first=discover_topic(plan_query('blackberry pruning trial'),inbox_dir=tmp_path,client=Client(),fetcher=fetch)
    second=discover_topic(plan_query('blackberry floricane yield'),inbox_dir=tmp_path,client=Client(),fetcher=fetch)
    cold_calls=len(calls)
    assert first['items']and second['items']and cold_calls>=2 and len(fetches)==1
    assert second['items'][0]['research_cache_reused']and 'previously captured'in second['items'][0]['match_reason']
    assert second['history_candidates_count']==1
    warm=discover_topic(plan_query('blackberry floricane yield'),inbox_dir=tmp_path,client=Client(),fetcher=fetch)
    assert warm['cache_hit']and warm['queries_this_request']==0 and len(calls)==cold_calls
    assert not list(tmp_path.glob('evidence/*.json'))


def test_changed_cached_body_is_not_reused(tmp_path):
    import sqlite3,json
    remember_sources(tmp_path,[source()])
    with sqlite3.connect(tmp_path/'research_public_sources.sqlite3')as db:
        row=source();row['article']['paragraphs'][0]['text']='Unverified replacement text'
        db.execute('UPDATE sources SET record=?',(json.dumps(row),))
    assert cached_sources(tmp_path,plan_query('blackberry'))==([],'ready')



def test_cited_pages_from_one_pdf_survive_capture_and_cache(tmp_path):
    from app.services.research_source_cache import cached_source_urls

    class Client:
        def search(self, query, **kwargs):
            hits = tuple(
                SearchHit("Blackberry field trial", f"https://publisher.example/trial.pdf#page={page}", "")
                for page in (4, 6)
            )
            return SearchResponse("fixture", query, hits, 0.01)

    calls = set()

    def fetch(url):
        calls.add(url)
        page = url.rsplit("=", 1)[1]
        return {
            "availability": "excerpt_only",
            "passages": [f"A floricane blackberry field trial measured crop yield on page {page}."],
            "passage_locators": [f"pdf:page:{page}"],
        }

    discover_topic(plan_query("blackberry trial"), inbox_dir=tmp_path, client=Client(), fetcher=fetch)
    assert calls == {
        "https://publisher.example/trial.pdf#page=4",
        "https://publisher.example/trial.pdf#page=6",
    }
    assert cached_source_urls(tmp_path) == ({
        "publisher.example/trial.pdf#page=4",
        "publisher.example/trial.pdf#page=6",
    }, "available")
