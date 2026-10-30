from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.services.research_desk import ResearchScope, interpret_research_scope, _within_window, _provider_call
from app.services.industry_pulse.matrix import generate_pulse_queries
from app.services.industry_pulse.query_text import date_window_of, perplexity_date_kwargs, firecrawl_tbs
from app.services.industry_pulse.exa import ExaSearchProvider
from app.services.industry_pulse.firecrawl import FirecrawlSearchProvider
from app.services.industry_pulse.brightdata import BrightDataSearchProvider
from app.services.industry_pulse.perplexity_provider import PerplexitySearchProvider


def test_broad_research_has_no_hidden_archive_cutoff_and_followups_keep_or_replace_it():
    args=dict(berries={'berry-raspberry':'Raspberry'},entities=[],questions=[],relationships=[])
    broad=interpret_research_scope('Raspberry breeding developments',**args)
    assert broad.all_time
    assert ResearchScope.from_dict(broad.as_dict()).all_time
    assert _within_window({'published_date':'2004-01-01'},broad.window_days,today=date(2026,10,28),all_time=broad.all_time)
    follow=interpret_research_scope('Only licensing',previous=broad,**args)
    assert follow.all_time
    recent=interpret_research_scope('Only the last 45 days',previous=broad,**args)
    assert not recent.all_time and recent.window_days==45
    assert not _within_window({'published_date':'2004-01-01'},recent.window_days,today=date(2026,10,28),all_time=recent.all_time)


def test_provider_receives_actual_research_window_instead_of_a_seven_or_thirty_day_cap():
    args=dict(berries={'berry-raspberry':'Raspberry'},entities=[],questions=[],relationships=[])
    broad=interpret_research_scope('Raspberry breeding developments',**args)
    queries=[]
    class Provider:
        name='fixture'
        def discover(self,query):queries.append(query);return []
    assert _provider_call(Provider(),'raspberry breeding',broad)[2] is None
    assert queries[-1].date_window=='all' and 'when:' not in queries[-1].text
    recent=interpret_research_scope('Raspberry breeding in the last 45 days',**args)
    _provider_call(Provider(),'raspberry breeding',recent)
    assert queries[-1].date_window=='45d' and queries[-1].text.endswith('when:45d')
    assert perplexity_date_kwargs('45d',today=date(2026,10,28))=={'search_after_date_filter':'09/13/2026'}
    assert perplexity_date_kwargs('all',today=date(2026,10,28))=={}


def test_all_date_provider_requests_do_not_silently_fall_back_to_one_week():
    calls=[]
    class Response:
        status_code=200
        def json(self):return {'results':[],'data':{'web':[]},'organic':[]}
    def post(url,**kwargs):calls.append((url,kwargs));return Response()
    query=generate_pulse_queries()[0].with_window('all')
    ExaSearchProvider(api_key='fixture',post=post).discover(query)
    assert 'startPublishedDate' not in calls[-1][1]['json']
    FirecrawlSearchProvider(api_key='fixture',post=post).discover(query)
    assert 'tbs' not in calls[-1][1]['json']
    BrightDataSearchProvider(api_key='fixture',zone='fixture',post=post).discover(query)
    assert '&tbs=' not in calls[-1][1]['json']['url']
    searches=[]
    class Client:
        def search(self,*args,**kwargs):searches.append(kwargs);return SimpleNamespace(hits=[])
    PerplexitySearchProvider(api_key='fixture',client=Client()).discover(query)
    assert not any(key.startswith('search_') and 'filter' in key for key in searches[-1])
    assert date_window_of(query)=='all' and firecrawl_tbs('all',today=date(2026,10,28))==''


