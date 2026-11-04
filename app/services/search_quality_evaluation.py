"""Offline, source-judged evaluation of recorded search rankings.

This module never calls a provider or infers relevance labels from ranking.
An incomplete pool or non-comparable baseline cannot establish parity.
"""
from __future__ import annotations

import math
from datetime import datetime
from statistics import mean

from app.services.article_dedup import normalize_canonical_url
from app.services.topic_retrieval import plan_query


def unique_results(rows, depth=20):
    seen=set();result=[]
    for row in rows:
        key=normalize_canonical_url(row.get('source_url') or row.get('url'))
        if not key or key in seen:continue
        seen.add(key);result.append({**row,'canonical_key':key})
        if len(result)>=depth:break
    return result


def checked_judgment(row):
    return isinstance(row,dict) and type(row.get('grade')) is int and row['grade'] in range(4) and row.get('source_checked') is True and bool(row.get('reason')) and bool(row.get('source_locator'))


def score_query(record, judgments, google=None, depth=10):
    google=google or {}
    systems={key:unique_results(record.get(key) or [],20) for key in ('old_app','improved_app')}
    systems['google']=unique_results(google.get('results',record.get('google') or []),20)
    labels={normalize_canonical_url(url):row for url,row in (judgments or {}).items()}
    pool={row['canonical_key'] for rows in systems.values() for row in rows}
    versions={key:{str(row['source_version']) for rows in systems.values() for row in rows if row['canonical_key']==key and row.get('source_version')} for key in pool}
    def checked(key):
        return checked_judgment(labels.get(key)) and (not versions[key] or versions[key]=={labels[key].get('source_version')})
    missing=sorted(key for key in pool if not checked(key))
    complete=not missing
    missing_events=sorted(key for key in pool if checked(key) and labels[key]['grade']==3
                          and not (isinstance(labels[key].get('event_group'),str) and labels[key]['event_group'].strip())
                          and labels[key].get('event_not_applicable') is not True)
    events={labels[key].get('event_group') for key in pool if checked_judgment(labels.get(key)) and labels[key]['grade']==3 and labels[key].get('event_group')}
    plan=plan_query(record['query'])
    requested={key:value for key,value in [('start',plan.start),('end',plan.end)] if value}
    comparable=bool(google.get('complete_depth')) and (len(systems['google'])>=depth or google.get('exhausted_results') is True) and (not requested or google.get('date_filters')==requested)
    metrics={}
    for system,rows in systems.items():
        top=rows[:depth]
        top_checked=all(checked(row['canonical_key']) for row in top)
        grades=[labels[row['canonical_key']]['grade'] for row in top] if top_checked else []
        scored={'result_count':len(rows),'top_checked':top_checked,'direct_precision_at_10':None,'ndcg_at_10':None,'pooled_development_coverage_sample':None}
        if top_checked:
            scored['direct_precision_at_10']=grades.count(3)/depth
        if complete:
            ideal=sorted((labels[key]['grade'] for key in pool),reverse=True)[:depth]
            dcg=sum((2**grade-1)/math.log2(i+2) for i,grade in enumerate(grades))
            idcg=sum((2**grade-1)/math.log2(i+2) for i,grade in enumerate(ideal))
            scored['ndcg_at_10']=dcg/idcg if idcg else None
            found={labels[row['canonical_key']].get('event_group') for row in top if labels[row['canonical_key']]['grade']==3 and labels[row['canonical_key']].get('event_group')}
            scored['pooled_development_coverage_sample']=len(found)/len(events) if events and not missing_events else None
        metrics[system]=scored
    return {'query':record['query'],'split':record.get('split'),'judged_pool_complete':complete,'pool_size':len(pool),'pool_urls':sorted(pool),
            'missing_judgments':missing,'missing_event_judgments':missing_events,'event_judgments_complete':not missing_events,'google_comparable':comparable,'metrics':metrics}


def score_snapshot(run, baseline, judgments):
    google={row['query']:row for row in baseline.get('queries',[])}
    queries=[score_query(row,judgments.get(row['query'],{}),google.get(row['query'])) for row in run.get('queries',[])]
    google_date=baseline.get('captured_date') or (baseline.get('capture_window_utc') or [''])[0]
    try:
        paired=datetime.fromisoformat(str(run.get('started_at') or '')[:10]).date()==datetime.fromisoformat(str(google_date)[:10]).date()
    except ValueError:
        paired=False
    ready=bool(queries) and paired and all(q['judged_pool_complete'] and q['event_judgments_complete'] and q['google_comparable'] for q in queries)
    aggregates={}
    regressions=[]
    if ready:
        for system in ('old_app','improved_app','google'):
            aggregates[system]={key:mean(values) if (values:=[q['metrics'][system][key] for q in queries if q['metrics'][system][key] is not None]) else None
                                for key in ('direct_precision_at_10','ndcg_at_10','pooled_development_coverage_sample')}
        for row in queries:
            for key in ('direct_precision_at_10','ndcg_at_10','pooled_development_coverage_sample'):
                app=row['metrics']['improved_app'][key];other=row['metrics']['google'][key]
                if app is not None and other is not None and app<other:regressions.append({'query':row['query'],'metric':key,'app':app,'google':other})
    return {'version':1,'source_run_started_at':run.get('started_at'),'query_count':len(queries),
            'unique_pooled_urls':len({key for query in queries for key in query['pool_urls']}),
            'judgment_pairs_missing':sum(len(q['missing_judgments']) for q in queries),
            'non_comparable_google_queries':[q['query'] for q in queries if not q['google_comparable']],
            'acceptance_ready':ready,'aggregate_metrics':aggregates,'individual_regressions':regressions,
            'same_day_capture_pairing':paired,
            'google_parity':'UNVERIFIED' if not ready else 'MEASURED — inspect aggregates and individual regressions; citation audit remains separate',
            'queries':queries}
