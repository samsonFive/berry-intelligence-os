"""Original documents improve provenance without approving identity or rights."""
from copy import deepcopy
from pathlib import Path

from app.services.variety_photos import compatible, source_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'


def documents():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith('portfolio-so-')]


def test_original_document_types_and_literal_patent_metadata_remain_unreviewed():
    original = documents()
    before = deepcopy(original)
    _, candidates = reconcile_portfolios(sources=original, varieties=[], entities=[], candidates=[])
    assert len(original) == 12 and len(candidates) == 11
    ofelia = next(c for c in candidates if c['candidate_name'] == 'Ofelia SO')
    assert ofelia['source_tier'] == 'tier_1_patent_pvr'
    registration = ofelia['registration']
    assert registration['application_number'] == '18/073,772'
    assert registration['grant_number'] == 'USPP35680P3'
    assert registration['application_date'] == '2022-12-02'
    assert registration['grant_date'] == '2024-03-12'
    assert not registration['status'] and not registration['official_registry_source']
    assert all(not c['human_gated'] and not c['auto_confirmed'] and not c['aliases'] and not c['proposed_relationships'] for c in candidates)
    assert all(c['source_tier'] == 'tier_2_technical_sheet' for c in candidates if c != ofelia)
    assert all(not s.get('published_date') for s in original)
    assert original == before


def test_ofelia_labels_stay_separate_and_photo_does_not_match_wrong_crop_or_short_label():
    sources = [s for s in load_portfolio_observations(DATA) if s['id'].startswith(('portfolio-so-', 'portfolio-santorsola-'))]
    _, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    assert len(candidates) == 12
    short = next(c for c in candidates if c['candidate_name'] == 'Ofelia')
    full = next(c for c in candidates if c['candidate_name'] == 'Ofelia SO')
    assert short['id'] != full['id'] and not short['aliases'] and not full['aliases']
    photos = source_photos(full, candidate=True)
    assert len(photos) == 1 and photos[0]['reuse'] == 'unknown'
    assert not source_photos(short, candidate=True)
    assert not compatible(photos[0], {**full, 'berry_id':'berry-strawberry'}, candidate=True)
    assert not {'Tulameen', 'SO.LR.08.25.30'} & {c['candidate_name'] for c in candidates}
    lagorai = next(c for c in candidates if c['candidate_name'].casefold() == 'lagorai plus')
    assert {s['candidate_name'] for s in lagorai['portfolio_sources']} == {'Lagorai Plus', 'Lagorai plus'}


def test_replay_keeps_human_patent_and_photo_decisions():
    human = dict(id='human-ofelia', candidate_name='Ofelia SO', berry_id='berry-raspberry',
                 status='rejected', identity_state='rejected', human_gated=True,
                 review_notes='Different identity; keep my decision', knowledge={'notes':'User-authored'},
                 registration={'status':'user-specified', 'grant_number':'keep-existing'})
    before = deepcopy(human)
    _, candidates = reconcile_portfolios(sources=documents(), varieties=[], entities=[], candidates=[human])
    retained = next(c for c in candidates if c['id'] == human['id'])
    assert retained['registration'] == before['registration'] and retained['knowledge'] == before['knowledge']
    assert retained['review_notes'] == before['review_notes'] and human == before


def test_new_document_provenance_preserves_existing_company_candidate_links():
    all_sources = load_portfolio_observations(DATA)
    old = [s for s in all_sources if s['id'].startswith('portfolio-santorsola-')]
    combined = [s for s in all_sources if s['id'].startswith(('portfolio-santorsola-', 'portfolio-so-'))]
    _, before = reconcile_portfolios(sources=old, varieties=[], entities=[], candidates=[])
    _, after = reconcile_portfolios(sources=combined, varieties=[], entities=[], candidates=[])
    new_by_name = {c['candidate_name']: c['id'] for c in after}
    assert all(new_by_name[c['candidate_name']] == c['id'] for c in before)
