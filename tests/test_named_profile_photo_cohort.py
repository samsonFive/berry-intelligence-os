"""Real source photographs retain attribution, permissions and identity holds."""
from copy import deepcopy
import json
from pathlib import Path

from app.services.variety_photos import gallery, source_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations

DATA = Path(__file__).resolve().parents[1] / 'data'


def test_named_cohort_reaches_twelve_existing_profiles_without_changing_identities_or_reuse():
    # Historical cohort eligibility, before the later USDA code/name bridge
    # adds a Kwanza identity hold. The national-cohort tests check that hold.
    sources = [s for s in load_portfolio_observations(DATA)
               if not s['id'].startswith('portfolio-national-')]
    batch = [s for s in sources if s['id'].startswith('portfolio-named-photo-cohort-')]
    assert len(batch) == 13 and sum(len(s['names']) for s in batch) == 13
    varieties = [json.loads(p.read_text(encoding='utf-8')) for p in (DATA/'entities/varieties').glob('*.json')]
    original = deepcopy(varieties)
    reached = set()
    for source in batch:
        name = source['names'][0]['candidate_name']
        variety = next(v for v in varieties if v['name'] == name)
        photos = source_photos(variety, sources=sources, varieties=varieties)
        assert source['review_state'] == 'unreviewed'
        assert source['capture_reference']['original_image_visual_reviewed']
        assert not source['capture_reference']['reuse_permission_verified']
        if name == "Rutgers D'Light":
            assert photos == []  # Do not bypass the existing source-code discrepancy hold.
            continue
        reached.add(name)
        photo = next(p for p in photos if p['source_url'] == source['url'])
        assert photo['named_variety'] == name and photo['reuse'] == 'unknown'
        assert photo['license_url'] == '' and photo['credit'] and photo['caption']
        assert gallery(variety, sourced=photos, authoring=False) == []
        assert not any(p['display_image'] for p in gallery(variety, sourced=photos, authoring=True))
    assert len(reached) == 12 and varieties == original
    assert not any(s['names'][0].get(k) for s in batch for k in ('grant_number', 'application_number', 'traits', 'growing_regions'))


def test_capture_labels_and_full_size_links_do_not_invent_codes_aliases_or_measurements():
    batch = {s['id'].removeprefix('portfolio-named-photo-cohort-'): s
             for s in load_portfolio_observations(DATA) if s['id'].startswith('portfolio-named-photo-cohort-')}
    melissa = batch['melissa']
    assert melissa['capture_reference']['h1_label'] == 'Nsg 203'
    assert 'Melissa' in melissa['capture_reference']['document_title']
    assert not melissa['names'][0].get('breeder_code')
    assert batch['marimbella']['names'][0]['breeder_code'] == 'NSG 203'
    assert batch['marimbella']['capture_reference']['image_alt'] == 'marinbella_0001_DSC09511'
    rutgers = batch['rutgers-dlight']
    assert rutgers['published_date'] == '2022-05-19'
    assert rutgers['capture_reference']['image_width'] == 1920
    assert rutgers['capture_reference']['thumbnail_replaced_by_observed_full_size_link']
    assert 'no size measurements' in rutgers['names'][0]['photos'][0]['caption']
    assert not any(s['names'][0]['candidate_name'] in {'Example Blue', 'Example Red', 'Blue Manila', 'Blue Maldiva'}
                   for s in batch.values())
