"""Captured article names reach company review without approving a portfolio."""
from copy import deepcopy
import json

import pytest

from app import main
from app.services import feed_first_reader as reader
from app.services.feed_first_live import save_bundle
from app.services.variety_universe.candidates import persist_variety_candidates


COMPANY = {'id':'company-example','name':'Example Grower','entity_type':'company'}
OTHER = {'id':'company-other','name':'Other Grower','entity_type':'company'}


def prepare(monkeypatch, tmp_path, *, reviewed=True, entities=()):
    record = {'id':'ev-company-article','status':'published' if reviewed else 'unreviewed',
              'source_type':'company_website','source_name':'Example publisher',
              'title':'A genetics collaboration','source_url':'https://example.test/announcement',
              'summary':'A company announces a collaboration.',
              'published_date':'2026-07-30','berry_ids':['berry-blueberry'],
              'entity_ids':[COMPANY['id']],'private_note':'Never copy private notes into source context'}
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'DATA_DIR',tmp_path/'empty-data')
    monkeypatch.setattr(main,'all_entities',lambda:[COMPANY,OTHER,*entities])
    monkeypatch.setattr(main,'published_evidence',lambda:[record] if reviewed else [])
    if not reviewed:
        save_bundle(tmp_path,{'today':'2026-11-03','records':[record]})
    monkeypatch.setattr(main,'all_facts',lambda:[])
    monkeypatch.setattr(main,'list_drafts',lambda:[])
    monkeypatch.setattr(reader,'capture_item',lambda *a,**k:pytest.fail('A GET must not capture an article'))
    return record


def capture(inbox, record, text):
    reader.save_capture(inbox,record['id'],{'item_id':record['id'],'requested_url':record['source_url'],
        'ok':True,'availability':'partial','passages':[text]})


def contents(inbox):
    return {str(p.relative_to(inbox)):p.read_bytes()for p in inbox.rglob('*')if p.is_file()}


@pytest.mark.parametrize('reviewed',[True,False])
def test_company_receives_captured_name_source_status_and_reader_link_without_writes(tmp_path, monkeypatch, reviewed):
    record=prepare(monkeypatch,tmp_path,reviewed=reviewed)
    capture(tmp_path,record,"Example Grower's Golden Dawn raspberry variety received an award.")
    original=deepcopy(record);before=contents(tmp_path)
    result=main.company_source_varieties(COMPANY['id'],None)
    assert result['rows']==[] and result['source_count']==0 and result['article_count']==1
    row=result['article_rows'][0]
    assert row['name']=='Golden Dawn' and row['berry_id']=='berry-raspberry'
    assert row['label']=='Name needs review' and 'Named in captured news'==row['basis_label']
    assert row['sources'][0]['href']==record['source_url']
    assert row['sources'][0]['reader_href']=='/intelligence/ev-company-article?personal=1'
    assert row['sources'][0]['context']==('Source reviewed' if reviewed else 'Unreviewed source')
    assert row['sources'][0]['date']=='2026-07-30'
    assert '/varieties/candidates?' in row['href'] and '#vcand-' in row['href']
    assert main.company_source_varieties(OTHER['id'],None)['article_rows']==[]
    assert result['letters']==['G'] and result['berries']==[('berry-raspberry','Raspberry')]
    html=main.templates.env.get_template('_company_variety_discoveries.html').render(
        authoring_mode=True,static_build=False,company_source_varieties=result)
    assert 'Golden Dawn' in html and 'captured article' in html and 'Read captured article' in html
    assert 'data-open-reader data-item-id="ev-company-article"' in html
    assert 'Being named here does not confirm' in html and 'does not establish breeding' in html
    assert 'data-source-letter="G"' in html and 'data-source-search' in html
    assert 'Never copy private notes' not in html
    assert record==original and contents(tmp_path)==before


def test_human_rejection_is_not_reopened_by_company_news_handoff(tmp_path,monkeypatch):
    record=prepare(monkeypatch,tmp_path)
    capture(tmp_path,record,"Example Grower's Golden Dawn raspberry variety received an award.")
    _,rows,_=main.variety_candidate_universe()
    candidate=deepcopy(next(r for r in rows if r['candidate_name']=='Golden Dawn'))
    candidate.update(status='rejected',identity_state='rejected',human_gated=True,
                     review_notes='Keep my decision',reviewer='Human')
    persist_variety_candidates([candidate],inbox_dir=tmp_path)
    before=contents(tmp_path)
    result=main.company_source_varieties(COMPANY['id'],None)
    assert result['article_rows']==[] and result['article_count']==0
    assert contents(tmp_path)==before
    stored=json.loads(next((tmp_path/'variety_candidates').glob('*.json')).read_text(encoding='utf-8'))
    assert stored['review_notes']=='Keep my decision' and stored['reviewer']=='Human'


