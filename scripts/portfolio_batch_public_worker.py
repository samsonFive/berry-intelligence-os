"""Offline full-response comparison; no production data or provider calls."""
from pathlib import Path
from datetime import date, datetime, timezone
import dataclasses, hashlib, importlib.abc, importlib.util, json, os, socket, sys, time, types

ROOT = Path(__file__).resolve().parents[1]
home = Path(os.environ['BIOS_BATCH_PROBE_HOME']).resolve()
assert home.name.startswith('berry-batch-probe-')
assert json.loads((home/'scope.json').read_text()) == {'repo':str(ROOT),'public_seed_only':True}
for key in list(os.environ):
    if key.endswith(('_API_KEY','_API_TOKEN')):
        os.environ[key] = ''
os.environ.update(BIOS_DATA_DIR=str(ROOT/'data'),BIOS_INBOX_DIR=str(home/'inbox'),
    BIOS_REMOTE_INTERACTIVE='false',BIOS_MODE='authoring',ENABLE_SOURCE_POLLING='false',
    ENABLE_PERPLEXITY_PULSE='false',BIOS_SOCIAL_MANUAL_COLLECTION='false')
attempts = 0
def denied(*args,**kwargs):
    global attempts
    attempts += 1
    raise AssertionError('External connections forbidden')
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = denied
sys.path.insert(0,str(ROOT))
variant, order, replicate = sys.argv[1:]
assert variant in {'baseline','candidate'} and order in {'company','candidates'}
if variant == 'baseline':
    class Loader(importlib.abc.Loader):
        def create_module(self,spec): return None
        def exec_module(self,module):
            actual = ROOT/'app/services/variety_portfolio_coverage.py'
            module.__file__ = str(actual)
            exec(compile((home/'baseline.py').read_text(encoding='utf-8'),str(actual),'exec'),module.__dict__)
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname == 'app.services.variety_portfolio_coverage':
                return importlib.util.spec_from_loader(fullname,Loader())
    sys.meta_path.insert(0,Finder())
from app import main
from app.services.variety_universe import registry_import, article_sources
from app.services.request_corpus import RequestCorpus,bind_request_corpus,reset_request_corpus
from starlette.requests import Request
revision = 0
class Clock(datetime):
    @classmethod
    def now(cls,tz=None):
        value = datetime(2026,11,3,12,revision*10,tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)
registry_import.datetime = Clock
original_drafts = main.list_drafts
fictional = {'id':'ev-offline-batch-probe','status':'in_review','evidence_role':'publication_artifact',
    'source_type':'company_website','source_id':'fixture-offline-only','source_name':'Fictional offline publisher',
    'source_url':'https://example.test/offline-batch','title':'Offline performance fixture',
    'summary':'An invented article used only for offline measurement.','published_date':'2026-11-03',
    'berry_ids':['berry-blueberry'],'entity_ids':['company-hortifrut'],
    'article':{'full_text':'Blueberry varieties include Nebula Benchmark. Fictional offline data, never a market claim.'}}
main.list_drafts = lambda: [*original_drafts(),fictional] if revision else original_drafts()
universes, articles = [],[]
original_universe = main.variety_candidate_universe
def observed_universe():
    value = original_universe()
    universes.append((step,value))
    return value
main.variety_candidate_universe = observed_universe
original_articles = article_sources.available_article_sources
def observed_articles(*args,**kwargs):
    value = original_articles(*args,**kwargs)
    articles.append((step,value))
    return value
article_sources.available_article_sources = observed_articles

def typed(value):
    if value is None or type(value) in {str,bool,int,float}:
        return [type(value).__name__,value]
    if isinstance(value,(date,datetime)):
        return [type(value).__name__,value.isoformat()]
    if isinstance(value,dict):
        return ['dict',[[typed(k),typed(v)] for k,v in value.items()]]
    if isinstance(value,(list,tuple)):
        return [type(value).__name__,[typed(v) for v in value]]
    if isinstance(value,(set,frozenset)):
        return [type(value).__name__,sorted([typed(v) for v in value],key=repr)]
    if dataclasses.is_dataclass(value):
        return [type(value).__name__,typed(dataclasses.asdict(value))]
    if type(value) is types.CodeType:
        return ['code',value.co_code.hex(),typed(value.co_consts),typed(value.co_names),typed(value.co_varnames)]
    if type(value) is types.FunctionType:
        return ['function',value.__module__,value.__qualname__,typed(value.__code__),
            typed(value.__defaults__),typed(value.__kwdefaults__),typed(tuple(cell.cell_contents for cell in value.__closure__ or ()))]
    raise TypeError(type(value))
def signature(value):
    return hashlib.sha256(json.dumps(typed(value),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
timings, outputs = {},{}
for step in [order,'candidates' if order == 'company' else 'company','fresh_news']:
    if step == 'fresh_news': revision = 1
    route = order if step == 'fresh_news' else step
    path = '/entities/company/company-hortifrut' if route == 'company' else '/varieties/candidates'
    query = b'tab=varieties' if route == 'company' else b'company=company-hortifrut'
    request = Request({'type':'http','app':main.app,'method':'GET','scheme':'http','path':path,
        'query_string':query,'headers':[],'server':('fixture.local',80),'client':('127.0.0.1',1),'root_path':''})
    token = bind_request_corpus(RequestCorpus(main.DATA_DIR,main.SCHEMAS_DIR,main.INBOX_DIR))
    start = time.perf_counter()
    try:
        response = main.entity_detail(request,'company','company-hortifrut') if route == 'company' else main.variety_candidates_page(request)
    finally: reset_request_corpus(token)
    timings[step] = time.perf_counter()-start
    assert response.status_code == 200
    outputs[step] = {'HTML':hashlib.sha256(response.body).hexdigest(),
        'typed_context':signature({key:value for key,value in response.context.items() if key != 'request'}),
        'complete_universes':[signature(value) for label,value in universes if label == step],
        'complete_article_bundles':[signature(value) for label,value in articles if label == step]}
assert any(row.get('candidate_name') == 'Nebula Benchmark' for label,value in universes if label == 'fresh_news' for row in value[1])
assert not any(row.get('candidate_name') == 'Nebula Benchmark' for label,value in universes if label != 'fresh_news' for row in value[1])
assert attempts == 0 and not any(path.is_file() for path in (home/'inbox').rglob('*'))
print(json.dumps({'variant':variant,'order':order,'replicate':replicate,'seconds':timings,
    'workflow_seconds':sum(timings.values()),'outputs':outputs,'network_attempts':0,'reader_writes':0}))
