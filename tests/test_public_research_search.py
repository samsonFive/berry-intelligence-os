import json
from types import SimpleNamespace
from urllib.parse import urlsplit,parse_qs

import pytest

from app.services.ai_gateway.errors import GatewayAuthError,GatewayUnavailableError
from app.services.public_research_search import PublicResearchSearchClient
from app.services.resilient_topic_search import ResilientTopicSearchClient,_CIRCUITS
from app.services.topic_discovery import discover_topic
from app.services.topic_retrieval import plan_query


def metadata(url):
    p=urlsplit(url);params=parse_qs(p.query)
    if p.hostname=='api.mwmbl.org':return b'{"results":[]}'
    if p.hostname=='api.openaire.eu':return b'{"results":[]}'
    if p.hostname=='api.crossref.org':
        assert params['rows']==['10']
        return json.dumps({'message':{'items':[{'DOI':'10.1234/example','title':['Synthetic strawberry field trial'],'abstract':'<p>Metadata only.</p>'}]}}).encode()
    if p.hostname=='www.ebi.ac.uk':
        return json.dumps({'resultList':{'result':[{'id':'123','source':'MED','title':'Synthetic strawberry trial','pmcid':'PMC456'}]}}).encode()
    assert p.hostname=='news.google.com'
    return b'<rss><channel><item><title>Strawberry trial</title><link>https://publisher.example/trial</link></item></channel></rss>'


def test_public_routes_interleave_without_promoting_metadata_to_body():
    client=PublicResearchSearchClient(get=metadata)
    rows=client.search('strawberry trial').hits
    assert [r.url for r in rows]==['https://pmc.ncbi.nlm.nih.gov/articles/PMC456/','https://doi.org/10.1234/example','https://publisher.example/trial']
    assert client.requests==5 and client.failures==[]
    assert all(not hasattr(r,'article')for r in rows)


def test_saved_primary_urls_respect_positive_name_and_crop():
    entity=dict(id='v',entity_type='variety',name='Synthetic Scarlet',berry_ids=['berry-strawberry'],attributes={'identity_review':{'source_url':'https://breeder.example/scarlet'}})
    client=PublicResearchSearchClient(entities={'v':entity},get=metadata)
    assert client._registry('strawberry Synthetic Scarlet')
    assert not client._registry('strawberry -"Synthetic Scarlet"')
    assert not client._registry('blueberry Synthetic Scarlet')
    entity['attributes']['identity_review']['source_url']='http://127.0.0.1/private'
    assert not client._registry('strawberry Synthetic Scarlet')


def test_registered_catalog_follows_exact_named_sheet_without_recursive_or_external_links():
    entity=dict(id='v',entity_type='variety',name='Synthetic Scarlet',berry_ids=['berry-strawberry'],attributes={'identity_review':{'source_url':'https://breeder.example/varieties/'}})
    body=b'<main><a href="/sheets/synthetic-scarlet.pdf">Technical sheet</a><a href="/sheets/other.pdf">Other Scarlet</a><a href="https://outside.example/synthetic-scarlet.pdf">Synthetic Scarlet</a><a href="http://127.0.0.1/synthetic-scarlet">Synthetic Scarlet</a></main>'
    reads=[]
    def primary(url):reads.append(url);return body
    client=PublicResearchSearchClient(entities={'v':entity},get=metadata,primary_get=primary)
    hits=client.search('strawberry "Synthetic Scarlet" breeder technical sheet').hits
    assert hits[0].url=='https://breeder.example/sheets/synthetic-scarlet.pdf'
    assert reads==['https://breeder.example/varieties/'] and client.primary_page_requests==1
    assert not client._primary_links('strawberry -"Synthetic Scarlet"',client._registry('strawberry -"Synthetic Scarlet"'))
    assert not any('outside.example'in h.url or 'other.pdf'in h.url for h in hits)


def test_total_public_outage_without_source_leads_is_failure():
    def fail(url):raise TimeoutError('private transport detail')
    client=PublicResearchSearchClient(get=fail)
    with pytest.raises(GatewayUnavailableError):client.search('strawberry trial')
    assert client.requests==5 and all('private'not in x for x in client.failures)


