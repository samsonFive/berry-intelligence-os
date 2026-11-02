"""Read-only table projections over retained research; never merge identities or claims."""
from datetime import date
import json
import re
from math import ceil
from urllib.parse import urlencode

LABELS = {'person':'Person observation','job':'Job posting','hiring_event':'Organizational observation',
          'role_context':'Role context','profile':'Profile observation','gap':'Research gap',
          'relationship':'Relationship','exposure':'Exposure','batch':'Import batch','mapping':'Mapping review','saved':'Saved comparison'}


def text(fields, *names):
    return next((str(fields[k]) for k in names if fields.get(k) and str(fields[k]).casefold() not in {'unknown','unspecified','none','n/a'}), 'Unknown')


def iso(value):
    try:
        return date.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        return ''


def build(model, view, params, *, page_size=50):
    entities=model['entities']; rows=[]
    company=lambda key:entities.get(key,{}).get('name',key or 'Unknown')
    def make(record, kind=None, history=None):
        f=record['fields']; kind=kind or record['kind']; sources=record.get('sources',[])
        check=[s.get('verification',{}).get('status')=='inspected_supports_claim' for s in sources]
        source_state='missing' if not sources else 'inspected' if all(check) else 'partial' if any(check) else 'unverified'
        return {'id':record['id'],'entity_id':record.get('entity_id'),'kind':kind,'type':LABELS.get(kind,kind),'company':company(record.get('entity_id')),
                'name':text(f,'name_original','person_name','name','title','event_type','resolved_name','legal_name','issue'),
                'role':text(f,'role_title','new_role','function_seniority','function','peer_roles','predicate','pestel_category'),
                'status':text(f,'role_status','observed_status','fact_claim_hypothesis','identity_status'),
                'date':text(f,'last_observed_date','observed_date','scope_period'), 'date_basis':'Last observed',
                'location':text(f,'location','location_remote_scope','origin_scope','production_origin_ids_or_names'),
                'scope':text(f,'berry_market_program_scope','crop_program_scope','berry_scope','destination_scope','destination_market_ids_or_names'),
                'detail':text(f,'supporting_text','disambiguation_context','interpretation_and_limits','limitations','unresolved_question','gaps'),
                'sources':sources,'source_state':source_state,'resolution':record['resolution'],
                'records':history or [record], 'link':''}
    if view=='people':
        people_by_ref={(r['batch_id'],r['local_id']):r for r in model['records'] if r['kind']=='person'}
        for r in model['records']:
            if r['kind'] not in {'person','hiring_event'}:continue
            row=make(r)
            if r['kind']=='hiring_event':
                f=r['fields']
                row['name']=text(f,'person_name','name_original','name','person_id_or_unknown')
                refs=re.findall(r'[BR]\d{2}-P\d+',str(f.get('person_id_or_unknown') or ''))
                if refs and row['name']==text(f,'person_id_or_unknown'):
                    linked=[people_by_ref.get((r['batch_id'],ref)) for ref in refs]
                    if all(linked):
                        names=[text(person['fields'],'name_original','name') for person in linked]
                        if all(name!='Unknown' for name in names):row['name']='; '.join(dict.fromkeys(names))
                row['role']=text(f,'new_role','event_type')
                row['status']=text(f,'event_type')
                row['date']=text(f,'effective_date','event_date','announced_date','announcement_date')
                row['date_basis']='Reported event / announcement; observed '+text(f,'observed_date','last_observed_date')
                if 'not a hiring event' in str(f.get('event_type','')).lower():
                    row.update(kind='role_context',type=LABELS['role_context'])
                elif iso(row['date']) and row['date'] < model['events_after']:continue
            rows.append(row)
        # Reuse canonical requisition/URL grouping. Search all retained posting history.
        from app.services.competitive_evaluation import job_groups
        for group in job_groups(model['records']):
            row=make(group['latest'],history=group['observations'])
            row.update(id=group['id'],name=text(group['latest']['fields'],'title'),detail=group['interpretation'])
            row['sources']=list({s['id']:s for r in group['observations'] for s in r.get('sources',[])}.values())
            rows.append(row)
    elif view in {'overview','exposure','relationships'}:
        allowed={'overview':{'profile','gap'},'exposure':{'exposure'},'relationships':{'relationship'}}[view]
        for r in model['records']:
            if r['kind'] not in allowed:continue
            row=make(r);f=r['fields']
            if view=='overview':
                row.update(name=company(r.get('entity_id')),role=text(f,'peer_roles','capability_id_or_identity'),
                           detail=text(f,'issue','gaps','identity_status'),status=r['resolution'],
                           date_basis='Source scope period' if text(f,'last_observed_date','observed_date')=='Unknown' and text(f,'scope_period')!='Unknown' else 'Last observed')
            elif view=='exposure':
                row.update(name=text(f,'dependency','exposure_statement'),role=text(f,'pestel_category'),
                           detail=text(f,'exposure_statement','mechanism'),mitigation=text(f,'reported_mitigation'),
                           outcome=text(f,'mitigation_outcome_or_unknown'),status=r['resolution'])
            else:
                row.update(name=company(f.get('subject_entity_id')),role=text(f,'predicate'),
                           target=company(f.get('object_entity_id_or_proposed_name')),status=text(f,'fact_claim_hypothesis'),
                           date=text(f,'start_date','observed_date'),date_basis='Start / observation as recorded')
            rows.append(row)
        if view=='relationships':
            for edge in model['graph']:
                if edge['id'].startswith('competitive-record-'):continue
                rows.append({'id':edge['id'],'kind':'relationship','type':'Canonical relationship','company':company(edge['subject']),
                             'name':company(edge['subject']),'role':edge['predicate'],'target':company(edge['object']),
                             'status':edge['status'],'date':text(edge['scope'],'effective_date','start_date'),
                             'date_basis':'Recorded effective / start','scope':json.dumps(edge['scope'],ensure_ascii=False),
                             'detail':edge['basis'],'sources':[],'source_state':'unverified','resolution':'Existing canonical record',
                             'records':[],'edge':edge,'link':''})
    elif view=='imports':
        for b in model['batches']:
            rows.append({'id':b['id'],'kind':'batch','type':LABELS['batch'],'name':b['batch_id'],'company':'All batch entities',
                         'role':'Research import','status':', '.join(f'{k}: {v}' for k,v in b['counts'].items()),
                         'date':b['updated_at'],'date_basis':'Imported','detail':b['original_return_sha256'],
                         'scope':str(len(b.get('issues',[])))+' row issues','resolution':'Structural review only',
                         'sources':[],'source_state':'missing','records':[],'batch':b,'link':''})
        for r in model['records']:
            if not r.get('mapping_review'):continue
            row=make(r,'mapping');row.update(name=r['batch_id']+' / '+r['local_id'],role=r['kind'],
                 status=r['resolution'],detail=r['mapping_review']['rationale'],date=r['mapping_review']['reviewed_at'],date_basis='Mapping reviewed')
            rows.append(row)
    elif view=='saved':
        for saved in model['saved']:
            rows.append({'id':saved['id'],'kind':'saved','type':LABELS['saved'],'name':saved['title'],'company':saved.get('updated_by','Unknown'),
                         'role':'Immutable snapshot','date':saved['updated_at'],'date_basis':'Saved','status':'Frozen comparison',
                         'scope':str(len(saved.get('snapshot',{}).get('assessments',[])))+' cells','detail':saved.get('narrative',''),
                         'sources':[],'source_state':'missing','records':[],'snapshot':saved,
                         'resolution':'Original snapshot retained','link':'/competitive-evaluation?saved='+saved['id']})
    columns={
      'people':[('name','Person / job title',200),('company','Company',145),('role','Role / function',170),('type','Record type',115),('status','Observed status',170),('date','Event / observed date',150),('location','Location',140),('scope','Berry / programme',160)],
      'overview':[('name','Entity',200),('type','Record type',125),('role','Roles / capability',180),('scope','Berry / market',180),('detail','Finding / open question',340),('date','Recorded period',150),('status','Mapping status',140)],
      'relationships':[('name','From',200),('role','Relationship',195),('target','To',200),('scope','Crop / territory',200),('status','Attribution',200),('date','Start / observed',140)],
      'exposure':[('company','Company',175),('role','PESTEL',140),('name','Dependency',190),('detail','Exposure / mechanism',260),('mitigation','Reported mitigation',230),('outcome','Outcome / limits',230),('location','Origin',150)],
      'imports':[('name','Batch / row',200),('type','Review type',120),('company','Entity',180),('role','Record kind',130),('status','Disposition / counts',240),('detail','Review rationale / SHA',320),('date','Reviewed / imported',170)],
      'saved':[('name','Comparison',250),('company','Saved by',140),('date','Saved date',185),('scope','Coverage',100),('detail','Analyst narrative',400),('status','State',150)]
    }.get(view,[])
    counts={kind:sum(r['kind']==kind for r in rows) for kind in sorted({r['kind'] for r in rows})}
    statuses=sorted({r.get('status','Unknown') for r in rows});roles=sorted({r.get('role','Unknown') for r in rows})
    q=str(params.get('people_q' if view=='people' else 'record_q') or '').strip().casefold()
    kind=params.get('record_kind','');status=params.get('record_status','');source=params.get('record_source','');role=params.get('record_role','')
    if source not in {'','inspected','partial','unverified','missing'}:raise ValueError('Choose a source inspection filter')
    def searchable(row):
        # Search visible values, original observation fields and source identity;
        # do not match incidental HTTP diagnostics or unrelated source-body text.
        return json.dumps({'values':{k:v for k,v in row.items() if isinstance(v,(str,int))},
            'aliases':entities.get(row.get('entity_id'),{}).get('aliases',[]),
            'observations':[r['fields'] for r in row['records']],
            'sources':[{k:s['fields'].get(k) for k in ['publisher','title_original','original_url']} for s in row['sources']]},ensure_ascii=False).casefold()
    filtered=[r for r in rows if (not kind or r['kind']==kind) and (not status or r.get('status')==status)
              and (not role or r.get('role')==role) and (not source or r['source_state']==source)
              and (not q or q in searchable(r))]
    key=params.get('record_sort') or ('date' if view in {'people','saved'} else columns[0][0] if columns else 'name')
    direction=params.get('record_direction') or ('desc' if key=='date' else 'asc')
    if key not in {c[0] for c in columns} or direction not in {'asc','desc'}:raise ValueError('Choose a valid record sort')
    def sortable(row):
        value=str(row.get(key,''))
        return iso(value[:10]) if key=='date' and (len(value)==10 or value[10:11]=='T') else '' if key=='date' else value.casefold()
    filtered.sort(key=lambda r:(sortable(r),r['id']),reverse=direction=='desc')
    filtered.sort(key=lambda r:not sortable(r) if key=='date' else str(r.get(key,'Unknown')).casefold() in {'unknown','unspecified',''})
    try:page=max(1,int(params.get('record_page') or 1))
    except ValueError as exc:raise ValueError('Choose a numbered record page') from exc
    pages=max(1,ceil(len(filtered)/page_size));page=min(page,pages)
    url=lambda updates:'/competitive-evaluation?'+urlencode({**params,**updates,'view':view})
    return {'columns':[{'key':k,'label':label,'width':width,'url':url({'record_sort':k,'record_direction':'desc' if key==k and direction=='asc' else 'asc','record_page':1})} for k,label,width in columns],
            'rows':filtered[(page-1)*page_size:page*page_size],'all_rows':filtered,'total':len(filtered),'scoped_total':len(rows),
            'counts':counts,'kind_labels':LABELS,'statuses':statuses,'roles':roles,'page':page,'pages':pages,'page_size':page_size,
            'previous':url({'record_page':max(1,page-1)}),'next':url({'record_page':page+1}), 'sort':key,'direction':direction}
