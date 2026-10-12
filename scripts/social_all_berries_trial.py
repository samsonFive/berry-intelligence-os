"""Six predeclared free-credit probes; offline replay is the default."""
import argparse
from pathlib import Path
import json
import sys
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.services.social_intelligence.sociavault_pilot import MultiPlatformPilot,private_key
from app.services.social_intelligence.sociavault_normalize import normalize
from app.services.social_intelligence.store import Store
from app.services.social_intelligence.adapters import AccessBlocked
from app.services.social_intelligence.presentation import readable_in_english

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--key-file');args=parser.parse_args()
    manifest=json.loads((ROOT/'benchmarks/social-bakeoff/all-berries-rollout-manifest.json').read_text(encoding='utf-8'))
    private=ROOT/'inbox/social-bakeoff/sociavault-multiplatform-2026-10-07'
    pilot=MultiPlatformPilot(private,enabled=args.live,key=private_key(args.key_file) if args.live else None,ceiling=manifest['cumulative_attempt_ceiling'])
    store=Store(private/'evaluation-inbox');entities=[json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'data/entities').rglob('*.json')]
    before=len(store.records(mode='live'));results=[]
    existing_report=ROOT/'artifacts/social-all-berries/trial-summary.json'
    baseline=json.loads(existing_report.read_text(encoding='utf-8'))['records_before'] if existing_report.exists() else before
    for query in manifest['queries']:
        attempted=next((a for a in pilot.ledger['attempts'] if a['case_id']==query['id']),None)
        try:
            if args.live:data,cached=pilot.fetch(query['task'],query['params'],case_id=query['id'])
            elif attempted and (private/(attempted['id']+'.json')).exists():data=json.loads((private/(attempted['id']+'.json')).read_text(encoding='utf-8'));cached=True
            else:results.append({'case':query['id'],'state':'not-tested','berry':query['berry']});continue
            normalized=normalize(data,query['task']);attempted=next(a for a in pilot.ledger['attempts'] if a['case_id']==query['id'])
            for row in normalized['rows']:
                row['collected_at']=attempted['at']
                # Match a native author supplied by the source, never infer from the query.
                if row['source']=='x' and (row.get('author_handle') or '').casefold()=='driscollsberry':
                    row.update(content_role='company_owned',content_role_basis='Native author @driscollsberry matches the previously verified official Driscolls account; proposed classification, not independent accuracy review')
            from app.services.social_intelligence.store import identity
            import hashlib
            assessments=json.loads((private/'inspected-english-language.json').read_text(encoding='utf-8')) if (private/'inspected-english-language.json').exists() else []
            for row in normalized['rows']:
                assessment=next((v for v in assessments if v['id']==identity(row) and v['text_sha256']==hashlib.sha256(row['text'].encode()).hexdigest()),None)
                if assessment:
                    row.update(language=assessment['language'],language_basis=assessment['basis'])
                    if assessment.get('proposed_role'):row.update(content_role=assessment['proposed_role'],content_role_basis=assessment['role_basis'])
            ids=store.ingest(normalized['rows'],entities,mode='live')
            store.save_job({'id':query['id'],'source':query['task'].split('-')[0],'market':'Not inferred from query','language':'und','status':'partial','last_success':attempted['at'],'observed_volume':len(ids),'query_changed':True,'failure':'One-page trial; relevance, coverage and independent accuracy unqualified'})
            results.append({'case':query['id'],'berry':query['berry'],'state':'offline-replay' if cached else 'retrieved','http':attempted.get('http'),'credit_delta':attempted.get('observed_credit_delta'),'returned':normalized['returned_items'],'mapped':len(ids),'mapping_errors':normalized['mapping_errors'],'readable':sum(readable_in_english(r) for r in normalized['rows']),'media_references':sum(len(r['media']) for r in normalized['rows'])})
        except AccessBlocked as exc:
            results.append({'case':query['id'],'berry':query['berry'],'state':'blocked','reason':str(exc)})
    records=store.records(mode='live');counts={}
    for berry in ('berry-blueberry','berry-strawberry','berry-raspberry','berry-blackberry'):
        raw=[r for r in records if berry in r['analysis']['berry_ids']];visible=[r for r in raw if readable_in_english(r)]
        counts[berry]={'raw_relevant':len(raw),'english_readable':len(visible),'sources':dict(Counter(r['source'] for r in visible)),'roles':dict(Counter(r['content_role'] for r in visible))}
    report={'date':'2026-10-07','cash_spend_usd':0,'additional_requests_cap':6,'results':results,'records_before':baseline,'records_after':len(records),'unique_added':len(records)-baseline,'replay_added':len(records)-before,'by_berry':counts,'independent_live_accuracy_graded':0,'remaining_free_credits':pilot.balance()['balance'] if args.live else pilot.ledger['attempts'][-1].get('balance_after'),'balance_evidence':'Actual free-only account; latest saved receipt when replaying offline','cumulative_attempts':len(pilot.ledger['attempts']),'consumed_free_credits':pilot.ledger['initial_balance']-pilot.ledger['attempts'][-1].get('balance_after',pilot.ledger['initial_balance'])}
    out=ROOT/'artifacts/social-all-berries/trial-summary.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report),flush=True)

if __name__=='__main__':
    from app.services.collection_runner import CollectionRunLock
    lock=ROOT/'inbox/social-bakeoff/sociavault-multiplatform-2026-10-07/evaluation-inbox/operations/collection.lock'
    with CollectionRunLock(lock,run_id='social-all-berries-trial'):main()
