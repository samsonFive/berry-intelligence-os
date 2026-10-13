"""Stored numbered references remain unreviewed and obey existing identity gates."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import main
from app.services.variety_patent_references import load_registry_filing_observations, original_patent_references

VARIETY={'id':'v-known','name':'Commercial name','entity_type':'variety','aliases':['Original 123'], 'berry_ids':['berry-blueberry']}
ROW={'candidate_name':'Original 123','denomination':'Original 123','breeder_code':'unapproved-code',
     'berry_id':'berry-blueberry','source_id':'source-original-register','source_type':'plant_breeders_rights_record',
     'source_url':'https://example.test/register?q=Original%20123','source_label':'Public register',
     'application_number':'APP123','grant_number':'GRANT456','application_date':'2018-08-09',
     'granting_date':'2023-04-17','registration_status':'Approved','applicant':'Reported party'}

def snapshot(tmp_path, initial_rows, **extra):
    path=tmp_path/'imports/variety-universe-test/registry_rows.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'rows':initial_rows,'acquired_at':'2026-08-26T03:33:39+00:00',**extra}))
    return path

def project(sources, candidates=(), varieties=()):
    return original_patent_references(variety=VARIETY,varieties=[VARIETY,*varieties],entities=[],candidates=list(candidates),sources=sources)

def test_numbered_import_keeps_original_url_names_dates_and_unreviewed_boundary(tmp_path):
    path=snapshot(tmp_path,[ROW]); before=path.read_bytes()
    sources=load_registry_filing_observations(tmp_path); original=deepcopy(sources)
    refs=project(sources)
    assert len(refs)==1
    ref=refs[0]
    assert (ref['number'],ref['application_number'],ref['grant_number'])==('GRANT456','APP123','GRANT456')
    assert ref['url']==ROW['source_url'] and ref['checked_on']=='2026-08-26'
    assert ref['published_date']=='2023-04-17' and ref['date_label']=='Grant date'
    assert ref['application_date']=='2018-08-09' and ref['reference_kind']=='register'
    assert not ref['claim_url'] and not ref['document_url'] and not ref['figures_url']
    assert not {'legal_status','owner','trusted','current_rights'} & ref.keys()
    assert sources==original and path.read_bytes()==before
    assert list(tmp_path.rglob('*.json'))==[path]


def test_source_publication_date_is_not_mislabeled_as_a_grant_date(tmp_path):
    snapshot(tmp_path,[ROW]); sources=load_registry_filing_observations(tmp_path)
    sources[0]['published_date']='2026-07-01'
    ref=project(sources)[0]
    assert ref['published_date']=='2026-07-01' and ref['date_label']=='Published'
    assert sources[0]['names'][0]['grant_date']=='2023-04-17'

@pytest.mark.parametrize('identity,status',[('distinct','reviewed'),('rejected','rejected')])
def test_imported_reference_does_not_override_saved_human_identity(tmp_path,identity,status):
    snapshot(tmp_path,[ROW])
    candidate={'id':'saved','candidate_name':'Original 123','berry_id':'berry-blueberry',
               'human_gated':True,'identity_state':identity,'status':status,'review_notes':'Retain this decision'}
    original=deepcopy(candidate)
    assert project(load_registry_filing_observations(tmp_path),[candidate])==[]
    assert candidate==original

def test_wrong_crop_ambiguous_catalog_and_code_conflicts_do_not_attach(tmp_path):
    snapshot(tmp_path,[ROW])
    sources=load_registry_filing_observations(tmp_path)
    assert project(sources,varieties=[{**VARIETY,'id':'v-other'}])==[]
    sources[0]['names'][0]['berry_id']='berry-strawberry'
    assert project(sources)==[]
    sources=load_registry_filing_observations(tmp_path)
    conflict=deepcopy(sources[0]); conflict['id']='conflicting-register'
    conflict['names'][0]['denomination']='Different 456'
    assert project([*sources,conflict])==[]


def test_denomination_only_record_does_not_invent_an_extra_commercial_label(tmp_path):
    from app.services.variety_portfolio_coverage import reconcile_portfolios
    snapshot(tmp_path,[ROW]); sources=load_registry_filing_observations(tmp_path)
    for row in sources[0]['names']:
        row.update(source_company_ids=['company-reported'],source_company_context='Register names this party, unreviewed')
    commercial=deepcopy(sources[0]); commercial['id']='commercial-label'
    commercial['names'][0].update(candidate_name='Commercial name',trade_name='Commercial name')
    combined=[*sources,commercial]
    rows,_=reconcile_portfolios(sources=combined,varieties=[VARIETY],entities=[],candidates=[])
    assert all(n['catalog_id']==VARIETY['id'] and not n['identity_notes'] for s in rows for n in s['names'])
    assert len(project(combined))==1  # identical URL/number is one reference
    other=deepcopy(commercial); other['id']='different-commercial-label'
    other['names'][0].update(candidate_name='Another commercial label',trade_name='Another commercial label')
    assert project([*combined,other])==[]  # genuine extra label stays held

def test_only_numbered_rights_records_are_projected_with_actual_capture_date(tmp_path):
    rows=[{**ROW,'source_type':'grower_marketer_technical_program'},
          {**ROW,'application_number':'','grant_number':''},
          {**ROW,'source_url':'https://user:password@example.test/private'},
          {**ROW,'source_url':'javascript:alert(1)'},
          {**ROW,'knowledge':{'checked_on':'2026-10-07'}}]
    snapshot(tmp_path,rows)
    sources=load_registry_filing_observations(tmp_path)
    assert len(sources)==1 and sources[0]['checked_on']=='2026-10-07'


def test_profile_inventory_counts_the_same_unreviewed_register_reference(tmp_path):
    from app.services.variety_profile_coverage import profile_field_coverage
    snapshot(tmp_path,[ROW]); sources=load_registry_filing_observations(tmp_path)
    def inventory(candidates=()):
        return profile_field_coverage(varieties=[VARIETY],entities=[VARIETY],relationships=[],published_evidence=[],
            reference_sources=sources,candidates=candidates,reconciled_sources=[])['rows'][0]
    row=inventory()
    assert row['rights_refs']==0 and row['unreviewed_rights_refs']==1 and 'rights' not in row['missing']
    denied={'candidate_name':'Original 123','berry_id':'berry-blueberry','status':'rejected','identity_state':'rejected','human_gated':True}
    row=inventory([denied])
    assert row['unreviewed_rights_refs']==0 and 'rights' in row['missing']

@pytest.mark.parametrize('change',[{'acquired_at':None},{'acquired_at':'bad-date'},{'rows':['bad-row']}])
def test_bad_snapshot_is_visible_error_without_reset_or_writes(tmp_path,change):
    path=snapshot(tmp_path,[ROW],**change); before=path.read_bytes()
    with pytest.raises(ValueError,match='failed validation'):
        load_registry_filing_observations(tmp_path)
    assert path.read_bytes()==before

def test_actual_blue_maldiva_register_link_is_private_in_both_profile_views(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client=TestClient(main.app)
    for suffix in ('','?view=legacy'):
        response=client.get('/entities/variety/variety-blue-maldiva'+suffix)
        assert response.status_code==200
        assert 'Application 20182072' in response.text and 'Grant 63750' in response.text
        assert 'Register page' in response.text and 'CPVO public register' in response.text
        assert 'Unreviewed reference' in response.text and 'Grant date 4/17/2023' in response.text
        assert 'captured 2026-08-26' in response.text and 'Plablue 1542' in response.text
        assert 'application details rechecked October 13 UTC' in response.text
        assert 'Source captured 10/13/2026' in response.text
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    public=client.get('/entities/variety/variety-blue-maldiva').text
    assert '20182072' not in public and '63750' not in public and 'Register page' not in public
    assert not list(tmp_path.rglob('*.json'))


def test_bad_import_does_not_hide_available_original_filing_links(monkeypatch,tmp_path):
    from app.services import variety_patent_references
    def bad_import(data_dir):
        raise ValueError('Invalid imported snapshot')
    monkeypatch.setattr(variety_patent_references,'load_registry_filing_observations',bad_import)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    html=TestClient(main.app).get('/entities/variety/variety-colossus').text
    assert 'https://patents.google.com/patent/USPP33802P3/en#claims' in html
    assert 'Filing and register references could not be fully loaded' in html
    assert not list(tmp_path.rglob('*.json'))
