"""Source-code photos stay usable without deciding disputed trade-name identity."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios
from app.services.variety_universe.candidates import load_variety_candidates
from app.services.variety_universe.registry_import import import_registry_rows, load_registry_rows

DATA = Path(__file__).resolve().parents[1] / 'data'
FIXTURE = DATA / 'imports/variety-universe-cfia-photo-records-2026-10-07/registry_rows.json'


def candidates():
    sources = load_portfolio_observations(DATA)
    _, rows = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    return sources, rows


def test_original_codes_have_held_photos_without_resolving_uncoded_ava_labels():
    sources, rows = candidates()
    before = deepcopy((sources, rows))
    for code, label, comparator_count in [('ASF219', 'AVA Star', 5), ('ASF218', 'AVA Blush', 2)]:
        row = next(item for item in rows if item['candidate_name'] == code)
        assert row['denomination'] == code and row['portfolio_identity_notes']
        assert not row['human_gated'] and not row['auto_confirmed'] and not row['aliases']
        assert not row['proposed_relationships'] and not row['candidate_canonical_match']
        gallery = photos.gallery(row, sourced=photos.source_photos(row, candidate=True), authoring=True)
        assert len(gallery) == 2
        assert {image['kind'] for image in gallery} == {'plant', 'fruit'}
        assert all(image['named_variety'] == code and image['reuse'] == 'unknown' and not image['display_image'] for image in gallery)
        assert all('Photographer not credited' in image['credit'] and 'trade-name match unconfirmed' in image['origin'] for image in gallery)
        assert not photos.gallery(row, sourced=gallery, authoring=False)
        uncoded = next(item for item in rows if item['candidate_name'] == label)
        assert uncoded['portfolio_identity_notes'] and not photos.source_photos(uncoded, candidate=True)
        focal = next(source for source in sources if source['id'] == 'portfolio-cfia-' + code.lower() + '-record')
        assert len(focal['names']) == 1 and len(focal['accounting']['exclusions']) == comparator_count
    assert (sources, rows) == before


@pytest.mark.parametrize('change', ['target_label', 'target_code', 'photo_label', 'photo_code', 'reference_code', 'berry', 'source'])
def test_disputed_label_never_transfers_a_photo_between_identities(change):
    _, rows = candidates()
    row = deepcopy(next(item for item in rows if item['candidate_name'] == 'ASF219'))
    ref = row['portfolio_sources'][0]
    image = ref['photos'][0]
    ref['photos'] = [image]
    if change == 'target_label':
        row['candidate_name'] = row['trade_name']
    elif change == 'target_code':
        row['denomination'] = 'ASF218'
    elif change == 'photo_label':
        image['named_variety'] = row['trade_name']
    elif change == 'photo_code':
        image['named_variety'] = 'ASF218'
    elif change == 'reference_code':
        ref['denomination'] = 'ASF218'
    elif change == 'berry':
        ref['berry_id'] = 'berry-blueberry'
    else:
        image['source_url'] = 'https://example.test/different-source'
    assert not photos.source_photos(row, candidate=True)


def test_canonical_profile_keeps_the_pairing_gate_even_for_the_recorded_code():
    sources, _ = candidates()
    canonical = {'id': 'variety-fixture-asf219', 'entity_type': 'variety', 'name': 'ASF219',
                 'aliases': ['AVA Star'], 'berry_ids': ['berry-strawberry']}
    before = deepcopy(canonical)
    assert not photos.source_photos(canonical, sources=sources, varieties=[canonical])
    assert canonical == before


def test_original_registry_fields_and_additive_import_preserve_human_edits(tmp_path):
    rows = load_registry_rows(FIXTURE)
    result = import_registry_rows(rows, varieties=[], inbox_dir=tmp_path)
    assert result['written_count'] == 2
    for candidate in load_variety_candidates(tmp_path):
        assert candidate['status'] == 'proposed' and not candidate['human_gated'] and not candidate['auto_confirmed']
        assert not candidate['aliases'] and not candidate['proposed_relationships']
        assert candidate['registration']['application_date'] == '2020-04-14'
        assert candidate['registration']['grant_date'] == '2022-02-04'
        assert candidate['registration']['expiry'] == ''
        assert 'Rights surrendered' in candidate['registration']['status']
        assert candidate['knowledge']['rights_surrendered_on'] == '2024-02-04'
        assert candidate['knowledge']['compulsory_licensing_exemption_expires_on'] == '2024-02-04'
        path = tmp_path / 'variety_candidates' / (candidate['id'] + '.json')
        candidate['review_notes'] = 'Fictional user correction — preserve on refresh'
        path.write_text(json.dumps(candidate), encoding='utf-8')
    before = {path.name: path.read_bytes() for path in tmp_path.rglob('*.json')}
    assert import_registry_rows(rows, varieties=[], inbox_dir=tmp_path)['written_count'] == 0
    assert before == {path.name: path.read_bytes() for path in tmp_path.rglob('*.json')}


def test_coded_photo_preview_is_private_source_labeled_and_get_does_not_write(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    coded = client.get('/varieties/candidates?q=ASF219&berry=berry-strawberry')
    uncoded = client.get('/varieties/candidates?q=AVA+Star&berry=berry-strawberry')
    assert coded.status_code == uncoded.status_code == 200
    # Search also finds the separate coded lead through its source trade label.
    # Check the uncoded candidate's own card, not the entire result page.
    target = next(row for row in main.variety_candidate_universe()[1] if row['candidate_name'] == 'AVA Star')
    class CandidatePhotos(HTMLParser):
        def __init__(self):
            super().__init__()
            self.depth = 0
            self.seen = False
            self.images = []

        def handle_starttag(self, tag, attrs):
            fields = dict(attrs)
            if tag == 'details':
                if fields.get('id') == target['id']:
                    self.depth = 1
                    self.seen = True
                elif self.depth:
                    self.depth += 1
            if self.depth and fields.get('data-image-url'):
                self.images.append(fields['data-image-url'])

        def handle_endtag(self, tag):
            if tag == 'details' and self.depth:
                self.depth -= 1

    card = CandidatePhotos()
    card.feed(uncoded.text)
    assert card.seen and not card.images
    for suffix in ['a', 'b']:
        image = 'https://active.inspection.gc.ca/english/plaveg/pbrpov/image/10143' + suffix + '.jpg'
        assert 'data-image-url="' + image + '"' in coded.text
        assert 'src="' + image + '"' not in coded.text
    assert 'Photo labeled ASF219 · trade-name match unconfirmed' in coded.text
    assert 'Ignore permission' in coded.text and 'Permission unconfirmed' in coded.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    readonly = client.get('/varieties/candidates?q=ASF219&berry=berry-strawberry')
    assert readonly.status_code == 403 and '10143a.jpg' not in readonly.text
    assert not list(tmp_path.rglob('*.json'))
