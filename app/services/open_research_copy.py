"""Bounded, identity-checked open repository copies for NCBI discovery URLs.

This is a separate published copy, never an authentication-wall bypass. Its
URL, edition, abstract/full-text scope and date basis travel with the capture.
No search provider, credentials, model or trust writes are involved.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from urllib.parse import urlencode, urlsplit

import httpx
from lxml import etree, html


def fetch_open_research_copy(url, *, client):
    """Return an official Europe PMC copy only for an exact PMID or PMCID."""
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.port not in (None, 443) or parsed.username:
        return None
    if parsed.hostname == 'pmc.ncbi.nlm.nih.gov':
        match = re.fullmatch(r'/articles/(PMC\d+)(?:/|/pdf/[^/]*)?', parsed.path)
        kind = 'pmcid'
    elif parsed.hostname == 'pubmed.ncbi.nlm.nih.gov':
        match = re.fullmatch(r'/(\d+)/?', parsed.path)
        kind = 'pmid'
    else:
        return None
    if not match:
        return None
    identifier = match[1]
    query = f'PMCID:{identifier}' if kind == 'pmcid' else f'EXT_ID:{identifier} AND SRC:MED'
    api = 'https://www.ebi.ac.uk/europepmc/webservices/rest/'
    from app.services.feed_first_reader import _bounded_public_response

    def read(target, limit):
        final, raw, _, _, status, limited = _bounded_public_response(target, client, limit=limit)
        if status != 200 or limited or urlsplit(final).hostname != 'www.ebi.ac.uk':
            raise ValueError('repository-response-unavailable')
        return raw

    try:
        metadata_url = api + 'search?' + urlencode({'query': query, 'format': 'json', 'resultType': 'core'})
        results = json.loads(read(metadata_url, 512_000)).get('resultList', {}).get('result', [])
        if len(results) != 1:
            return None
        record = results[0]
        if kind == 'pmcid':
            if record.get('pmcid') != identifier:
                return None
        elif record.get('id') != identifier or record.get('source') != 'MED':
            return None
        pmcid = record.get('pmcid')
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        passages, locators, stamp = [], [], None
        canonical = 'https://europepmc.org/abstract/MED/' + str(record.get('pmid') or record['id'])
        edition = 'publisher-deposited abstract'
        if record.get('abstractText'):
            # Europe PMC abstracts are HTML fragments and can contain literal
            # comparisons such as "p < 0.05", rather than well-formed XML.
            root = html.fragment_fromstring(record['abstractText'], create_parent='div')
            text = ' '.join(' '.join(root.itertext()).split())
            if text:
                passages, locators = [text], ['repository:abstract:0']
        if pmcid and re.fullmatch(r'PMC\d+', pmcid) and record.get('isOpenAccess') == 'Y':
            try:
                fulltext_url = api + pmcid + '/fullTextXML'
                root = etree.fromstring(read(fulltext_url, 4_000_000), parser)
                ids = {n.get('pub-id-type'): ''.join(n.itertext()).strip()
                       for n in root.xpath('./front/article-meta/article-id')}
                # Europe PMC JATS can label the numeric PMC id as "pmc".
                xml_pmc = ids.get('pmcid') or ids.get('pmc') or ''
                if xml_pmc.removeprefix('PMC') != pmcid.removeprefix('PMC'):
                    raise ValueError('repository-identity-mismatch')
                nodes = root.xpath('./front/article-meta/abstract//p|./body//p[not(ancestor::ref-list)]')
                body = [' '.join(' '.join(n.itertext()).split()) for n in nodes]
                if any(body):
                    passages = [p for p in body if p]
                    locators = ['repository:jats:p:' + str(i) for i, p in enumerate(body) if p]
                    canonical = 'https://europepmc.org/articles/' + pmcid
                    edition = 'open repository full text'
                    # FIRST_PDATE in the index may infer missing month/day.
                    # Only a complete publication date in this copy is eligible.
                    from app.services.article_acquisition import _publication_date
                    dates = []
                    for node in root.xpath('./front/article-meta/pub-date[not(@pub-type="collection")]'):
                        y, m, day = (node.findtext(k) for k in ('year', 'month', 'day'))
                        if y and m and day and all(v.isdigit() for v in (y, m, day)):
                            value = _publication_date(f'{int(y):04}-{int(m):02}-{int(day):02}')
                            if value:dates.append(value)
                    stamp = min(dates) if dates else None
            except (ValueError, etree.XMLSyntaxError, OSError, httpx.HTTPError):
                pass  # An available abstract remains explicitly an abstract.
        if not passages:
            return None
        return {'url': canonical, 'canonical_url': canonical, 'original_url': url,
                'ok': True, 'availability': 'partial' if edition.endswith('full text') else 'excerpt_only',
                'headline': record.get('title') or '', 'passages': passages, 'passage_locators': locators,
                'published_date': stamp, 'published_date_basis': 'repository_jats_publication_date' if stamp else 'unknown',
                'method': 'official_europe_pmc_api', 'copy_scope': edition,
                'reason': edition, 'images': [], 'content_kind': 'article',
                'frame_allowed': False, 'reader_modes': ['structured_fallback'],
                'retrieved_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'repository_identifiers': {k: record.get(k) for k in ('pmid', 'pmcid', 'doi') if record.get(k)}}
    except (ValueError, KeyError, TypeError, etree.XMLSyntaxError, OSError, httpx.HTTPError):
        return None


def fetch_topic_source(url):
    """Keep direct capture failures visible if no verified open copy exists."""
    import httpx
    from app.services.feed_first_reader import fetch_public_article, FETCH_TIMEOUT, USER_AGENT
    if urlsplit(url).hostname=='api.crossref.org':
        # JSON envelopes are not article prose. Read the exact DOI deposit
        # through the same identity/edition/date checks as publisher fallbacks.
        from app.services.doi_research_copy import fetch_doi_abstract
        from app.services.feed_first_reader import empty_capture
        with httpx.Client(timeout=FETCH_TIMEOUT,follow_redirects=False,headers={'User-Agent':USER_AGENT})as client:
            recovered=fetch_doi_abstract(url,client=client)
        return recovered or empty_capture(url,reason='deposited-abstract-unavailable')
    direct = fetch_public_article(url)
    text=' '.join(direct.get('passages') or [])
    if urlsplit(url).hostname in {'actahort.org','www.actahort.org','ishs.org','www.ishs.org','journals.ashs.org'} and direct.get('content_kind')!='pdf':
        # A citation heading/download footer is metadata, not readable paper
        # content. It must not prevent the exact publisher-copy fallback.
        compact=lambda s:re.sub(r'\W+','',s.casefold())
        title=compact(str(direct.get('headline')or''))
        body=[p for p in direct.get('passages')or[] if len(p)>=80 and compact(p)!=title
              and not re.match(r'^(?:Download Adobe|URL www\.|Division |Working Group |Commission )',p)]
        if not body:
            direct={**direct,'ok':False,'availability':'metadata_only','reason':'publisher-citation-metadata-only','passages':[]}
    if len(text)<300 and re.search(r'\b(?:automatically redirected|redirecting you)\b',text,re.I):
        from app.services.feed_first_reader import empty_capture
        direct=empty_capture(url,reason='redirect-interstitial')
    if direct.get('ok') and direct.get('passages'):
        # An undated readable NCBI HTML page can conceal its exact JATS date.
        # Prefer the already-supported, identity-checked official edition;
        # never borrow search dates, reference-list dates or modified dates.
        if not direct.get('published_date') and urlsplit(url).hostname in {'pmc.ncbi.nlm.nih.gov','pubmed.ncbi.nlm.nih.gov'}:
            try:
                with httpx.Client(timeout=FETCH_TIMEOUT,follow_redirects=False,headers={'User-Agent':USER_AGENT}) as client:
                    recovered=fetch_open_research_copy(url,client=client)
                if recovered and recovered.get('published_date'):
                    recovered['original_capture_status']=direct.get('availability')
                    recovered['original_capture_reason']='Readable original copy has no verified publication date'
                    return recovered
            except httpx.HTTPError:
                pass
        return direct
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=False, headers={'User-Agent': USER_AGENT}) as client:
            from app.services.doi_research_copy import fetch_doi_abstract, fetch_ishs_abstract
            recovered = (fetch_open_research_copy(url, client=client)
                         or fetch_publisher_abstract(url, client=client)
                         or fetch_doi_abstract(url, client=client)
                         or fetch_ishs_abstract(url, client=client))
        if recovered:
            recovered['original_capture_status'] = direct.get('availability')
            recovered['original_capture_reason'] = direct.get('reason')
            return recovered
    except httpx.HTTPError:
        pass
    return direct


def fetch_publisher_abstract(url, *, client):
    """A publisher's Crossref deposit, matched to the exact ASHS citation.

    A title search is deliberately insufficient to substitute an article copy.
    No full-text license is inferred from the existence of an abstract.
    """
    parsed=urlsplit(url)
    if parsed.scheme not in {'http','https'} or parsed.hostname!='journals.ashs.org' or parsed.username:
        return None
    citation=re.fullmatch(r'/(?:downloadpdf/)?view/journals/(hortsci|horttech|jashs)/(\d{1,3})/(\d{1,2})/article-p(\d{1,5})\.(?:xml|pdf)',parsed.path)
    if not citation:return None
    journal,volume,issue,page=citation.groups()
    issn,base={'hortsci':('0018-5345',1965),'horttech':('1063-0198',1990),'jashs':('0003-1062',1875)}[journal]
    year=int(volume)+base
    api='https://api.crossref.org/journals/'+issn+'/works?'+urlencode({
        'query.bibliographic':f'{journal} {volume} {issue} {page}', 'rows':8,
        'filter':f'from-pub-date:{year}-01-01,until-pub-date:{year}-12-31'})
    from app.services.feed_first_reader import _bounded_public_response
    try:
        final,raw,_,_,status,limited=_bounded_public_response(api,client,limit=512_000)
        if status!=200 or limited or urlsplit(final).hostname!='api.crossref.org':return None
        rows=json.loads(raw)['message']['items']
        matches=[r for r in rows if issn in r.get('ISSN',[]) and str(r.get('volume'))==volume
                 and str(r.get('issue'))==issue and str(r.get('page','')).split('-')[0]==page]
        if len(matches)!=1:return None
        record=matches[0]
        if not record.get('abstract') or not re.fullmatch(r'10\.\d{4,9}/[A-Za-z0-9.\-]+',record.get('DOI','')):return None
        root=etree.fromstring(('<abstract xmlns:jats="http://jats.nlm.nih.gov">'+record['abstract']+'</abstract>').encode(),
                              etree.XMLParser(resolve_entities=False,no_network=True))
        passage=' '.join(' '.join(root.itertext()).split())
        if not passage:return None
        dates=[]
        from app.services.article_acquisition import _publication_date
        for key in ('published-online','published-print'):
            parts=(record.get(key)or{}).get('date-parts')or[]
            if len(parts)==1 and len(parts[0])==3 and all(type(v)is int for v in parts[0]):
                value=_publication_date('%04d-%02d-%02d'%tuple(parts[0]))
                if value:dates.append(value)
        canonical='https://api.crossref.org/works/'+record['DOI']
        return {'url':canonical,'canonical_url':canonical,'original_url':url,'ok':True,
                'availability':'excerpt_only','headline':(record.get('title')or[''])[0],
                'passages':[passage],'passage_locators':['publisher-deposited-abstract:0'],
                'published_date':min(dates)if dates else None,
                'published_date_basis':'publisher_deposited_complete_publication_date'if dates else'unknown',
                'method':'official_crossref_api','copy_scope':'publisher-deposited abstract',
                'reason':'abstract only; full text not acquired','images':[],'content_kind':'article',
                'frame_allowed':False,'reader_modes':['structured_fallback'],
                'retrieved_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'repository_identifiers':{'doi':record['DOI'],'issn':issn,'volume':volume,'issue':issue,'first_page':page}}
    except (ValueError,KeyError,TypeError,etree.XMLSyntaxError,OSError,httpx.HTTPError):
        return None