def test_total_public_outage_keeps_named_primary_source_lead():
    def fail(url):
        raise TimeoutError()

    entity = {"id": "ervin", "entity_type": "variety", "name": "Ervin", "berry_ids": ["berry-blackberry"]}
    url = "https://rubus.ces.ncsu.edu/news/meet-ervin-blackberry/"
    client = PublicResearchSearchClient(
        get=fail, entities={"ervin": entity},
        primary_sources={"ervin": [{"title": "Ervin blackberry", "url": url}]},
    )
    response = client.search("Ervin blackberry")
    assert [hit.url for hit in response.hits] == [url]
    assert len(client.failures) == 5


def test_openaire_repository_leads_are_public_metadata_only():
    def get(url):
        if 'api.openaire.eu'in url:
            return json.dumps({'results':[{'mainTitle':'Synthetic strawberry field trial','instances':[{'urls':['http://127.0.0.1/private','https://doi.org/10.1234/work','https://repository.example/study']}]}]}).encode()
        return metadata(url)
    client=PublicResearchSearchClient(get=get)
    lead=client.search('strawberry field trial').hits[0]
    assert lead.url=='https://repository.example/study' and 'OpenAIRE Graph'in lead.snippet
    assert not hasattr(lead,'article')


def test_openaire_anonymous_budget_recovers_after_hour_without_network():
    from app.services.public_research_search import _OPENAIRE_REQUESTS,_reserve_openaire
    saved=list(_OPENAIRE_REQUESTS);_OPENAIRE_REQUESTS.clear()
    try:
        for _ in range(50):_reserve_openaire(10)
        with pytest.raises(GatewayUnavailableError):_reserve_openaire(11)
        _reserve_openaire(3610)
        assert list(_OPENAIRE_REQUESTS)==[3610]
    finally:
        _OPENAIRE_REQUESTS.clear();_OPENAIRE_REQUESTS.extend(saved)


def test_technical_source_leads_are_scoped_deduplicated_and_not_claims():
    entity=dict(id='v',entity_type='variety',name='Synthetic Scarlet',berry_ids=['berry-strawberry'],attributes={})
    sources={'v':[{'url':'https://breeder.example/release','title':'Strawberry release'},
                  {'url':'https://breeder.example/release','title':'Duplicate'},
                  {'url':'http://127.0.0.1/private','title':'Private'}]}
    client=PublicResearchSearchClient(entities={'v':entity},primary_sources=sources,get=metadata)
    hits=client.search('strawberry Synthetic Scarlet release').hits
    assert hits[0].url=='https://breeder.example/release'
    assert 'claims and dates require source inspection'in hits[0].snippet
    assert sum(h.url=='https://breeder.example/release'for h in hits)==1
    assert not client._registry('blueberry Synthetic Scarlet')
    assert not client._registry('strawberry -"Synthetic Scarlet"')
    entity['attributes']['catalog_removed']=True
    assert not client._registry('strawberry Synthetic Scarlet')


def test_primary_source_loader_does_not_expose_identity_holds():
    from pathlib import Path
    from app.services.public_research_search import registered_primary_sources
    entities={r['id']:r for p in Path('data/entities/varieties').glob('*.json')for r in [json.loads(p.read_text(encoding='utf8'))]}
    leads=registered_primary_sources('data',entities)
    assert 'variety-twilight'not in leads and 'variety-zara'not in leads
    assert any('niab.com/news' in s['url'] for s in leads['variety-malling-champion-22fb8a80'])
    assert all(set(s)=={'url','title'}for rows in leads.values()for s in rows)
    assert any('app00011977e.shtml'in s['url']for s in leads['variety-drisbluetwentythree'])


