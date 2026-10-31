"""Official crop figures stay separate through capture, review and export."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import map_statistics_refresh as refresh
from app.services import market_statistics_reference as reference
from app.services.global_explorer import IntelligenceQuery, snapshot_model
from app.services.map_workspace import statistics
from app.services.report_builder import pdf_export
from scripts.capture_map_statistics import capture

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'data/imports/map-market-references-2026-10-31-three-crops/eurostat-berries.json'
BERRIES = {identity: name for identity, name in reference.EUROSTAT_CROPS.values()}


def document():
    return json.loads(CAPTURE.read_text(encoding='utf-8'))


def test_original_three_crop_response_reproduces_every_group_without_seed_writes(tmp_path):
    doc = document()
    original = deepcopy(doc)
    baseline = (ROOT / 'data/configuration/market_statistics_reference.json').read_bytes()
    calls = []
    def fetch(**kwargs):
        calls.append(kwargs)
        return deepcopy(doc['payload'])
    file, groups = capture(output_dir=tmp_path, fetch=fetch, now=datetime.fromisoformat(doc['captured_at']))
    assert groups == doc['groups'] and doc == original
    assert len(groups) == 21 and sum(len(g['metrics']) for g in groups) == 42
    assert calls == [{'crops': ['S0000', 'F3200', 'F3300'], 'geos': list(reference.GEOS), 'since_year': 2023}]
    assert json.loads(file.read_text())['payload'] == doc['payload']
    assert all(g['period'] == '2025 calendar year' for g in groups)
    assert {g['berry_id'] for g in groups} == set(BERRIES)
    assert all([m['unit'] for m in g['metrics']] == ['1000 ha', '1000 t'] for g in groups)
    assert all(g['published_date'] == 'Not supplied' for g in groups)
    refresh.validate_groups(groups)
    assert (ROOT / 'data/configuration/market_statistics_reference.json').read_bytes() == baseline


def test_each_crop_keeps_its_own_latest_populated_year_zero_and_confidential_cells():
    categories = {'freq': ['A'], 'crops': ['S0000', 'F3300'],
                  'strucpro': ['AR_THS_HA', 'HPRD_HUMD_EU_THS_T'],
                  'geo': ['PL'], 'time': ['2024', '2025', '2026']}
    payload = {'id': list(categories), 'size': [len(v) for v in categories.values()],
               'dimension': {k: {'category': {'index': {v: i for i, v in enumerate(values)}}}
                             for k, values in categories.items()},
               'value': {'1': 2.0, '4': 9.0, '6': 0, '9': 3.5, '10': 99},
               'status': {'4': 'p', '9': 'e', '10': 'c'}}
    before = deepcopy(payload)
    groups = reference.eurostat_groups(payload, captured_at='2026-10-31T00:00:00+00:00')
    by_crop = {g['berry_id']: g for g in groups}
    assert by_crop['berry-strawberry']['period'] == '2025 calendar year'
    assert by_crop['berry-blueberry']['period'] == '2024 calendar year'
    assert [m['value'] for m in by_crop['berry-blueberry']['metrics']] == [0, 3.5]
    assert by_crop['berry-blueberry']['metrics'][1]['source_flag'] == 'e'
    assert payload == before and all('Yield' not in [m['label'] for m in g['metrics']] for g in groups)


@pytest.mark.parametrize('code', ['F3000', 'F3900', 'F4300', 'S0000S'])
def test_combined_other_and_different_categories_cannot_be_saved_as_a_named_berry(code):
    payload = document()['payload']
    crops = payload['dimension']['crops']['category']['index']
    crops[code] = crops.pop('F3300')
    with pytest.raises(ValueError, match='separately reported'):
        reference.eurostat_groups(payload, captured_at=document()['captured_at'])


@pytest.mark.parametrize('change', ['crop_url', 'berry_id', 'commodity', 'duplicate'])
def test_country_crop_identity_and_original_url_must_agree(change):
    groups = document()['groups']
    group = next(g for g in groups if g['berry_id'] == 'berry-blueberry')
    if change == 'crop_url': group['source_url'] = group['source_url'].replace('F3300', 'S0000')
    if change == 'berry_id': group['berry_id'] = 'berry-blackberry'
    if change == 'commodity': group['commodity'] = 'Strawberries'
    if change == 'duplicate': groups.append(deepcopy(group))
    with pytest.raises(ValueError):
        refresh.validate_groups(groups)


@pytest.mark.parametrize('flag', ['c', 'C', 'N', 'P', 'm', 'z', 'eC', 'pN'])
def test_withheld_or_missing_cells_cannot_be_proposed_or_saved(flag):
    doc = document()
    payload = doc['payload']
    payload['status'] = {key: flag for key in payload['value']}
    with pytest.raises(ValueError, match='No populated'):
        reference.eurostat_groups(payload, captured_at=doc['captured_at'])
    group = doc['groups'][0]
    group['metrics'][0]['source_flag'] = flag
    with pytest.raises(ValueError):
        refresh.validate_groups([group])


def test_small_values_and_estimates_are_readable_without_changing_original_flags():
    france = next(g for g in document()['groups'] if g['country_id'] == 'iso:FR' and g['berry_id'] == 'berry-blueberry')
    assert [(m['value'], m['source_flag']) for m in france['metrics']] == [(0.0, 'n'), (0.0, 'n')]
    refresh.validate_groups([france])
    assert 'not a true zero' in reference.flag_label('n')
    assert reference.flag_label('ep') == 'Estimated; Provisional'
    assert reference.flag_label('x') == 'Source flag: x'


def test_selecting_one_crop_preserves_other_crops_history_and_public_data(tmp_path, monkeypatch):
    groups = document()['groups']
    baseline = reference.reference_groups()
    seed = (ROOT / 'data/configuration/market_statistics_reference.json').read_bytes()
    job, _ = refresh.reserve(tmp_path, 'explicit-three-crop-selection')
    refresh.update(tmp_path, job['id'], status='ready', message='Ready.', groups=groups)
    state = refresh.load(tmp_path)
    assert state['approved'] == [] and refresh.references(baseline, tmp_path, True) == baseline
    selected = next(g for g in groups if g['country_id'] == 'iso:FR' and g['berry_id'] == 'berry-blueberry')
    refresh.apply(tmp_path, job['id'], [reference.group_id(selected)], state['revision'], 'Fictional analyst')
    saved = refresh.path(tmp_path).read_bytes()
    assert refresh.load(tmp_path)['approved'] == [selected]
    assert refresh.load(tmp_path)['history'][0]['before'] == []
    assert refresh.references(baseline, tmp_path, True) == baseline + [selected]
    assert refresh.references(baseline, tmp_path, False) == baseline
    assert not refresh.apply(tmp_path, job['id'], [reference.group_id(selected)], refresh.load(tmp_path)['revision'], 'Fictional analyst')
    assert refresh.path(tmp_path).read_bytes() == saved
    monkeypatch.setattr('app.services.map_workspace.reference_groups', lambda: deepcopy(baseline))
    query = IntelligenceQuery.parse('iso:FR', 'berry-blueberry', {}, BERRIES)
    model = snapshot_model(query, [], {}, [], BERRIES, ['statistics'], inbox_dir=tmp_path, authoring=True)
    assert model['statistics']['groups'] == statistics(query, {}, [], inbox_dir=tmp_path, authoring=True)['groups']
    assert [g['berry_id'] for g in model['statistics']['groups']] == ['berry-blueberry']
    assert not statistics(query, {}, [], inbox_dir=tmp_path, authoring=False)['groups']
    strawberry = IntelligenceQuery.parse('iso:FR', 'berry-strawberry', {}, BERRIES)
    assert not statistics(strawberry, {}, [], inbox_dir=tmp_path, authoring=True)['groups']
    assert (ROOT / 'data/configuration/market_statistics_reference.json').read_bytes() == seed


def test_blueberry_snapshot_pdf_has_only_selected_crop_and_original_source_units(monkeypatch):
    monkeypatch.setattr('app.services.map_workspace.reference_groups', lambda: deepcopy(document()['groups']))
    paragraphs = []
    original = pdf_export.Paragraph
    def paragraph(text, style, **kwargs):
        paragraphs.append(text)
        return original(text, style, **kwargs)
    monkeypatch.setattr(pdf_export, 'Paragraph', paragraph)
    query = IntelligenceQuery.parse('iso:PL', 'berry-blueberry', {}, BERRIES)
    model = snapshot_model(query, [], {}, [], BERRIES, ['statistics'])
    content = pdf_export.render_report_pdf(model['report'], model['packet'], model['coverage'])
    text = '\n'.join(paragraphs)
    assert content.startswith(b'%PDF') and 'Poland' in text and 'Blueberries' in text
    assert 'Raspberries' not in text and 'Strawberries' not in text
    assert '1000 ha' in text and '1000 t' in text and '2025 calendar year' in text
    assert 'crops=F3300' in model['packet']['source_trace'][0]['source_url']
    assert not model['packet']['source_trace'][0]['published_date']


def test_review_get_names_crops_and_pair_count_without_fetching_or_saving(tmp_path, monkeypatch):
    job, _ = refresh.reserve(tmp_path, 'explicit-three-crop-page-review')
    refresh.update(tmp_path, job['id'], status='ready', message='Ready.', groups=document()['groups'])
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(refresh, 'capture', lambda **kw: pytest.fail('GET must never fetch.'))
    before = refresh.path(tmp_path).read_bytes()
    page = TestClient(main.app).get('/explorer/statistics')
    assert page.status_code == 200 and '21 country / crop references' in page.text
    assert 'France · Blueberries' in page.text and 'France · Strawberries' in page.text
    assert 'Blackberry has no separate category' in page.text
    assert 'not a true zero' in page.text and 'Estimated · original flag e' in page.text
    assert '21 countries' not in page.text and refresh.path(tmp_path).read_bytes() == before
