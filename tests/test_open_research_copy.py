"""Repository-copy recovery uses exact identity and preserves edition scope."""
import httpx
import pytest

from app.services.open_research_copy import fetch_open_research_copy, fetch_topic_source, fetch_publisher_abstract


def transport(*, metadata=None, xml=None, full_status=200):
    metadata = metadata if metadata is not None else {'id':'123','source':'MED','pmid':'123',
        'pmcid':'PMC456','isOpenAccess':'Y','title':'Synthetic trial',
        'abstractText':'A publisher abstract about a <i>synthetic</i> trial (p < 0.05).',
        'firstPublicationDate':'2020-01-01'}
    def handler(request):
        if request.url.path.endswith('/search'):
            assert request.url.params['query'] in {'PMCID:PMC456','EXT_ID:123 AND SRC:MED'}
            return httpx.Response(200,json={'resultList':{'result':[metadata]}})
        assert str(request.url)=='https://www.ebi.ac.uk/europepmc/webservices/rest/PMC456/fullTextXML'
        return httpx.Response(full_status,content=xml or b'''<article><front><article-meta>
            <article-id pub-id-type="pmcid">PMC456</article-id>
            <pub-date pub-type="epub"><year>2020</year><month>5</month><day>7</day></pub-date>
            <abstract><p>Repository abstract.</p></abstract></article-meta></front>
            <body><sec><p>Trial body.</p></sec></body><back><ref-list><ref><p>Excluded reference.</p></ref></ref-list></back></article>''')
    return httpx.MockTransport(handler)


@pytest.mark.parametrize('url',['https://pmc.ncbi.nlm.nih.gov/articles/PMC456/',
                               'https://pubmed.ncbi.nlm.nih.gov/123/'])
def test_open_copy_binds_identity_locators_and_exact_publication_date(url):
    with httpx.Client(transport=transport()) as client:
        row=fetch_open_research_copy(url,client=client)
    assert row['canonical_url']=='https://europepmc.org/articles/PMC456'
    assert row['original_url']==url and row['copy_scope']=='open repository full text'
    assert row['published_date']=='2020-05-07'
    assert row['passages']==['Repository abstract.','Trial body.']
    assert row['passage_locators']==['repository:jats:p:0','repository:jats:p:1']


def test_unavailable_fulltext_retains_explicit_abstract_without_inferred_date():
    with httpx.Client(transport=transport(full_status=403)) as client:
        row=fetch_open_research_copy('https://pubmed.ncbi.nlm.nih.gov/123/',client=client)
    assert row['copy_scope']=='publisher-deposited abstract'
    assert row['availability']=='excerpt_only' and row['published_date'] is None
    assert row['passage_locators']==['repository:abstract:0']
    assert 'p < 0.05' in row['passages'][0]


def test_wrong_repository_identity_is_not_accepted():
    with httpx.Client(transport=transport(metadata={'id':'999','source':'MED'})) as client:
        assert fetch_open_research_copy('https://pubmed.ncbi.nlm.nih.gov/123/',client=client) is None


def test_wrong_fulltext_identity_cannot_replace_verified_abstract():
    with httpx.Client(transport=transport(xml=b'<article><front><article-meta><article-id pub-id-type="pmcid">PMC999</article-id></article-meta></front><body><p>Wrong copy.</p></body></article>')) as client:
        row=fetch_open_research_copy('https://pubmed.ncbi.nlm.nih.gov/123/',client=client)
    assert row['copy_scope']=='publisher-deposited abstract' and 'Wrong copy.' not in row['passages']


@pytest.mark.parametrize('url',['https://pmc.ncbi.nlm.nih.gov.attacker.example/articles/PMC456/',
    'https://pmc.ncbi.nlm.nih.gov/search/','http://pmc.ncbi.nlm.nih.gov/articles/PMC456/',
    'https://user@pmc.ncbi.nlm.nih.gov/articles/PMC456/'])
def test_unrecognized_urls_make_no_repository_request(url):
    def fail(request):raise AssertionError('unexpected request')
    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        assert fetch_open_research_copy(url,client=client) is None


def test_failed_recovery_keeps_original_blocked_status(monkeypatch):
    import app.services.feed_first_reader as reader
    original={'ok':False,'availability':'blocked','reason':'blocked','passages':[]}
    monkeypatch.setattr(reader,'fetch_public_article',lambda url:original)
    assert fetch_topic_source('https://publisher.example/blocked')==original


