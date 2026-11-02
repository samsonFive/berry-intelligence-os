import json

from fastapi.testclient import TestClient
import pytest

from app import main
from app.services.variety_research_sheet import HEADERS, sheet


@pytest.fixture
def sheet_inbox(tmp_path):
    base=tmp_path/'variety_research/imports/test-sheet';(base/'profiles').mkdir(parents=True)
    manifest={'id':'test-sheet','kind':'private_variety_research_import','version':1,'checked_on':'2026-11-01',
        'counts':{'input_rows':4},'profiles':[{'entity_id':'variety-test','href':'/entities/variety/variety-test'}],
        'unresolved':[{'key':'unknown','summary':'Name missing','sources':[]}]}
    dossier={'key':'same','commercial_contacts':[{'name':'Example Nursery','role':'Supplier'}],
        'commercial_status':'Commercial route supported','summary':'Source claim, unreviewed.',
        'sources':[{'url':'https://example.test/variety'}],'baseline_status':'No match in local snapshot','aliases':['Trade Label']}
    hold={**dossier,'key':'hold','commercial_status':'Identity conflict — hold','issue':'Crop mismatch'}
    (base/'manifest.json').write_text(json.dumps(manifest))
    (base/'profiles/variety-test.json').write_text(json.dumps({'dossiers':[dossier,hold]}))
    def row(number,name,commercial=''):
        values=['Blueberry','APP-'+str(number),'GRANT','4/1/2026','','','CA','Status',name,'',commercial,'Vaccinium','Party A\nParty B','PBR']
        return {'row':number,'fields':dict(zip(HEADERS,values)),'review_notes':['Check photo date'] if number==2 else []}
    (base/'source_sheet_rows.json').write_text(json.dumps({'groups':{'same':[row(2,'Code'),row(4,'Code','Existing Supplier')],
        'unknown':[row(3,'')],'hold':[row(5,'Ambiguous')]}}))
    return tmp_path


def test_one_row_per_original_record_and_exact_column_order(sheet_inbox):
    model=sheet(sheet_inbox)
    assert model['headers']==HEADERS and len(HEADERS)==14
    assert [row['row'] for row in model['rows']]==[2,3,4,5]
    assert model['rows'][0]['original'][8]==model['rows'][2]['original'][8]=='Code'
    assert model['rows'][0]['original'][3]=='4/1/2026'
    assert model['rows'][0]['original'][12]=='Party A\nParty B'


def test_proposals_never_replace_original_values_or_fill_identity_holds(sheet_inbox):
    model=sheet(sheet_inbox)
    first,unknown,existing,hold=model['rows']
    assert first['original'][10]=='' and first['proposal']=='Example Nursery' and first['can_fill']
    assert existing['original'][10]=='Existing Supplier' and not existing['can_fill']
    assert not unknown['can_fill'] and unknown['status']=='Identity unresolved'
    assert hold['proposal']=='Example Nursery' and not hold['can_fill']
    assert model['counts']=={'rows':4,'missing_roles':3,'proposals_for_blanks':1,'unresolved_blanks':2}


def test_projection_keeps_research_provenance_and_is_read_only(sheet_inbox):
    before={str(path):path.read_bytes() for path in sheet_inbox.rglob('*.json')}
    model=sheet(sheet_inbox)
    assert model['rows'][0]['sources']==['https://example.test/variety']
    assert model['rows'][0]['review_notes']==['Check photo date']
    assert model['rows'][0]['role']=='Example Nursery — Supplier'
    assert before=={str(path):path.read_bytes() for path in sheet_inbox.rglob('*.json')}


def test_duplicate_row_identity_stops_projection(sheet_inbox):
    path=sheet_inbox/'variety_research/imports/test-sheet/source_sheet_rows.json'
    value=json.loads(path.read_text());value['groups']['unknown'][0]['row']=2;path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='unique'):
        sheet(sheet_inbox)


def test_individual_row_conflict_does_not_fill_an_otherwise_supported_variety(sheet_inbox):
    path=sheet_inbox/'variety_research/imports/test-sheet/profiles/variety-test.json'
    value=json.loads(path.read_text());value['dossiers'][0]['row_holds']={'2':'Application identifies a different cultivar'}
    path.write_text(json.dumps(value));first=sheet(sheet_inbox)['rows'][0]
    assert first['proposal']=='Example Nursery' and not first['can_fill']
    assert 'Hold' in first['status'] and 'different cultivar' in first['issue']


def test_empty_and_missing_source_sheet_are_explicit(sheet_inbox):
    assert sheet(sheet_inbox,'../unrelated')['rows']==[]
    (sheet_inbox/'variety_research/imports/test-sheet/source_sheet_rows.json').unlink()
    assert 'not available' in sheet(sheet_inbox)['error']


def test_sheet_route_is_private_and_preserves_row_data(monkeypatch,sheet_inbox):
    monkeypatch.setattr(main,'INBOX_DIR',sheet_inbox);monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client=TestClient(main.app);response=client.get('/varieties/research/sheet')
    assert response.status_code==200 and 'research-sheet-data' in response.text
    assert 'Commercial Entity' in response.text and 'Paste Commercial Entity values into column K' in response.text
    assert response.headers['cache-control']=='private, no-store' and response.headers['x-robots-tag']=='noindex'
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/research/sheet').status_code==404
