"""One selection/evidence bundle for every visual, count and briefing export."""
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
from urllib.parse import urlencode
from .model import PLATFORMS, MODES
from .extraction import ASPECTS, VOCAB

VIEWS=('posts','phrases','heatmap','atlas','momentum','coverage')
MIN_SAMPLE=5

def selection(params):
    f={k:str(params.get(k,'') or '') for k in ('source','language','market','entity','role','start','end','q')}
    f.update(mode=str(params.get('mode','live')),view=str(params.get('view','posts')),berry=str(params.get('berry','berry-blueberry')))
    if f['mode'] not in MODES or f['view'] not in VIEWS or f['berry'] not in VOCAB or f['source'] and f['source'] not in PLATFORMS:
        raise ValueError('Invalid social selection')
    for k in ('start','end'):
        if f[k]: datetime.strptime(f[k],'%Y-%m-%d')
    if f['start'] and f['end'] and f['start']>f['end']: raise ValueError('Date range is reversed')
    if any(len(v)>300 for v in f.values()): raise ValueError('Filter too long')
    return f

def href(filters,**changes):
    return '/social?'+urlencode({**filters,**changes})

def bundle(records,jobs,params, *, access=None):
    f=selection(params)
    rows=[]
    for r in records:
        a=r['analysis']; day=(r['published_at'] or r['collected_at'])[:10]
        if r['mode']!=f['mode'] or f['berry'] not in a.get('berry_ids',[]): continue
        if any(f[k] and r[rk]!=f[k] for k,rk in (('source','source'),('language','language'),('role','content_role'))): continue
        if f['start'] and day<f['start'] or f['end'] and day>f['end']: continue
        if f['market'] and (r.get('purchase_market') or {}).get('value')!=f['market']: continue
        if f['entity'] and f['entity'] not in {link['entity_id'] for link in a.get('entity_links',[])}: continue
        if f['q'] and f['q'].casefold() not in r['text'].casefold(): continue
        rows.append(r)
    by_id={r['id']:r for r in rows}; total=len(rows)
    phrases=defaultdict(set); labels=defaultdict(set); heat=defaultdict(list); timeline=defaultdict(set); countries=defaultdict(set)
    fingerprints=Counter(r['analysis'].get('content_fingerprint') for r in rows)
    for r in rows:
        a=r['analysis']; rid=r['id']
        for asp in a['aspects']:
            heat[asp['aspect']].append((rid,asp['sentiment']))
            phrases[asp['aspect']].add(rid)
            labels[asp['aspect']].update(h['span']['text'] for h in asp['evidence'])
        for link in a['retailers']:
            phrases[link['name']+' · '+link['relation']].add(rid)
            labels[link['name']+' · '+link['relation']].add(link['span']['text'])
        day=(r['published_at'] or r['collected_at'])[:10]; timeline[day].add(rid)
        countries[(r.get('purchase_market') or {}).get('value','Unknown purchase location')].add(rid)
    cells=[]
    for aspect in ASPECTS:
        values=heat[aspect]; counts=Counter(s for _,s in values); denominator=len(values)
        cells.append({'aspect':aspect,'count':denominator,'denominator':denominator,'sample_size':denominator,
                      'scope_denominator':total,'sentiment':dict(counts),'state':'insufficient evidence' if denominator<MIN_SAMPLE else 'observed sample',
                      'evidence_ids':sorted({i for i,_ in values})})
    phrase_rows=[]
    for p,ids in sorted(phrases.items(),key=lambda x:(-len(x[1]),x[0])):
        phrase_rows.append({'phrase':p,'labels':sorted(labels[p]),'count':len(ids),'denominator':total,'evidence_ids':sorted(ids),
                            'sentiment':dict(Counter(s for c in cells if c['aspect']==p for s,n in c['sentiment'].items() for _ in range(n)))})
    health=[]
    clock=datetime.now(timezone.utc)
    for platform in PLATFORMS:
        source_jobs=[j for j in jobs if j['source']==platform]
        status=(access or {}).get(platform,{}).get('status','setup-required')
        for j in source_jobs:
            last=j.get('last_success')
            stale=bool(last and clock-datetime.fromisoformat(last)>timedelta(days=1))
            health.append({**j,'status':'stale' if stale and j['status'] in ('live','partial') else j['status']})
        for market,language in [('US','en'),('Spain','es'),('Brazil','pt'),('China','zh'),('Japan','ja')]:
            if not any(j['market']==market and j['language']==language for j in source_jobs):
                health.append({'source':platform,'status':status,'market':market,'language':language,'last_success':None,'observed_volume':None,
                               'failure':(access or {}).get(platform,{}).get('blocker','No configured automated collection; manual/import does not monitor this source')})
    warnings=['Counts are unique retained source records, not sales, market share or representative population sentiment.',
              'Translations are inspectable; literal concept rules do not establish fully validated multilingual understanding.',
              'Trend claims suppressed: pilot samples and collection comparability are not sufficient.']
    if f['mode']=='fixture': warnings.insert(0,'DEMO · synthetic fixture only. No live collection is represented.')
    if any(j.get('query_changed') or j['status'] not in ('live','partial') for j in health):
        warnings.append('Coverage contains new queries, unavailable sources or outages; a gap is not zero activity.')
    groups=[{'label':c,'count':len(ids),'evidence_ids':sorted(ids)} for c,ids in sorted(countries.items())]
    # Coordinates only from explicit evidence, never guessed from retailer/language.
    points=[{'id':r['id'],'label':r['purchase_market']['value'],'lat':r['purchase_market']['latitude'],'lon':r['purchase_market']['longitude'],
             'basis':r['purchase_market']['basis']} for r in rows if r.get('purchase_market') and r['purchase_market'].get('latitude') is not None and r['purchase_market'].get('longitude') is not None]
    return {'version':'social-1-'+hashlib.sha256(json.dumps([rows,jobs,f],sort_keys=True).encode()).hexdigest()[:12],
      'filters':f,'url':href(f),'records':rows,'by_id':by_id,'count':total,'phrases':phrase_rows,'heatmap':cells,'countries':groups,'points':points,
      'timeline':[{'day':d,'count':len(ids),'evidence_ids':sorted(ids),'trend':'qualified / insufficient comparable evidence',
        'themes':{concept:sorted(i for i in ids if concept in by_id[i]['analysis']['concepts']) for concept in sorted({c for i in ids for c in by_id[i]['analysis']['concepts']})},
        'entities':{entity:sorted(i for i in ids if any(l['entity_id']==entity for l in by_id[i]['analysis']['entity_links'])) for entity in sorted({l['entity_id'] for i in ids for l in by_id[i]['analysis']['entity_links']})}} for d,ids in sorted(timeline.items())],
      'health':health,'warnings':warnings,'role_counts':dict(Counter(r['record_role'] for r in rows)),
      'duplicate_content_groups':sum(n>1 for n in fingerprints.values()),
      'continuation':{'version':1,'node_ids':'canonical entity IDs; no social registry creation',
         'edge_types':['co-mention','claimed-purchase','label-identification','verified-relationship'],
         'rule':'Social proposals never enter Landscape registry relationships; verified-relationship requires an existing canonical relationship ID.',
         'views':['variety footprint','competitive attention','conversation network','market comparison','announcement → sighting → reaction'],
         'status':'design contract only; no live graph/navigation'}}