def test_partial_public_failure_is_briefly_cached_without_hiding_recovery(tmp_path):
    import os,time
    def get(url):
        if 'api.crossref.org'in url:raise TimeoutError()
        return metadata(url)
    client=ResilientTopicSearchClient(None,fallback=PublicResearchSearchClient(get=get))
    fetch=lambda url:dict(headline='Strawberry trial',passages=['Strawberry field trials compared fruit quality.'],published_date='2026-01-01',availability='full')
    plan=plan_query('strawberry field trial')
    first=discover_topic(plan,inbox_dir=tmp_path,client=client,fetcher=fetch)
    assert first['status']=='partial' and first['cache_ttl_seconds']==120
    count=client.fallback.requests
    warm=discover_topic(plan,inbox_dir=tmp_path,client=client,fetcher=fetch)
    assert warm['cache_hit'] and warm['fallback_requests_this_request']==0
    assert client.fallback.requests==count
    for p in (tmp_path/'topic_research_cache').glob('*.json'):os.utime(p,(time.time()-121,)*2)
    retry=discover_topic(plan,inbox_dir=tmp_path,client=client,fetcher=fetch)
    assert not retry['cache_hit'] and client.fallback.requests>count


def test_requested_document_format_does_not_reject_owned_variety_description():
    from app.services.topic_retrieval import match_record
    entity=dict(id='v',entity_type='variety',name='Synthetic Scarlet',berry_ids=['berry-strawberry'])
    record=dict(id='x',title='Synthetic Scarlet variety description',article={'paragraphs':[{'index':0,'text':'The strawberry variety Synthetic Scarlet was bred by Synthetic Breeder. The variety has firm fruit.'}]})
    assert match_record(record,plan_query('strawberry "Synthetic Scarlet" breeder technical sheet'),entities={'v':entity})['support_status']=='body_supported'
    assert match_record(record,plan_query('strawberry "technical sheet" "Synthetic Scarlet"'),entities={'v':entity}) is None
    caption={**record,'article':{'paragraphs':[{'index':0,'text':'Strawberry variety Synthetic Scarlet is shown in the photograph.'}]}}
    assert match_record(caption,plan_query('strawberry "Synthetic Scarlet" breeder technical sheet'),entities={'v':entity})['support_status']=='scope_unverified'


def test_primary_auth_fault_circuits_across_queries_and_resets_after_cooldown():
    _CIRCUITS.clear();calls=[];now=[0]
    class Primary:
        def search(self,q,**kw):
            calls.append(q)
            if len(calls)==1:raise GatewayAuthError('secret must not be surfaced')
            return SimpleNamespace(provider='primary',hits=[])
    fallback=PublicResearchSearchClient(get=metadata)
    client=ResilientTopicSearchClient(Primary(),credential='fixture',fallback=fallback,clock=lambda:now[0])
    assert client.search('strawberry trial').provider=='public_metadata_fallback'
    assert client.search('strawberry trial two').provider=='public_metadata_fallback'
    assert len(calls)==1 and client.diagnostics()['primary_failure']=='GatewayAuthError'
    now[0]=301
    assert client.search('strawberry trial three').provider=='primary'
    assert len(calls)==2
    _CIRCUITS.clear()


def test_fallback_cannot_evade_scope_and_warm_cache_does_not_repeat_calls(tmp_path):
    client=ResilientTopicSearchClient(None,fallback=PublicResearchSearchClient(get=metadata))
    def fetch(url):
        return dict(headline='Synthetic strawberry field trial',passages=['A strawberry field trial compared mildew resistance in two cultivars.'],published_date='2026-01-01',published_date_basis='publisher_metadata',availability='full')
    plan=plan_query('strawberry field trial "not present"')
    first=discover_topic(plan,inbox_dir=tmp_path,client=client,fetcher=fetch)
    assert first['status']=='partial' and first['fallback_used'] and first['items']==[]
    assert first['primary_failure']=='MissingCredentialError'
    count=client.fallback.requests
    second=discover_topic(plan,inbox_dir=tmp_path,client=client,fetcher=fetch)
    assert second['cache_hit'] and second['queries_this_request']==0
    assert client.fallback.requests==count
    assert second['primary_requests_this_request']==second['fallback_requests_this_request']==0


