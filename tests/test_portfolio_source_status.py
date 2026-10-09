"""Coverage is scoped source work, not a claim of complete or approved portfolios."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
BLUE='berry-blueberry'
STRAW='berry-strawberry'


def setup_plan(tmp_path):
    folder=tmp_path/'imports/competitor-coverage-registry-2026-09-21'
    folder.mkdir(parents=True)
    entities=[dict(id='company-'+name.lower(),entity_type='company',name=name,berry_ids=[BLUE,STRAW])
              for name in ('Alpha','Beta','Gamma','Delta')]
    registry=[dict(input_registry_name=e['name'],canonical_entity_ids=[e['id']],
                   resolution_status='matched',website='https://example.test/'+e['id']) for e in entities]
    (folder/'reconciliation-matrix.json').write_text(json.dumps(dict(rows=registry)))
    def source(sid,company,berry,status,names):
        return dict(id=sid,title=sid,url='https://example.test/'+sid,checked_on='2026-10-08',
            source_type='company_catalog',company_ids=[company],berry_ids=[berry],
            capture_status=status,enumerated_scope='Explicit test scope',limitations='Source claims only',
            names=[dict(candidate_name=name,berry_id=berry) for name in names])
    sources=[source('alpha-straw','company-alpha',STRAW,'names_enumerated',['Dely']),
             source('alpha-blue','company-alpha',BLUE,'unreadable',[]),
             source('beta-brand','company-beta',STRAW,'partial',[]),
             source('gamma-blue','company-gamma',BLUE,'unreadable',[])]
    return entities,sources


def test_source_progress_partitions_named_partial_unavailable_and_unstarted(tmp_path):
    entities,sources=setup_plan(tmp_path)
    report=portfolio_coverage(data_dir=tmp_path,sources=sources,varieties=[],entities=entities,candidates=[])
    assert {s['name']:s['source_status'] for s in report['subjects']} == {
        'Alpha':'names_found','Beta':'partial','Gamma':'unreadable','Delta':'not_started'}
    summary=report['summary']
    assert [summary[k] for k in ('registry_entries_checked','registry_entries_partial_checks',
        'registry_entries_unavailable','registry_entries_not_started')] == [1,1,1,1]
    assert summary['registry_entries']==4
    assert next(s for s in report['subjects'] if s['name']=='Alpha')['has_source_gaps']


def test_unresolved_labels_and_people_are_not_unchecked_company_portfolios(tmp_path):
    entities,sources=setup_plan(tmp_path)
    path=tmp_path/'imports/competitor-coverage-registry-2026-09-21/reconciliation-matrix.json'
    payload=json.loads(path.read_text())
    held=[dict(input_registry_name='Generic genetics',canonical_entity_ids=[],entity_type='unresolved label',
               resolution_status='EXCLUDED_WITH_REASON',notes='Cannot identify a berry organization.'),
          dict(input_registry_name='Named person',canonical_entity_ids=[],entity_type='person',
               resolution_status='EXCLUDED_WITH_REASON',notes='An individual, not an organization.')]
    payload['rows']+=held
    path.write_text(json.dumps(payload))
    original=deepcopy(payload)
    report=portfolio_coverage(data_dir=tmp_path,sources=sources,varieties=[],entities=entities,candidates=[])
    subjects={s['name']:s for s in report['subjects']}
    assert report['summary']['registry_entries']==6
    assert report['summary']['registry_entries_not_started']==1
    assert report['summary']['registry_entries_identity_hold']==2
    assert subjects['Generic genetics']['identity_hold_label']=='Company not identified'
    assert subjects['Named person']['identity_hold_label']=='Person, not a company'
    assert all(not subjects[r['input_registry_name']]['checked'] and
               subjects[r['input_registry_name']]['source_status']=='identity_hold' and
               subjects[r['input_registry_name']]['identity_hold_reason']==r['notes'] and
               not subjects[r['input_registry_name']]['href'] for r in held)
    assert json.loads(path.read_text())==original
    assert not report['visible_candidates'] or all(c['candidate_name']=='Dely' for c in report['visible_candidates'])


def test_held_real_registry_names_show_reasons_without_company_creation(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client=TestClient(main.app)
    generic=client.get('/varieties/coverage',params={'q':'Genetics Uruguay'})
    person=client.get('/varieties/coverage',params={'q':'Mario Aguas-Alvarado'})
    assert generic.status_code==person.status_code==200
    assert 'Company not identified' in generic.text and 'Why this entry is held' in generic.text
    assert 'Person, not a company' in person.text and 'Why this entry is held' in person.text
    assert 'No source check in this scope' not in generic.text and 'No source check in this scope' not in person.text
    assert not list(tmp_path.rglob('*.json'))


def test_blueberry_source_plan_cannot_borrow_a_strawberry_check(tmp_path):
    entities,sources=setup_plan(tmp_path)
    original=deepcopy(sources)
    report=portfolio_coverage(data_dir=tmp_path,sources=sources,varieties=[],entities=entities,candidates=[],filters={'berry':BLUE})
    subjects={s['name']:s for s in report['subjects']}
    assert subjects['Alpha']['source_status']=='unreadable' and not subjects['Alpha']['checked']
    assert [s['id'] for s in subjects['Alpha']['sources']]==['alpha-blue']
    assert subjects['Beta']['source_status']=='not_started' and not subjects['Beta']['sources']
    assert report['summary']['registry_entries_checked']==0
    assert report['summary']['registry_entries_unavailable']==2
    assert report['summary']['registry_entries_not_started']==2
    assert report['summary']['names']==0 and sources==original
    strawberry=portfolio_coverage(data_dir=tmp_path,sources=sources,varieties=[],entities=entities,candidates=[],filters={'berry':STRAW})
    assert strawberry['summary']['registry_entries_checked']==1
    assert strawberry['summary']['registry_entries_partial_checks']==1


def test_mixed_page_without_selected_berry_names_cannot_count_as_named_coverage(tmp_path):
    entities,sources=setup_plan(tmp_path)
    mixed=sources[0]
    mixed['berry_ids']=[BLUE,STRAW]
    original=deepcopy(mixed)
    report=portfolio_coverage(data_dir=tmp_path,sources=[mixed],varieties=[],entities=entities,candidates=[],filters={'berry':BLUE,'company':'company-alpha'})
    assert len(report['subjects'])==1
    assert report['subjects'][0]['source_status']=='partial'
    assert not report['subjects'][0]['checked'] and report['subjects'][0]['named_occurrences']==0
    assert report['summary']['registry_entries_checked']==0
    assert report['summary']['registry_entries_partial_checks']==1
    assert mixed==original


def test_source_title_search_keeps_the_company_plan_in_the_same_scope(tmp_path):
    entities,sources=setup_plan(tmp_path)
    original=deepcopy(sources)
    report=portfolio_coverage(data_dir=tmp_path,sources=sources,varieties=[],entities=entities,candidates=[],filters={'q':'alpha-blue'})
    assert [s['id'] for s in report['sources']]==['alpha-blue']
    assert len(report['subjects'])==1 and report['subjects'][0]['name']=='Alpha'
    assert report['subjects'][0]['source_status']=='unreadable'
    assert report['summary']['registry_entries']==1 and report['summary']['registry_entries_checked']==0
    assert report['summary']['registry_entries_unavailable']==1 and sources==original


def test_original_collective_sections_refresh_without_duplicate_brands_or_identity_approval():
    sources=[s for s in load_portfolio_observations(DATA) if 'company-the-berry-collective' in s['company_ids']]
    assert len(sources)==len({s['url'] for s in sources})==3
    assert sum(bool(s['capture_reference'].get('refresh_of_existing_section')) for s in sources)==2
    assert all('University/Public' in s['review_warnings'][0] for s in sources)
    _,candidates=reconcile_portfolios(sources=sources,varieties=[],entities=[],candidates=[])
    assert not candidates
    product=next(s for s in sources if s['url'].endswith('/products/'))
    assert {'Eureka Blueberries','Marvelus Strawberries'} <= {e['label'] for e in product['accounting']['exclusions']}
    company=json.loads((DATA/'entities/companies/company-the-berry-collective.json').read_text())
    assert company['status']=='unverified' and not company['relationship_ids']


def test_live_progress_is_clear_and_private_without_review_state_writes(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client=TestClient(main.app)
    page=client.get('/varieties/coverage',params={'company':'company-smart-berries','berry':BLUE})
    assert page.status_code==200
    assert 'tracked entries with named varieties' in page.text
    assert 'Company source-check progress' in page.text and 'checked, list incomplete' in page.text
    assert 'Pages checked · varieties not named here' in page.text
    assert 'company lists still need names checked' not in page.text
    assert 'variety_coverage.css?v=6' in page.text
    assert 'href="#portfolio-source-plan"' in page.text
    assert 'id="portfolio-source-plan" tabindex="-1"' in page.text
    benning=client.get('/varieties/coverage',params={'company':'company-denning-blueberries','berry':BLUE})
    assert benning.status_code==200 and 'No names captured in this scope' in benning.text
    assert 'Page names enumerated' not in benning.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    public=client.get('/varieties/coverage',params={'company':'company-smart-berries','berry':BLUE})
    assert public.status_code==200 and 'portfolio-smartberries-original-' not in public.text
    assert 'Company source-check progress' not in public.text
    assert not list(tmp_path.rglob('*.json'))
