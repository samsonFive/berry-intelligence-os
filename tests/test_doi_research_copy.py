import httpx
import pytest
from app.services.doi_research_copy import publisher_doi, fetch_doi_abstract


def response(**overrides):
    return {'DOI':'10.1111/synthetic.capture','title':['Synthetic blueberry experiment'],
            'abstract':'<jats:p>An owned abstract with p &lt; 0.05.</jats:p>',
            'published-online':{'date-parts':[[2021,6,12]]},**overrides}


def client_for(record):
    def handle(request):
        assert request.url.host=='api.crossref.org'
        assert str(request.url).startswith('https://api.crossref.org/works/')
        return httpx.Response(200,json={'message':record})
    return httpx.Client(transport=httpx.MockTransport(handle))


def test_exact_doi_deposit_keeps_original_scope_date_and_locator():
    url='https://onlinelibrary.wiley.com/doi/full/10.1111/synthetic.capture?version=old'
    with client_for(response())as client:row=fetch_doi_abstract(url,client=client)
    assert row['original_url']==url and row['availability']=='excerpt_only'
    assert row['copy_scope']=='publisher-deposited abstract'
    assert row['passages']==['An owned abstract with p < 0.05.']
    assert row['passage_locators']==['publisher-deposited-abstract:0']
    assert row['published_date']=='2021-06-12'
    assert row['repository_identifiers']['requested_publisher_version']=='old'
    assert 'full-text/version not acquired'in row['reason']


@pytest.mark.parametrize('record',[response(DOI='10.1111/another'),response(abstract=None)])
def test_wrong_identity_or_no_deposit_never_substitutes(record):
    with client_for(record)as client:
        assert fetch_doi_abstract('https://onlinelibrary.wiley.com/doi/10.1111/synthetic.capture',client=client)is None


def test_year_only_and_metadata_created_dates_do_not_become_publication_dates():
    with client_for(response(**{'published-online':{'date-parts':[[2021]]},'created':{'date-parts':[[2021,6,12]]}}))as client:
        row=fetch_doi_abstract('https://doi.org/10.1111/synthetic.capture',client=client)
    assert row['published_date']is None and row['published_date_basis']=='unknown'


def test_mdpi_candidate_requires_exact_publisher_resource_identity():
    url='https://www.mdpi.com/2073-4395/12/10/2279/pdf'
    base=response(DOI='10.3390/agronomy12102279')
    with client_for(base)as client:assert fetch_doi_abstract(url,client=client)is None
    with client_for({**base,'resource':{'primary':{'URL':'https://www.mdpi.com/2073-4395/12/10/22790'}}})as client:
        assert fetch_doi_abstract(url,client=client)is None
    with client_for({**base,'resource':{'primary':{'URL':'https://www.mdpi.com/2073-4395/12/10/2279'}}})as client:
        assert fetch_doi_abstract(url,client=client)['repository_identifiers']['doi']==base['DOI']


@pytest.mark.parametrize('url',['https://onlinelibrary.wiley.com.attacker.example/doi/10.1111/synthetic.capture',
 'https://attacker.example/10.1111/synthetic.capture','https://user@doi.org/10.1111/synthetic.capture',
 'http://doi.org/10.1111/synthetic.capture','https://doi.org:444/10.1111/synthetic.capture'])
def test_unrecognized_publisher_makes_no_request(url):
    def fail(request):raise AssertionError('unexpected request')
    with httpx.Client(transport=httpx.MockTransport(fail))as client:assert fetch_doi_abstract(url,client=client)is None


def test_springer_pdf_suffix_is_not_part_of_doi():
    assert publisher_doi('https://link.springer.com/content/pdf/10.1007/synthetic-2021.pdf')=='10.1007/synthetic-2021'


def test_public_ishs_abstract_requires_exact_article_number_not_a_nearby_page(monkeypatch):
    from app.services.doi_research_copy import fetch_ishs_abstract
    import app.services.feed_first_reader as reader
    body='A trial evaluated raspberry plants and cold-storage treatments under controlled conditions. '*3
    def capture(url,client):
        assert url=='https://ishs.org/ishs-article/1234_56/'
        return {'passages':['Article number 1234_56 Abstract '+body+' Publication Synthetic symposium'], 'published_date':'2026-01-01'}
    monkeypatch.setattr(reader,'fetch_public_article',capture)
    with httpx.Client()as client:row=fetch_ishs_abstract('https://www.actahort.org/books/1234/1234_56.htm',client=client)
    assert row['passages']==[body.strip()] and row['published_date']is None
    monkeypatch.setattr(reader,'fetch_public_article',lambda *a,**k:{'passages':['Article number 1234_57 Abstract '+body]})
    with httpx.Client()as client:assert fetch_ishs_abstract('https://www.actahort.org/books/1234/1234_56.htm',client=client)is None