def test_specific_intervention_disease_and_geography_cannot_borrow_general_passage():
    from app.services.topic_retrieval import match_record
    entities={'es':dict(id='es',entity_type='geography',name='Spain',aliases=[])}
    def row(body):return dict(id='x',title='Strawberry nursery anthracnose Spain research ultraviolet greenhouse trials',published_date='2026-01-01',article={'paragraphs':[{'index':0,'text':body}]})
    wrong=row('A strawberry nursery experiment compared plant health in Louisiana. Anthracnose was recorded in this field study.')
    assert match_record(wrong,plan_query('strawberry nursery anthracnose Spain research'),entities=entities)['support_status']=='scope_unverified'
    assert match_record(row('Strawberry field trials measured mildew resistance in new cultivars.'),plan_query('strawberry ultraviolet disease control greenhouse trials'))['support_status']=='scope_unverified'
    assert match_record(row('Strawberry greenhouse trials used UV-C to control powdery mildew.'),plan_query('strawberry ultraviolet disease control greenhouse trials'))['support_status']=='body_supported'
    assert match_record(row('A strawberry nursery research study in Spain investigated Colletotrichum infection.'),plan_query('strawberry nursery anthracnose Spain research'),entities=entities)['support_status']=='body_supported'


def test_trademark_punctuation_and_explicit_cultivar_list_preserve_identity():
    from app.services.topic_retrieval import normalize,match_record
    entities={'v':dict(id='v',entity_type='variety',name='Synthetic Champion',aliases=[],berry_ids=['berry-strawberry'])}
    assert normalize('Synthetic™ Champion®')==normalize('Synthetic Champion')
    r=dict(id='x',title='Strawberries',article={'paragraphs':[{'index':0,'text':'The strawberry breeding programme includes the varieties Synthetic™ Champion and Other Scarlet.'}]})
    assert match_record(r,plan_query('strawberry Synthetic Champion breeder'),entities=entities)['support_status']=='body_supported'
    from app.services.topic_support import identity_in_passage
    assert identity_in_passage('Synthetic Champion is a new ever-bearer variety with firm fruit.',entities['v'])
    assert not identity_in_passage('Synthetic Champion is a new comedy film about a breeder.',entities['v'])


def test_scholarly_date_filters_are_not_literal_title_words():
    seen=[]
    def get(url):
        seen.append(url)
        return metadata(url)
    client=PublicResearchSearchClient(get=get)
    client.search('strawberry ultraviolet greenhouse trials 2020-01-01 through 2026-11-03')
    params=parse_qs(urlsplit(next(u for u in seen if 'api.crossref.org'in u)).query)
    assert '2020'not in params['query.bibliographic'][0]
    assert params['filter']==['from-pub-date:2020-01-01,until-pub-date:2026-11-03']


def test_owned_abstract_keeps_disease_definition_with_field_validation():
    from app.services.topic_retrieval import match_record
    body='Powdery mildew (PM) resistance in strawberry was studied. '+('We measured genetic and physiological responses. '*26)+' Field trials compared PM resistance in cultivars.'
    row=dict(id='abstract',title='Strawberry resistance experiment',article={'paragraphs':[{'index':0,'text':body}]})
    match=match_record(row,plan_query('strawberry powdery mildew resistance cultivar field trials'))
    assert match['support_status']=='body_supported'
    assert match['passage'] in body and len(match['passage'])<=2400


def test_field_capacity_and_future_pollination_work_cannot_be_field_evidence():
    from app.services.topic_support import passage_intent_supported
    plan=plan_query('blueberry pollination bumblebee fruit set field experiment')
    assert not passage_intent_supported('Blueberry plants were tested at 80% field capacity. Honeybees were used in controlled pollination experiments.',plan)
    assert not passage_intent_supported('Blueberry volatiles were tested on Bombus terrestris in laboratory experiments. The compounds should be evaluated under greenhouse and open-field conditions for fruit set.',plan)
    assert passage_intent_supported('A blueberry field experiment compared bumblebee visitation and fruit set in replicated plots.',plan)
