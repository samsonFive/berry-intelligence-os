PREPARATION_BOOTSTRAP = "from pathlib import Path\nfrom datetime import datetime,timezone\nimport os,runpy,sys\nroot=Path(os.environ['BIOS_PUBLIC_PROBE_REPO'])\nsys.path.insert(0,str(root))\nfrom app.services.variety_universe import registry_import\nclass ControlledCandidateTime(datetime):\n @classmethod\n def now(cls,tz=None):\n  value=datetime(2026,11,3,12,0,0,tzinfo=timezone.utc)\n  return value.astimezone(tz)if tz else value.replace(tzinfo=None)\nregistry_import.datetime=ControlledCandidateTime\nscript=str(root/'scripts/prepare_private_read_models.py')\nsys.argv=[script,'--prepare']\nrunpy.run_path(script,run_name='__main__')\n"
'Controlled cold/next-click experiment on one disposable read-only copy.'
from pathlib import Path
from datetime import date, datetime, timezone
import dataclasses, hashlib, json, os, socket, subprocess, sys, tempfile, time, types
ROOT = Path(__file__).resolve().parents[1]
PROBE_HOME = Path(os.environ['BIOS_PUBLIC_PROBE_HOME']).resolve()
assert PROBE_HOME.parent == Path(tempfile.gettempdir()).resolve()
assert PROBE_HOME.name.startswith('berry-public-model-probe-')
assert json.loads((PROBE_HOME / 'public-seed-only.json').read_text()) == {
    'repo': str(ROOT), 'checked_source': '0cec711590f97653d9e5a5f368fb822b232537fe',
    'purpose': 'public-seed-measurement-only'}
for setting, leaf in [('BIOS_PUBLIC_PROBE_INBOX', 'inbox'),
                      ('BIOS_PUBLIC_PROBE_ARTIFACT_ROOT', 'artifacts'),
                      ('BIOS_PUBLIC_PROBE_BASELINE', 'baseline')]:
    assert Path(os.environ[setting]).resolve() == PROBE_HOME / leaf
assert not any(path.is_file() for path in (PROBE_HOME / 'inbox').rglob('*'))
for key in list(os.environ):
    if key.endswith(('_API_KEY', '_API_TOKEN')):
        os.environ[key] = ''
os.environ.update(BIOS_DATA_DIR=str(ROOT / 'data'), BIOS_INBOX_DIR=os.environ['BIOS_PUBLIC_PROBE_INBOX'], BIOS_REMOTE_INTERACTIVE='false', BIOS_MODE='authoring', ENABLE_SOURCE_POLLING='false', ENABLE_PERPLEXITY_PULSE='false', BIOS_SOCIAL_MANUAL_COLLECTION='false', PYTHONHASHSEED='0')

network_attempts = 0

def denied(*args, **kwargs):
    global network_attempts
    network_attempts += 1
    raise AssertionError('External connections forbidden')
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = denied
sys.path.insert(0, str(ROOT))
variant, order, phase, replicate = sys.argv[1:]
assert variant in {'baseline', 'candidate'} and order in {'company', 'candidates'}
os.environ['BIOS_PRIVATE_READ_MODELS'] = 'true' if variant == 'candidate' else 'false'
os.environ['BIOS_SESSION_SECRET'] = 'offline-only-private-model-fixture-secret-32'
artifact_root = Path(os.environ['BIOS_PUBLIC_PROBE_ARTIFACT_ROOT']) / (order + '-' + replicate)
os.environ['BIOS_PRIVATE_MODEL_ROOT'] = str(artifact_root)
if variant == 'baseline':
    import importlib.abc, importlib.util

    class BaselineLoader(importlib.abc.Loader):

        def __init__(self, name):
            self.name = name

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            relative = self.name.replace('.', '/') + '.py'
            actual = ROOT / relative
            module.__file__ = str(actual)
            exec(compile((Path(os.environ['BIOS_PUBLIC_PROBE_BASELINE']) / relative).read_text(), str(actual), 'exec'), module.__dict__)

    class BaselineFinder(importlib.abc.MetaPathFinder):

        def find_spec(self, fullname, path=None, target=None):
            if fullname in {'app.main', 'app.services.presentation_memo'}:
                return importlib.util.spec_from_loader(fullname, BaselineLoader(fullname), origin=str(ROOT / (fullname.replace('.', '/') + '.py')))
    sys.meta_path.insert(0, BaselineFinder())
from app import main
from app.services.variety_universe import registry_import, article_sources
from app.services.request_corpus import RequestCorpus, bind_request_corpus, reset_request_corpus
from starlette.requests import Request

class ControlledCandidateTime(datetime):

    @classmethod
    def now(cls, tz=None):
        value = datetime(2026, 11, 3, 12, 10 if globals().get('fresh_update', False) else 0, 0, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)
registry_import.datetime = ControlledCandidateTime
fresh_update = False
original_drafts = main.list_drafts
fictional_draft = {'id': 'ev-offline-fresh-news-fixture', 'status': 'in_review', 'evidence_role': 'publication_artifact', 'source_type': 'company_website', 'source_id': 'fixture-offline-only', 'source_name': 'Fictional offline performance publisher', 'source_url': 'https://example.test/offline-news-update', 'title': 'Fictional parsing fixture', 'summary': 'An invented article used only in an offline performance comparison.', 'published_date': '2026-11-03', 'captured_date': '2026-11-03', 'berry_ids': ['berry-blueberry'], 'entity_ids': ['company-hortifrut'], 'article': {'full_text': 'Blueberry varieties include Nebula Benchmark. This is fictional test data, never a market claim.'}}

def drafts_with_update():
    return [*original_drafts(), fictional_draft] if fresh_update else original_drafts()
