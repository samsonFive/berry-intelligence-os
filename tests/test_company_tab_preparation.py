"""Unrelated company tabs must not build source-heavy News/location models."""
from copy import deepcopy

import pytest
from starlette.requests import Request

from app import company_routes,main
from app.services import map_regions,news_workspace,personal_digest,people_watchlist


@pytest.mark.parametrize('tab,wants_news,wants_regions',[
    ('overview',True,True),('news',True,False),('regions',False,True),
    ('varieties',False,False),('people',False,False),('details',False,False),
    ('intelligence',False,False),('unknown',True,True),
])
@pytest.mark.parametrize('authoring',[True,False])
def test_only_visible_tab_prepares_news_and_regions(tmp_path,monkeypatch,tab,wants_news,wants_regions,authoring):
    company={'id':'company-fixture','entity_type':'company','name':'Fixture Berries',
             'canonical':False,'profile_url':'/entities/company/company-fixture'}
    record={'id':'ev-fixture','entity_ids':['company-fixture'],'summary':'Current source text.'}
    before=deepcopy(record);calls=[]
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',authoring)
    monkeypatch.setattr(company_routes.directory,'catalog',lambda *a,**k:{company['id']:company})
    monkeypatch.setattr(company_routes.directory,'people_for',lambda *a,**k:[])
    monkeypatch.setattr(people_watchlist,'discover_people',lambda *a:[])
    def published():
        assert wants_news or wants_regions,'Unrelated tab loaded source records'
        calls.append('published');return [record]
    monkeypatch.setattr(main,'published_evidence',published)
    monkeypatch.setattr(main,'all_relationships',lambda:[])
    def facts():
        assert wants_news,'Non-News tab requested News facts'
        calls.append('facts');return []
    monkeypatch.setattr(main,'all_facts',facts)
    def sources(rows,inbox):
        assert authoring and (wants_news or wants_regions)
        calls.append('sources');return {record['id']:record}
    monkeypatch.setattr(personal_digest,'source_records',sources)
    news={'cards':[],'matching':1,'filters':{'company':company['id']}}
    def news_model(**kwargs):
        assert wants_news
        assert kwargs['records']=={record['id']:record}
        assert kwargs['params']['company']==company['id']and kwargs['params']['tz']=='Pacific/Auckland'
        calls.append('news');return news
    monkeypatch.setattr(news_workspace,'model',news_model)
    regions=[{'entity_id':company['id'],'country':'New Zealand'},{'entity_id':'other','country':'Elsewhere'}]
    def locations(entities,relations,records,overlay):
        assert wants_regions and records==[record]
        calls.append('regions');return regions
    monkeypatch.setattr(map_regions,'catalog',locations)
    request=Request({'type':'http','method':'GET','path':company['profile_url'],
                     'query_string':('tab='+tab+'&tz=Pacific/Auckland').encode(),'headers':[]})
    context=company_routes.profile_context(request,company['id'],[company])
    assert context['tab']==('overview'if tab=='unknown'else tab)
    assert context['company_news_model']==(news if wants_news else None)
    assert context['profile_regions']==(regions[:1]if wants_regions else [])
    assert calls.count('news')==int(wants_news)
    assert calls.count('regions')==int(wants_regions)
    assert calls.count('published')==int(wants_news or wants_regions)
    assert calls.count('sources')==int(authoring and (wants_news or wants_regions))
    assert record==before and not list(tmp_path.iterdir())