def crossref_transport(**overrides):
    record={'ISSN':['0018-5345'],'volume':'54','issue':'12','page':'2231-2239',
        'DOI':'10.21273/synthetic-test','title':['Synthetic cooling trial'],
        'abstract':'<jats:p>A publisher-deposited abstract.</jats:p>',
        'published-online':{'date-parts':[[2019,10,29]]},**overrides}
    def handler(request):
        assert request.url.host=='api.crossref.org'
        assert request.url.params['filter']=='from-pub-date:2019-01-01,until-pub-date:2019-12-31'
        return httpx.Response(200,json={'message':{'items':[record]}})
    return httpx.MockTransport(handler)


def test_publisher_deposit_requires_exact_journal_volume_issue_and_first_page():
    with httpx.Client(transport=crossref_transport()) as client:
        row=fetch_publisher_abstract('https://journals.ashs.org/view/journals/hortsci/54/12/article-p2231.xml',client=client)
    assert row['copy_scope']=='publisher-deposited abstract'
    assert row['published_date']=='2019-10-29'
    assert row['canonical_url']=='https://api.crossref.org/works/10.21273/synthetic-test'
    assert row['passages']==['A publisher-deposited abstract.']
    with httpx.Client(transport=crossref_transport()) as client:
        pdf=fetch_publisher_abstract('https://journals.ashs.org/downloadpdf/view/journals/hortsci/54/12/article-p2231.pdf',client=client)
    assert pdf['repository_identifiers']==row['repository_identifiers']


@pytest.mark.parametrize('overrides',[{'page':'2232-2239'},{'ISSN':['9999-9999']},{'issue':'11'},{'volume':'53'}])
def test_nearby_article_does_not_substitute_for_requested_citation(overrides):
    with httpx.Client(transport=crossref_transport(**overrides)) as client:
        assert fetch_publisher_abstract('https://journals.ashs.org/view/journals/hortsci/54/12/article-p2231.xml',client=client)is None


def test_incomplete_publication_date_remains_unknown():
    with httpx.Client(transport=crossref_transport(**{'published-online':{'date-parts':[[2019]]}})) as client:
        row=fetch_publisher_abstract('https://journals.ashs.org/view/journals/hortsci/54/12/article-p2231.xml',client=client)
    assert row['published_date']is None


def test_empty_publisher_abstract_does_not_become_captured_article():
    with httpx.Client(transport=crossref_transport(abstract='')) as client:
        assert fetch_publisher_abstract('https://journals.ashs.org/view/journals/hortsci/54/12/article-p2231.xml',client=client)is None


def test_redirect_notice_is_not_mistaken_for_readable_article(monkeypatch):
    import app.services.feed_first_reader as reader
    monkeypatch.setattr(reader,'fetch_public_article',lambda url:{'ok':True,'passages':['Click here if you are not automatically redirected after 5 seconds.']})
    row=fetch_topic_source('https://publisher.example/blocked')
    assert row['ok']is False and row['reason']=='redirect-interstitial' and row['passages']==[]


def test_readable_undated_ncbi_copy_can_recover_exact_repository_date(monkeypatch):
    from app.services import open_research_copy as service,feed_first_reader as reader
    direct={'ok':True,'passages':['Readable original abstract.'],'availability':'full','published_date':None}
    recovered={'ok':True,'passages':['Identity-checked repository abstract.'],'published_date':'2020-05-07',
        'published_date_basis':'repository_jats_publication_date','canonical_url':'https://europepmc.org/articles/PMC456','copy_scope':'open repository full text'}
    calls=[]
    monkeypatch.setattr(reader,'fetch_public_article',lambda u:dict(direct))
    monkeypatch.setattr(service,'fetch_open_research_copy',lambda u,**kw:(calls.append(u)or dict(recovered)))
    row=fetch_topic_source('https://pmc.ncbi.nlm.nih.gov/articles/PMC456/')
    assert row['published_date']=='2020-05-07'and row['copy_scope']=='open repository full text'
    assert row['original_capture_status']=='full'and 'no verified publication date'in row['original_capture_reason']
    direct['published_date']='2020-01-01'
    assert fetch_topic_source('https://pmc.ncbi.nlm.nih.gov/articles/PMC456/')['published_date']=='2020-01-01'
    assert len(calls)==1
    direct['published_date']=None
    recovered['published_date']=None
    assert fetch_topic_source('https://pmc.ncbi.nlm.nih.gov/articles/PMC456/')['passages']==direct['passages']