main.list_drafts = drafts_with_update
universes = []
articles = []
step = ''
original_universe = main.variety_candidate_universe

def observed_universe():
    value = original_universe()
    universes.append((step, value))
    return value
main.variety_candidate_universe = observed_universe
original_articles = article_sources.available_article_sources

def observed_articles(*args, **kwargs):
    value = original_articles(*args, **kwargs)
    articles.append((step, value))
    return value
article_sources.available_article_sources = observed_articles

def typed(x):
    if x is None or type(x) in {bool, int, float, str}:
        return [type(x).__name__, x]
    if isinstance(x, (date, datetime)):
        return [type(x).__name__, x.isoformat()]
    if isinstance(x, dict):
        return ['dict', [[typed(k), typed(v)] for k, v in x.items()]]
    if isinstance(x, (list, tuple)):
        return [type(x).__name__, [typed(v) for v in x]]
    if isinstance(x, (set, frozenset)):
        return [type(x).__name__, sorted([typed(v) for v in x], key=repr)]
    if dataclasses.is_dataclass(x):
        return [type(x).__name__, typed(dataclasses.asdict(x))]
    if type(x) is types.FunctionType:
        from app.services.derived_model_scope import executing_code_digest
        return ['function', x.__module__, x.__qualname__, executing_code_digest(x.__code__).hex(), typed(x.__defaults__), typed(x.__kwdefaults__), typed(tuple((cell.cell_contents for cell in x.__closure__ or ())))]
    raise TypeError(type(x))

def signature(value):
    return hashlib.sha256(json.dumps(typed(value), ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
preparation_seconds = 0.0
preparation_receipt = None
if variant == 'candidate' and phase == 'initial':
    start = time.perf_counter()
    artifact_root.mkdir(parents=True, mode=448)
    prepared = subprocess.run([sys.executable, '-c', PREPARATION_BOOTSTRAP], capture_output=True, text=True, timeout=90)
    preparation_seconds = time.perf_counter() - start
    assert prepared.returncode == 0, 'Actual preparation command failed: ' + prepared.stderr[-1800:]
    preparation_receipt = json.loads(prepared.stdout.splitlines()[-1])
    assert preparation_receipt['prepared'] and preparation_receipt['provider_requests'] == 0

def artifact_hashes():
    return {str(p.relative_to(artifact_root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifact_root.rglob('*') if p.is_file()} if artifact_root.exists() else {}
before_artifacts = artifact_hashes()
model_scopes = []
if variant == 'candidate':
    from app.services import derived_model_scope
    original_configure = derived_model_scope.configured_scope

    def observed_configure(**kwargs):
        scope = original_configure(**kwargs)
        assert scope is not None and (not scope.writer)
        model_scopes.append((step, scope))
        return scope
    derived_model_scope.configured_scope = observed_configure
timings = {}
responses = {}
models = {}
for step in [order, 'candidates' if order == 'company' else 'company', 'fresh_news']:
    route = order if step == 'fresh_news' else step
    if step == 'fresh_news':
        fresh_update = True
    path = '/entities/company/company-hortifrut' if route == 'company' else '/varieties/candidates'
    query = b'tab=varieties' if route == 'company' else b'company=company-hortifrut'
    request = Request({'type': 'http', 'app': main.app, 'method': 'GET', 'scheme': 'http', 'path': path, 'query_string': query, 'headers': [], 'server': ('fixture.local', 80), 'client': ('127.0.0.1', 1), 'root_path': ''})
    token = bind_request_corpus(RequestCorpus(main.DATA_DIR, main.SCHEMAS_DIR, main.INBOX_DIR))
    start = time.perf_counter()
    try:
        response = main.entity_detail(request, 'company', 'company-hortifrut') if route == 'company' else main.variety_candidates_page(request)
    finally:
        reset_request_corpus(token)
    timings[step] = time.perf_counter() - start
    assert response.status_code == 200
    responses[step] = response.body
    models[step] = {key: value for key, value in response.context.items() if key != 'request'}
assert any((row.get('candidate_name') == 'Nebula Benchmark' for label, value in universes if label == 'fresh_news' for row in value[1])), 'Fictional new source did not exercise discovery'
assert any((row.get('id') == 'ev-offline-fresh-news-fixture' and row.get('status') == 'unreviewed' for label, value in articles if label == 'fresh_news' for row in value[0])), 'Fresh source is missing or its unreviewed status changed'
assert artifact_hashes() == before_artifacts, 'Ordinary reader changed artifact files'
assert network_attempts == 0, 'A worker attempted an external connection'
outputs = {step: {'HTML': hashlib.sha256(body).hexdigest(), 'typed_context': signature(models[step]), 'complete_universes': [signature(value) for label, value in universes if label == step], 'complete_article_bundles': [signature(value) for label, value in articles if label == step]} for step, body in responses.items()}
print(json.dumps({'variant': variant, 'order': order, 'seconds': timings, 'workflow_seconds': sum(timings.values()), 'preparation_seconds': preparation_seconds, 'charged_total_seconds': preparation_seconds + sum(timings.values()), 'preparation_receipt': preparation_receipt, 'actual_scope_counts': [(label, scope.counts) for label, scope in model_scopes], 'outputs': outputs, 'phase': phase, 'replicate': replicate, 'model_counts': globals().get('model_counts', {}), 'repository_copy_counts': {}, 'identity_lookup_counts': {}, 'reader_key_paths': globals().get('key_counts', {}), 'parser_counts': globals().get('parser_counts', {}), 'source_gate_counts': globals().get('source_gate_counts', {}), 'fictional_fresh_news_exercised': True, 'source_records': [len(value[0]) for _, value in articles]}))
