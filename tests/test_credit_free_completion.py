import json
from types import SimpleNamespace
from urllib.parse import urlsplit,parse_qs

import httpx

from app.services.feed_first_reader import paragraphs_from_html,fetch_public_article
from app.services.doi_research_copy import fetch_doi_abstract
from app.services.public_research_search import PublicResearchSearchClient
from app.services.resilient_topic_search import ResilientTopicSearchClient
from app.services.topic_support import identity_in_passage


def test_credit_free_mode_never_calls_an_available_paid_primary(monkeypatch):
    monkeypatch.setenv('BIOS_RESEARCH_CREDIT_FREE_ONLY','1')
    def forbidden(*args,**kwargs):raise AssertionError('Paid search must be unreachable')
    fallback=SimpleNamespace(search=lambda *a,**k:'free results',failures=[],requests=1)
    client=ResilientTopicSearchClient(SimpleNamespace(search=forbidden),fallback=fallback)
    assert client.search('public berry query')=='free results'
    assert client.diagnostics()['primary_failure']=='CreditFreeMode'
    assert client.diagnostics()['primary_requests_this_request']==0
    from app.services.ai_gateway.credentials import resolve_perplexity_api_key,MissingCredentialError
    import pytest
    with pytest.raises(MissingCredentialError,match='disabled'):
        resolve_perplexity_api_key({'PERPLEXITY_API_KEY':'synthetic-not-a-real-key','BIOS_RESEARCH_CREDIT_FREE_ONLY':'1'})


def test_anonymous_web_api_preserves_literals_and_does_not_export_notes():
    calls=[]
    def get(url):
        calls.append(url)
        return json.dumps({'results':[{'title':'Cultivar source','url':'https://publisher.example/source','content':'Search metadata'},
            {'title':'Private','url':'http://127.0.0.1/admin'}]}).encode()
    client=PublicResearchSearchClient(get=get)
    hits=client._mwmbl('blackberry "Unknown Name" breeder technical sheet -software',10)
    q=parse_qs(urlsplit(calls[0]).query)['q'][0]
    assert '"Unknown Name"'in q and '-software'in q and 'technical sheet'not in q
    assert [h.url for h in hits]==['https://publisher.example/source']
    assert 'api_key'not in calls[0] and not hasattr(hits[0],'article')


def test_condition_query_can_discover_a_cited_source_without_knowing_the_name():
    entity={'id':'v-one','name':'Synthetic Scarlet','entity_type':'variety','berry_ids':['berry-blackberry']}
    client=PublicResearchSearchClient(entities={'v-one':entity},primary_sources={'v-one':[
        {'title':'Breeder technical sheet','url':'https://publisher.example/sheet'}]},primary_terms={'https://publisher.example/sheet':['floricane','trial','high','tunnels']})
    assert len(client._registry('Floricane blackberry developments'))==1
    assert not client._registry('Floricane blueberry developments')
    assert not client._registry('Blackberry "Unknown Name"')
    assert not entity.get('attributes')  # A lead does not create a trait.


def test_legacy_government_tables_require_exact_document_host_and_path():
    page='<html><body><h1>AVISO â€” Synthetic notice</h1><table><tr><th>Crop</th><th>Denomination</th><th>Historical number</th></tr><tr><td>Zarzamora</td><td>Synthetic Berry</td><td>2136</td></tr></table></body></html>'
    url='https://sidof.segob.gob.mx/notas/docFuente/1234567'
    rows=paragraphs_from_html(page,source_url=url)
    assert 'Zarzamora | Synthetic Berry | 2136'in rows
    for other in ['https://publisher.example/page','https://sidof.segob.gob.mx/search','https://sidof.segob.gob.mx.attacker.example/notas/docFuente/1234567']:
        assert 'Zarzamora | Synthetic Berry | 2136'not in paragraphs_from_html(page,source_url=other)
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,text=page)))as client:
        capture=fetch_public_article(url,client=client)
    assert 'Zarzamora | Synthetic Berry | 2136'in capture['passages']
    assert capture['availability']!='full' and 'prose may be incomplete'in capture['reason']