def test_catalog_identity_never_implies_company_role_and_linked_identity_stays_above(tmp_path,monkeypatch):
    variety={'id':'variety-golden-dawn','name':'Golden Dawn','entity_type':'variety',
             'berry_ids':['berry-raspberry'],'aliases':[]}
    record=prepare(monkeypatch,tmp_path,entities=[variety])
    capture(tmp_path,record,"Example Grower's Golden Dawn raspberry variety received an award.")
    before=contents(tmp_path)
    row=main.company_source_varieties(COMPANY['id'],None)['article_rows'][0]
    assert row['href']=='/entities/variety/variety-golden-dawn'
    assert row['label']=='Check company connection'
    assert main.company_source_varieties(COMPANY['id'],{'variety_rows':[{'id':variety['id']}]})['article_rows']==[]
    assert contents(tmp_path)==before


def test_summary_only_company_name_is_not_misrepresented_as_captured_news(tmp_path,monkeypatch):
    record=prepare(monkeypatch,tmp_path)
    record['summary']='Raspberry varieties include Golden Dawn.'
    before=contents(tmp_path)
    result=main.company_source_varieties(COMPANY['id'],None)
    assert result['article_rows']==[] and result['article_count']==0
    assert contents(tmp_path)==before


def test_company_handoff_and_static_output_do_not_read_or_render_private_article_context(tmp_path,monkeypatch):
    record=prepare(monkeypatch,tmp_path)
    capture(tmp_path,record,"Example Grower's Golden Dawn raspberry variety received an award.")
    model=main.company_source_varieties(COMPANY['id'],None)
    for authoring,static in [(False,False),(True,True)]:
        html=main.templates.env.get_template('_company_variety_discoveries.html').render(
            authoring_mode=authoring,static_build=static,company_source_varieties=model)
        assert 'Golden Dawn' not in html and 'data-company-source-varieties' not in html
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:pytest.fail('Public view must not scan private articles'))
    assert main.company_source_varieties(COMPANY['id'],None) is None


def test_source_identity_mismatch_cannot_supply_a_company_article_link(tmp_path,monkeypatch):
    record=prepare(monkeypatch,tmp_path)
    capture(tmp_path,record,"Example Grower's Golden Dawn raspberry variety received an award.")
    varieties,candidates,report=main.variety_candidate_universe()
    report['article_source_context'][record['id']]['source_url']='https://example.test/different'
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:(varieties,candidates,report))
    assert main.company_source_varieties(COMPANY['id'],None)['article_rows']==[]


@pytest.mark.parametrize('state,match,label,prefix',[
    ('distinct','','Catalog entry pending','/varieties/candidates?'),
    ('confirmed_same','variety-existing','Check company connection','/entities/variety/variety-existing'),
    ('confirmed_same','variety-missing','Name needs review','/varieties/candidates?'),
])
def test_saved_identity_decision_and_current_catalog_control_the_handoff(tmp_path,monkeypatch,state,match,label,prefix):
    variety={'id':'variety-existing','name':'A Different Catalog Name','entity_type':'variety',
             'berry_ids':['berry-raspberry'],'aliases':[]}
    record=prepare(monkeypatch,tmp_path,entities=[variety])
    capture(tmp_path,record,"Example Grower's Golden Dawn raspberry variety received an award.")
    _,candidates,_=main.variety_candidate_universe()
    saved=deepcopy(next(r for r in candidates if r['candidate_name']=='Golden Dawn'))
    saved.update(status='confirmed',identity_state=state,human_gated=True,
                 candidate_canonical_match=match,review_notes='My current decision')
    persist_variety_candidates([saved],inbox_dir=tmp_path)
    before=contents(tmp_path)
    row=main.company_source_varieties(COMPANY['id'],None)['article_rows'][0]
    assert row['label']==label and row['href'].startswith(prefix)
    assert 'variety-missing' not in row['href']
    assert contents(tmp_path)==before


def test_each_article_keeps_its_own_company_and_publication_review_context(tmp_path,monkeypatch):
    record=prepare(monkeypatch,tmp_path)
    other={**record,'id':'ev-second-article','source_url':'https://example.test/second',
           'status':'unreviewed','entity_ids':[COMPANY['id'],OTHER['id']]}
    save_bundle(tmp_path,{'today':'2026-11-03','records':[other]})
    for item in [record,other]:
        capture(tmp_path,item,"Example Grower's Golden Dawn raspberry variety received an award.")
    before=contents(tmp_path)
    model=main.company_source_varieties(COMPANY['id'],None)
    assert len(model['article_rows'])==1 and model['article_count']==2
    sources=model['article_rows'][0]['sources']
    assert {(s['id'],s['context'],s['href'])for s in sources}=={
        (record['id'],'Source reviewed',record['source_url']),
        (other['id'],'Unreviewed source',other['source_url'])}
    other_model=main.company_source_varieties(OTHER['id'],None)
    assert other_model['article_count']==1
    assert [s['id']for s in other_model['article_rows'][0]['sources']]==[other['id']]
    assert any('is linked to this company' in note for note in other_model['article_rows'][0]['notes'])
    assert not any('also names this company' in note for note in other_model['article_rows'][0]['notes'])
    assert contents(tmp_path)==before
