"""Replay quotation-fidelity checks over saved benchmark captures; no network."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.report_builder.topic_report import topic_sections
from app.services.topic_citation_audit import audit_topic_citations, audit_semantic_reviews


def audit_snapshot(run, semantic_reviews=None):
    results=[]
    as_of=date.fromisoformat(run['started_at'][:10])
    for query in run['queries']:
        originals={r['id']:r for r in query['improved_app']}
        rows=[{**r,'origin':'web','trust_class':'LIVE / UNREVIEWED'} for r in originals.values()]
        packet={'topic_sources':rows,'topic_research':{'plan':query['plan'],'source_scope':'combined','discovery':query['discovery']}}
        sections=topic_sections(packet,as_of=as_of)
        audit=audit_topic_citations(packet,sections,originals)
        if semantic_reviews is not None:
            audit['semantic_review']=audit_semantic_reviews(query['query'],packet,sections,semantic_reviews)
        results.append({'query':query['query'],'split':query['split'],'captured_candidates':len(rows),
                        'unreadable_candidates':sum(not (r.get('article') or {}).get('paragraphs') for r in rows),**audit})
    return {'version':1,'captured_run_started_at':run['started_at'],'audit_kind':'Offline quotation fidelity replay; no source truth, relevance or Google parity claim',
            'query_count':len(results),'quotations_checked':sum(r['quotations_checked'] for r in results),
            'failure_count':sum(len(r['failures']) for r in results),'queries':results}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--semantic-reviews',type=Path)
    args=parser.parse_args();raw=args.run.read_bytes()
    reviews=json.loads(args.semantic_reviews.read_text(encoding='utf-8')) if args.semantic_reviews else None
    result=audit_snapshot(json.loads(raw),reviews.get('reviews',[]) if reviews is not None else None);result['run_sha256']=hashlib.sha256(raw).hexdigest()
    if reviews is not None:
        result['semantic_review_totals']={key:sum(q['semantic_review'][key] for q in result['queries']) for key in ('reviewed','unreviewed','issues')}
        result['semantic_reviews_sha256']=hashlib.sha256(args.semantic_reviews.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='queries'}))
