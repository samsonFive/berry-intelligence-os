"""Regenerate content-free pilot summary from private local samples; no network."""
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.services.social_intelligence.bakeoff import raw_metrics, ingest_isolated
from app.services.social_intelligence.extraction import analyze
from scripts.social_intelligence import entities

def summarize():
    inbox=ROOT/'inbox/social-bakeoff';artifacts=ROOT/'artifacts/social-blueberry'
    runs=['news-2026-10-07','news-rest-2026-10-07']
    rows=[];attempts=[];cache_bytes=0
    for run in runs:
        rows+=json.loads((inbox/run/'normalized.json').read_text(encoding='utf-8'))
        file='bakeoff-news.json' if run==runs[0] else 'bakeoff-news-rest.json'
        attempts+=json.loads((artifacts/file).read_text(encoding='utf-8'))['results'][0]['attempts']
        cache_bytes+=sum(p.stat().st_size for p in (inbox/run/'cache').glob('*.bin'))
    registry=entities();proof=ingest_isolated(rows,inbox/'news-combined-2026-10-07',registry)
    unique={(r['source'],r['native_id']):r for r in rows}
    by_language={}
    for lang in ('en','es','pt','zh','ja'):
        calls=[a for a in attempts if a['language']==lang]
        selected=[r for r in unique.values() if r['language']==lang]
        analysis=[analyze(r,registry) for r in selected]
        by_language[lang]={'attempted_queries':len(calls),'successful_queries':sum(a['state']=='live-tested' for a in calls),
          'blocked_queries':sum(a['state']=='blocked' for a in calls),'returned_with_duplicates':sum(a.get('returned',0) for a in calls),
          'unique_titles':len(selected),'local_berry_relevance_machine_only':dict(Counter(a['relevance'] for a in analysis)),
          'original_language_verified':False,'reviewed_precision':{'numerator':0,'denominator':0,'estimate':None}}
    repeat_file=inbox/'news-repeat-2026-10-07'/'normalized.json'
    repeat={'state':'pending','provider_repeat':False}
    if repeat_file.exists():
        repeated=json.loads(repeat_file.read_text(encoding='utf-8'))
        first=json.loads((inbox/runs[0]/'normalized.json').read_text(encoding='utf-8'))[:4]
        a={r['native_id'] for r in first};b={r['native_id'] for r in repeated}
        repeat={'state':'live-tested','provider_repeat':True,'first_n':len(a),'second_n':len(b),
          'same_ids_n':len(a&b),'same_id_sets':a==b,'source':'news titles only',
          'cached':False,'social_repeat_proof':False}
        ingest_isolated(repeated,inbox/'news-combined-2026-10-07',registry)
    summary={'version':1,'as_of':'2026-10-07','recommendation':'no proven winner yet',
      'query_attempts':len(attempts),'successful_queries':sum(a['state']=='live-tested' for a in attempts),
      'blocked_queries':sum(a['state']=='blocked' for a in attempts),'news':raw_metrics(rows,sum(a['state']=='live-tested' for a in attempts)),
      'by_feed_locale_not_verified_original_language':by_language,'same_pipeline_unique':proof['unique'],
      'cached_feed_bytes':cache_bytes,'repeat':repeat,
      'cost_ledger':{'cash_usd':0,'apify_credit_usd':0,'sociavault_credits':0,'youtube_quota':0,
         'public_news_http_attempts':len(attempts)+int(repeat['provider_repeat']),
         'paid_models':0,'paid_proxies':0,'paid_storage':0,'scheduled':False,
         'replacement_cost_usd':0,'local_disk_bytes':cache_bytes,
         'notes':'Local disk/connection/compute use existing resources; no incremental cash. Raw normalized JSON/SQLite add local bytes not counted as feed transfer.'},
      'acceptance':{'reviewed_social_discovery':0,'reference_fetch_attempts':0,'live_comment_images':0,
         'verified_scores':0,'tested_score_weight_percent':0,'global_monitor_proven':False}}
    (artifacts/'bakeoff-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'returned_titles':len(rows),'unique_titles':len(unique),'by_locale':by_language,
                      'same_pipeline_unique':proof['unique'],'repeat':repeat,'feed_bytes':cache_bytes},ensure_ascii=False))

if __name__=='__main__':summarize()
