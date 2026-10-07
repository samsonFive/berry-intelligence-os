"""External coverage is independent, reversible and never a trust shortcut."""
import csv
from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app import main
from app.services.variety_external_coverage import analyze_gdr_csv, compare_baseline, external_coverage_view, load_external_baselines

ROOT = Path(__file__).resolve().parents[1]


def export(tmp_path, rows):
    path = tmp_path / 'public.csv'
    fields = ['Unique Name', 'Type', 'Organism', 'Cultivar', 'Accession', 'Institutional Name', 'Dataset',
              'Name', 'Alias', 'Sample Name', 'Pedigree', 'Legend']
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({'Type': 'accession', 'Organism': 'Rubus idaeus', **row})
    return path


def analyze(tmp_path, rows, count):
    return analyze_gdr_csv(export(tmp_path, rows), checked_on='2026-10-07', reported_stocks=count)


def test_dataset_joins_do_not_inflate_labels_or_collection_keys(tmp_path):
    result = analyze(tmp_path, [{'Unique Name': 'PI 1', 'Cultivar': 'Lewis', 'Dataset': dataset} for dataset in ['a', 'b', 'b']], 1)
    assert result['totals']['export_rows'] == 3 and result['totals']['stock_organism_keys'] == 1
    assert result['totals']['genus_label_keys'] == 1
    assert result['entries'][0]['references'][0]['datasets'] == ['a', 'b']


def test_namesake_stock_and_genus_collisions_remain_separate(tmp_path):
    result = analyze(tmp_path, [{'Unique Name': 'Same', 'Cultivar': 'Shared', 'Organism': org}
                               for org in ['Rubus idaeus', 'Rubus hybrid', 'Fragaria x ananassa']], 3)
    assert result['totals']['stock_organism_keys'] == 3 and result['totals']['distinct_cultivar_labels'] == 1
    assert result['totals']['genus_label_keys'] == 2
    rubus = next(row for row in result['entries'] if row['genus'] == 'Rubus')
    assert len(rubus['references']) == 2


def test_only_literal_cultivar_field_supplies_labels_not_aliases_samples_or_parents(tmp_path):
    result = analyze(tmp_path, [{'Unique Name': 'PI 9', 'Name': 'NotACultivar', 'Alias': 'DoNotImport',
        'Sample Name': 'Chip42', 'Pedigree': 'Parent1 x Parent2', 'Legend': 'private body'},
        {'Unique Name': 'PI 10', 'Cultivar': 'ORUS_1234-1'}], 2)
    assert [row['name'] for row in result['entries']] == ['ORUS_1234-1']
    assert result['totals']['stocks_without_cultivar_label'] == 1
    assert all(text not in json.dumps(result) for text in ['NotACultivar', 'DoNotImport', 'Chip42', 'Parent1', 'private body'])


def test_shared_stock_key_with_conflicting_labels_warns_instead_of_silently_choosing(tmp_path):
    result = analyze(tmp_path, [{'Unique Name': 'PI 1', 'Cultivar': name} for name in ['First', 'Second']], 1)
    assert result['totals']['stocks_with_multiple_cultivar_labels'] == 1
    assert result['entries'][0]['references'][0]['other_cultivar_labels'] == ['Second']


@pytest.mark.parametrize('org,typ,count', [('Malus x domestica', 'accession', 1), ('Rubus idaeus', 'population', 1),
                                         ('Rubus idaeus', 'accession', 2)])
def test_wrong_crop_population_and_unexplained_count_shortfalls_fail_closed(tmp_path, org, typ, count):
    with pytest.raises(ValueError):
        analyze(tmp_path, [{'Unique Name': 'PI 1', 'Cultivar': 'Lewis', 'Organism': org, 'Type': typ}], count)


def test_native_query_scope_is_distinct_from_returned_species(tmp_path):
    path = export(tmp_path, [{'Unique Name': 'PI 1', 'Cultivar': 'Lewis'}])
    query = ['Rubus idaeus', 'Fragaria vesca']
    result = analyze_gdr_csv(path, checked_on='2026-10-07', reported_stocks=1, query_organisms=query)
    assert result['query']['selected_organisms'] == sorted(query)
    assert result['observed_organisms'] == ['Rubus idaeus']
    with pytest.raises(ValueError):
        analyze_gdr_csv(path, checked_on='2026-10-07', reported_stocks=1, query_organisms=['Fragaria vesca'])


