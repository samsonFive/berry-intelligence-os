"""Bounded operator CLI. No scheduling, credentials or paid calls by default."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.runtime_config import resolve_inbox_dir,resolve_data_dir
from app.services.social_intelligence.store import Store
from app.services.social_intelligence.adapters import Bluesky,YouTube,Transport,collect
from app.services.social_intelligence.model import Intake

def entities():
    return [json.loads(p.read_text(encoding='utf-8')) for p in (resolve_data_dir(ROOT)/'entities').rglob('*.json')]

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['status','fixture','import','collect','expire','schema','attach','translate'])
    p.add_argument('--file',type=Path);p.add_argument('--source',choices=['bluesky','youtube'],default='bluesky')
    p.add_argument('--query',default='blueberries');p.add_argument('--language',default='en');p.add_argument('--market',default='US')
    p.add_argument('--enable',action='store_true');p.add_argument('--max-pages',type=int,default=1);p.add_argument('--max-items',type=int,default=40)
    p.add_argument('--include-comments',action='store_true')
    p.add_argument('--evidence-id');p.add_argument('--media-id');p.add_argument('--mime',default='image/png')
    args=p.parse_args();store=Store(resolve_inbox_dir(ROOT));result={}
    if args.action=='schema': result=Intake.model_json_schema()
    elif args.action=='status': result={'jobs':store.jobs(),'counts':{m:len(store.records(mode=m)) for m in ('live','imported','manual','fixture')}}
    elif args.action in ('fixture','import'):
        path=args.file or ROOT/'benchmarks/social-blueberry-fixtures.json'
        payload=json.loads(path.read_text(encoding='utf-8'));rows=payload['records'] if isinstance(payload,dict) else payload
        result={'ids':store.ingest(rows,entities(),mode='fixture' if args.action=='fixture' else 'imported')}
    elif args.action=='translate':
        if not args.file: p.error('translate needs a verified enrichment file')
        packet=json.loads(args.file.read_text(encoding='utf-8'))
        result={'id':store.enrich_translation(packet['evidence_id'],packet['source_hash'],packet['translation'],packet['reviewer'])}
    elif args.action=='expire': result={'expired':store.expire()}
    elif args.action=='attach':
        if not args.file or not args.evidence_id or not args.media_id: p.error('attach needs file, evidence-id and media-id')
        result={'hash':store.attach_media(args.evidence_id,args.media_id,args.file.read_bytes(),args.mime)}
    elif args.action=='collect':
        adapter=(Bluesky if args.source=='bluesky' else YouTube)(Transport(max_requests=12))
        result=collect(store,adapter,entities(),query=args.query,language=args.language,market=args.market,max_pages=args.max_pages,max_items=args.max_items,enabled=args.enable,include_comments=args.include_comments)
        from datetime import datetime,timezone
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        run={'pipeline':'social_intelligence','started_at':result['job']['started_at'],'completed_at':datetime.now(timezone.utc).isoformat(),
             'outcome':'FAILED' if result.get('state')=='error' else 'PARTIAL' if result['job']['status']=='partial' else 'SUCCESS',
             'failure_count':len(result.get('failed',[])),'failure_sample':result.get('failed',[]),
             'counts':{'records_retained':len(result.get('created',[])),'requests':result['job']['calls']}}
        folder=store.inbox/'operations'/'pipelines'/'social_intelligence'/'runs';folder.mkdir(parents=True,exist_ok=True)
        (folder/(stamp+'.json')).write_text(json.dumps(run,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if result.get('state')=='error' else 0

if __name__=='__main__': raise SystemExit(main())
