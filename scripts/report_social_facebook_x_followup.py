from pathlib import Path
import json,sys,os,hashlib
from urllib.parse import urlsplit
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));p=root/'inbox/social-bakeoff/sociavault-multiplatform-2026-10-07';os.environ['BIOS_INBOX_DIR']=str(p/'evaluation-inbox');os.environ['ENABLE_SOURCE_POLLING']='false';os.environ['BIOS_MODE']='authoring'
from app.services.social_intelligence.sociavault_normalize import normalize,values
from app.services.social_intelligence.store import Store
from app.main import all_entities
ledger=json.loads((p/'ledger.json').read_text(encoding='utf-8'));store=Store(p/'evaluation-inbox');before=len(store.records(mode='live'));results=[]
for a in ledger['attempts']:
 if a['case_id'] not in {'fb-fallcreek-followup','fb-driscolls-followup','x-fallcreek-followup','x-driscolls-followup'}:continue
 cache=p/(a['id']+'.json');n={'rows':[],'returned_items':None,'mapping_errors':[]}
 if cache.exists():
  data=json.loads(cache.read_text(encoding='utf-8'));n=normalize(data,a['task'],supplied_url=a['params'].get('url'))
  assessments=json.loads((p/'inspected-english-language.json').read_text(encoding='utf-8')) if (p/'inspected-english-language.json').exists() else []
  for row in n['rows']:
   row['collected_at']=a['at']
   expected={'fb-fallcreek-followup':'fallcreeknursery','fb-driscolls-followup':'driscollsberries','x-fallcreek-followup':'fallcreekblues','x-driscolls-followup':'driscollsberry'}[a['case_id']]
   source=urlsplit(row['canonical_url']);handle=source.path.strip('/').split('/')[0].casefold()
   allowed={'facebook.com','www.facebook.com'} if row['source']=='facebook' else {'twitter.com','www.twitter.com','x.com','www.x.com'}
   if source.hostname in allowed and handle==expected:row['content_role']='company_owned'
   from app.services.social_intelligence.store import identity
   assessment=next((v for v in assessments if v['id']==identity(row) and v['text_sha256']==hashlib.sha256(row['text'].encode()).hexdigest()),None)
   if assessment:row.update(language=assessment['language'],language_basis=assessment['basis'])
  ids=store.ingest(n['rows'],all_entities(),mode='live');print(a['case_id'],'reader_ids',ids)
  store.save_job({'id':'trial-'+a['case_id'],'source':a['task'].split('-')[0],'market':'Known public company source','language':'und','status':'partial','last_success':a['at'],'observed_volume':len(n['rows']),'failure':'Bounded company-path follow-up; no ongoing/global monitoring; rights/accuracy pending','query_changed':True})
 results.append({'case':a['case_id'],'task':a['task'],'http':a.get('http'),'state':a['state'],'credit_delta':a.get('observed_credit_delta'),'returned_items':n['returned_items'],'mapped':len(n['rows']),'mapping_errors':n['mapping_errors'],'images':sum(len(r['media']) for r in n['rows']),'dates_present':sum(bool(r['published_at']) for r in n['rows']),'language_present_count':sum(r['language']!='und' for r in n['rows'])})
after=len(store.records(mode='live'));saved=root/'artifacts/social-blueberry/facebook-x-followup-summary.json';baseline=json.loads(saved.read_text(encoding='utf-8'))['records_before'] if saved.exists() else before
summary={'date':'2026-10-07','cash_spend_usd':0,'remaining_free_credits':ledger['attempts'][-1]['balance_after'],'total_consumed_free_credits':ledger['initial_balance']-ledger['attempts'][-1]['balance_after'],'followup_credits':4,'cumulative_attempts':len(ledger['attempts']),'results':results,'records_before':baseline,'records_after':after,'unique_new':after-baseline,'replay_added':after-before,'independent_accuracy_ungraded':True,'no_fresh_discovery_score':True,'no_comments_or_private_group_access_tested':True}
saved.write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
