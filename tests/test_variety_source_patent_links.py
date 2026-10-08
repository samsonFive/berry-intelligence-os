"""Later patent provenance must not replace saved candidate identity or rights."""
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios
from app.services.variety_photos import source_photos

DATA = Path(__file__).resolve().parents[1] / 'data'


def sources():
    return [s for s in load_portfolio_observations(DATA)
            if s['id'].startswith(('portfolio-so-', 'portfolio-santorsola-'))]


@pytest.mark.parametrize('name,grant', [('Lagorai Plus','USPP25636P3'), ('Dafne','USPP31991P3')])
def test_later_patent_keeps_company_candidate_id_and_own_document_metadata(name, grant):
    current = sources()
    old = [s for s in current if s['id'] not in {'portfolio-so-patent-lagorai-plus','portfolio-so-patent-dafne'}]
    _, before = reconcile_portfolios(sources=old, varieties=[], entities=[], candidates=[])
    rows, after = reconcile_portfolios(sources=current, varieties=[], entities=[], candidates=[])
    first = next(c for c in before if c['candidate_name'] == name)
    candidate = next(c for c in after if c['candidate_name'] == name)
    assert candidate['id'] == first['id'] and candidate['registration'] == first['registration']
    assert candidate['source_tier'] == 'tier_1_breeder_catalog'
    reference = next(s for s in candidate['portfolio_sources'] if s['source_type'] == 'plant_patent')
    assert reference['grant_number'] == grant and reference['jurisdiction'] == 'US'
    assert reference['product_url'].endswith('.pdf#page=3')
    assert not candidate['human_gated'] and not candidate['auto_confirmed'] and not candidate['aliases']
    assert not candidate['proposed_relationships'] and not candidate['registration']['status']
    photos = source_photos(candidate, candidate=True)
    assert len(photos) == 1 and photos[0]['reuse'] == 'unknown' and photos[0]['named_variety'] == name
    assert not next(s for s in rows if s['id'] == reference['id'])['needs_follow_up']


def test_saved_registration_and_human_decisions_survive_source_enrichment():
    human = dict(id='human-dafne',candidate_name='Dafne',berry_id='berry-raspberry',
        status='reviewed',identity_state='distinct',human_gated=True,reviewer='Analyst',review_notes='Keep this identity',
        registration={'application_number':'operator-value','status':'operator-status','expiry':'operator-date'},
        knowledge={'notes':'User edited'},aliases=['User alias'])
    before = deepcopy(human)
    _, candidates = reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[human])
    candidate = next(c for c in candidates if c['id'] == human['id'])
    assert candidate['registration'] == before['registration'] and candidate['knowledge'] == before['knowledge']
    assert candidate['aliases'] == before['aliases'] and candidate['review_notes'] == before['review_notes']
    assert any(s.get('grant_number') == 'USPP31991P3' for s in candidate['portfolio_sources'])
    assert human == before


@pytest.mark.parametrize('name,number,filing,granted', [('Lagorai Plus','USPP25636P3','13/815,342','2015-06-23'),
                                                   ('Dafne','USPP31991P3','16/350,828','2020-07-21')])
def test_private_render_shows_original_claim_without_eager_photo_or_review_writes(monkeypatch,tmp_path,name,number,filing,granted):
    _, candidates = reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[])
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda: ([],candidates,{}))
    before = deepcopy(candidates)
    page = TestClient(main.app).get('/varieties/candidates',params={'q':name,'berry':'berry-raspberry'})
    assert page.status_code == 200
    assert 'Source references' in page.text and 'Original claim ↗' in page.text
    assert number in page.text and filing in page.text and granted in page.text
    assert 'current rights still need review' in page.text and 'Ignore permission' in page.text
    assert 'data-image-url="https://patentimages.storage.googleapis.com/' in page.text
    assert '<img src="https://patentimages.storage.googleapis.com/' not in page.text
    assert candidates == before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert TestClient(main.app).get('/varieties/candidates').status_code == 403


def test_capture_gaps_are_not_zero_variety_or_completed_company_checks():
    all_sources = load_portfolio_observations(DATA)
    gaps = [s for s in all_sources if s['id'].startswith('portfolio-gap-')]
    assert {s['capture_status'] for s in gaps} == {'partial','unreadable'}
    assert all(not s['names'] for s in gaps)
    assert not any(n['candidate_name'] == 'CraveABelles' for s in all_sources for n in s['names'])
    for source in sources():
        if source['id'].startswith('portfolio-santorsola-current-'):
            assert source['capture_reference']['full_technical_sheets_checked']
            assert not any('contents and any rights claim remain unchecked' in n['portfolio_context'] for n in source['names'])
    ofelia = next(s for s in sources() if s['id'] == 'portfolio-so-patent-ofelia')
    assert ofelia['capture_reference']['visually_reviewed_pages'] == list(range(1,10))
    assert 'remain unread' not in ofelia['limitations']
