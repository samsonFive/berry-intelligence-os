from pathlib import Path
import json,sys,os
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));p=root/'inbox/social-bakeoff/sociavault-multiplatform-2026-10-07';os.environ['BIOS_INBOX_DIR']=str(p/'evaluation-inbox');os.environ['ENABLE_SOURCE_POLLING']='false';os.environ['BIOS_MODE']='authoring'
from app.services.social_intelligence.sociavault_normalize import normalize
from app.services.social_intelligence.store import Store
from app.main import all_entities
ledger=json.loads((p/'ledger.json').read_text(encoding='utf-8'));store=Store(p/'evaluation-inbox');before=len(store.records(mode='live'));saved=root/'artifacts/social-blueberry/linkedin-followup-summary.json';baseline=json.loads(saved.read_text(encoding='utf-8'))['records_before'] if saved.exists() else before;results=[]
for a in ledger['attempts']:
 if not a['case_id'].startswith('li-'):continue
 path=p/(a['id']+'.json');rows=[]
 if path.exists():
  data=json.loads(path.read_text(encoding='utf-8'));n=normalize(data,a['task'],supplied_url=a['params'].get('url'));rows=n['rows']
  for row in rows:row['collected_at']=a['at']
  store.ingest(rows,all_entities(),mode='live');store.save_job({'id':'trial-'+a['case_id'],'source':'linkedin','market':'Known company/post' if a['task']!='linkedin-search' else 'Query target unknown','language':'und','status':'partial','last_success':a['at'],'observed_volume':len(rows),'failure':'One-off public LinkedIn trial; no scheduled coverage; rights/language remain unverified','query_changed':True})
  results.append({'case':a['case_id'],'task':a['task'],'http':a.get('http'),'state':a['state'],'credit_delta':a.get('observed_credit_delta'),'returned_items':n['returned_items'],'mapped':len(rows),'mapping_errors':len(n['mapping_errors']),'images':sum(len(r['media']) for r in rows),'dates_present':sum(bool(r['published_at']) for r in rows),'comments_returned':len(data['data'].get('comments',{})) if a['task']=='linkedin-post' else None,'language_verified':False})
  if a['case_id']=='li-variety-followup' and rows:print('variety_reader_id',store.ingest(rows,all_entities(),mode='live')[0])
after=len(store.records(mode='live'));summary={'date':'2026-10-07','cash_spend_usd':0,'remaining_free_credits':ledger['attempts'][-1]['balance_after'],'total_consumed_free_credits':ledger['initial_balance']-ledger['attempts'][-1]['balance_after'],'followup_credits':4,'results':results,'records_before':baseline,'records_after':after,'unique_new':after-baseline,'replay_added':after-before,'previous_failures_not_reinterpreted':True,'independent_accuracy_ungraded':True,'known_posts_older_than_original_interval':True}
(root/'artifacts/social-blueberry/linkedin-followup-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