def test_live_comparison_preserves_ambiguity_crop_boundaries_and_human_decisions(tmp_path):
    baseline = analyze(tmp_path, [{'Unique Name': 'PI 1', 'Cultivar': 'Shared'},
        {'Unique Name': 'PI 2', 'Cultivar': 'Declined'}, {'Unique Name': 'PI 3', 'Cultivar': 'Bluecrop'}], 3)
    varieties = [{'id': key, 'name': 'Shared', 'berry_ids': [berry]} for key, berry in [('r', 'berry-raspberry'), ('b', 'berry-blackberry')]]
    varieties += [{'id': 'blue', 'name': 'Bluecrop', 'berry_ids': ['berry-blueberry']}]
    candidate = {'id': 'human', 'candidate_name': 'Declined', 'berry_id': 'berry-raspberry', 'status': 'rejected',
                 'human_gated': True, 'review_notes': 'Not a release', 'knowledge': {'notes': 'User edit'}}
    original = deepcopy((baseline, varieties, candidate))
    report = compare_baseline(baseline, varieties=varieties, candidates=[candidate])
    shared = next(row for row in report['entries'] if row['name'] == 'Shared')
    assert {match['id'] for match in shared['catalog_matches']} == {'r', 'b'}
    assert next(row for row in report['entries'] if row['name'] == 'Bluecrop')['status'] == 'no_name_match'
    declined = next(row for row in report['entries'] if row['name'] == 'Declined')['candidate_matches'][0]
    assert declined['human_gated'] and declined['status'] == 'rejected'
    assert (baseline, varieties, candidate) == original


def test_search_and_pagination_retain_names_and_accession_scope(tmp_path):
    baseline = analyze(tmp_path, [{'Unique Name': f'PI {i}', 'Cultivar': f'Name {i:03d}'} for i in range(70)], 70)
    view = external_coverage_view(baselines=[baseline], varieties=[], candidates=[], filters={})
    assert len(view['entries']) == 50 and view['pages'] == 2 and 'external_page=2' in view['next_href']
    view = external_coverage_view(baselines=[baseline], varieties=[], candidates=[], filters={'external_q': 'PI 69'})
    assert view['filtered_count'] == 1 and view['entries'][0]['name'] == 'Name 069'
    view = external_coverage_view(baselines=[baseline], varieties=[], candidates=[], filters={'external_page': '999'})
    assert view['page'] == 2 and len(view['entries']) == 20


def test_captured_export_is_fully_accounted_and_body_free():
    report = load_external_baselines(ROOT / 'data')[0]
    assert report['totals']['export_rows'] == 26905
    assert report['totals']['stock_organism_keys'] == report['totals']['reported_stocks'] == 6453
    assert report['totals']['distinct_cultivar_labels'] == 2355 and len(report['entries']) == 2372
    assert len(report['query']['selected_organisms']) == 203
    assert report['input_sha256'] == 'c9c5b70aa6e3116f5d9982004cb3ebfaef9c8765d619d65d797b59b8b17d9d00'
    assert all(set(row) == {'genus', 'name', 'export_rows', 'references'} for row in report['entries'])
    assert not any(key in json.dumps(report) for key in ['Pedigree', 'Legend', 'Sample Name', 'Image Name'])


def test_saved_snapshot_rejects_duplicate_labels_and_wrong_genus_references(tmp_path):
    baseline = analyze(tmp_path, [{'Unique Name': 'PI 1', 'Cultivar': 'Lewis'}], 1)
    folder = tmp_path / 'imports/variety-external-baseline-test'
    folder.mkdir(parents=True)
    path = folder / 'comparison.json'
    baseline['entries'].append(deepcopy(baseline['entries'][0]))
    baseline['totals']['genus_label_keys'] = 2
    path.write_text(json.dumps(baseline), encoding='utf-8')
    with pytest.raises(ValueError, match='repeats'):
        load_external_baselines(tmp_path)
    baseline['entries'].pop()
    baseline['totals']['genus_label_keys'] = 1
    baseline['entries'][0]['references'][0]['organism'] = 'Malus x domestica'
    path.write_text(json.dumps(baseline), encoding='utf-8')
    with pytest.raises(ValueError, match='scope'):
        load_external_baselines(tmp_path)


def test_coverage_page_comparison_is_read_only_and_authoring_only(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    before = sorted(tmp_path.rglob('*'))
    page = client.get('/varieties/coverage?external_q=Lewis&external_status=')
    assert page.status_code == 200 and 'Missing names in public collections' in page.text
    assert 'PI 553534' in page.text and 'Blueberries are outside this comparison' in page.text
    assert sorted(tmp_path.rglob('*')) == before
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert 'Missing names in public collections' not in client.get('/varieties/coverage').text