def test_recent_historical_and_unverified_dates_are_separated_without_relabeling_source_dates():
    from app.services.research_desk import compose_research_answer
    items=[dict(id='live-'+str(i),title=title,date=stamp,url='https://source.test/'+str(i),source_name='Fixture',snippet='Source wording')
           for i,(title,stamp) in enumerate([('Recent','2026-10-01'),('Historical','2004-01-01'),('Unknown',''),('Future date','2030-01-01')])]
    answer=compose_research_answer({'source_index':{}}, live={'items':items,'coverage_as_of':'2026-10-28'})
    assert [r['title'] for r in answer['current_developments']]==['Recent']
    assert [r['title'] for r in answer['historical_developments']]==['Historical']
    assert {r['title'] for r in answer['undated_developments']}=={'Unknown','Future date'}


def test_absolute_publication_dates_survive_followups_and_do_not_use_capture_dates():
    args=dict(berries={'berry-raspberry':'Raspberry'},entities=[],questions=[],relationships=[])
    bounded=interpret_research_scope('Raspberry breeding 2020-01-01 through 2020-12-31',**args)
    assert not bounded.all_time and bounded.publication_start=='2020-01-01' and bounded.publication_end=='2020-12-31'
    follow=interpret_research_scope('Only licensing',previous=bounded,**args)
    assert follow.publication_start==bounded.publication_start and follow.publication_end==bounded.publication_end
    carried=ResearchScope.from_dict(follow.as_dict())
    kw=dict(today=date(2026,10,28),publication_start=carried.publication_start,publication_end=carried.publication_end)
    assert _within_window({'published_date':'2020-01-01'},carried.window_days,**kw)
    assert _within_window({'published_date':'2020-12-31'},carried.window_days,**kw)
    assert not _within_window({'published_date':'2019-12-31'},carried.window_days,**kw)
    assert not _within_window({'captured_date':'2020-06-01'},carried.window_days,**kw)
    recent=interpret_research_scope('Only the last 45 days',previous=carried,**args)
    assert recent.publication_start is None and recent.publication_end is None and recent.window_days==45


def test_a_bounded_relative_window_does_not_treat_an_unknown_date_as_in_range():
    assert not _within_window({},45,today=date(2026,10,28))
    assert not _within_window({'published_date':'not-a-date'},45,today=date(2026,10,28))
    assert _within_window({},3650,today=date(2026,10,28),all_time=True)


def test_invalid_explicit_dates_fail_before_any_packet_or_provider_call(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    def forbidden(*args,**kwargs):raise AssertionError('invalid dates must fail before research')
    monkeypatch.setattr(main,'_research_packet',forbidden)
    monkeypatch.setattr(main,'_pulse_providers',forbidden)
    response=TestClient(main.app).post('/api/research/live',json={'scope':{'question':'raspberry 2026-99-99'}})
    assert response.status_code==422


def test_cane_refinement_retains_topic_and_does_not_restore_obsolete_dates():
    from app.services.topic_retrieval import plan_query
    args=dict(berries={'berry-blackberry':'Blackberry'},entities=[],questions=[],relationships=[])
    bounded=interpret_research_scope('Floricane blackberry developments 2026-01-01 through 2026-10-26',**args)
    follow=interpret_research_scope('Only Europe',previous=bounded,**args)
    assert plan_query(follow.question).cane_type == 'floricane'
    assert 'Only Europe' in follow.question and follow.publication_start == '2026-01-01'
    recent=interpret_research_scope('Only the last 45 days',previous=follow,**args)
    assert recent.publication_start is None and recent.publication_end is None
    assert recent.window_days == 45 and '2026-01-01' not in recent.question
    assert plan_query(recent.question).cane_type == 'floricane'
    different=interpret_research_scope('Primocane blackberry trials',previous=follow,**args)
    assert plan_query(different.question).cane_type == 'primocane'


def test_verified_code_refinement_keeps_the_named_identity_context():
 args=dict(berries={'berry-blackberry':'Blackberry'},entities=[{'id':'v','entity_type':'variety','name':'Ervin','aliases':['NC 740'],'berry_ids':['berry-blackberry']}],questions=[],relationships=[])
 first=interpret_research_scope('NC 740 blackberry',**args)
 follow=interpret_research_scope('Only Europe',previous=first,**args)
 assert 'NC 740 blackberry' in follow.question and 'Only Europe' in follow.question
