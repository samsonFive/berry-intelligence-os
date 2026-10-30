"""Offline rerank of captured candidates; original captures stay immutable.

The reranked run contains private source bodies: keep --output under inbox/.
Only the explicit --metadata-output may be published. No provider/model calls.
"""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.topic_retrieval import VERSION,plan_query,retrieve
from app.services.report_builder.topic_report import topic_sections
from app.services.topic_citation_audit import audit_topic_citations


def replay(run,entities,reviews):
    queries=[];resolutions=[];audits=[]
    for query in run['queries']:
        plan=plan_query(query['query'])
        rows=retrieve(query['improved_app'],plan,entities=entities,limit=20)
        packet={'topic_sources':[{**r,'origin':'web','trust_class':'LIVE / UNREVIEWED'} for r in rows],
                'topic_research':{'plan':plan.as_dict(),'source_scope':'combined','discovery':query['discovery']}}
        sections=topic_sections(packet,as_of=date.fromisoformat(run['started_at'][:10]))
        originals={r['id']:r for r in query['improved_app']}
        audits.append({'query':query['query'],**audit_topic_citations(packet,sections,originals)})
        by_id={r['id']:r for r in rows}
        for review in reviews:
            if review['query']!=query['query'] or review['disposition']!='needs_review':continue
            row=by_id.get(review['source_id'])
            original=originals.get(review['source_id'])
            binding_valid=bool(original and original.get('source_version')==review.get('source_version')
                               and hashlib.sha256(str(original.get('passage') or '').encode()).hexdigest()==review.get('passage_sha256'))
            quoted=next((s for s in sections if s.section_id in {'topic_findings','topic_background'} and review['source_id'] in s.citation_ids),None)
            action=('stale_review_binding' if not binding_valid else 'candidate_excluded' if not row else 'quotation_withheld' if not quoted else
                    'moved_to_background' if quoted.section_id=='topic_background' and quoted.section_id!=review['section_id'] else
                    'passage_replaced' if hashlib.sha256(row['passage'].encode()).hexdigest()!=review['passage_sha256'] else 'unresolved')
            resolutions.append({'query':query['query'],'source_id':review['source_id'],'source_url':review['source_url'],
                                'source_version':review['source_version'],'original_issue':review['reason'],
                                'action':action,'support_status':row.get('support_status') if row else None,
                                'new_section':quoted.section_id if quoted else None,'new_locator':row.get('passage_locator') if row and quoted else None,
                                'new_passage_sha256':hashlib.sha256(row['passage'].encode()).hexdigest() if row and quoted else None})
        queries.append({**query,'plan':plan.as_dict(),'improved_app':rows})
    holdout_note='Legacy cases 18 and 21 supplied explicitly requested citation fixes and are now regressions. Fresh blind holdouts are required for later acceptance.'
    expected=sum(r['disposition']=='needs_review' for r in reviews)
    unique_flags={(r['query'],r['section_id'],r['source_id']) for r in reviews if r['disposition']=='needs_review'}
    return {**run,'queries':queries,'rerank_version':VERSION,
            'original_held_out_query_indices':run.get('held_out_query_indices',[]),
            'held_out_query_indices':[i for i in run.get('held_out_query_indices',[]) if i not in {18,21}],
            'holdout_status':holdout_note}, {
        'scope':'Offline candidate rerank and report regeneration. A changed passage requires semantic inspection; holds are not source-truth resolution. Original snapshots are unchanged.',
        'retrieval_version':VERSION,'original_flag_count':expected,
        'unmapped_flags':expected-len(resolutions),
        'duplicate_flag_bindings':expected-len(unique_flags),
        'holdout_status':holdout_note,
        'unchanged_flagged_contexts':sum(r['action']=='unresolved' for r in resolutions),
        'stale_review_bindings':sum(r['action']=='stale_review_binding' for r in resolutions),
        'fidelity_failure_count':sum(len(r['failures']) for r in audits),'resolutions':resolutions,
        'quotation_audits':audits}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--reviews',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--metadata-output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if not args.output.resolve().is_relative_to((root/'inbox').resolve()):parser.error('Private reranked source bodies must stay under inbox/')
    raw=args.run.read_bytes();run=json.loads(raw);reviews=json.loads(args.reviews.read_text(encoding='utf-8'))['reviews']
    entities={}
    for path in (root/'data/entities').rglob('*.json'):
        entity=json.loads(path.read_text(encoding='utf-8'));entities[entity['id']]=entity
    reranked,metadata=replay(run,entities,reviews);metadata['original_run_sha256']=hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(reranked,ensure_ascii=False),encoding='utf-8')
    args.metadata_output.parent.mkdir(parents=True,exist_ok=True);args.metadata_output.write_text(json.dumps(metadata,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in metadata.items() if k not in {'resolutions','quotation_audits'}}))
