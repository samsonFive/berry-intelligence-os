"""Offline, content-free trial report and isolated same-pipeline preview store."""
from collections import Counter
from datetime import datetime,timezone
import json
import hashlib
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
PRIVATE=ROOT/'inbox/social-bakeoff/sociavault-multiplatform-2026-10-07'
os.environ['BIOS_INBOX_DIR']=str(PRIVATE/'evaluation-inbox')
os.environ['ENABLE_SOURCE_POLLING']='false';os.environ['BIOS_MODE']='authoring'
from app.services.social_intelligence.sociavault_normalize import normalize
from app.services.social_intelligence.store import Store,identity
from app.services.social_intelligence.bakeoff import raw_metrics,verified_score

def main():
    ledger=json.loads((PRIVATE/'ledger.json').read_text(encoding='utf-8'))
    manifest=json.loads((PRIVATE/'manifest.json').read_text(encoding='utf-8'))
    refs=json.loads((PRIVATE/'reference-probes.json').read_text(encoding='utf-8'))
    targets={r['id']:r for r in refs};queries={q['id']:q for q in manifest['queries']}
    results=[];discovery=[];reference=[];repeat=[];all_rows=[];jobs=[]
    for a in ledger['attempts']:
        f=PRIVATE/(a['id']+'.json');t=targets.get(a['case_id'],{});q=queries.get(a['case_id'],{})
        result={'case':a['case_id'],'task':a['task'],'transport_state':a['state'],
                'http':a.get('http'),'credit_delta':a.get('observed_credit_delta'),
                'returned_items':None,'mapped_items':0,'in_interval':0,'unknown_date':0,
                'outside_interval':0,'media_references':0,'mapping_errors':0}
        rows=[]
        if f.exists():
            payload=json.loads(f.read_text(encoding='utf-8'))
            normalized=normalize(payload,a['task'],
                                 supplied_url=t.get('url'),supplied_parent_id=t.get('native_id'))
            rows=normalized['rows'];result.update(returned_items=normalized['returned_items'],
                  mapped_items=len(rows),mapping_errors=len(normalized['mapping_errors']),
                  media_references=sum(len(r['media']) for r in rows))
            for r in rows:
                r['collected_at']=a['at']
                if q:
                    r['search_market']={'value':q['market'],'basis':'query_target','evidence_ref':q['id'],'confidence':1}
                published=r['published_at']
                if not published:result['unknown_date']+=1
                elif manifest['start_utc']<=published<=manifest['end_utc']:result['in_interval']+=1
                else:result['outside_interval']+=1
            if a['case_id'].endswith('-repeat'):repeat=rows
            elif t:
                reference+=rows
                # A supplied thread response contains its actual parent post;
                # retain that context rather than attaching comments to an invented parent.
                if a['task']=='reddit-comments' and payload.get('data',{}).get('post'):
                    parents=normalize({'success':True,'data':{'posts':[payload['data']['post']]}},'reddit-search')['rows']
                    reference+=parents;all_rows+=parents
            else:discovery+=rows
            all_rows+=rows
        results.append(result)
        jobs.append({'id':'trial-'+a['case_id'],'source':a['task'].split('-')[0],
            'market':q.get('market','Known URL'),'language':q.get('language','und'),
            'status':'partial' if f.exists() else 'access-pending',
            'last_success':a['at'] if f.exists() else None,'observed_volume':len(rows) if f.exists() else None,
            'failure':'One-off trial; no scheduled coverage. Original language/date/rights require inspection.' if f.exists() else 'Trial request '+a['state']+'; not zero volume',
            'query_changed':True})
    store=Store(PRIVATE/'evaluation-inbox')
    drafts_path=PRIVATE/'draft-translations.json'
    provider_tags=dict(Counter(r['language'] for r in {identity(r):r for r in all_rows}.values()))
    drafts=json.loads(drafts_path.read_text(encoding='utf-8')) if drafts_path.exists() else []
    translated=set()
    for row in all_rows:
        for draft in drafts:
            if (row['source'],row['native_id'],hashlib.sha256(row['text'].encode()).hexdigest())!=(draft['source'],draft['native_id'],draft['source_text_sha256']):continue
            if row['language']=='und':
                row['language']=draft['original_language'];row['language_basis']='Assistant inspection of original text; not independently checked'
            row['translation']={'text':draft['translation'],'language':'en','method':'machine',
              'version':'assistant-in-chat-2026-10-07','uncertainty':'Draft English translation; not independently reviewed'}
            translated.add(identity(row))
    from app.main import all_entities
    before=len(store.records(mode='live'));store.ingest(all_rows,all_entities(),mode='live')
    unique_after=len(store.records(mode='live'));store.ingest(all_rows,all_entities(),mode='live')
    for job in jobs:store.save_job(job)
    first=next((r for r in results if r['case']=='bb-en-1'),None)
    original=[r for r in discovery if r['source']=='reddit' and r.get('search_market',{}).get('evidence_ref')=='bb-en-1']
    original_ids={identity(r) for r in original};repeat_ids={identity(r) for r in repeat}
    summary={'version':manifest['version'],'date':'2026-10-07','cash_spend_usd':0,
      'initial_free_credits':ledger['initial_balance'],'remaining_free_credits':ledger['attempts'][-1].get('balance_after'),
      'metered_attempts_reserved':len(ledger['attempts']),
      'consumed_free_credits':ledger['initial_balance']-ledger['attempts'][-1].get('balance_after',ledger['initial_balance']),
      'reserve_required':ledger['initial_balance']*.2,'credit_ceiling':30,
      'cases':results,'discovery':raw_metrics(discovery,sum(bool(r['mapped_items']) for r in results if r['case'] in queries)),
      'references':raw_metrics(reference,len(refs)),'reference_url_count':len({r['url'] for r in refs}),
      'unique_live_records_in_isolated_store':unique_after,'restart_unique_records':len(store.records(mode='live')),
      'store_preexisting_records':before,'platforms_mapped':dict(Counter(r['source'] for r in {identity(r):r for r in all_rows}.values())),
      'provider_language_tags':provider_tags,
      'display_language_tags':dict(Counter(r['language'] for r in {identity(r):r for r in all_rows}.values())),
      'repeat':{'original':len(original_ids),'returned':len(repeat_ids),'stable_ids':len(original_ids&repeat_ids),
                'real_second_request':True,'cache_replay_is_not_provider_proof':True},
      'scores':verified_score({}),'independent_human_reviews':0,'translations_generated':len(translated),
      'screenshots_from_provider':0,'downloaded_media_bytes':0,
      'limits':['Source images are references until browser inspection; no original screenshot service demonstrated',
        'Account is actual free/no purchased pack; one-time signup credits do not establish recurring zero-cost monitoring',
        'Two TikTok requests hit the two-megabyte cap and may consume credit; not retried',
        'Initial LinkedIn request used an incorrect route; corrected documented route also returned 404',
        'Provider may return more than ten items in one response; client intake capped ten posts/twenty comments',
        'Missing publication dates and unverified languages are not inferred from query targets',
        'No independently scored precision, regional coverage, deletion refresh or global recall established']}
    for bucket in ('discovery','references'):
        fields=summary[bucket]['field_presence_not_correctness']
        fields['language_tag_including_unknown']=fields.pop('language')
        fields['language_tag_including_unknown']['does_not_establish_original_language']=True
    (PRIVATE/'normalized.json').write_text(json.dumps(all_rows,ensure_ascii=False),encoding='utf-8')
    (PRIVATE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'unique':unique_after,'discovery':summary['discovery'],'references':summary['references'],
                     'platforms':summary['platforms_mapped'],'repeat':summary['repeat'],
                     'remaining_free_credits':summary['remaining_free_credits']},ensure_ascii=True))

if __name__=='__main__':main()
