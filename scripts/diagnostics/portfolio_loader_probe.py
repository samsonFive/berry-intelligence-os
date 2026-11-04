"""Diagnostic only: public seed, no provider or runtime changes. Never merge."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,statistics,subprocess,sys,time
repo=Path(__file__).resolve().parents[2]
child=Path(__file__).with_name('portfolio_loader_probe_child.py')
out=Path(os.environ['BIOS_DIAGNOSTIC_OUT']);out.mkdir(parents=True,exist_ok=True)
def inventory():
    return {str(p.relative_to(repo/'data')):hashlib.sha256(p.read_bytes()).hexdigest()for p in(repo/'data').rglob('*')if p.is_file()}
before=inventory();assert len(before)==2998
rows=[];start=time.perf_counter()
for order in ['company','candidates']:
    for replicate in ['0','1']:
        variants=['baseline','candidate']if replicate=='0'else['candidate','baseline']
        for variant in variants:
            assert time.perf_counter()-start<480
            process=subprocess.run([sys.executable,'-X','utf8',str(child),variant,order,replicate],cwd=repo,capture_output=True,text=True,encoding='utf-8',timeout=75)
            (out/('loader-prototype-'+variant+'-'+order+'-'+replicate+'.log')).write_text(process.stdout+'\n'+process.stderr,encoding='utf-8')
            assert process.returncode==0,process.stderr[-1400:]
            row=json.loads(process.stdout.splitlines()[-1]);rows.append(row)
            (out/'loader-prototype-partial.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'finished':len(rows),'variant':variant,'order':order,'replicate':replicate,'workflow_seconds':row['workflow_seconds']}),flush=True)
assert inventory()==before
summary=[]
for order in ['company','candidates']:
    selected=[r for r in rows if r['order']==order]
    assert len(selected)==4 and all(row['outputs']==selected[0]['outputs']for row in selected),'Complete outputs differ: '+order
    summary.append({'order':order,**{variant:{key:statistics.median(r[key]if key=='workflow_seconds'else r['seconds'][key]for r in selected if r['variant']==variant)
         for key in ['workflow_seconds',order,'fresh_news']}for variant in ['baseline','candidate']}})
result={'checked_at':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
 'kind':'unaccepted_exact_inventory_portfolio_loader_cache','fresh_processes':8,'complete_responses':24,
 'typed_article_universe_context_and_html_match':True,'public_files_raw_bytes_unchanged':2998,
 'network_attempts':0,'provider_calls':0,'production_changed':False,'summaries':summary,'runs':rows,
 'limitation':'Linux single-CPU, 1GiB-address-space public-seed empty-inbox prototype. Two replicates per order/variant. Not production implementation, private acceptance or VPS timing.'}
(out/'loader-prototype-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'complete_outputs_match':True,'summaries':summary,'runtime_change_retained':False}))
