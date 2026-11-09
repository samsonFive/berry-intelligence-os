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
from urllib.parse import urlencode, quote, urlsplit, urljoin,unquote

import httpx
from lxml import etree, html

from app.services.ai_gateway.results import SearchHit, SearchResponse
from app.services.ai_gateway.errors import GatewayUnavailableError
from app.services.article_dedup import normalize_canonical_url
from app.services.feed_first_reader import _bounded_public_response, is_public_http_url

_OPENAIRE_REQUESTS=deque()
_OPENAIRE_LOCK=threading.Lock()
_MWMBL_LOCK=threading.Lock()
_MWMBL_LAST=0.0
_MWMBL_BLOCKED_UNTIL=0.0


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
    from app.services.variety_season import season_source_leads
    varieties=[e for e in entities.values() if e.get('entity_type')=='variety']
    notes=all_profile_source_details(data_dir,varieties=varieties)
    sources={key:[{'url':s['url'],'title':s['title']}for s in note['sources'].values()
                 if is_public_http_url(s['url'])]
            for key,note in notes.items() if note['status'] in {'source_reported','limited'}}
    for key, title, url, _ in season_source_leads(data_dir):
        if key in entities and (notes.get(key) or {}).get("status") != "identity_hold" and is_public_http_url(url):
            sources.setdefault(key, []).append({"url": url, "title": title})
    # Canonical varieties may predate identity-review metadata and already have
    # inspected public citations. Reuse explicit published links, not fuzzy
    # entity-name matches or private note text, as discovery leads.
    from pathlib import Path
    eligible=[e for e in entities.values()if e.get('entity_type')in {'variety','company','breeding_program'}]
    published={}
    for path in (Path(data_dir)/'evidence').rglob('*.json'):
        try:record=json.loads(path.read_text(encoding='utf8'))
        except (OSError,ValueError):continue
        if record.get('status')=='published':published[record.get('id')]=record
    # Public, attributed research imports already shown in the analyst lens
    # supply links only. Their pending claims are never indexed or approved.
    from app.services.gene_editing import load_snapshot
    try:research=(load_snapshot(data_dir)or{}).get('evidence',[])
    except (OSError,ValueError,KeyError):research=[]
    pending={r.get('id'):r for r in research if isinstance(r,dict)and r.get('status')in {'in_review','published'}}
    eligible_ids={e['id']for e in eligible}
    for record in [*published.values(),*pending.values()]:
        url=record.get('source_url')
        if not is_public_http_url(url):continue
        for key in record.get('entity_ids',[]):
            if key in eligible_ids and (notes.get(key)or{}).get('status')!='identity_hold':
                sources.setdefault(key,[]).append({'url':url,'title':record.get('title')or entities[key]['name']})
    for entity in eligible:
        if (notes.get(entity['id']) or {}).get('status')=='identity_hold':continue
        for eid in entity.get('evidence_ids') or []:
            if not re.fullmatch(r'[a-zA-Z0-9_-]+',eid):continue
            record=published.get(eid)or pending.get(eid)or{}
            linked=entity['id']in record.get('entity_ids',[])
            if not linked and entity.get('entity_type')=='breeding_program':
                from app.services.topic_retrieval import normalize
                title=normalize(record.get('title',''));name=normalize(entity.get('name',''))
                crops={c.removeprefix('berry-')for c in entity.get('berry_ids',[])}
                linked=bool(len(name)>=4 and re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',title)and crops&set(title.split()))
            if not linked:continue
            url=record.get('source_url')
            if url and is_public_http_url(url):
                sources.setdefault(entity['id'],[]).append({'url':url,'title':record.get('title')or entity['name']})
    return sources


def registered_primary_terms(data_dir,entities):
    """Local candidate index, never an external search payload or trait proof.

    Only the public, attributed import is indexed. Private analyst notes,
    source bodies, identity-held material and user annotations are excluded.
    """
    from app.services.variety_profile_sources import all_profile_source_details
    from app.services.variety_season import season_source_leads
    from app.services.topic_retrieval import normalize
    notes=all_profile_source_details(data_dir,varieties=[e for e in entities.values()if e.get('entity_type')=='variety'])
    terms={}
    for key, _, url, words in season_source_leads(data_dir):
        if key in entities and (notes.get(key) or {}).get("status") != "identity_hold" and is_public_http_url(url):
            terms.setdefault(url, set()).update(normalize(" ".join(words)).split())
    for note in notes.values():
        if note['status']not in {'source_reported','limited'}:continue
        for row in note['details']:
            url=note['sources'][row['source_id']]['url']
            if is_public_http_url(url):
                terms.setdefault(url,set()).update(normalize(' '.join(str(row.get(k)or'')for k in ('field','value','context'))).split())
    return {url:sorted(words)for url,words in terms.items()}


@dataclass
class PublicResearchSearchClient:
    entities: dict = field(default_factory=dict)
    primary_sources: dict = field(default_factory=dict)
    primary_terms: dict = field(default_factory=dict)
    get: object = None
    primary_get: object = None
    failures: list = field(default_factory=list)
    requests: int = 0
    primary_page_requests: int = 0
    primary_page_failures: list = field(default_factory=list)
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
        named=False
        for entity in self.entities.values():
            if entity.get('entity_type') not in {'variety','company','breeding_program'}:continue
            if (entity.get('attributes') or {}).get('catalog_removed'):continue
            names = [entity.get('name') or '', *(entity.get('aliases') or [])]
            if not any(len(normalize(n)) >= 4 and re.search(r'(?<!\w)'+re.escape(normalize(n))+r'(?!\w)', positive) for n in names):continue
            crop = {v.removeprefix('berry-') for v in entity.get('berry_ids') or []}
            asked = set(plan.terms)&{'blueberry','raspberry','strawberry','blackberry'}
            if asked and not crop&asked:
                if entity.get('entity_type')=='variety' or crop:continue
                # Crop-unassigned companies/programs need crop-bearing public
                # citation metadata. Corporate presence alone is insufficient.
                leads=self.primary_sources.get(entity['id'],[])
                if not any(asked&set(normalize(s.get('title','')).split())for s in leads):continue
            named=True
            review = (entity.get('attributes') or {}).get('identity_review') or {}
            url = review.get('source_url')
            if url and is_public_http_url(url):
                out.append(SearchHit(review.get('source_label') or entity['name'],url,'Registered identity-source lead; not a verified claim.'))
            for source in self.primary_sources.get(entity['id'],[]):
                if is_public_http_url(source.get('url')):
                    out.append(SearchHit(source.get('title') or entity['name'],source['url'],'Attributed technical-source lead; claims and dates require source inspection.'))
        if not named and not plan.phrases:
            # Match existing cited research notes locally, without exporting
            # their values to a search provider or treating them as traits.
            # This lets a cane/condition query find a primary lead even when
            # the analyst does not already know the cultivar name.
            asked=set(plan.terms)&{'blueberry','raspberry','strawberry','blackberry'}
            concepts=set(plan.terms)-asked-{'breeder','technical','sheet','sheets','variety','research','trial','breeding'}
            scored=[]
            for key,sources in self.primary_sources.items():
                entity=self.entities.get(key,{})
                if not asked or not asked&{v.removeprefix('berry-')for v in entity.get('berry_ids',[])}:continue
                if (entity.get('attributes')or{}).get('catalog_removed'):continue
                if any(normalize(n)in plan.exclusions for n in [entity.get('name')or'',*(entity.get('aliases')or[])]):continue
                for source in sources:
                    overlap=concepts&(set(normalize(source.get('title','')).split())|set(self.primary_terms.get(source.get('url'),[])))
                    if overlap and is_public_http_url(source.get('url')):
                        scored.append((len(overlap),source['url'],source))
            for _,_,source in sorted(scored,key=lambda row:(-row[0],row[1])):
                out.append(SearchHit(source['title'],source['url'],'Locally cited technical-source lead; source-reported notes are not verified classification.'))
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

    def _primary_links(self, query, seeds):
        """Find named sheets on already registered public catalog pages.

        Two same-host pages and their advertised public WordPress search APIs,
        no recursive crawl, no inferred cultivar aliases.
        Each linked candidate still needs independent body/scope inspection.
        """
        if self.get is not None and self.primary_get is None:return []
        from app.services.topic_retrieval import normalize
        positive=normalize(re.sub(r'(?<!\w)-("[^"]+"|[\w-]+)','',query))
        names={normalize(n) for e in self.entities.values() for n in [e.get('name')or'',*(e.get('aliases')or[])]
               if e.get('entity_type')=='variety' and len(normalize(n))>=4 and re.search(r'(?<!\w)'+re.escape(normalize(n))+r'(?!\w)',positive)}
        out=[]
        pages=[seed for seed in seeds if not urlsplit(seed.url).path.lower().endswith(('.pdf','.epub','.zip'))]
        for seed in pages[:2]:
            with self._lock:self.primary_page_requests+=1
            try:
                if self.primary_get is not None:raw=self.primary_get(seed.url)
                else:
                    with httpx.Client(timeout=4,follow_redirects=False)as client:
                        final,raw,_,_,status,_=_bounded_public_response(seed.url,client,limit=750_000)
                    if status!=200 or urlsplit(final).hostname.removeprefix('www.')!=urlsplit(seed.url).hostname.removeprefix('www.'):
                        self.primary_page_failures.append('PrimaryCatalogUnavailable')
                        continue
                root=html.fromstring(raw,parser=html.HTMLParser(no_network=True))
                anchors=sorted(root.xpath('//a[@href]'),key=lambda a:not urlsplit(a.get('href')).path.lower().endswith('.pdf'))
                for anchor in anchors:
                    target=urljoin(seed.url,anchor.get('href'))
                    if target==seed.url or not is_public_http_url(target)or urlsplit(target).hostname.removeprefix('www.')!=urlsplit(seed.url).hostname.removeprefix('www.'):continue
                    label=' '.join(anchor.itertext()).strip()
                    text=normalize(label+' '+unquote(urlsplit(target).path).replace('_',' '))
                    if any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',text)for name in names):
                        out.append(SearchHit(label or seed.title,target,'Named link from registered primary catalog; identity, claims and dates require inspection.'))
                    if len(out)>=4:return out
                # Search only an API explicitly advertised by the publisher.
                # No guessed CMS endpoints, admin calls or arbitrary host hops.
                apis=root.xpath('//link[@rel="https://api.w.org/"]/@href')
                if apis:
                    api=urljoin(seed.url,apis[0])
                    if (is_public_http_url(api)and urlsplit(api).hostname==urlsplit(seed.url).hostname
                            and urlsplit(api).path.endswith('/wp-json/')and not urlsplit(api).query):
                        from app.services.topic_retrieval import plan_query
                        plan=plan_query(query)
                        terms=' '.join(plan.phrases)if plan.phrases else' '.join(t for t in plan.terms if t not in {'blackberry','blueberry','raspberry','strawberry','breeder','technical','sheet','sheets'})
                        if not terms:continue
                        target=urljoin(api,'wp/v2/search')+'?'+urlencode({'search':terms[:240],'per_page':8,'type':'post'})
                        with self._lock:self.primary_page_requests+=1
                        if self.primary_get is not None:payload=json.loads(self.primary_get(target))
                        else:
                            with httpx.Client(timeout=4,follow_redirects=False)as client:
                                final,raw,_,_,status,limited=_bounded_public_response(target,client,limit=512000)
                            if status!=200 or limited or urlsplit(final).hostname!=urlsplit(api).hostname:
                                raise ValueError('PrimarySiteSearchUnavailable')
                            payload=json.loads(raw)
                        if not isinstance(payload,list):raise ValueError('InvalidPrimarySiteSearch')
                        for result in payload[:8]:
                            target=result.get('url')if isinstance(result,dict)else None
                            if target and is_public_http_url(target)and urlsplit(target).hostname==urlsplit(seed.url).hostname:
                                out.append(SearchHit(_text(result.get('title'))or seed.title,target,'Publisher public-search lead; independently captured body and original query scope remain required.'))
                                if len(out)>=4:return out
            except Exception as exc:
                # A source-page parse/access failure is not a global outage.
                self.primary_page_failures.append(type(exc).__name__)
                continue
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

    def _mwmbl(self, query, count):
        """Documented anonymous general-web API; no key or billing path.

        The provider hard-caps anonymous IP usage at 1,000/month and 1/sec.
        Serialize this process's calls and cool down on failures; never rotate
        hosts, identities or keys to evade quotas. Results remain metadata.
        """
        global _MWMBL_LAST,_MWMBL_BLOCKED_UNTIL
        from app.services.topic_retrieval import plan_query
        plan=plan_query(query)
        pieces=re.split(r'(-"[^"]+"|"[^"]+")',plan.interpreted_query)
        for i in range(0,len(pieces),2):
            pieces[i]=re.sub(r'\b(?:technical\s+sheets?|developments?|breeder)\b','',pieces[i],flags=re.I)
            pieces[i]=re.sub(r'\b\d{4}-\d{2}-\d{2}\b|\b(?:through|between|until)\b','',pieces[i])
        text=' '.join(''.join(pieces).split())
        if self.get is None:
            with _MWMBL_LOCK:
                now=time.monotonic()
                if now<_MWMBL_BLOCKED_UNTIL:raise GatewayUnavailableError('Anonymous web search cooling down')
                delay=max(0.0,1.05-(now-_MWMBL_LAST))
                if delay:time.sleep(delay)
                _MWMBL_LAST=time.monotonic()
                try:
                    raw=self._read('https://api.mwmbl.org/api/v2/search/?'+urlencode({'q':text}),'api.mwmbl.org')
                    payload=json.loads(raw)
                    if not isinstance(payload,dict)or not isinstance(payload.get('results'),list):raise ValueError('Invalid web-search response')
                except Exception:
                    _MWMBL_BLOCKED_UNTIL=time.monotonic()+300
                    raise
        else:
            raw=self._read('https://api.mwmbl.org/api/v2/search/?'+urlencode({'q':text}),'api.mwmbl.org')
            payload=json.loads(raw)
        if not isinstance(payload,dict)or not isinstance(payload.get('results'),list):raise ValueError('Invalid web-search response')
        return [SearchHit(_text(r.get('title'))[:500],r['url'],_text(r.get('content'))[:600])
                for r in payload['results'][:count]if isinstance(r,dict)and is_public_http_url(r.get('url'))]

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
        lanes=[('mwmbl_web',self._mwmbl),('openaire',self._openaire),('europe_pmc',self._pmc),('crossref',self._crossref),('google_news_rss',self._news)]
        results=[];errors=[]
        with ThreadPoolExecutor(max_workers=len(lanes)) as pool:
            futures=[pool.submit(fn,query,count)for _,fn in lanes]
            for (name,_),future in zip(lanes,futures):
                try:results.append((name,future.result()))
                except Exception as e:errors.append(name+':'+type(e).__name__)
        self.failures.extend(errors)
        registry = self._registry(query)
        if not results and not registry:
            raise GatewayUnavailableError('All public metadata discovery routes failed')
        # Interleave scholarly/news lanes so one fuzzy index cannot consume the
        # acquisition budget. Preserve ordering within each provider lane.
        rows=[*self._primary_links(query,registry),*registry[:4]]
        for i in range(count):
            rows.extend(items[i]for _,items in results if i<len(items))
        seen=set();hits=[]
        for row in rows:
            key=normalize_canonical_url(row.url)
            if key and key not in seen and is_public_http_url(row.url):
                seen.add(key);hits.append(row)
            if len(hits)==max_results:break
        return SearchResponse('public_metadata_fallback',query,tuple(hits),round(time.monotonic()-started,3))
