"""Existing breeding programs can open source varieties without a company dossier."""
from fastapi.testclient import TestClient
from app import main


def test_program_varieties_without_company_backbone_remain_read_only(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    page = TestClient(main.app).get("/entities/breeding_program/breeding_program-university-of-georgia-blueberry?tab=varieties")
    assert page.status_code == 200
    assert 'aria-current="page">Varieties' in page.text
    assert "Varieties named in sources" in page.text and "Blue Suede" in page.text
    assert "Recorded variety links · 0" in page.text
    assert not list(tmp_path.iterdir())


def test_existing_program_overview_and_varieties_show_the_same_active_link(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client=TestClient(main.app)
    url='/entities/breeding_program/breeding_program-njaes-rutgers-strawberry'
    overview=client.get(url)
    assert overview.status_code==200 and 'Program overview' in overview.text
    assert '<b>1</b><span>linked varieties</span>' in overview.text
    page=client.get(url+'?tab=varieties')
    assert page.status_code==200 and 'Recorded variety links · 1' in page.text
    assert '/entities/variety/variety-rutgers-dlight' in page.text and 'Breeder' in page.text
    assert 'Detailed portfolio →' not in page.text and 'Variety directory →' in page.text
    assert not list(tmp_path.iterdir())


def test_program_and_brand_rows_exclude_proposed_inactive_and_source_only_roles():
    from copy import deepcopy
    from app.services.variety_navigation import program_variety_rows
    entities={e['id']:e for e in [
        dict(id='program-a',name='Program',entity_type='breeding_program'),
        dict(id='brand-a',name='Brand',entity_type='brand'),
        dict(id='company-a',name='Company',entity_type='company'),
        dict(id='variety-a',name='Alpha',entity_type='variety',berry_ids=['berry-strawberry']),
        dict(id='variety-b',name='Beta',entity_type='variety',attributes={'breeder':'Program'}),
    ]}
    edges=[dict(subject_id='program-a',object_id='variety-a',predicate='develops',status='active'),
           dict(subject_id='program-a',object_id='variety-a',predicate='owns',status='proposed'),
           dict(subject_id='program-a',object_id='variety-b',predicate='develops',status='inactive'),
           dict(subject_id='brand-a',object_id='variety-a',predicate='markets',status='active')]
    before=deepcopy((entities,edges))
    rows=program_variety_rows('program-a',entities,edges)
    assert len(rows)==1 and rows[0]['id']=='variety-a' and rows[0]['roles']==['Breeder']
    assert rows[0]['berries']==['Strawberry'] and 'geographies' not in rows[0]
    assert program_variety_rows('brand-a',entities,edges)[0]['roles']==['Marketer']
    assert program_variety_rows('company-a',entities,edges)==[]
    assert (entities,edges)==before
