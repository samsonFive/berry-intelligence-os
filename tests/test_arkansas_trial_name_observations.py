"""An image-table trial list supplies identity leads, not breeding or trait facts."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'


def source():
    return next(row for row in load_portfolio_observations(DATA)
                if row['id']=='portfolio-arkansas-2024-blueberry-trial')


def test_image_table_scope_and_historical_context_do_not_replace_breeding_listing():
    row=source()
    assert len(row['names']) == row['accounting']['reported_items'] == row['accounting']['observed_items'] == 20
    assert {name['candidate_name'] for name in row['names']} == {
        'Bluecrop','Blueray','Blue Ribbon','Duke','Top Shelf','Legacy','New Hanover',"O'Neal",'Summit',
        'Alapaha','Brightwell','Climax','Krewer','Ochlockonee','Premier','Tiftblue','Titan','Vernon','Overtime','Powderblue'}
    assert row['source_type']=='trial_report' and row['published_date']=='2024-11-22'
    assert row['review_state']=='unreviewed' and row['capture_reference']['url'].endswith('table1.png')
    assert all('not an inferred breeder' in name['portfolio_context'] for name in row['names'])
    assert all(not name.get('photos') and not name.get('registration') for name in row['names'])
    assert all(name['product_url']==row['capture_reference']['url'] for name in row['names'])
    licensing=next(row for row in load_portfolio_observations(DATA) if row['id']=='portfolio-arkansas-current-blueberry')
    assert licensing['capture_status']=='names_enumerated'
    assert [name['candidate_name'] for name in licensing['names']]==['Norman']
    assert licensing['url']=='https://aaes.uada.edu/fruit-breeding/blueberries/'


def test_unreviewed_trial_leads_preserve_human_rejection_and_never_create_roles():
    row=source()
    before=deepcopy(row)
    _rows,candidates=reconcile_portfolios(sources=[row],varieties=[],entities=[],candidates=[])
    assert len(candidates)==20
    assert all(not item['auto_confirmed'] and item['proposed_relationships']==[] for item in candidates)
    rejected=deepcopy(next(item for item in candidates if item['candidate_name']=='Overtime'))
    rejected.update(identity_state='REJECTED',status='rejected',human_gated=True,reviewer='Fixture reviewer',
                    review_notes='Keep my rejection')
    _rows,rediscovered=reconcile_portfolios(sources=[row],varieties=[],entities=[],candidates=[rejected])
    retained=next(item for item in rediscovered if item['candidate_name']=='Overtime')
    assert retained['human_gated'] and retained['review_notes']=='Keep my rejection' and retained['status']=='rejected'
    assert row==before


def test_named_lead_has_original_report_context_and_get_does_not_persist(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client=TestClient(main.app)
    page=client.get('/varieties/candidates?q=Overtime&berry=berry-blueberry')
    assert page.status_code==200 and 'University of Arkansas — 2024 blueberry trial' in page.text
    assert 'not an inferred breeder' in page.text and '2024-11-22' in page.text
    assert source()['url'] in page.text
    assert not list(tmp_path.rglob('*'))
