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
    assert client.requests==3 and client.failures==[]
    assert all(not hasattr(r,'article')for r in rows)


def test_saved_primary_urls_respect_positive_name_and_crop():
    entity=dict(id='v',entity_type='variety',name='Synthetic Scarlet',berry_ids=['berry-strawberry'],attributes={'identity_review':{'source_url':'https://breeder.example/scarlet'}})
    client=PublicResearchSearchClient(entities={'v':entity},get=metadata)
    assert client._registry('strawberry Synthetic Scarlet')
    assert not client._registry('strawberry -"Synthetic Scarlet"')
    assert not client._registry('blueberry Synthetic Scarlet')
    entity['attributes']['identity_review']['source_url']='http://127.0.0.1/private'
    assert not client._registry('strawberry Synthetic Scarlet')


def test_total_public_outage_is_failure_even_with_registered_seed():
    def fail(url):raise TimeoutError('private transport detail')
    client=PublicResearchSearchClient(get=fail)
    with pytest.raises(GatewayUnavailableError):client.search('strawberry trial')
    assert client.requests==3 and all('private'not in x for x in client.failures)


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
