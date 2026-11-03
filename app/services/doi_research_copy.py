"""Exact DOI publisher deposits, with explicit abstract/edition provenance.

No title search, subscriptions, model calls or trust writes. A deposit is an
alternative edition, never a claim that blocked publisher full text was read.
"""
from datetime import datetime, timezone
import json
import re
from urllib.parse import quote, unquote, urlsplit, parse_qs

import httpx
from lxml import etree

_MDPI = {'2073-4395':'agronomy', '2624-7402':'agriengineering',
         '2076-0825':'actuators', '2311-7524':'horticulturae', '2077-0472':'agriculture'}


def publisher_doi(url):
    """Return an explicit known-publisher DOI, or a verifiable MDPI candidate."""
    try:
        p=urlsplit(url)
        if p.scheme!='https' or p.port not in (None,443) or p.username or p.password:return None
    except ValueError:
        return None
    host=(p.hostname or '').lower();path=unquote(p.path)
    if host in {'mdpi.com','www.mdpi.com'}:
        parts=path.strip('/').split('/')
        if len(parts) not in (4,5) or (len(parts)==5 and parts[4]!='pdf'):return None
        journal=parts[0]
        if journal not in _MDPI or not all(re.fullmatch(r'\d{1,5}',s) for s in parts[1:4]):return None
        return '10.3390/'+_MDPI[journal]+parts[1]+parts[2].zfill(2)+parts[3].zfill(4)
    if host in {'doi.org','dx.doi.org'}:candidate=path.lstrip('/')
    elif (host=='onlinelibrary.wiley.com' or host.endswith('.onlinelibrary.wiley.com')
          or host in {'journals.sagepub.com','www.tandfonline.com','www.cabidigitallibrary.org'}):
        match=re.fullmatch(r'/doi/(?:full/|abs/|pdf/|epdf/)?(10\..+)',path)
        candidate=match[1]if match else ''
    elif host=='link.springer.com':
        match=re.fullmatch(r'/(?:article|content/pdf)/(10\..+?)(?:\.pdf)?',path)
        candidate=match[1]if match else ''
    else:return None
    return candidate if re.fullmatch(r'10\.\d{4,9}/[A-Za-z0-9._;()/:+\-]{1,180}',candidate)else None


def fetch_doi_abstract(url, *, client):
    doi=publisher_doi(url)
    if not doi:return None
    from app.services.feed_first_reader import _bounded_public_response
    target='https://api.crossref.org/works/'+quote(doi,safe='')
    try:
        final,raw,_,_,status,limited=_bounded_public_response(target,client,limit=512_000)
        if status!=200 or limited or urlsplit(final).hostname!='api.crossref.org':return None
        record=json.loads(raw)['message']
        if str(record.get('DOI','')).casefold()!=doi.casefold():return None
        if urlsplit(url).hostname in {'mdpi.com','www.mdpi.com'}:
            # Constructed DOI is only a lookup candidate. The publisher's
            # deposited resource must confirm the exact journal/article URL.
            expected=urlsplit(url).path.strip('/').split('/')[:4]
            links=[record.get('resource',{}).get('primary',{}).get('URL','')]
            links.extend(v.get('URL','')for v in record.get('link',[]))
            if not any(urlsplit(v).hostname in {'mdpi.com','www.mdpi.com'}
                       and urlsplit(v).path.strip('/').split('/')[:4]==expected for v in links):return None
        if not isinstance(record.get('abstract'),str):return None
        tree=etree.fromstring(('<abstract xmlns:jats="http://jats.nlm.nih.gov">'+record['abstract']+'</abstract>').encode(),
                              etree.XMLParser(resolve_entities=False,no_network=True))
        passages=[' '.join(' '.join(tree.itertext()).split())]
        if not passages[0]:return None
        from app.services.article_acquisition import _publication_date
        dates=[]
        for field in ('published-online','published-print'):
            parts=(record.get(field)or{}).get('date-parts')or[]
            if len(parts)==1 and len(parts[0])==3 and all(type(v)is int for v in parts[0]):
                stamp=_publication_date('%04d-%02d-%02d'%tuple(parts[0]))
                if stamp:dates.append(stamp)
        version=parse_qs(urlsplit(url).query).get('version',[''])[0]
        return {'url':target,'canonical_url':target,'original_url':url,'ok':True,
                'availability':'excerpt_only','headline':(record.get('title')or[''])[0],
                'passages':passages,'passage_locators':['publisher-deposited-abstract:0'],
                'published_date':min(dates)if dates else None,
                'published_date_basis':'publisher_deposited_complete_publication_date'if dates else'unknown',
                'method':'official_crossref_api','copy_scope':'publisher-deposited abstract',
                'reason':'Abstract only; requested publisher full-text/version not acquired',
                'images':[],'content_kind':'article','frame_allowed':False,'reader_modes':['structured_fallback'],
                'retrieved_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'repository_identifiers':{'doi':record['DOI'],**({'requested_publisher_version':version}if version else{})}}
    except (ValueError,KeyError,TypeError,etree.XMLSyntaxError,OSError,httpx.HTTPError):
        return None


def fetch_ishs_abstract(url, *, client):
    """Public publisher abstract for an exact legacy Acta article number."""
    p=urlsplit(url)
    if p.scheme not in {'https','http'} or p.hostname not in {'www.actahort.org','actahort.org'} or p.username:return None
    match=re.fullmatch(r'/books/(\d{1,5})/\1_(\d{1,4})\.htm',p.path)
    if not match:return None
    identifier=match[1]+'_'+match[2]
    target='https://ishs.org/ishs-article/'+identifier+'/'
    from app.services.feed_first_reader import fetch_public_article
    capture=fetch_public_article(target,client=client)
    text=' '.join(capture.get('passages')or[])
    if not re.search(r'\bArticle number\s+'+re.escape(identifier)+r'\b',text):return None
    abstract=re.search(r'\bAbstract\s+(.+)',text,re.S)
    if not abstract:return None
    passage=re.split(r'\b(?:Publication|Full text|Authors|Keywords)\s+',abstract[1],maxsplit=1)[0].strip()
    if len(passage)<120:return None
    return {**capture,'url':target,'canonical_url':target,'original_url':url,'ok':True,
            'availability':'excerpt_only','passages':[passage],'passage_locators':['publisher:abstract:0'],
            'published_date':None,'published_date_basis':'unknown',
            'method':'official_ishs_abstract_page','copy_scope':'publisher abstract extract',
            'reason':'Abstract extract only; full text and publication date not established',
            'images':[],'frame_allowed':False,'reader_modes':['structured_fallback'],
            'repository_identifiers':{'ishs_article_number':identifier}}
