"""Rendered publisher cards recover scoped gaps without approving identities."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
OLD = DATA / 'imports/variety-portfolio-observations-2026-10-07-psg-ozblu/observations.json'
CURRENT = DATA / 'imports/variety-portfolio-observations-2026-11-03-psg-rendered-selector/observations.json'


def captures():
    return json.loads(CURRENT.read_text(encoding='utf-8'))['sources']


def test_recovered_country_selection_preserves_historical_gaps_and_explicit_scope():
    sources = captures()
    latest = {s['id']: s for s in load_portfolio_observations(DATA)}
    historical = {s['id']: s for s in json.loads(OLD.read_text(encoding='utf-8'))['sources']}
    assert len(sources) == 5 and sum(len(s['names']) for s in sources) == 44
    assert len({n['breeder_code'] for s in sources for n in s['names']}) == 34
    for crop, count in [('strawberry', 19), ('raspberry', 7), ('blackberry', 1)]:
        id = 'portfolio-psg-selection-' + crop
        source = latest[id]
        assert source == next(s for s in sources if s['id'] == id)
        assert historical[id]['capture_status'] == 'unreadable' and not historical[id]['names']
        assert source['capture_status'] == 'names_enumerated' and len(source['names']) == count
        reference = source['capture_reference']
        assert reference['selected_country'] == 'United States of America'
        assert reference['selected_region'] == '-All Regions-' and reference['selected_type'] == '-All Types-'
        assert reference['previous_capture']['retained_file_sha256'] == hashlib.sha256(OLD.read_bytes()).hexdigest()
        assert len(reference['detail_pages']) == count
        assert all(not d['linked_sheet_bodies_checked'] and not d['current_legal_status_verified']
                   for d in reference['detail_pages'])
        assert 'not a worldwide portfolio' in source['enumerated_scope']
    related = sources[-2:]
    assert [len(s['names']) for s in related] == [8, 9]
    assert all('do not inherit the US selector scope' in s['enumerated_scope'] for s in related)
    assert all(s['review_state'] == 'unreviewed' and not s.get('published_date') for s in sources)


def test_short_labels_do_not_merge_full_codes_or_create_brand_cultivars():
    sources = captures()
    original = deepcopy(sources)
    rows, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    assert len(candidates) == 34 and all(not r['accounting_view']['issues'] for r in rows)
    short = [n for s in sources for n in s['names'] if n['display_label'] == "'060'"]
    assert {n['candidate_name'] for n in short} == {'VS-17.5417-060', 'SB_15_089-060'}
    selected = {c['candidate_name']: c for c in candidates}
    assert selected['VS-17.5417-060']['id'] != selected['SB_15_089-060']['id']
    assert not {'060', 'BK6-13', 'Rejoice'} & selected.keys()
    assert 'PS-BK3-17.006-13' in selected and 'Inspire' in selected
    for candidate in candidates:
        assert not candidate['auto_confirmed'] and not candidate['human_gated']
        assert not candidate['aliases'] and not candidate['proposed_relationships']
        assert not candidate['deployment'] and not candidate['breeder_owner']
        assert not candidate['registration']['official_registry_source']
        assert not candidate['registration']['grant_number']
    assert sources == original


def test_replay_preserves_rejections_operator_notes_and_photo_choices():
    sources = captures()
    _, saved = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    inspire = next(c for c in saved if c['candidate_name'] == 'Inspire')
    inspire.update(human_gated=True, status='rejected', identity_state='rejected',
                   review_notes='Keep my identity decision', aliases=['My spelling'],
                   knowledge={'notes': 'My research'}, photos=[{'operator': 'Keep my photo'}])
    before = deepcopy((sources, saved))
    rows, after = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=saved)
    assert len(after) == 34
    indexed = {c['id']: c for c in after}
    for prior in saved:
        for key, value in prior.items():
            if key not in {'portfolio_sources', 'portfolio_review_warnings', 'portfolio_identity_notes'}:
                assert indexed[prior['id']][key] == value
    assert all(n['status'] == 'previously_rejected' for s in rows for n in s['names']
               if n['candidate_name'] == 'Inspire')
    assert reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=after) == (rows, after)
    assert (sources, saved) == before


def test_full_source_corpus_retains_every_earlier_candidate_key():
    from app.services.variety_universe.corpus_discovery import build_discovered_candidates, merge_visible_candidates
    def records(folder):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((DATA / folder).rglob('*.json'))]
    entities = records('entities')
    varieties = [row for row in entities if row.get('entity_type') == 'variety']
    report = build_discovered_candidates(varieties=varieties, entities=entities,
        published_evidence=[e for e in records('evidence') if e.get('status') == 'published'], facts=records('facts'))
    corpus_candidates = merge_visible_candidates([], report['candidates'])
    sources = load_portfolio_observations(DATA)
    ids = {s['id'] for s in captures()}
    historical = {s['id']: s for s in json.loads(OLD.read_text(encoding='utf-8'))['sources']}
    prior = [historical[s['id']] if s['id'] in ids and s['id'] in historical else s
             for s in sources if s['id'] not in ids or s['id'] in historical]
    _, before = reconcile_portfolios(sources=prior, varieties=varieties, entities=entities, candidates=corpus_candidates)
    _, after = reconcile_portfolios(sources=sources, varieties=varieties, entities=entities, candidates=before)
    assert len(before) == 1315 and len(after) == 1333
    assert {c['id'] for c in before} < {c['id'] for c in after}


def test_photos_remain_attributed_held_references_and_original_patent_is_not_duplicated():
    sources = captures()
    _, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    photos = [p for c in candidates for p in variety_photos.source_photos(c, candidate=True)]
    assert len(photos) == len({p['image_url'] for p in photos}) == 34
    assert all(p['reuse'] == 'unknown' and not p['license_url'] for p in photos)
    assert all(p['credit'].startswith('Plant Sciences Genetics') for p in photos)
    for c in candidates:
        held = variety_photos.source_photos(c, candidate=True)
        assert all(not p['display_image'] for p in variety_photos.gallery(c, sourced=held, authoring=True))
        assert not variety_photos.gallery(c, sourced=held, authoring=False)
    patents = [s for s in load_portfolio_observations(DATA)
               if s['id'] == 'portfolio-reference-gap-original-uspp34597p2']
    assert len(patents) == 1 and patents[0]['source_type'] == 'plant_patent'
    assert patents[0]['url'] == 'https://patents.google.com/patent/USPP34597P2/en'
    assert all(s['source_type'] == 'breeder_catalog' for s in sources)


def test_private_routes_offer_session_preview_without_get_writes_or_public_images(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    for source, name in [('portfolio-psg-selection-blackberry', 'PS-BK3-17.006-13'),
                         ('portfolio-psg-resolution-related', 'SB_15_089-060')]:
        response = client.get('/varieties/candidates', params={'source': source, 'q': name})
        assert response.status_code == 200 and len(response.context['candidates']) == 1
        candidate = response.context['candidates'][0]
        image = variety_photos.source_photos(candidate, candidate=True)[0]['image_url']
        assert 'data-image-url="' + image + '"' in response.text
        assert 'src="' + image + '"' not in response.text
        assert 'Ignore permission' in response.text and 'Permission unconfirmed' in response.text
    page = client.get('/varieties/coverage/source/portfolio-psg-selection-strawberry')
    assert page.status_code == 200 and 'United States' in page.text
    assert 'VS-17.5417-060' in page.text and 'Inspire' in page.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates').status_code == 403
    assert client.get('/varieties/coverage/source/portfolio-psg-selection-strawberry').status_code == 403
