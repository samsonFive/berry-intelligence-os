from pathlib import Path
import hashlib,json,os,statistics,subprocess,sys,tempfile,time

repo = Path(__file__).resolve().parents[1]
assert __name__ == '__main__' and '--public-seed-only' in sys.argv
assert os.name == 'posix' and sys.platform == 'linux'
assert os.environ.get('GITHUB_ACTIONS') == 'true'
assert os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
assert os.environ.get('GITHUB_REF_NAME') == 'perf/portfolio-batch-ci-probe-20261104'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip() == os.environ.get('GITHUB_SHA')
checked = 'b76792c0'
assert not subprocess.check_output(['git','diff','--name-only',checked,'--','app','schemas','data'],cwd=repo)
import resource, shutil
assert shutil.disk_usage(repo).free >= 10*1024**3
available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))) * 1024
assert available >= 2*1024**3
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
assert len(os.sched_getaffinity(0)) == 1
resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
tracked = {path for path in subprocess.check_output(['git','ls-files','data','schemas'],cwd=repo,text=True).splitlines() if path.endswith('.json')}
assert tracked == {str(path.relative_to(repo)) for folder in ('data','schemas') for path in (repo/folder).rglob('*.json')}
out = repo/'inbox/public-batch-measurement'
out.mkdir(parents=True,exist_ok=True)
diagnostic_start = time.perf_counter()
base = '3ffe5bade1fb58616bcc9863aa6afe0109b7bb60'
baseline = subprocess.check_output(['git','show',base+':app/services/variety_portfolio_coverage.py'],cwd=repo)
inventory = {str(path.relative_to(repo)):hashlib.sha256(path.read_bytes()).hexdigest()
             for folder in ('data','schemas') for path in (repo/folder).rglob('*.json')}
assert len(inventory) == 2942
rows = []
with tempfile.TemporaryDirectory(prefix='berry-batch-probe-',dir=out) as temporary:
    home = Path(temporary)
    (home/'inbox').mkdir()
    (home/'scope.json').write_text(json.dumps({'repo':str(repo),'public_seed_only':True}))
    (home/'baseline.py').write_bytes(baseline)
    env = {key:value for key,value in os.environ.items() if not key.startswith('BIOS_') and not key.endswith(('_API_KEY','_API_TOKEN'))}
    env.update(BIOS_BATCH_PROBE_HOME=str(home),PYTHONHASHSEED='0',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    for order in ('company','candidates'):
        for replicate in ('0','1'):
            variants = ('baseline','candidate') if replicate == '0' else ('candidate','baseline')
            for variant in variants:
                result = subprocess.run([sys.executable,str(repo/'scripts/portfolio_batch_public_worker.py'),variant,order,replicate],cwd=repo,env=env,capture_output=True,text=True,timeout=90)
                assert time.perf_counter()-diagnostic_start < 360
                assert result.returncode == 0,result.stderr[-3000:]
                row = json.loads(result.stdout.splitlines()[-1])
                rows.append(row)
                (out/'measurement-progress.json').write_text(json.dumps(rows,indent=2)+'\n')
                print(json.dumps({key:row[key] for key in ('variant','order','replicate','seconds','workflow_seconds')}),flush=True)
assert inventory == {str(path.relative_to(repo)):hashlib.sha256(path.read_bytes()).hexdigest()
                     for folder in ('data','schemas') for path in (repo/folder).rglob('*.json')}
summaries = []
for order in ('company','candidates'):
    selected = [row for row in rows if row['order'] == order]
    assert all(row['outputs'] == selected[0]['outputs'] for row in selected),'Complete outputs differ for '+order
    summaries.append({'order':order,**{variant:{key:statistics.median(row[key] if key == 'workflow_seconds' else row['seconds'][key] for row in selected if row['variant'] == variant)
        for key in ('workflow_seconds',order,'fresh_news')} for variant in ('baseline','candidate')}})
proof = {'baseline':base,'source_sha256':hashlib.sha256((repo/'app/services/variety_portfolio_coverage.py').read_bytes()).hexdigest(),
    'fresh_processes':8,'complete_responses':24,'all_complete_typed_models_context_HTML_match':True,
    'public_json_files_preserved':len(inventory),'network_attempts':0,'reader_writes':0,
    'summaries':summaries,'runs':rows,'scope':'Linux public seed only, empty disposable inbox and warm filesystem, one CPU and 1GiB address-space cap. Handler timings exclude imports/comparison work. Not VPS latency or private-production preservation acceptance.'}
(out/'workflow-result.json').write_text(json.dumps(proof,indent=2)+'\n')
proof['checked_runtime_head'] = subprocess.check_output(['git','rev-parse',checked],cwd=repo,text=True).strip()
proof['diagnostic_head'] = os.environ['GITHUB_SHA']
proof['identity_source_sha256'] = hashlib.sha256((repo/'app/services/identity_read_model.py').read_bytes()).hexdigest()
proof['one_cpu'] = True
proof['address_space_limit_bytes'] = 1024**3
proof['production_changed'] = False
proof['provider_requests'] = 0
print('PORTFOLIO_BATCH_DIAGNOSTIC='+json.dumps(proof,separators=(',',':')))
