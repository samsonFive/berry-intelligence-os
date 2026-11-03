"""Bounded credit-free metadata discovery; never source truth or model output.

These public indexes are narrower than a general web search. Candidates still
pass through the shared reader and all original query/scope checks.
"""
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from dataclasses import dataclass, field
import json
import re
import time
import threading
from urllib.parse import urlencode, quote, urlsplit

import httpx
from lxml import etree, html

from app.services.ai_gateway.results import SearchHit, SearchResponse
from app.services.ai_gateway.errors import GatewayUnavailableError
from app.services.article_dedup import normalize_canonical_url
from app.services.feed_first_reader import _bounded_public_response, is_public_http_url

_OPENAIRE_REQUESTS=deque()
_OPENAIRE_LOCK=threading.Lock()


def _reserve_openaire(now):
    # Anonymous allowance is 60/hour. Keep headroom for other local clients;
    # upstream 429s remain ordinary partial-route failures across processes.
    with _OPENAIRE_LOCK:
        while _OPENAIRE_REQUESTS and now-_OPENAIRE_REQUESTS[0]>=3600:_OPENAIRE_REQUESTS.popleft()
        if len(_OPENAIRE_REQUESTS)>=50:raise GatewayUnavailableError('Public research hourly budget reached')
        _OPENAIRE_REQUESTS.append(now)


def _text(value):
    return ' '.join(html.fragment_fromstring(str(value or ''), create_parent='div').itertext()).strip()


def registered_primary_sources(data_dir, entities):
    """Reuse attributed profile citations as leads, never their trait claims."""
    from app.services.variety_profile_sources import all_profile_source_details
    varieties=[e for e in entities.values() if e.get('entity_type')=='variety']
    notes=all_profile_source_details(data_dir,varieties=varieties)
    sources={key:[{'url':s['url'],'title':s['title']} for s in note['sources'].values()
                 if is_public_http_url(s['url'])]
            for key,note in notes.items() if note['status'] in {'source_reported','limited'}}
    # Canonical varieties may predate identity-review metadata and already have
    # inspected public citations. Reuse explicit published links, not fuzzy
    # entity-name matches or private note text, as discovery leads.
    from pathlib import Path
    for entity in varieties:
        if (notes.get(entity['id']) or {}).get('status')=='identity_hold':continue
        for eid in entity.get('evidence_ids') or []:
            if not re.fullmatch(r'[a-zA-Z0-9_-]+',eid):continue
            path=Path(data_dir)/'evidence'/f'{eid}.json'
            try:record=json.loads(path.read_text(encoding='utf8'))
            except (OSError,ValueError):continue
            if record.get('status')!='published' or entity['id'] not in record.get('entity_ids',[]):continue
            url=record.get('source_url')
            if url and is_public_http_url(url):
                sources.setdefault(entity['id'],[]).append({'url':url,'title':record.get('title')or entity['name']})
    return sources


