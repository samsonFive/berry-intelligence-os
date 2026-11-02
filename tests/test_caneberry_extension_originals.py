"""Original bramble names retain crop boundaries, attribution and review gates."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations,reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
PATH=DATA/'imports/variety-portfolio-observations-2026-11-02-caneberry-extension/observations.json'
PHOTO_SOURCE='portfolio-osu-coast-additional-names-photos'


def sources():
    return json.loads(PATH.read_text(encoding='utf-8'))['sources']


def test_complete_table_notes_and_caption_accounting_retains_source_spelling_and_clocks():
    rows=sources()
    assert [len(s['names'])for s in rows]==[21,18,5,13,10,10]
    assert sum(len(s['names'])for s in rows)==77
    assert len({n['candidate_name']for s in rows[:3]for n in s['names']})==40
    assert rows[0]['names'][0]['candidate_name']=='Prelude'
    assert rows[1]['names'][-1]['candidate_name']=='Prime-Ark Freedom'
    assert rows[1]['names'][-1]['display_label']=='Prime-Ark® Freedom'
    assert rows[3]['names'][6]['candidate_name']=='Himbo-Top'
    assert rows[3]['names'][6]['display_label']=='Himbo-Top®'
    assert rows[3]['names'][9]['candidate_name']=='Joan-J'
    assert rows[2]['names'][0]['candidate_name']=='Chester Thornless'
    for source in rows:
        assert not source['company_ids'] and source['review_state']=='unreviewed'
        assert not source.get('published_date') and source['checked_on']=='2026-11-01'
        assert source['capture_reference']['html']['checked_at'].startswith('2026-11-02T')
        assert source['capture_reference']['checked_on_timezone']=='America/Los_Angeles'
        for name in source['names']:
            assert not any(name.get(k)for k in ['rights','growing_regions','traits','breeder_code','source_company_ids'])
    for source in rows[:3]:
        assert source['capture_reference']['date_discrepancy_retained']
        assert source['capture_reference']['visible_publication_label']=='Published March 2018, Reviewed 2025'
        assert source['capture_reference']['html_published_time'].startswith('2017-10-02')
    for source in rows[3:]:
        assert source['capture_reference']['html_updated_on']=='2026-07-30'


def test_same_name_in_different_berries_and_saved_decisions_are_not_overwritten():
    blueberry={'id':'variety-fixture-prelude-blue','name':'Prelude','aliases':[],
               'entity_type':'variety','berry_ids':['berry-blueberry']}
    _,before=reconcile_portfolios(sources=sources()[:1],varieties=[blueberry],entities=[blueberry],candidates=[])
    prelude=next(c for c in before if c['candidate_name']=='Prelude')
    assert prelude['berry_id']=='berry-raspberry' and not prelude['proposed_relationships']
    prelude.update(status='rejected',identity_state='rejected',human_gated=True,aliases=['My spelling'],
                   review_notes='Keep my decision',photos=[{'operator':'My image'}],knowledge={'notes':'My research'})
    frozen=deepcopy(before)
    _,after=reconcile_portfolios(sources=sources(),varieties=[blueberry],entities=[blueberry],candidates=before)
    assert before==frozen
    indexed={c['id']:c for c in after}
    for old in before:
        assert all(indexed[old['id']][k]==v for k,v in old.items()if k not in {'portfolio_sources','portfolio_review_warnings','portfolio_identity_notes'})
    _,again=reconcile_portfolios(sources=sources(),varieties=[blueberry],entities=[blueberry],candidates=after)
    assert again==after
    assert any(c['candidate_name']=='Prelude'and c['berry_id']=='berry-raspberry'for c in after)


def test_only_four_named_credited_photos_are_referenced_and_permission_stays_unknown():
    loaded=load_portfolio_observations(DATA)
    assert {s['id']for s in sources()}<={s['id']for s in loaded}
    refs=[(name,photo)for s in sources()for name in s['names']for photo in name.get('photos',[])]
    assert len(refs)==4
    assert [n['candidate_name']for n,p in refs]==['Cascade Delight','Columbia Star','Logan','Meeker']
    for name,photo in refs:
        assert photo['reuse']=='unknown' and not photo['license_url']
        assert photo['named_variety']==name['candidate_name'] and photo['berry_id']==name['berry_id']
        assert '?itok='in photo['image_url'] and '© Oregon State University'in photo['credit']
        assert ('Sally Reill'if name['candidate_name']=='Logan'else'Bernadine Strik')in photo['credit']
    _,candidates=reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[])
    for candidate in candidates:
        sourced=variety_photos.source_photos(candidate,candidate=True)
        assert not variety_photos.gallery(candidate,sourced=sourced,authoring=False)
        assert all(not p['display_image']for p in variety_photos.gallery(candidate,sourced=sourced,authoring=True))
        assert not candidate['proposed_relationships'] and not candidate['auto_confirmed']


def test_private_candidate_handoff_retains_credit_without_default_image_requests(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client=TestClient(main.app)
    response=client.get('/varieties/candidates',params={'source':PHOTO_SOURCE,'berry':'berry-raspberry','q':'Cascade Delight'})
    assert response.status_code==200 and len(response.context['candidates'])==1
    candidate=response.context['candidates'][0]
    assert candidate['berry_id']=='berry-raspberry'
    assert 'Bernadine Strik'in response.text and 'Oregon State University'in response.text
    for source in sources():
        for name in source['names']:
            for photo in name.get('photos',[]):
                assert 'src="'+photo['image_url']+'"'not in response.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/candidates').status_code==403
