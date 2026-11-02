"""A regional source adds recall and credited photo references without trust."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
PATH=DATA/'imports/variety-portfolio-observations-2026-11-02-maryland-extension/observations.json'
TABLE='portfolio-umd-mid-atlantic-blueberry-table'
PHOTOS='portfolio-umd-mid-atlantic-blueberry-photos'


def sources():
    return json.loads(PATH.read_text(encoding='utf-8'))['sources']


def test_table_and_caption_accounting_keeps_original_names_and_distinct_clocks():
    table,photos=sources()
    assert (table['id'],photos['id'])==(TABLE,PHOTOS)
    assert len(table['names'])==53 and len(photos['names'])==6
    assert len({r['candidate_name']for s in sources()for r in s['names']})==54
    assert [r['candidate_name']for r in photos['names']]==['Blue Ribbon','Bluecrop','Duke','Last Call','Legacy','Valor']
    assert 'Valor'not in {r['candidate_name']for r in table['names']}
    blue=next(r for r in table['names']if r['candidate_name']=='Blue Ribbon')
    assert blue['display_label']=='Blue Ribbon*' and 'asterisk'in blue['portfolio_context']
    assert table['names'][2]['candidate_name']=='Hannah’s Choice'
    assert table['names'][3]['candidate_name']=='O’Neal'
    for source in sources():
        assert source['review_state']=='unreviewed' and not source['company_ids'] and not source.get('published_date')
        assert source['checked_on']=='2026-11-01'
        ref=source['capture_reference']
        assert ref['checked_on_timezone']=='America/Los_Angeles'
        assert ref['html']['checked_at'].startswith('2026-11-02T')
        assert ref['html_updated_on']=='2026-06-30' and ref['pdf_publication_label']=='June 2026'
        assert ref['original_document_formats_not_independent'] and not ref['publication_day_established']
        assert ref['visually_reviewed_pdf_pages']==list(range(1,9)) and ref['pdf']['pages']==8
        assert ref['pdf_cover_title']!=ref['html_title'] and 'different title'in source['limitations']
        for row in source['names']:
            assert not any(row.get(k)for k in ('breeder_code','denomination','source_company_ids','rights','growing_regions','traits'))
    assert [int(r['product_url'].rsplit('=',1)[1])for r in table['names']]==[5]*14+[6]*14+[7]*14+[8]*11


def test_credited_exact_photo_urls_stay_held_and_do_not_create_relationships():
    table,photos=sources()
    loaded=load_portfolio_observations(DATA)
    assert {TABLE,PHOTOS}<={s['id']for s in loaded}
    _,candidates=reconcile_portfolios(sources=[table,photos],varieties=[],entities=[],candidates=[])
    assert len(candidates)==54
    assert sum(len(variety_photos.source_photos(c,candidate=True))for c in candidates)==6
    for candidate in candidates:
        assert not candidate['human_gated'] and not candidate['auto_confirmed']
        assert not candidate['aliases'] and not candidate['proposed_relationships']
        assert not candidate['breeder_owner'] and not candidate['deployment']
        sourced=variety_photos.source_photos(candidate,candidate=True)
        assert not variety_photos.gallery(candidate,sourced=sourced,authoring=False)
    for row in photos['names']:
        photo,=row['photos']
        assert photo['credit']=='Haley Sater · University of Maryland Extension'
        assert photo['reuse']=='unknown' and not photo['license_url']
        assert '?itok='in photo['image_url'] and photo['source_url']==table['url']
        assert photo['named_variety']==row['candidate_name']
        assert 'No individual photo was downloaded'in photo['reuse_note']


def test_repeat_source_reconciliation_retains_saved_decisions_text_and_photos():
    _,before=reconcile_portfolios(sources=sources()[:1],varieties=[],entities=[],candidates=[])
    selected=next(row for row in before if row['candidate_name']=='Blue Ribbon')
    selected.update(status='rejected',identity_state='rejected',human_gated=True,
                    aliases=['My spelling'],review_notes='Keep my review',photos=[{'operator':'My chosen image'}],
                    knowledge={'notes':'My literal notes'})
    original=deepcopy(before)
    rows,after=reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=before)
    assert before==original and len(after)==54
    indexed={row['id']:row for row in after}
    for prior in before:
        assert all(indexed[prior['id']][k]==v for k,v in prior.items()if k not in {'portfolio_sources','portfolio_review_warnings','portfolio_identity_notes'})
    assert reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=after)==(rows,after)


def test_private_source_handoffs_expose_original_rows_and_keep_photos_unloaded(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client=TestClient(main.app)
    response=client.get('/varieties/candidates',params={'source':PHOTOS,'q':'Valor'})
    assert response.status_code==200 and len(response.context['candidates'])==1
    valor=response.context['candidates'][0]
    assert valor['portfolio_identity_notes'] and not valor['photos']
    assert any(ref.get('photos')for ref in valor['portfolio_sources']if ref['id']==PHOTOS)
    assert sources()[1]['names'][-1]['product_url']in response.text
    assert 'Haley Sater'in response.text and 'Reuse permission remains unknown'in response.text
    photo=sources()[1]['names'][-1]['photos'][0]
    assert 'src="'+photo['image_url']+'"'not in response.text
    duke=client.get('/varieties/candidates',params={'source':PHOTOS,'q':'Duke'})
    assert duke.status_code==200 and len(duke.context['candidates'])==1
    shown,=duke.context['candidates'][0]['photos']
    expected=next(r['photos'][0]for r in sources()[1]['names']if r['candidate_name']=='Duke')
    assert shown['image_url']==expected['image_url'] and not shown['display_image']
    assert shown['credit']=='Haley Sater · University of Maryland Extension'
    assert 'Ignore permission'in duke.text and 'src="'+shown['image_url']+'"'not in duke.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/candidates').status_code==403
