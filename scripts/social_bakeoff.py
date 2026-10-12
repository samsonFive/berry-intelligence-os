"""Offline default; explicitly bounded free-only live evaluation. No scheduling."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.services.social_intelligence.bakeoff import (BoundedRead, bluesky_search,
    news_feed, jetstream_rows, ingest_isolated, raw_metrics, verified_score, AccessBlocked)

def run(args):
    pack=ROOT/'benchmarks/social-bakeoff'
    manifest=json.loads((pack/'manifest.json').read_text(encoding='utf-8'))
    candidates=json.loads((pack/'candidates.json').read_text(encoding='utf-8'))['candidates']
    private=ROOT/'inbox/social-bakeoff'/args.run_id
    private.mkdir(parents=True,exist_ok=True)
    results=[]
    if not args.live:
        from scripts.evaluate_social_blueberry import evaluate
        evaluation=evaluate()
        results.append({'candidate':'offline-pipeline','state':'fixture-only','synthetic':True,
                        'evaluation':evaluation,'provider_proof':False})
    else:
        transport=BoundedRead(private/'cache',enabled=True,max_requests=args.max_requests)
        rows=[]; attempts=[]
        if args.candidate in ('bluesky-search','google-news-rss'):
            adapter=bluesky_search if args.candidate=='bluesky-search' else news_feed
            for query in manifest['queries'][args.start_query:args.start_query+args.max_queries]:
                try:
                    found=adapter(transport,query,manifest)
                    rows.extend(found)
                    attempts.append({'query':query['id'],'language':query['language'],'target_market':query['market'],
                                     'state':'live-tested','returned':len(found),'cap':10,'pages':1})
                except AccessBlocked as exc:
                    attempts.append({'query':query['id'],'language':query['language'],'state':'blocked','reason':str(exc)})
                    if transport.requests >= transport.max_requests:
                        break
        elif args.candidate=='bluesky-jetstream':
            import subprocess
            raw=private/'jetstream.json'
            if not raw.exists():
                subprocess.run(['node',str(ROOT/'scripts/social_jetstream_probe.mjs'),str(raw)],check=True,timeout=45)
            result=json.loads(raw.read_text(encoding='utf-8'))
            rows=jetstream_rows(result,manifest)
            attempts=[{k:result[k] for k in ('state','frames','bytes','connected','duration_ms','window_exception')}]
        else:
            # No metered calls with undocumented price bounds/account billing.
            candidates=[c for c in candidates if c['id']==args.candidate]
            if not candidates:
                raise ValueError('Unknown candidate')
            attempts=[{'state':'blocked','reason':candidates[0]['blocker']}]
        from scripts.social_intelligence import entities
        proof=ingest_isolated(rows,private,entities())
        (private/'normalized.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        state='live-tested' if any(a['state']=='live-tested' for a in attempts) else 'blocked'
        results.append({'candidate':args.candidate,'state':state,'attempts':attempts,
          'metrics':raw_metrics(rows,sum(a.get('query') is not None and a['state']=='live-tested' for a in attempts)),
          'same_pipeline_unique':proof['unique'],'requests':transport.requests,'cache_hits':transport.cache_hits,
          'score':verified_score({}), 'score_reason':'No independently reviewed sample; no dimension scored',
          'cash_usd':0,'free_credits_consumed':0,'paid_models':0,'retries':0})
    report={'version':1,'manifest_version':manifest['version'],'manifest_interval':[manifest['start_utc'],manifest['end_utc']],
        'at':datetime.now(timezone.utc).isoformat(),'scheduled':False,'cash_usd':0,'results':results,
        'unmet':['30 reviewed discovery results','10 applicable reference fetches','three live non-English languages',
                 'more than one evidenced region','live comment images','verified redisplay/retention permissions']}
    # This output has counts/labels only; raw content stays in ignored runtime.
    destination=args.report or private/'report.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(destination),'cash_usd':0,'states':[r['state'] for r in results]}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live',action='store_true');p.add_argument('--candidate',default='bluesky-search')
    p.add_argument('--run-id',default='pilot-2026-10-07');p.add_argument('--report',type=Path)
    p.add_argument('--max-queries',type=int,choices=range(1,21),default=1)
    p.add_argument('--max-requests',type=int,choices=range(1,21),default=1)
    p.add_argument('--start-query',type=int,choices=range(20),default=0,
                   help='Zero-based next pack case; explicitly skip already attempted blocked cases')
    run(p.parse_args())
