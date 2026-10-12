"""Bounded multi-platform trial; offline by default. Never print the API key."""
import argparse
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.services.social_intelligence.sociavault_pilot import MultiPlatformPilot,private_key
from app.services.social_intelligence.adapters import AccessBlocked

def plan():
    original=json.loads((ROOT/'benchmarks/social-bakeoff/manifest.json').read_text(encoding='utf-8'))
    assignments=[(0,'reddit'),(5,'tiktok'),(10,'linkedin'),(16,'x'),(18,'instagram'),(17,'pinterest'),(12,'youtube'),
                 (1,'reddit'),(2,'tiktok'),(3,'x'),(4,'youtube'),(6,'instagram'),(7,'pinterest'),(8,'linkedin'),
                 (9,'reddit'),(11,'x'),(13,'youtube'),(14,'pinterest'),(15,'instagram'),(19,'tiktok')]
    now=datetime.now(timezone.utc)
    result={**original,'version':'sociavault-multiplatform-2026-10-07-v1',
      'predeclared_at':now.isoformat(),'start_utc':(now-timedelta(days=30)).isoformat(),'end_utc':now.isoformat(),
      'credit_ceiling':30,'known_url_cap':5,'exceptions':{
        'instagram':'Hashtag discovery through Google index, not arbitrary phrase search; index date is not post date',
        'linkedin':'Google-indexed public posts; date filter may apply to index age',
        'pinterest':'No date parameter; exact date filtered only when present',
        'youtube':'Search this_month approximates interval; unknown dates remain explicitly unverified',
        'x':'Native since/until dates are day-granular; exact local date filter when returned',
        'known-url':'Known-URL media/comment probes may be outside interval; separate from discovery score'},'queries':[]}
    for index,platform in assignments:
        q=original['queries'][index].copy();q['platform']=platform;q['task']=platform+'-search'
        value=q['query']
        if platform=='instagram':
            value={'en':'blueberries','es':'arandanos','ja':'いちご'}[q['language']]
            params={'hashtag':value,'date_posted':'last-month','media_type':'all'}
            q['syntax_exception']='Hashtag replaces phrase; retailer/intent terms not preserved'
        elif platform=='reddit':params={'query':value,'timeframe':'month','sort':'new','trim':'false'}
        elif platform=='tiktok':params={'query':value,'date_posted':'this-month','sort_by':'date-posted','trim':'false'}
        elif platform=='linkedin':params={'query':value,'date_posted':'last-month'}
        elif platform=='youtube':params={'query':value,'uploadDate':'this_month','sortBy':'relevance'}
        elif platform=='x':params={'query':value+f" since:{result['start_utc'][:10]} until:{(now+timedelta(days=1)).date().isoformat()}",'type':'Latest'}
        else:params={'query':value,'trim':'false'}
        q['params']=params;result['queries'].append(q)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');p.add_argument('--key-file')
    p.add_argument('--limit',type=int,default=7);p.add_argument('--start',type=int,default=0)
    args=p.parse_args()
    private=ROOT/'inbox/social-bakeoff/sociavault-multiplatform-2026-10-07'
    private.mkdir(parents=True,exist_ok=True)
    manifest_path=private/'manifest.json'
    if manifest_path.exists():manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    else:
        manifest=plan();manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    if not args.live:
        print(json.dumps({'state':'offline-plan','queries':len(manifest['queries']),'credit_ceiling':30}));return
    if not 0<=args.start<20 or not 1<=args.limit<=20:raise SystemExit('Invalid bounded query slice')
    pilot=MultiPlatformPilot(private,enabled=True,key=private_key(args.key_file))
    for q in manifest['queries'][args.start:args.start+args.limit]:
        try:
            data,cached=pilot.fetch(q['task'],q['params'],case_id=q['id'])
            data_root=data.get('data',data)
            print(json.dumps({'case':q['id'],'platform':q['platform'],'state':'cached' if cached else 'retrieved',
                              'top_fields':list(data_root)[:12] if isinstance(data_root,dict) else [],
                              'reported_credits':data.get('credits_used')},ensure_ascii=False),flush=True)
        except AccessBlocked as exc:
            print(json.dumps({'case':q['id'],'platform':q['platform'],'state':'blocked','reason':str(exc)}),flush=True)
            if any(a['state']=='price-mismatch' for a in pilot.ledger['attempts']):break
    final=pilot.balance()
    print(json.dumps({'remaining_free_credits':final['balance'],'reserved_attempts':len(pilot.ledger['attempts']),
                      'cash_spend':0}),flush=True)

if __name__=='__main__':main()
