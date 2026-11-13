from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import main
from app.services import variety_research as research
from scripts.import_patent_variety_research import install, digest_tree


def group(name, crop="Blueberry", **changes):
    return {"key":name or "unknown", "name":name, "resolved_name":name,"berry":crop,
        "rows":[2],"applications":["TEST-2026"],"aliases":[],"summary":"Publisher reports large fruit; unverified claim.",
        "availability":"Confirm local nursery access", "commercial_status":"Commercial route unverified", "role":"",
        "patent_assignee_lead":"Rights owner lead", "baseline_status":"No match in local snapshot",
        "new_information_assessment":"Candidate profile", "issue":"", "sources":[{"id":"s1","title":"Source",
            "url":"https://example.test/variety","kind":"Breeder source","access":"Captured","prior_url":"New URL"}],
        "variety_image_links":[],"captures":[],"commercial_entities":"","existing_entities":[],"prior_mentions":[],"prior_evidence":[],**changes}


@pytest.fixture
def imported(tmp_path):
    data=tmp_path/'data';inbox=tmp_path/'inbox';(data/'entities'/'varieties').mkdir(parents=True)
    entity={"id":"variety-known","record_type":"entity","entity_type":"variety","name":"Known","berry_ids":["berry-blueberry"],"status":"active"}
    (data/'entities'/'varieties'/'known.json').write_text(json.dumps(entity))
    packet=tmp_path/'research-data.json'
    rows=[group('Known',existing_entities=[{'id':'variety-known','file':'data/entities/varieties/known.json'}]),
          group('ABC-123',commercial_entities='Example Nursery',role='Nursery supplier'),
          group('',resolved_name='ABC 123',key='resolved-blank',rows=[3]),
          group('ABC-123','Strawberry',rows=[4]),group('',rows=[5])]
    packet.write_text(json.dumps({'metadata':{'checked_on':'2026-11-01','baseline_commit':'baseline','method':'Exact crop-aware names'},'varieties':rows}))
    before=digest_tree(data);receipt=install(packet,data_dir=data,inbox_dir=inbox)
    return data,inbox,packet,receipt,before


def test_installs_actual_private_pages_without_trusted_mutation(imported):
    data,inbox,packet,receipt,before=imported
    assert digest_tree(data)==before
    assert receipt['new_unverified_profiles']==2 and receipt['existing_profiles_updated']==1
    assert receipt['unresolved_applications']==1
    assert len(research.profile(inbox,'variety-research-blueberry-abc123')['dossiers'])==2
    assert research.private_entity(inbox,'variety','variety-research-blueberry-abc123')['status']=='unverified'
    assert research.private_entity(inbox,'variety','variety-known') is None
    assert len(research.index(inbox)['rows'])==3


def test_replay_preserves_private_analyst_edits(imported):
    data,inbox,packet,receipt,before=imported
    path=inbox/research.ROOT/'imports'/receipt['batch_id']/'profiles'/'variety-known.json'
    saved=json.loads(path.read_text());saved['analyst_note']='Keep this decision';path.write_text(json.dumps(saved))
    original=path.read_bytes()
    assert install(packet,data_dir=data,inbox_dir=inbox)['replayed']
    assert path.read_bytes()==original


def test_unsafe_source_links_do_not_install_a_visible_batch(imported):
    data,inbox,packet,receipt,before=imported
    value=json.loads(packet.read_text());value['varieties'][0]['sources'][0]['url']='javascript:alert(1)'
    packet.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='HTTP'):
        install(packet,data_dir=data,inbox_dir=inbox)
    assert len(research.imports(inbox))==1 and digest_tree(data)==before


def test_later_source_snapshot_updates_the_page_without_duplicate_dossiers(imported):
    data,inbox,packet,receipt,before=imported
    value=json.loads(packet.read_text());value['varieties'][0]['summary']='Updated source claim, still unreviewed.'
    packet.write_text(json.dumps(value));second=install(packet,data_dir=data,inbox_dir=inbox)
    assert second['batch_id']!=receipt['batch_id']
    dossiers=research.profile(inbox,'variety-known')['dossiers']
    assert len(dossiers)==1 and dossiers[0]['summary']=='Updated source claim, still unreviewed.'
    assert len(research.imports(inbox))==2 and len(research.index(inbox)['rows'])==3
    assert digest_tree(data)==before


