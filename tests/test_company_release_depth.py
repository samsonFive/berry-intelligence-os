"""Company releases and grower interviews must not become identity decisions."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.variety_photos import gallery, source_photos
from app.services.variety_portfolio_coverage import (
    load_portfolio_observations, portfolio_coverage, reconcile_portfolios,
)

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-release-depth-'


def inputs():
    all_sources = load_portfolio_observations(DATA)
    return all_sources, [s for s in all_sources if s['id'].startswith(PREFIX)]


def test_literal_release_names_keep_dates_brands_and_unnamed_selections_separate():
    _, cohort = inputs()
    assert len(cohort) == 6 and sum(len(s['names']) for s in cohort) == 10
    by_id = {s['id'][len(PREFIX):]: s for s in cohort}
    black = by_id['sunbelle-2023-blackberries']
    assert black['published_date'] == '2023-05-02'
    assert [n['candidate_name'] for n in black['names']] == ['Aketzali', 'Amelali', 'Erandy']
    straw = by_id['sunbelle-2025-strawberries']
    assert straw['published_date'] == '2025-10-09'
    assert [n['candidate_name'] for n in straw['names']] == [
        'Florida Brilliance', 'Florida Ember', 'Florida Encore', 'Sweet Sensation']
    crave = by_id['sunbelle-2026-premium-label-gap']
    assert crave['published_date'] == '2026-02-19' and crave['names'] == []
    assert crave['capture_status'] == 'partial'
    assert [x['label'] for x in crave['accounting']['exclusions']] == ['Craveabelles']
    hutton = by_id['hutton-highland-charm-2025']
    assert hutton['published_date'] == '2025-07-22'
    assert [n['candidate_name'] for n in hutton['names']] == ['Highland Charm']
    assert hutton['company_ids'] == ['company-james-hutton-institute']
    assert all(s['review_state'] == 'unreviewed' for s in cohort)
    assert all(not n.get(k) for s in cohort for n in s['names']
               for k in ('denomination', 'breeder_code', 'grant_number', 'grant_date', 'application_number'))


def test_historical_interview_keeps_season_only_date_and_marketing_context():
    _, cohort = inputs()
    interviews = [s for s in cohort if s['source_type'] == 'grower_interview']
    assert len(interviews) == 2
    assert {(s['names'][0]['candidate_name'], s['names'][0]['berry_id']) for s in interviews} == {
        ('Arabella', 'berry-strawberry'), ('Kwanza', 'berry-raspberry')}
    for source in interviews:
        assert not source.get('published_date')
        assert source['capture_reference']['publication_period'] == 'Autumn 2022'
        assert source['capture_reference']['publication_pages'] == '43–45'
        assert source['url'].endswith('.pdf#page=1')
        assert source['company_ids'] == ['company-perfection-fresh']
        row = source['names'][0]
        assert 'marketing/support partner' in row['portfolio_context']
        assert row['source_company_ids'] == ['company-perfection-fresh']
        assert not row.get('photos')


def test_append_preserves_all_saved_ids_human_decisions_and_photo_choices():
    sources, _ = inputs()
    before_sources = [s for s in sources if not s['id'].startswith(PREFIX)]
    _, saved = reconcile_portfolios(sources=before_sources, varieties=[], entities=[], candidates=[])
    aketzali = next(c for c in saved if c['candidate_name'] == 'Aketzali' and c['berry_id'] == 'berry-blackberry')
    aketzali.update(status='rejected', identity_state='rejected', human_gated=True,
                    reviewer='Fixture analyst', review_notes='Retain rejection',
                    aliases=['My spelling'], photos=[{'operator': 'Keep this image'}],
                    registration={'status': 'My saved status'})
    before = deepcopy((sources, saved))
    rows, after = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=saved)
    by_id = {c['id']: c for c in after}
    for original in saved:
        assert original['id'] in by_id
        for key in ('candidate_name', 'source_id', 'source_url', 'status', 'identity_state',
                    'human_gated', 'reviewer', 'review_notes', 'aliases', 'photos', 'registration'):
            if key in original:
                assert by_id[original['id']][key] == original[key]
    rejected = next(s for s in rows if s['id'] == PREFIX+'sunbelle-2023-blackberries')['names'][0]
    assert rejected['candidate_id'] == aketzali['id'] and rejected['status'] == 'previously_rejected'
    assert not rejected['catalog_id']
    added = [c for c in after if c['id'] not in {o['id'] for o in saved}]
    assert added and all(not c['human_gated'] and not c['auto_confirmed'] for c in added)
    assert (sources, saved) == before


def test_named_source_progress_does_not_clear_other_portfolio_gaps_or_kwanza_identity():
    sources, _ = inputs()
    entities = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((DATA/'entities').rglob('*.json'))]
    varieties = [e for e in entities if e.get('entity_type') == 'variety']
    report = portfolio_coverage(data_dir=DATA, sources=sources, varieties=varieties,
                                entities=entities, candidates=[])
    for cid in ('company-sunbelle', 'company-perfection-fresh'):
        subject = next(s for s in report['subjects'] if cid in s['entity_ids'])
        assert subject['source_status'] == 'names_found' and subject['has_source_gaps']
    kwan = next(v for v in varieties if v['id'] == 'variety-kwanza')
    assert source_photos(kwan, sources=sources, varieties=varieties) == []
    assert kwan['aliases'] == []
    source = next(s for s in report['sources'] if s['id'] == PREFIX+'sunbelle-2026-premium-label-gap')
    assert source['needs_follow_up'] and not source['names']


def test_new_focal_photo_stays_attributed_unapproved_and_private(monkeypatch, tmp_path):
    sources, cohort = inputs()
    hutton = next(s for s in cohort if s['id'] == PREFIX+'hutton-highland-charm-2025')
    raw = hutton['names'][0]['photos'][0]
    assert raw['reuse'] == 'unknown' and not raw['license_url']
    assert raw['source_url'] == hutton['url'] and raw['named_variety'] == 'Highland Charm'
    target = {'id': 'fixture-highland-charm', 'name': 'Highland Charm', 'berry_ids': ['berry-blueberry']}
    sourced = source_photos(target, sources=sources, varieties=[target])
    assert len(sourced) == 1
    assert not gallery(target, sourced=sourced, authoring=True)[0]['display_image']
    assert gallery(target, sourced=sourced, authoring=False) == []
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    page = client.get('/varieties/candidates', params={'q': 'Highland Charm', 'berry': 'berry-blueberry'})
    assert page.status_code == 200 and 'Ignore permission' in page.text
    assert f'data-image-url="{raw["image_url"]}"' in page.text
    assert f'src="{raw["image_url"]}"' not in page.text
    assert 'does not establish a grant or current right' in page.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/candidates', params={'q': 'Highland Charm', 'berry': 'berry-blueberry'})
    assert raw['image_url'] not in public.text and 'Ignore permission' not in public.text


def test_season_only_interview_date_is_visible_without_inventing_a_publication_day(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    page = TestClient(main.app).get('/varieties/candidates', params={
        'q': 'Arabella', 'company': 'company-perfection-fresh', 'berry': 'berry-strawberry'})
    assert page.status_code == 200
    assert 'Arabella in the Autumn 2022 grower interview' in page.text
    assert 'The Autumn 2022 interview names this crop at Berried in Tas.' in page.text
    assert 'marketing/support partner, not its breeder or rights holder' in page.text
    # Its other source is a month-only Moroccan bulletin. Neither source
    # supplies a publication day; the capture date must not be substituted.
    assert 'Published <time' not in page.text
    assert not list(tmp_path.rglob('*.json'))