def test_direct_crossref_envelope_is_an_exact_deposited_abstract_not_raw_json():
    doi='10.1234/synthetic'
    def respond(request):return httpx.Response(200,json={'message':{'DOI':doi,'title':['Synthetic cultivar release'],'abstract':'<jats:p>Owned abstract.</jats:p>','published-print':{'date-parts':[[1987,8]]}}})
    with httpx.Client(transport=httpx.MockTransport(respond))as client:
        capture=fetch_doi_abstract('https://api.crossref.org/works/10.1234%2Fsynthetic',client=client)
    assert capture['passages']==['Owned abstract.']
    assert capture['copy_scope']=='publisher-deposited abstract' and capture['published_date']is None
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'message':{'DOI':'10.1234/other','abstract':'Wrong source'}})))as client:
        assert fetch_doi_abstract('https://api.crossref.org/works/'+doi,client=client)is None


def test_cultivar_description_cannot_borrow_a_person_from_the_previous_sentence():
    entity={'name':'Synthetic Scarlet','berry_ids':['berry-blueberry']}
    assert identity_in_passage('Synthetic Scarlet, a new low-chilling blueberry cultivar, was released.',entity)
    assert not identity_in_passage('The author was Synthetic Scarlet. A new low-chilling blueberry cultivar was released.',entity)
    assert not identity_in_passage('The evaluated blueberries used an established method (Synthetic Scarlet, 2020).',entity)


def test_publisher_search_requires_advertised_same_host_api_and_keeps_metadata_separate():
    from app.services.ai_gateway.results import SearchHit
    calls=[]
    def primary(url):
        calls.append(url)
        if '/wp/v2/search?'in url:
            assert parse_qs(urlsplit(url).query)['search']==['floricane']
            return json.dumps([{'title':'New floricane cultivar','url':'https://breeder.example/new-cultivar'},
                               {'title':'External','url':'https://outside.example/story'}]).encode()
        return b'<link rel="https://api.w.org/" href="https://breeder.example/wp-json/"><main>Public catalog</main>'
    client=PublicResearchSearchClient(get=lambda u:b'{}',primary_get=primary)
    hits=client._primary_links('floricane blackberry',[SearchHit('Catalog','https://breeder.example/catalog','')])
    assert [h.url for h in hits]==['https://breeder.example/new-cultivar']
    assert len(calls)==2 and client.primary_page_requests==2 and not hasattr(hits[0],'article')


def test_external_or_private_advertised_search_api_is_never_called():
    from app.services.ai_gateway.results import SearchHit
    for target in ['http://127.0.0.1/wp-json/','https://outside.example/wp-json/']:
        calls=[]
        def primary(url):calls.append(url);return ('<link rel="https://api.w.org/" href="'+target+'">').encode()
        client=PublicResearchSearchClient(get=lambda u:b'{}',primary_get=primary)
        assert not client._primary_links('floricane blackberry',[SearchHit('Catalog','https://breeder.example/catalog','')])
        assert calls==['https://breeder.example/catalog']
def test_company_and_program_public_citations_are_leads_without_exporting_claims(tmp_path):
    import json
    from app.services.public_research_search import registered_primary_sources,PublicResearchSearchClient
    entities={
        'c':{'id':'c','entity_type':'company','name':'Synthetic Plantik','aliases':[],'berry_ids':[],'evidence_ids':[]},
        'p':{'id':'p','entity_type':'breeding_program','name':'Synthetic Fontana','berry_ids':['berry-blackberry'],'evidence_ids':['published']},
    }
    folder=tmp_path/'imports/gene-editing-test';folder.mkdir(parents=True)
    (folder/'snapshot.json').write_text(json.dumps({'evidence':[{'id':'pending','status':'in_review','entity_ids':['c'],'title':'Strawberry heat tolerance partnership','source_url':'https://primary.example/heat','summary':'PRIVATE STRATEGY','article':{'full_text':'DO NOT EXPORT'}}]}))
    pub=tmp_path/'evidence/nested';pub.mkdir(parents=True)
    (pub/'published.json').write_text(json.dumps({'id':'published','status':'published','entity_ids':['c'],'title':'Synthetic Fontana blackberry introduced','source_url':'https://primary.example/compact'}))
    leads=registered_primary_sources(tmp_path,entities)
    assert set(leads)=={'c','p'}and 'PRIVATE'not in str(leads)and 'EXPORT'not in str(leads)
    client=PublicResearchSearchClient(entities=entities,primary_sources=leads)
    assert client._registry('Synthetic Plantik strawberry heat tolerance')[0].url=='https://primary.example/heat'
    assert client._registry('Synthetic Fontana blackberry')[0].url=='https://primary.example/compact'
    assert not client._registry('Synthetic Fontana blueberry')
    assert not client._registry('strawberry -"Synthetic Plantik"')
    assert entities['c']['berry_ids']==[]