def test_closeout_retains_individual_roles_territories_and_non_supplier_leads(imported):
    data,inbox,packet,_,before=imported
    value=json.loads(packet.read_text())
    value['varieties'][1].update(commercial_contacts=[
        {'name':'Example Nursery','role':'Propagator','territory':'Spain','source_urls':['https://example.test/nursery']},
        {'name':'Example Nursery','role':'Fruit marketer','territory':'UK','source_urls':['https://example.test/marketing']}],
        commercial_leads=[{'name':'Rights Only','role':'Patent owner','evidence_status':'Supply unverified','source_urls':['https://example.test/rights']}],
        closeout={'conclusion':'Route supported','checks':['Official catalogue'],'remaining_gap':'Stock unconfirmed','next_contact':''},
        partnerships=['Nursery and marketer roles are separately attributed.'])
    packet.write_text(json.dumps(value));install(packet,data_dir=data,inbox_dir=inbox)
    dossier=research.profile(inbox,'variety-research-blueberry-abc123')['dossiers'][0]
    assert [(p['role'],p['territory']) for p in dossier['commercial_contacts']]==[('Propagator','Spain'),('Fruit marketer','UK')]
    assert dossier['commercial_leads'][0]['name']=='Rights Only'
    html=main.templates.env.get_template('_variety_research.html').render(variety_research={'dossiers':[dossier]},authoring_mode=True,static_build=False)
    assert 'Role source 1' in html and 'Spain' in html and 'Stock unconfirmed' in html
    assert digest_tree(data)==before


def test_resolved_identity_supersedes_old_application_lead(imported):
    data,inbox,packet,_,_=imported
    value=json.loads(packet.read_text());value['varieties'][-1]['resolved_name']='Newly Identified'
    packet.write_text(json.dumps(value));install(packet,data_dir=data,inbox_dir=inbox)
    assert not research.index(inbox)['unresolved']


def test_source_findings_and_gap_capture_remain_private_unreviewed_research(imported):
    data,inbox,packet,_,before=imported
    value=json.loads(packet.read_text())
    value['varieties'][0].update(
        report_url='https://example.test/reports/library/known',
        findings=[{'topic':'Fruit size','value':'Trial reported 8 g < 10 g comparator.',
                   'source_urls':['https://example.test/trial']}],
        gaps=[{'topic':'Shelf life','missing_information':'Storage protocol missing.',
               'capture_path':'Attach protocol to the existing source record.',
               'review_needed':'Review before publishing a trait Fact.'}])
    packet.write_text(json.dumps(value));install(packet,data_dir=data,inbox_dir=inbox)
    profile=research.profile(inbox,'variety-known')
    dossier=profile['dossiers'][0]
    assert dossier['findings'][0]['topic']=='Fruit size' and dossier['gaps'][0]['topic']=='Shelf life'
    assert dossier['review_state']=='unreviewed' and digest_tree(data)==before
    template=main.templates.env.get_template('_variety_research.html')
    html=template.render(variety_research=profile,authoring_mode=True,static_build=False)
    assert '8 g &lt; 10 g' in html and 'https://example.test/trial' in html
    assert 'Storage protocol missing.' in html and 'download its PDF' in html
    assert not template.render(variety_research=profile,authoring_mode=True,static_build=True).strip()
    assert not template.render(variety_research=profile,authoring_mode=False,static_build=False).strip()


@pytest.mark.parametrize('field', ['findings','report_url'])
def test_research_findings_reject_unsafe_links_before_registration(imported,field):
    _,inbox,packet,_,_=imported
    value=json.loads(packet.read_text())
    value['varieties'][0][field]=([{'topic':'Trait','value':'Claim', 'source_urls':['javascript:alert(1)']}]
                                 if field=='findings' else 'javascript:alert(1)')
    packet.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='HTTP'):
        install(packet,data_dir=imported[0],inbox_dir=inbox)
    assert len(research.imports(inbox))==1


def test_closeout_party_sources_reject_unsafe_urls(imported):
    data,inbox,packet,_,_=imported
    value=json.loads(packet.read_text());value['varieties'][1]['commercial_contacts']=[{'name':'Bad','source_urls':['javascript:alert(1)']}]
    packet.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='HTTP'):
        install(packet,data_dir=data,inbox_dir=inbox)


def test_corrected_private_identity_hides_stale_candidate_without_rewriting_history(imported):
    data,inbox,packet,receipt,before=imported
    value=json.loads(packet.read_text());old='variety-research-strawberry-abc123'
    value['metadata']['superseded_entity_ids']=[old]
    value['varieties'][3]['resolved_name']='Corrected Code'
    archive=inbox/research.ROOT/'imports'/receipt['batch_id']/'profiles'/(old+'.json')
    original=archive.read_bytes();packet.write_text(json.dumps(value));install(packet,data_dir=data,inbox_dir=inbox)
    assert archive.read_bytes()==original and digest_tree(data)==before
    assert research.private_entity(inbox,'variety',old) is None and research.profile(inbox,old) is None
    assert old not in {r['entity_id'] for r in research.index(inbox)['rows']}
    assert research.profile(inbox,'variety-research-strawberry-correctedcode')
    value['metadata']['superseded_entity_ids']=['variety-known'];packet.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='private research'):
        install(packet,data_dir=data,inbox_dir=inbox)


def test_install_reconciles_against_newer_runtime_catalog(imported):
    data,inbox,packet,receipt,before=imported
    entity={'id':'variety-runtime-abc','record_type':'entity','entity_type':'variety','name':'New runtime name',
        'aliases':['ABC-123'],'berry_ids':['berry-blueberry'],'status':'active'}
    (data/'entities/varieties/new-runtime.json').write_text(json.dumps(entity))
    fresh=inbox.parent/'fresh-inbox';result=install(packet,data_dir=data,inbox_dir=fresh)
    assert result['existing_profiles_updated']==2 and result['new_unverified_profiles']==1
    assert len(research.profile(fresh,'variety-runtime-abc')['dossiers'])==2
    assert research.private_entity(fresh,'variety','variety-research-blueberry-abc123') is None


