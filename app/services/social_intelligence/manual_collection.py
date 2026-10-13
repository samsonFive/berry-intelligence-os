"""Operator-triggered, prepaid collection. Reads never collect or purchase.

One shared runtime lock, durable reservations before transport, no retries or
automatic restart, and bounded provider schemas. Trial guards remain unchanged.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import uuid
from functools import lru_cache
from app.services.analyst_state_io import atomic_json
from app.services.collection_runner import CollectionRunLock, CollectionLockedError
from .adapters import AccessBlocked
from .sociavault_pilot import MultiPlatformPilot, TASKS
from .sociavault_normalize import normalize
from .store import Store, identity, now
from .presentation import readable_in_english

VERSION = 'social-manual-1'
BERRIES = {'berry-blueberry':'blueberries', 'berry-strawberry':'strawberries',
           'berry-raspberry':'raspberries', 'berry-blackberry':'blackberries fruit'}
SOURCES = ('reddit','instagram','linkedin','x','facebook','youtube','tiktok')
FACEBOOK = ('https://www.facebook.com/FallCreekNursery', 'https://www.facebook.com/DriscollsBerries/')
MAX_REQUESTS = 40
MONTH_LIMIT = 200
TOTAL_LIMIT = 1000
RESERVE = 100

def plan(payload):
    if not isinstance(payload,dict) or set(payload)-{'berry','perspective','period','platforms'}:
        raise ValueError('Choose berry, scope, period and platforms')
    berry=payload.get('berry','all'); scope=payload.get('perspective','both'); period=payload.get('period','week')
    sources=payload.get('platforms',['reddit','instagram','linkedin','x','facebook'])
    if berry not in (*BERRIES,'all') or scope not in ('both','corporate','consumer') or period not in ('week','month'):
        raise ValueError('Unsupported collection scope')
    if not isinstance(sources,list) or not sources or any(s not in SOURCES for s in sources) or len(set(sources))!=len(sources):
        raise ValueError('Choose supported platforms once each')
    queries=[]; stamp=datetime.now(timezone.utc)
    for source in sources:
        if source=='facebook':
            if scope=='consumer':continue
            for url in FACEBOOK: queries.append({'source':source,'task':'facebook-posts','params':{'url':url},'scope':'corporate','berry':'all'})
            continue
        for key,term in BERRIES.items():
            if berry!='all' and key!=berry:continue
            scopes=['corporate','consumer'] if scope=='both' else [scope]
            if source=='linkedin':scopes=[s for s in scopes if s=='corporate']
            for target in scopes:
                query=term+' (grower OR breeding OR harvesting OR robotics)' if target=='corporate' else term
                if source=='instagram':
                    # Hashtag discovery cannot preserve a corporate phrase.
                    if target=='corporate':continue
                    params={'hashtag':term.split()[0],'date_posted':'last-week' if period=='week' else 'last-month','media_type':'all'}
                elif source=='reddit':params={'query':query,'sort':'new','timeframe':period,'trim':'false'}
                elif source=='linkedin':params={'query':query,'date_posted':'last-week' if period=='week' else 'last-month'}
                elif source=='x':params={'query':query+' since:'+(stamp-timedelta(days=7 if period=='week' else 30)).date().isoformat(),'type':'Latest'}
                elif source=='youtube':params={'query':query,'uploadDate':'this_week' if period=='week' else 'this_month','sortBy':'relevance'}
                else:params={'query':query,'date_posted':'this-week' if period=='week' else 'this-month','sort_by':'date-posted','trim':'false'}
                queries.append({'source':source,'task':source+'-search','params':params,'scope':target,'berry':key})
    if not queries or len(queries)>MAX_REQUESTS:raise ValueError('Choose a smaller scope; maximum 40 requests per update')
    options={'berry':berry,'perspective':scope,'period':period,'platforms':sources}
    digest=hashlib.sha256(json.dumps(options,sort_keys=True).encode()).hexdigest()
    return {'version':VERSION,'options':options,'queries':queries,'max_credits':len(queries),'fingerprint':digest,
            'note':'One page per search; dates depend on provider support. Facebook collects two known company pages, not global Facebook search. Language/role labels are proposed; unreadable posts stay out of the reader.'}

def enabled():
    return os.environ.get('BIOS_SOCIAL_MANUAL_COLLECTION')=='true' and bool(os.environ.get('SOCIAVAULT_API_KEY'))

def _paths(inbox):
    return Path(inbox)/'operations/collection.lock', Path(inbox)/'social/manual-credit-ledger.json'

def _ledger(path):
    if not path.exists():return {'version':VERSION,'reservations':[],'halted':False,'balance':None}
    value=json.loads(path.read_text())
    if value.get('version')!=VERSION or not isinstance(value.get('reservations'),list):raise AccessBlocked('Collection ledger requires operator repair')
    return value

def status(inbox):
    _,path=_paths(inbox); ledger=_ledger(path)
    jobs=[j for j in Store(inbox).jobs() if j.get('manual_collection')]
    return {'enabled':enabled(),'balance':ledger.get('balance'),'balance_checked_at':ledger.get('checked_at'),
            'reserved_credits':len(ledger['reservations']),'monthly_limit':MONTH_LIMIT,'reserve':RESERVE,
            'halted':ledger['halted'],'jobs':sorted(jobs,key=lambda j:j['started_at'],reverse=True)[:10]}

def queue(inbox,payload):
    if not enabled():raise AccessBlocked('Manual collection is not configured by the operator')
    selected=plan(payload); lock,path=_paths(inbox); key='social-manual-'+uuid.uuid4().hex
    with CollectionRunLock(lock,run_id=key):
        store=Store(inbox); ledger=_ledger(path)
        if ledger['halted']:raise AccessBlocked('Credit discrepancy requires operator review')
        previous=[j for j in store.jobs() if j.get('manual_collection')]
        if any(j['status'] in ('queued','running') for j in previous):raise AccessBlocked('A collection is already queued or running; interrupted jobs require operator review')
        for job in previous:
            if job.get('fingerprint')==selected['fingerprint'] and datetime.fromisoformat(job['started_at'])>datetime.now(timezone.utc)-timedelta(hours=24):
                return job,False
        month=now()[:7]; reserved=ledger['reservations']
        if len(reserved)+selected['max_credits']>TOTAL_LIMIT or sum(r['at'].startswith(month) for r in reserved)+selected['max_credits']>MONTH_LIMIT:
            raise AccessBlocked('Operator credit limit reached; no automatic top-up')
        job={'id':key,'source':'manual-collection','market':'Not inferred','language':'und','manual_collection':True,
             'status':'queued','started_at':now(),'fingerprint':selected['fingerprint'],'plan':selected,'results':[],
             'observed_volume':None,'last_success':None,'failure':None,'query_changed':True}
        store.save_job(job)
        return job,True

class PrepaidClient(MultiPlatformPilot):
    """Reuse the bounded transport, never the free-trial entitlement bypass."""
    def account(self):
        status,data=self._read('/v1/credits')
        balance=data.get('credits')
        if status!=200 or not isinstance(balance,int) or isinstance(balance,bool) or balance<0:
            raise AccessBlocked('Cannot verify prepaid balance')
        return balance

@lru_cache(maxsize=1)
def _language_detector():
    from langid.langid import LanguageIdentifier, model
    return LanguageIdentifier.from_modelstring(model,norm_probs=True)

def propose_labels(row, prior=None):
    if prior and prior['text']==row['text']:
        for key in ('language','language_basis','content_role','content_role_basis','translation'):
            if prior.get(key) and (key not in row or row.get(key) in (None,'und','unknown','Not classified')):row[key]=prior[key]
    # Offline model, no text export or translation charges. Short/ambiguous
    # captions remain unknown; probability is not an accuracy measurement.
    if row['language']=='und' and len(re.findall(r'\w+',row['text']))>=15:
        detector=_language_detector()
        language,score=detector.classify(row['text'])
        if language=='en' and score>=.99:
            row.update(language='en',language_basis='langid 1.1.6 English proposal, score >= .99; not independently graded')
    if row['content_role']=='unknown':
        text=row['text'].lower()
        words=re.findall(r'\b(?:harvesting|breeding|growers|robotics|cultivars|nursery|agtech|exporters)\b',text)
        if len(set(words))>=2:row.update(content_role='trade',content_role_basis='Proposed trade topic from explicit terms: '+', '.join(sorted(set(words))))
        elif re.search(r'\b(?:ingredients|recipe|cheesecake|smoothie)\b',text):row.update(content_role='recipe',content_role_basis='Proposed recipe topic from explicit food-use wording; author ownership unknown')
        elif re.search(r'\b(?:i bought|i picked|i tried|my berries|we picked)\b',text):row.update(content_role='consumer',content_role_basis='Proposed consumer account from first-person purchase/picking wording; author ownership unknown')
    return row

def run(inbox,key,entities,client=None):
    lock,path=_paths(inbox); store=Store(inbox); job=store.job(key)
    if not job or job['status']!='queued':return
    client=client or PrepaidClient(Path(inbox)/'social',enabled=True,key=os.environ.get('SOCIAVAULT_API_KEY'))
    try:
        with CollectionRunLock(lock,run_id=key):
            if not enabled():raise AccessBlocked('Operator disabled collection')
            ledger=_ledger(path); job['status']='running'; store.save_job(job)
            for query in job['plan']['queries']:
                before=client.account(); ledger.update(balance=before,checked_at=now());atomic_json(path,ledger)
                if before<=RESERVE or ledger['halted']:raise AccessBlocked('Prepaid credit reserve reached')
                if len(ledger['reservations'])>=TOTAL_LIMIT or sum(r['at'].startswith(now()[:7]) for r in ledger['reservations'])>=MONTH_LIMIT:raise AccessBlocked('Operator credit limit reached')
                receipt={'job':key,'at':now(),'source':query['source'],'reserved':1,'state':'reserved'}
                ledger['reservations'].append(receipt);atomic_json(path,ledger)
                result={'source':query['source'],'scope':query['scope'],'berry':query['berry'],'state':'failed','returned':None,'stored':0,'readable_relevant':0}
                try:
                    code,payload=client._read('/v1/scrape/'+TASKS[query['task']][0],query['params'])
                    after=client.account(); cost=payload.get('credits_used',payload.get('data',{}).get('credits_used'))
                    ledger.update(balance=after,checked_at=now());receipt.update(balance_before=before,balance_after=after,state='completed')
                    if before-after>1 or isinstance(cost,(int,float)) and cost>1:
                        ledger['halted']=True;raise AccessBlocked('Unexpected credit cost; remaining requests stopped')
                    if code!=200:raise AccessBlocked('Provider HTTP '+str(code)+'; not zero activity')
                    mapped=normalize(payload,query['task']); result['returned']=mapped['returned_items']
                    prior={r['id']:r for r in store.records(mode='live')}
                    rows=[]
                    for row in mapped['rows']:
                        row.update(discovery_method='sociavault-manual-prepaid',query_version=VERSION,
                                   permission_basis='Operator-funded public-source reference; no rehosting or redistribution rights inferred')
                        rows.append(propose_labels(row,prior.get(identity(row))))
                    ids=store.ingest(rows,entities,mode='live'); actual=[r for r in store.records(mode='live') if r['id'] in ids]
                    result.update(state='partial' if mapped['mapping_errors'] else 'success',stored=len(set(ids)),
                                  new=len(set(ids)-set(prior)),readable_relevant=sum(readable_in_english(r) and bool(r['analysis']['berry_ids']) for r in actual),
                                  pending_english=sum(not readable_in_english(r) for r in actual),mapping_errors=len(mapped['mapping_errors']))
                    job['last_success']=now()
                except (AccessBlocked,ValueError) as exc:
                    result['reason']=str(exc) if isinstance(exc,AccessBlocked) else 'Mapping validation failed'
                finally:
                    store.save_job({'id':key+'-'+str(len(job['results'])),'source':query['source'],
                                    'market':'Not inferred','language':'und','status':'partial' if result['state'] in ('success','partial') else 'failed',
                                    'started_at':receipt['at'],'last_success':now() if result['state'] in ('success','partial') else None,
                                    'observed_volume':result['stored'] if result['state'] in ('success','partial') else None,
                                    'query_changed':True,'failure':result.get('reason') or 'One-page manual search; dates and coverage are provider-limited'})
                    atomic_json(path,ledger);job['results'].append(result);store.save_job(job)
                if ledger['halted']:break
            job.update(status='partial' if any(r['state']!='success' for r in job['results']) else 'live',
                       observed_volume=sum(r['stored'] for r in job['results']),completed_at=now(),failure='Bounded manual sample; not representative coverage')
    except (AccessBlocked,CollectionLockedError,ValueError):
        job.update(status='blocked',failure='Collection stopped; check credits, runtime lock or ledger. No automatic retry.',completed_at=now())
    except Exception:
        job.update(status='failed',failure='Collection interrupted; operator review required. No automatic retry.',completed_at=now())
    finally:store.save_job(job)
