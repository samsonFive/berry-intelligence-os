"""Map reference identities, sourced boundary corrections and explicit review."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main, map_market_research_routes as routes
from app.services import map_boundaries, map_statistics_refresh as refresh
from app.services import market_reference_research as research
from app.services import market_statistics_reference as reference
from app.services.global_explorer import IntelligenceQuery, explorer_model, snapshot_model
from app.services.map_workspace import statistics
from app.services.market_reference_countries import countries, equivalent_ids

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'data/imports/map-market-references-2026-10-28-expanded/eurostat-strawberries.json'
BERRIES = {'berry-strawberry': 'Strawberry', 'berry-blueberry': 'Blueberry'}
GERMANY = {'id': 'geography-germany', 'entity_type': 'geography', 'name': 'Germany',
           'attributes': {'iso_3166_1_alpha_2': 'DE'}}


def source_capture():
    return json.loads(CAPTURE.read_text(encoding='utf-8'))


def test_research_choices_reuse_map_ids_without_creating_or_mutating_entities():
    entities = {GERMANY['id']: deepcopy(GERMANY)}
    before = deepcopy(entities)
    rows = countries(entities)
    assert rows['geography-germany'] == GERMANY and 'iso:DE' not in rows
    for code, name in [('FR', 'France'), ('IT', 'Italy'), ('PL', 'Poland')]:
        assert rows['iso:' + code]['name'] == name
        assert rows['iso:' + code]['reference_only'] is True
    assert entities == before
    rows['geography-germany']['name'] = 'Caller edit'
    assert entities == before
    assert [r['name'].casefold() for r in countries(entities).values()] == sorted(r['name'].casefold() for r in countries(entities).values())


def test_ambiguous_catalog_code_cannot_be_reintroduced_as_iso_fallback():
    entities = {'first': GERMANY, 'second': {**GERMANY, 'id': 'other-germany'}}
    rows = countries(entities)
    assert 'geography-germany' not in rows and 'other-germany' not in rows and 'iso:DE' not in rows
    assert equivalent_ids('iso:DE', entities) == {'iso:DE'}
    assert 'iso:FR' in rows


def test_explicit_france_metadata_restores_selector_without_changing_geometry():
    features = json.loads((ROOT / 'app/static/countries.geojson').read_text(encoding='utf-8'))['features']
    corrections = json.loads((ROOT / 'app/static/country-reference-metadata.json').read_text(encoding='utf-8'))
    before = deepcopy(features)
    names, metadata = map_boundaries.catalog(features, corrections)
    original_names = {f['properties']['ISO3166-1-Alpha-2']: f['properties']['name'] for f in features
                      if len(f['properties']['ISO3166-1-Alpha-2']) == 2 and f['properties']['ISO3166-1-Alpha-2'].isalpha()}
    assert names == {**original_names, 'FR': 'France'}
    assert names['FR'] == 'France' and metadata['FR']['expected_alpha_2'] == '-99'
    france = next(f for f in features if f['properties']['name'] == 'France')
    assert france['properties']['ISO3166-1-Alpha-2'] == '-99'
    assert features == before
    model = explorer_model(IntelligenceQuery(country_codes=('FR',)), [], {}, [], BERRIES)
    row = next(r for r in model['countries'] if r['iso'] == 'FR')
    assert row['id'] == 'iso:FR' and row['count'] == 0 and row['boundary_reference'] == metadata['FR']
    assert model['entries'] == []  # Boundary selection is not intelligence.
    # A renamed or recoded source feature requires another review.
    france['properties']['ISO3166-1-Alpha-2'] = 'XX'
    assert 'FR' not in map_boundaries.catalog(features, corrections)[0]
    assert map_boundaries.catalog(features, corrections)[1] == {}


def test_real_seven_country_capture_preserves_sparse_units_periods_and_payload():
    doc = source_capture()
    before = deepcopy(doc)
    groups = reference.eurostat_groups(doc['payload'], captured_at=doc['captured_at'])
    assert groups == doc['groups'] and doc == before
    assert len(groups) == 7 and sum(len(g['metrics']) for g in groups) == 14
    assert {g['country_id'] for g in groups} >= {'iso:FR', 'iso:IT', 'iso:PL'}
    assert all(g['period'] == '2025 calendar year' for g in groups)
    assert all([m['unit'] for m in g['metrics']] == ['1000 ha', '1000 t'] for g in groups)
    assert all('Yield' not in [m['label'] for m in g['metrics']] for g in groups)
    refresh.validate_groups(groups)
    assert doc['state'] == 'reference_capture_for_review'


@pytest.mark.parametrize('mutation', ['country_name', 'country_url', 'unknown_iso', 'mixed_crop'])
def test_country_source_mismatch_cannot_be_saved_as_an_official_check(mutation):
    group = deepcopy(next(g for g in source_capture()['groups'] if g['country_id'] == 'iso:FR'))
    if mutation == 'country_name': group['country'] = 'Italy'
    if mutation == 'country_url': group['source_url'] = group['source_url'].replace('geo=FR', 'geo=IT')
    if mutation == 'unknown_iso': group['country_id'] = 'iso:ZZ'
    if mutation == 'mixed_crop': group['source_url'] = group['source_url'].replace('S0000', 'F3000')
    with pytest.raises(ValueError):
        refresh.validate_groups([group])


@pytest.mark.parametrize('selection,expected', [
    ('iso:FR', {'iso:FR'}), ('iso:IT', {'iso:IT'}),
    ('iso:FR,geography-germany', {'iso:FR', 'geography-germany'}),
])
def test_iso_and_mixed_country_scope_agree_in_map_snapshot_and_source_inventory(selection, expected, tmp_path, monkeypatch):
    groups = source_capture()['groups']
    monkeypatch.setattr('app.services.map_workspace.reference_groups', lambda: deepcopy(groups))
    entities = {GERMANY['id']: GERMANY}
    query = IntelligenceQuery.parse(selection, 'berry-strawberry', entities, BERRIES)
    result = statistics(query, entities, [])
    snapshot = snapshot_model(query, [], entities, [], BERRIES, ['statistics'])
    assert {g['country_id'] for g in result['groups']} == expected
    assert snapshot['statistics']['groups'] == result['groups']
    assert len(snapshot['packet']['source_trace']) == len(expected)
    assert result['gaps'] == [] and result['trades'] == []
    blueberry = statistics(IntelligenceQuery.parse(selection, 'berry-blueberry', entities, BERRIES), entities, [])
    assert blueberry['groups'] == [] and len(blueberry['gaps']) == len(expected)


def test_saved_iso_reference_stays_visible_after_country_is_added_to_catalog(monkeypatch):
    groups = source_capture()['groups']
    monkeypatch.setattr('app.services.map_workspace.reference_groups', lambda: deepcopy(groups))
    france = {'id': 'geography-france', 'name': 'France', 'entity_type': 'geography',
              'attributes': {'iso_3166_1_alpha_2': 'FR'}}
    entities = {france['id']: france}
    query = IntelligenceQuery.parse('iso:FR', 'berry-strawberry', entities, BERRIES)
    assert query.geography_ids == ('geography-france',) and not query.country_codes
    result = statistics(query, entities, [])
    assert [g['country_id'] for g in result['groups']] == ['iso:FR']
    assert result['gaps'] == [] and groups == source_capture()['groups']


def test_iso_research_get_is_pure_and_explicit_post_reuses_public_scope_only(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'all_entities', lambda: [])
    monkeypatch.setattr(routes, 'references', lambda *args: [])
    submitted = []
    def submit(inbox, key, factory):
        submitted.append(deepcopy(research.load(inbox)['jobs'][key]['scope']))
    monkeypatch.setattr(research, 'submit', submit)
    client = TestClient(main.app)
    origin = '/explorer?countries=iso:FR&berry=berry-strawberry'
    page = client.get(routes.BASE, params={'return_to': origin})
    assert page.status_code == 200 and 'value="iso:FR" selected' in page.text
    assert list(tmp_path.iterdir()) == [] and submitted == []
    form = {'country': 'iso:FR', 'berry': 'berry-strawberry', 'token': 'explicit-iso-reference-token',
            'return_to': origin, 'notes': 'PRIVATE_NOTE_NOT_FOR_PROVIDER'}
    assert client.post(routes.BASE, data=form, follow_redirects=False).status_code == 303
    assert client.post(routes.BASE, data=form, follow_redirects=False).status_code == 303
    assert len(submitted) == 1 and submitted[0]['country_code'] == 'FR' and submitted[0]['country'] == 'France'
    assert 'PRIVATE_NOTE' not in str(submitted)
    assert research.load(tmp_path)['approved'] == []


def test_full_official_capture_requires_selection_then_remains_shared_runtime_context(tmp_path, monkeypatch):
    seed = ROOT / 'data/configuration/market_statistics_reference.json'
    original = seed.read_bytes()
    baseline = json.loads(original)['groups']
    groups = source_capture()['groups']
    key, _ = refresh.reserve(tmp_path, 'explicit-seven-country-review')
    refresh.update(tmp_path, key['id'], status='ready', message='Captured for review.', groups=groups)
    state = refresh.load(tmp_path)
    assert state['approved'] == [] and refresh.references(baseline, tmp_path, True) == baseline
    france = next(g for g in groups if g['country_id'] == 'iso:FR')
    refresh.apply(tmp_path, key['id'], [reference.group_id(france)], state['revision'], 'Fictional fixture analyst')
    assert refresh.load(tmp_path)['approved'] == [france]
    assert refresh.load(tmp_path)['history'][0]['before'] == []
    assert refresh.references(baseline, tmp_path, False) == baseline
    combined = refresh.references(baseline, tmp_path, True)
    assert combined[:-1] == baseline and combined[-1] == france and seed.read_bytes() == original
    monkeypatch.setattr('app.services.map_workspace.reference_groups', lambda: deepcopy(baseline))
    query = IntelligenceQuery.parse('iso:FR', 'berry-strawberry', {}, BERRIES)
    assert statistics(query, {}, [], inbox_dir=tmp_path, authoring=True)['groups']
    assert statistics(query, {}, [], inbox_dir=tmp_path, authoring=False)['groups'] == []


def test_iso_only_snapshot_pdf_names_the_country_and_preserves_original_units(monkeypatch):
    from app.services.report_builder import pdf_export
    paragraphs = []
    original = pdf_export.Paragraph
    def paragraph(text, style, **kwargs):
        paragraphs.append(text)
        return original(text, style, **kwargs)
    monkeypatch.setattr(pdf_export, 'Paragraph', paragraph)
    monkeypatch.setattr('app.services.map_workspace.reference_groups', lambda: deepcopy(source_capture()['groups']))
    query = IntelligenceQuery.parse('iso:FR', 'berry-strawberry', {}, BERRIES)
    model = snapshot_model(query, [], {}, [], BERRIES, ['statistics'])
    content = pdf_export.render_report_pdf(model['report'], model['packet'], model['coverage'])
    text = '\n'.join(paragraphs)
    assert content.startswith(b'%PDF') and 'France' in text and '1000 ha' in text and '1000 t' in text
    assert '2025 calendar year' in text and 'iso:FR' not in text
    assert 'Italy' not in text and 'Poland' not in text
    assert 'Countries: France' in text and 'canonical geography' not in text
    assert 'Latest source-data update: Oct 27, 2026' in text
    assert 'Latest dated source in scope: Oct 27' not in text
    assert not model['packet']['source_trace'][0]['published_date']
    assert model['coverage']['gaps'] == []
    assert 'Known Gaps' not in text and 'Private location annotations' not in text
