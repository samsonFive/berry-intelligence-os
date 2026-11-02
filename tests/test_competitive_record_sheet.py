from copy import deepcopy
from app.services.competitive_record_sheet import build


def record(key, kind, fields):
    return {'id':key,'kind':kind,'fields':{'entity_id':'company-one',**fields},'entity_id':'company-one',
            'resolution':'accepted_structure','sources':[],'batch_id':'B01','local_id':key,'source_refs':[],'version':1}


def model(records):
    return {'entities':{'company-one':{'name':'Example Berry Company'}},'records':records,'events_after':'2024-01-01','graph':[],'batches':[],'saved':[]}


def test_people_search_company_role_and_history_before_pagination_without_merging_names():
    rows=[record(f'p{i:03}','person',{'name_original':'Same Name','role_title':'Scientist',
          'function':'Breeding','location':'Huelva','last_observed_date':'2026-10-30'}) for i in range(120)]
    rows[-1]['fields']['role_title']='Specialist breeder'
    original=deepcopy(rows)
    sheet=build(model(rows),'people',{'people_q':'Example Berry Company','record_page':'3'})
    assert sheet['total']==120 and len(sheet['rows'])==20
    assert build(model(rows),'people',{'people_q':'Specialist breeder'})['total']==1
    assert build(model(rows),'people',{'record_role':'Scientist'})['total']==119
    assert len({r['id'] for r in sheet['all_rows']})==120 and rows==original


def test_jobs_reuse_requisition_grouping_retain_history_and_never_infer_fill():
    base={'title':'Farm manager','requisition_id':'REQ1','original_url':'https://example.org/jobs/1'}
    rows=[record('j1','job',{**base,'observed_status':'Open when observed','last_observed_date':'2026-01-01','skills_technologies':'Historical skill XYZ'}),
          record('j2','job',{**base,'observed_status':'Removed listing; fill unknown','last_observed_date':'2026-10-30'})]
    sheet=build(model(rows),'people',{'people_q':'Historical skill XYZ','record_kind':'job'})
    assert sheet['total']==1 and len(sheet['rows'][0]['records'])==2
    assert sheet['rows'][0]['status']=='Removed listing; fill unknown'
    assert sheet['rows'][0]['source_state']=='missing'


def test_event_window_unknown_dates_and_context_do_not_create_completed_hires():
    rows=[record('old','hiring_event',{'person_name':'Old','event_date':'2020-01-01','event_type':'Announced appointment'}),
          record('unknown','hiring_event',{'person_name':'Undated','event_date':'Unknown','event_type':'Change lead'}),
          record('context','hiring_event',{'person_name':'Context','event_date':'2020-01-01','event_type':'Current role, not a hiring event'}),
          record('new','hiring_event',{'person_name':'Recent','announcement_date':'2026-01-01','event_type':'Announced appointment'})]
    sheet=build(model(rows),'people',{})
    assert sheet['total']==3 and {r['name'] for r in sheet['rows']}=={'Undated','Context','Recent'}
    assert next(r for r in sheet['rows'] if r['name']=='Context')['kind']=='role_context'
    assert next(r for r in sheet['rows'] if r['name']=='Recent')['date']=='2026-01-01'


def test_mapping_context_keeps_original_and_effective_fields_for_inspection():
    row=record('map1','person',{'name_original':'A','role_title':'Director'})
    row.update(mapping_review={'rationale':'Retained brand association','reviewed_at':'2026-11-02'},
               original_row={'returned_fields':{'name_original':'A'}})
    sheet=build(model([row]),'imports',{'record_kind':'mapping'})
    assert sheet['total']==1 and sheet['rows'][0]['records'][0]==row


def test_event_name_uses_only_exact_same_batch_person_reference():
    person=record('B01-P001','person',{'name_original':'Exact Professional'})
    event=record('B01-H001','hiring_event',{'person_id_or_unknown':'B01-P001','event_type':'Appointment lead'})
    assert next(r for r in build(model([person,event]),'people',{})['rows'] if r['kind']=='hiring_event')['name']=='Exact Professional'
    event['fields']['person_id_or_unknown']='B02-P001'
    assert next(r for r in build(model([person,event]),'people',{})['rows'] if r['kind']=='hiring_event')['name']=='B02-P001'
