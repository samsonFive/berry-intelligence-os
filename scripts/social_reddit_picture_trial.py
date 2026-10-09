"""One user-requested missing-picture probe; offline replay by default."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.services.collection_runner import CollectionRunLock
from app.services.social_intelligence.sociavault_pilot import MultiPlatformPilot,private_key
from app.services.social_intelligence.sociavault_normalize import normalize
from app.services.social_intelligence.store import Store
from app.services.social_intelligence.adapters import AccessBlocked

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--key-file');args=parser.parse_args()
    manifest=json.loads((ROOT/'benchmarks/social-bakeoff/reddit-picture-review-manifest.json').read_text(encoding='utf-8'))
    private=ROOT/'inbox/social-bakeoff/sociavault-multiplatform-2026-10-07'
    pilot=MultiPlatformPilot(private,enabled=args.live,key=private_key(args.key_file) if args.live else None,ceiling=manifest['cumulative_attempt_ceiling'])
    store=Store(private/'evaluation-inbox')
    target=next((r for r in store.records(mode='live') if r['source']=='reddit' and r['native_id']==manifest['expected_native_id']),None)
    if not target:raise SystemExit('Expected retained original post absent; no request made')
    receipt={'date':manifest['date'],'cash_spend_usd':0,'additional_requests_cap':1,'media_downloads':0,'source':'reddit'}
    try:
        if args.live:payload,cached=pilot.fetch(manifest['task'],manifest['params'],case_id=manifest['case_id'])
        else:
            attempt=next((a for a in pilot.ledger['attempts'] if a.get('case_id')==manifest['case_id']),None)
            if not attempt or not (private/(attempt['id']+'.json')).exists():raise AccessBlocked('No retained successful receipt; offline replay never collects')
            payload=json.loads((private/(attempt['id']+'.json')).read_text(encoding='utf-8'));cached=True
        normalized=normalize(payload,'reddit-post')
        post=next((r for r in normalized['rows'] if r['native_id']==manifest['expected_native_id']),None)
        if not post:raise AccessBlocked('Returned post identity did not match; no attachments associated')
        known={m['source_url'] for m in target['media'] if m.get('source_url')}
        additions=[m for m in post['media'] if m.get('source_url') not in known]
        for m in additions:
            m['id']='detail-'+hashlib.sha256(m['source_url'].encode()).hexdigest()[:24];m['attribution']='Original Reddit attachment via bounded SociaVault post-detail follow-up 2026-10-07; reference only'
        row={k:v for k,v in target.items() if k not in ('id','analysis')}
        row['media']+=additions
        entities=[json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'data/entities').rglob('*.json')]
        store.ingest([row],entities,mode='live')
        receipt.update(state='offline-replay' if cached else 'retrieved',returned_attachment_references=len(post['media']),new_attachment_references=len(additions),mapping_errors=normalized['mapping_errors'])
    except AccessBlocked as exc:receipt.update(state='blocked',reason=str(exc))
    attempt=next((a for a in pilot.ledger['attempts'] if a.get('case_id')==manifest['case_id']),{})
    receipt.update(http=attempt.get('http'),observed_credit_delta=attempt.get('observed_credit_delta'),remaining_free_credits=attempt.get('balance_after'),cumulative_attempts=len(pilot.ledger['attempts']))
    out=ROOT/'artifacts/social-all-berries/reddit-picture-review.json';out.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))

if __name__=='__main__':
    with CollectionRunLock(ROOT/'inbox/social-bakeoff/sociavault-multiplatform-2026-10-07/evaluation-inbox/operations/collection.lock',run_id='reddit-picture-review'):main()
