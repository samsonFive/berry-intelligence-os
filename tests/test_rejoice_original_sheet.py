"""Recovered original code evidence must not manufacture cultivar equivalence."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios
from app.services import variety_photos

DATA = Path(__file__).resolve().parents[1] / 'data'
SID = 'portfolio-psg-rejoice-english-sheet-attempt'
COHORT = {SID, 'portfolio-psg-rejoice-homepage-slide', 'portfolio-psg-rejoice-varietal-faq'}
BATCH = DATA / 'imports/variety-portfolio-observations-2026-11-01-rejoice-original-sheet/observations.json'


def inputs():
    sources = load_portfolio_observations(DATA)
    return sources, [s for s in sources if s['id'] in COHORT]


def test_recovery_reuses_failed_section_without_redating_publication_or_erasing_old_attempt():
    original = json.loads((DATA / 'imports/variety-portfolio-observations-2026-10-07-ozblu-patent-recheck/observations.json').read_text(encoding='utf-8'))
    old = next(s for s in original['sources'] if s['id'] == SID)
    current, _ = inputs()
    assert old['capture_status'] == 'unreadable' and not old['names']
    assert not old['capture_reference']['body_readable']
    assert sum(s['id'] == SID for s in current) == 1
    recovered = next(s for s in current if s['id'] == SID)
    assert recovered['checked_on'] == '2026-11-01' and recovered['capture_status'] == 'names_enumerated'
    assert recovered['capture_reference']['previous_capture']['blank_viewer']
    assert recovered['capture_reference']['body_readable']
    assert recovered['capture_reference']['capture_sha256'] == 'f6be227287b0947f6417ae7350f5554b4023c7c43d711d107df09554cad51efa'
    assert recovered['capture_reference']['capture_bytes'] == 949121
    assert recovered['capture_reference']['visually_reviewed_pages'] == [1]
    assert not recovered.get('published_date')
    assert recovered['url'].endswith('BK6-13_Sell-Sheet-ENG-v1.0.pdf#page=1')
    assert [n['candidate_name'] for n in recovered['names']] == ['BK 17.006-13']
    assert recovered['accounting'] == {'observed_items': 2, 'exclusions': [
        {'label': 'Rejoice', 'reason': 'Trade label/platform, not a second cultivar in this one-code scope.'}]}
    assert 'growing conditions' in recovered['capture_reference']['performance_qualification']
    assert 'not evidence of actual planting' in recovered['capture_reference']['production_window_context']


def test_code_variants_and_existing_catalog_are_not_merged_or_approved_by_recovery():
    _, cohort = inputs()
    catalog = json.loads((DATA / 'entities/varieties/variety-bk-6-13.json').read_text(encoding='utf-8'))
    rows, candidates = reconcile_portfolios(sources=cohort, varieties=[catalog], entities=[catalog], candidates=[])
    assert len(rows) == 3 and all(s['matched'] == 0 and s['needs_review'] == 1 for s in rows)
    assert {c['candidate_name'] for c in candidates} == {'BK 17.006-13', 'BK3-17.006-13', 'PS-BK3-17.006-13'}
    assert len({c['id'] for c in candidates}) == 3
    for c in candidates:
        assert c['portfolio_identity_notes'] and not c['auto_confirmed'] and not c['human_gated']
        assert not c['aliases'] and not c['proposed_relationships'] and not c['deployment']
        assert not c['breeder_owner'] and not c['registration']['grant_number']
        assert not c['registration']['grant_date']
    sheet = next(c for c in candidates if c['candidate_name'] == 'BK 17.006-13')
    assert not variety_photos.source_photos(sheet, candidate=True)
    assert any('filename' in warning and 'catalog BK 6-13' in warning for warning in sheet['portfolio_review_warnings'])
    faq = next(c for c in candidates if c['candidate_name'] == 'BK3-17.006-13')
    held = variety_photos.source_photos(faq, candidate=True)
    assert len(held) == 1 and held[0]['reuse'] == 'unknown'
    assert all(not p['display_image'] for p in variety_photos.gallery(faq, sourced=held, authoring=True))
    assert catalog['name'] == 'BK 6-13' and not catalog['aliases']


def test_original_keys_saved_decisions_and_operator_fields_survive_and_replay_is_idempotent():
    current, _ = inputs()
    old_source = next(s for s in json.loads((DATA / 'imports/variety-portfolio-observations-2026-10-07-ozblu-patent-recheck/observations.json').read_text(encoding='utf-8'))['sources'] if s['id'] == SID)
    baseline = [old_source if s['id'] == SID else s for s in current]
    _, saved = reconcile_portfolios(sources=baseline, varieties=[], entities=[], candidates=[])
    first = next(c for c in saved if c['candidate_name'] == 'BK3-17.006-13')
    first.update(human_gated=True, status='rejected', identity_state='rejected',
        review_notes='Keep this code unresolved', aliases=['My retained spelling'],
        knowledge={'notes': 'Keep my research'}, photos=[{'operator': 'Keep selected photograph'}])
    originals = deepcopy((current, saved))
    rows, after = reconcile_portfolios(sources=current, varieties=[], entities=[], candidates=saved)
    indexed = {c['id']: c for c in after}
    assert len(after) == len(saved) + 1
    for prior in saved:
        assert prior['id'] in indexed
        for key, value in prior.items():
            if key not in {'portfolio_sources', 'portfolio_review_warnings', 'portfolio_identity_notes'}:
                assert indexed[prior['id']][key] == value
    added = next(c for c in after if c['candidate_name'] == 'BK 17.006-13')
    assert not added['human_gated'] and added['status'] == 'proposed' and not added['aliases']
    assert added['id'] != first['id'] and not added.get('review_notes')
    again_rows, again = reconcile_portfolios(sources=current, varieties=[], entities=[], candidates=after)
    assert again_rows == rows and again == after and (current, saved) == originals


def test_current_routes_expose_recovery_conflict_and_original_without_get_writes(monkeypatch, tmp_path):
    protected = {p: p.read_bytes() for folder in ['entities', 'facts', 'evidence', 'relationships']
                 for p in (DATA / folder).rglob('*.json')}
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    candidate = client.get('/varieties/candidates', params={'company': 'company-plant-sciences-genetics', 'source': SID})
    assert candidate.status_code == 200
    assert len(candidate.context['candidates']) == 1
    assert candidate.context['candidates'][0]['candidate_name'] == 'BK 17.006-13'
    assert 'catalog BK 6-13' in candidate.text and 'different codes' in candidate.text
    assert 'BK6-13_Sell-Sheet-ENG-v1.0.pdf#page=1' in candidate.text
    detail = client.get('/varieties/coverage/source/' + SID)
    assert detail.status_code == 200
    assert 'BK 17.006-13' in detail.text and 'genetic potential' in detail.text
    assert 'Spanish sheet' in detail.text and 'BK6-13_Sell-Sheet-ENG-v1.0.pdf#page=1' in detail.text
    profile = client.get('/entities/company/company-plant-sciences-genetics', params={'tab': 'varieties'})
    assert profile.status_code == 200 and 'BK 17.006-13' in profile.text and 'Name needs review' in profile.text
    assert not list(tmp_path.rglob('*.json'))
    assert all(path.read_bytes() == value for path, value in protected.items())
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates').status_code == 403
    assert client.get('/varieties/coverage/source/' + SID).status_code == 403