@dataclass
class PublicResearchSearchClient:
    entities: dict = field(default_factory=dict)
    primary_sources: dict = field(default_factory=dict)
    get: object = None
    failures: list = field(default_factory=list)
    requests: int = 0
    _lock: object = field(default_factory=threading.Lock, repr=False)

    def _read(self, url, host):
        # Fixed public metadata hosts; redirects are preflighted by the reader.
        with self._lock:self.requests += 1
        if self.get is not None:
            return self.get(url)
        with httpx.Client(timeout=4, follow_redirects=False) as client:
            final, raw, _, _, status, limited = _bounded_public_response(url, client, limit=1_000_000)
        if status != 200 or limited or urlsplit(final).hostname != host:
            raise GatewayUnavailableError('Public metadata response unavailable')
        return raw

    def _registry(self, query):
        from app.services.topic_retrieval import normalize, plan_query
        plan = plan_query(query)
        # A negative-only name is never a positive seed. Normal matching still
        # enforces quoted phrases; this does not rewrite or approve aliases.
        positive = normalize(re.sub(r'(?<!\w)-("[^"]+"|[\w-]+)', '', query))
        out = []
        for entity in self.entities.values():
            if entity.get('entity_type') != 'variety':continue
            if (entity.get('attributes') or {}).get('catalog_removed'):continue
            names = [entity.get('name') or '', *(entity.get('aliases') or [])]
            if not any(len(normalize(n)) >= 4 and re.search(r'(?<!\w)'+re.escape(normalize(n))+r'(?!\w)', positive) for n in names):continue
            crop = {v.removeprefix('berry-') for v in entity.get('berry_ids') or []}
            asked = set(plan.terms)&{'blueberry','raspberry','strawberry','blackberry'}
            if asked and not crop&asked:continue
            review = (entity.get('attributes') or {}).get('identity_review') or {}
            url = review.get('source_url')
            if url and is_public_http_url(url):
                out.append(SearchHit(review.get('source_label') or entity['name'],url,'Registered identity-source lead; not a verified claim.'))
            for source in self.primary_sources.get(entity['id'],[]):
                if is_public_http_url(source.get('url')):
                    out.append(SearchHit(source.get('title') or entity['name'],source['url'],'Attributed technical-source lead; claims and dates require source inspection.'))
        # Relevant titles affect only which known URLs get acquired. Final
        # passage ranking still enforces the complete original query.
        words=set(plan.terms)
        out.sort(key=lambda hit:sum(w in normalize(hit.title).split() for w in words),reverse=True)
        seen=set();unique=[]
        for hit in out:
            key=normalize_canonical_url(hit.url)
            if key not in seen:seen.add(key);unique.append(hit)
        return unique[:4]

    def _crossref(self, query, count):
        from app.services.topic_retrieval import plan_query
        plan=plan_query(query)
        text=re.sub(r'\b\d{4}-\d{2}-\d{2}\b','',query)
        text=re.sub(r'\b(?:through|between|until)\b','',text,flags=re.I)
        if '"' not in text and not re.search(r'(?<!\w)-\w',text):
            text=' '.join(w for w in plan.terms if w not in {'research','trial','variety','control','disease'})
        params={'query.bibliographic':text,'rows':count,'select':'DOI,title,abstract,resource'}
        filters=[]
        if plan.start:filters.append('from-pub-date:'+plan.start)
        if plan.end:filters.append('until-pub-date:'+plan.end)
        if filters:params['filter']=','.join(filters)
        records=json.loads(self._read('https://api.crossref.org/works?'+urlencode(params),'api.crossref.org'))['message']['items']
        out=[]
        for r in records:
            doi=r.get('DOI') or ''
            if not re.fullmatch(r'10\.\d{4,9}/\S{1,180}',doi):continue
            # DOI resolution is identity-specific; deposited abstracts are
            # separately acquired/provenanced by the existing copy reader.
            out.append(SearchHit(_text((r.get('title')or[''])[0]),'https://doi.org/'+quote(doi,safe='/'),_text(r.get('abstract'))[:600]))
        return out

    def _pmc(self, query, count):
        # Only literal words/phrases are submitted as a relevance query. Public
        # indexes cannot interpret our UI's date grammar; final filtering stays
        # in the shared passage matcher, using captured publication dates.
        text=re.sub(r'\b\d{4}-\d{2}-\d{2}\b','',query)
        text=re.sub(r'\b(?:through|between|until)\b','',text,flags=re.I)
        if '"' not in text and not re.search(r'(?<!\w)-\w',text):
            from app.services.topic_retrieval import plan_query
            # Research/experiment words express intent rather than mandatory
            # abstract vocabulary. Exact original constraints remain enforced
            # on captured passages; names, places and exclusions are retained.
            words=[w for w in plan_query(text).terms if w not in {'research','trial','variety','control','disease'}]
            words=[('(ultraviolet OR UVC OR UVB OR "UV-C" OR "UV-B")' if w=='ultraviolet' else '(greenhouse OR glasshouse OR "high tunnel")' if w=='greenhouse' else w)for w in words]
            text=' AND '.join(words)
        params={'query':text,'format':'json','resultType':'lite','pageSize':count,'synonym':'false'}
        records=json.loads(self._read('https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urlencode(params),'www.ebi.ac.uk'))['resultList']['result']
        out=[]
        for r in records:
            pmcid=r.get('pmcid')or'';pmid=r.get('id')or''
            if re.fullmatch(r'PMC\d+',pmcid):url='https://pmc.ncbi.nlm.nih.gov/articles/'+pmcid+'/'
            elif r.get('source')=='MED' and re.fullmatch(r'\d+',pmid):url='https://pubmed.ncbi.nlm.nih.gov/'+pmid+'/'
            else:continue
            out.append(SearchHit(_text(r.get('title')),url,''))
        return out

    def _news(self, query, count):
        params={'q':query,'hl':'en-US','gl':'US','ceid':'US:en'}
        raw=self._read('https://news.google.com/rss/search?'+urlencode(params),'news.google.com')
        root=etree.fromstring(raw,etree.XMLParser(resolve_entities=False,no_network=True))
        if root.tag!='rss':raise ValueError('Not an RSS response')
        return [SearchHit(x.findtext('title')or'',x.findtext('link')or'',_text(x.findtext('description'))) for x in root.findall('./channel/item')[:count]]

    def _openaire(self, query, count):
        # Public, unauthenticated Graph v4. Repository instance links can lead
        # to editions not surfaced by the biomedical/deposited-abstract lanes.
        # Titles/descriptions remain metadata until separately captured.
        if self.get is None:_reserve_openaire(time.monotonic())
        text=re.sub(r'\b\d{4}-\d{2}-\d{2}\b','',query)
        text=re.sub(r'\b(?:through|between|until)\b','',text,flags=re.I)
        params={'search':text,'pageSize':count,'filter':'type:publication'}
        records=json.loads(self._read('https://api.openaire.eu/graph/v4/research-products?'+urlencode(params),'api.openaire.eu'))['results']
        out=[]
        for record in records[:count]:
            urls=[u for instance in record.get('instances')or[] for u in instance.get('urls')or[] if is_public_http_url(u)]
            # Prefer a repository/publisher edition over another DOI redirect.
            urls.sort(key=lambda u:urlsplit(u).hostname in {'doi.org','dx.doi.org'})
            if not urls:
                urls=['https://doi.org/'+quote(p['value'],safe='/')for p in record.get('pids')or[]if p.get('scheme')=='doi'and re.fullmatch(r'10\.\d{4,9}/\S{1,180}',p.get('value')or'')]
            if urls:out.append(SearchHit(_text(record.get('mainTitle')),urls[0],'OpenAIRE Graph metadata lead (CC BY); inspect the linked source.'))
        return out

    def search(self, query, *, max_results=10, **kwargs):
        if not query.strip() or not 1<=max_results<=20:raise ValueError('Invalid public metadata query')
        started=time.monotonic();count=min(max_results,10)
        lanes=[('openaire',self._openaire),('europe_pmc',self._pmc),('crossref',self._crossref),('google_news_rss',self._news)]
        results=[];errors=[]
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(fn,query,count)for _,fn in lanes]
            for (name,_),future in zip(lanes,futures):
                try:results.append((name,future.result()))
                except Exception as e:errors.append(name+':'+type(e).__name__)
        self.failures.extend(errors)
        if not results:
            # A few saved identity URLs are not evidence that live search ran.
            raise GatewayUnavailableError('All public metadata discovery routes failed')
        registry=self._registry(query)
        # Interleave scholarly/news lanes so one fuzzy index cannot consume the
        # acquisition budget. Preserve ordering within each provider lane.
        rows=registry[:4]
        for i in range(count):
            rows.extend(items[i]for _,items in results if i<len(items))
        seen=set();hits=[]
        for row in rows:
            key=normalize_canonical_url(row.url)
            if key and key not in seen and is_public_http_url(row.url):
                seen.add(key);hits.append(row)
            if len(hits)==max_results:break
        return SearchResponse('public_metadata_fallback',query,tuple(hits),round(time.monotonic()-started,3))