def test_explicit_original_sheet_is_installed_before_manifest(imported):
    data,inbox,packet,receipt,before=imported
    sheet=packet.parent/'sheet.json';sheet.write_text(json.dumps({'headers':['Field'+str(n) for n in range(14)],
        'rows':[['value']*14 for _ in range(4)],'review':[[2,'Field0','value','photo','Check original']]}))
    fresh=inbox.parent/'sheet-inbox';install(packet,data_dir=data,inbox_dir=fresh,source_sheet=sheet)
    record=research.profile(fresh,'variety-known')['dossiers'][0]['source_sheet_records'][0]
    assert record['fields']['Field0']=='value' and record['review_notes']==['Field0: Check original']


def test_search_and_crop_separation(imported):
    _,inbox,_,_,_=imported
    assert len(research.index(inbox,q='Example Nursery')['rows'])==1
    assert len(research.index(inbox,berry='Strawberry')['rows'])==1
    assert len(research.index(inbox,state='existing')['rows'])==1
    assert len(research.index(inbox)['unresolved'])==1


def test_original_registry_transcription_remains_labelled_private_context(imported):
    _,inbox,_,receipt,_=imported
    path=inbox/research.ROOT/'imports'/receipt['batch_id']/'source_sheet_rows.json'
    path.write_text(json.dumps({'groups':{'Known':[{'row':2,'fields':{'Grant Number':'UNVERIFIED-GRANT'},'review_notes':['Unreadable date']}]}}))
    value=research.profile(inbox,'variety-known')
    assert value['dossiers'][0]['source_sheet_records'][0]['fields']['Grant Number']=='UNVERIFIED-GRANT'
    template=main.templates.env.get_template('_variety_research.html')
    html=template.render(variety_research=value,authoring_mode=True,static_build=False)
    assert 'UNVERIFIED-GRANT' in html and 'Photo transcription' in html and 'Unreadable date' in html
    assert not template.render(variety_research=value,authoring_mode=True,static_build=True).strip()


def test_capture_access_is_allowlisted_and_cannot_escape(imported):
    _,inbox,_,receipt,_=imported
    root=inbox/research.ROOT/'imports'/receipt['batch_id']/'captures';root.mkdir(exist_ok=True)
    (root/'unlisted.png').write_bytes(b'not a source')
    assert research.capture_file(inbox,receipt['batch_id'],'unlisted.png') is None
    assert research.capture_file(inbox,'../other','a.png') is None
    assert research.capture_file(inbox,receipt['batch_id'],'../manifest.json') is None


def test_private_content_never_renders_in_public_template(imported):
    _,inbox,_,_,_=imported
    profile=research.profile(inbox,'variety-research-blueberry-abc123')
    template=main.templates.env.get_template('_variety_research.html')
    assert not template.render(variety_research=profile,authoring_mode=True,static_build=True).strip()
    assert not template.render(variety_research=profile,authoring_mode=False,static_build=False).strip()
    html=template.render(variety_research=profile,authoring_mode=True,static_build=False)
    assert 'UNREVIEWED RESEARCH' in html and 'Example Nursery' in html
    assert 'Rights lead only' in html and 'Publisher reports large fruit' in html


def test_research_routes_fail_closed_without_authoring(monkeypatch,imported):
    _,inbox,_,_,_=imported
    monkeypatch.setattr(main,'INBOX_DIR',inbox);monkeypatch.setattr(main,'AUTHORING_MODE',False)
    client=TestClient(main.app)
    assert client.get('/varieties/research').status_code==404
    assert client.get('/variety-research-captures/batch/file.png').status_code==404
    assert client.get('/entities/variety/variety-research-blueberry-abc123').status_code==404


def test_index_route_is_read_only_and_noindex(monkeypatch,imported):
    _,inbox,_,_,_=imported
    monkeypatch.setattr(main,'INBOX_DIR',inbox);monkeypatch.setattr(main,'AUTHORING_MODE',True)
    before=digest_tree(inbox)
    response=TestClient(main.app).get('/varieties/research?q=Example+Nursery')
    assert response.status_code==200 and 'variety-research-blueberry-abc123' in response.text
    assert response.headers['cache-control']=='private, no-store'
    assert response.headers['x-robots-tag']=='noindex'
    assert digest_tree(inbox)==before


def test_named_crop_conflict_and_missing_identity_do_not_create_roles(imported):
    _,inbox,_,_,_=imported
    row=research.private_entity(inbox,'variety','variety-research-strawberry-abc123')
    assert row['relationship_ids']==[] and row['fact_ids']==[] and row['evidence_ids']==[]
    unresolved=research.index(inbox)['unresolved'][0]
    assert unresolved['applications']==['TEST-2026'] and unresolved['key']=='unknown'
