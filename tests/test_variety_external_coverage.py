"""External coverage is independent, reversible and never a trust shortcut."""
import csv
from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app import main
from app.services.variety_external_coverage import analyze_gdr_csv, analyze_grin_values, compare_baseline, external_coverage_view, load_external_baselines, prepare_blueberry_identity_lead

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
    assert 'PI 553534' in page.text and 'four checked blueberry species' in page.text
    assert sorted(tmp_path.rglob('*')) == before
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert 'Missing names in public collections' not in client.get('/varieties/coverage').text


def grin(tmp_path, rows):
    headers = [None, 'ACCESSION', 'PLANT NAME', 'TAXONOMY', 'ORIGIN', 'GENEBANK', 'AVAILABILITY',
               'RECEIVED', 'SOURCE TYPE', 'SOURCE DATE', 'COLLECTION SITE', 'COORDINATES', 'ELEVATION',
               'HABITAT', 'IMPROVEMENT LEVEL', 'NARRATIVE', None]
    values = [["Search Accessions GRIN-Global", *([None] * 16)], headers]
    for row in rows:
        fields = {'TAXONOMY': 'Vaccinium corymbosum L. ', 'GENEBANK': 'COR', 'IMPROVEMENT LEVEL': 'Cultivar', **row}
        values.append([fields.get(key) for key in headers])
    workbook = tmp_path / 'retained.xlsx'
    workbook.write_bytes(b'fixture retained workbook')
    return analyze_grin_values(values, workbook_path=workbook, checked_on='2026-10-07', reported_accessions=len(rows))


def test_grin_reconciles_taxonomy_and_material_without_treating_search_hits_as_blueberries(tmp_path):
    report = grin(tmp_path, [
        {'ACCESSION': 'PI 1', 'PLANT NAME': 'Bluecrop'},
        {'ACCESSION': 'PI 2', 'PLANT NAME': 'Bluecrop'},
        {'ACCESSION': 'PI 3', 'PLANT NAME': 'Bluecrop', 'TAXONOMY': 'Vaccinium hybr.'},
        {'ACCESSION': 'PI 4', 'PLANT NAME': 'Cranberry', 'TAXONOMY': 'Vaccinium macrocarpon Aiton'},
        {'ACCESSION': 'PI 5', 'PLANT NAME': 'Wild1', 'IMPROVEMENT LEVEL': 'Wild material'},
        {'ACCESSION': 'PI 6', 'PLANT NAME': 'Breeding1', 'IMPROVEMENT LEVEL': 'Breeding material'},
        {'ACCESSION': 'PI 7', 'PLANT NAME': 'Synonym search hit', 'TAXONOMY': 'Gaylussacia brachycera (Michx.) A. Gray',
         'IMPROVEMENT LEVEL': None},
    ])
    assert report['dispositions'] == {'blueberry': 2, 'crop_unresolved': 1, 'other_taxon_cultivar': 1, 'other_material': 3}
    assert report['totals']['genus_label_keys'] == 2 and report['totals']['distinct_cultivar_labels'] == 1
    assert report['totals']['source_distinct_cultivar_labels'] == 2
    assert report['totals']['other_genus_records'] == 1
    assert len(report['entries'][0]['references']) == 2
    assert {'Cranberry', 'Wild1', 'Breeding1', 'Synonym search hit'}.isdisjoint(row['name'] for row in report['entries'])


def test_grin_withholds_generic_hybrid_matches_even_if_a_blueberry_has_the_same_name(tmp_path):
    baseline = grin(tmp_path, [{'ACCESSION': 'PI 1', 'PLANT NAME': 'Echo', 'TAXONOMY': 'Vaccinium hybr.'},
                              {'ACCESSION': 'PI 2', 'PLANT NAME': 'Bluecrop'}])
    varieties = [{'id': 'echo', 'name': 'Echo', 'berry_ids': ['berry-blueberry']},
                 {'id': 'wrong-crop', 'name': 'Bluecrop', 'berry_ids': ['berry-raspberry']}]
    candidates = [{'id': 'candidate', 'candidate_name': 'Echo', 'berry_id': 'berry-blueberry', 'status': 'rejected'}]
    original = deepcopy((baseline, varieties, candidates))
    report = compare_baseline(baseline, varieties=varieties, candidates=candidates)
    echo = next(row for row in report['entries'] if row['name'] == 'Echo')
    assert echo['status'] == 'crop_scope_needed' and not echo['catalog_matches'] and not echo['candidate_matches']
    assert next(row for row in report['entries'] if row['name'] == 'Bluecrop')['status'] == 'no_name_match'
    assert (baseline, varieties, candidates) == original


def test_grin_identifiers_dates_origin_and_narrative_never_become_alias_traits_or_regions(tmp_path):
    report = grin(tmp_path, [{'ACCESSION': 'PI 1', 'PLANT NAME': 'Literal name', 'GENEBANK': None,
        'SOURCE DATE': 1935, 'RECEIVED': 1980, 'ORIGIN': 'Not a growing region', 'COLLECTION SITE': 'Private site',
        'COORDINATES': 'Exact location', 'NARRATIVE': 'Alias inferred from body'}])
    assert report['entries'][0]['name'] == 'Literal name'
    assert report['entries'][0]['references'][0]['institutional_name'] == ''
    text = json.dumps(report)
    assert all(value not in text for value in ['1935', '1980', 'Not a growing region', 'Private site', 'Exact location', 'Alias inferred'])


@pytest.mark.parametrize('rows', [
    [{'ACCESSION': 'PI 1', 'PLANT NAME': 'First'}, {'ACCESSION': 'PI 1', 'PLANT NAME': 'Second'}],
    [{'ACCESSION': 'PI 1', 'PLANT NAME': None}], [{'ACCESSION': 'PI 1', 'PLANT NAME': 'Name', 'TAXONOMY': None}],
])
def test_grin_duplicate_accessions_and_incomplete_cultivar_records_fail_closed(tmp_path, rows):
    with pytest.raises(ValueError):
        grin(tmp_path, rows)


@pytest.mark.parametrize('mutation', ['scope', 'classification', 'population', 'identifier'])
def test_saved_grin_snapshot_rejects_classification_and_population_tampering(tmp_path, mutation):
    report = grin(tmp_path, [{'ACCESSION': 'PI 1', 'PLANT NAME': 'Bluecrop'}])
    if mutation == 'scope':
        report['entries'][0]['references'][0]['organism'] = 'Vaccinium macrocarpon Aiton'
    elif mutation == 'classification':
        report['entries'][0]['references'][0]['improvement_level'] = 'Wild material'
    elif mutation == 'population':
        report['dispositions']['other_material'] = 99
    else:
        report['entries'][0]['references'].append(deepcopy(report['entries'][0]['references'][0]))
        report['entries'][0]['export_rows'] = 2
    folder = tmp_path / 'imports/variety-external-baseline-grin'
    folder.mkdir(parents=True)
    (folder / 'comparison.json').write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises(ValueError):
        load_external_baselines(tmp_path)


def test_real_grin_baseline_reconciles_the_native_query_and_holds_uncertain_hybrids():
    report = next(row for row in load_external_baselines(ROOT / 'data') if row['id'] == 'grin-vaccinium-cultivars')
    assert report['totals']['export_rows'] == 2113
    assert report['totals']['source_cultivar_records'] == 315
    assert report['totals']['source_distinct_cultivar_labels'] == 273
    assert report['dispositions'] == {'other_material': 1798, 'blueberry': 178, 'crop_unresolved': 57, 'other_taxon_cultivar': 80}
    assert report['totals']['other_genus_records'] == 95
    assert len([row for row in report['entries'] if row['berry_scope'] == 'blueberry']) == 148
    assert len([row for row in report['entries'] if row['berry_scope'] == 'crop_unresolved']) == 53
    assert report['input_sha256'] == '4c39cc37a8a432a5ef153f44d72187c614c79ef173161ba65c73fc7712c15c7d'
    assert not any(key in json.dumps(report) for key in ['NARRATIVE', 'COLLECTION SITE', 'COORDINATES', 'ORIGIN', 'RECEIVED'])
    view = external_coverage_view(baselines=[report], varieties=[], candidates=[],
        filters={'external_genus': 'Vaccinium', 'external_status': 'crop_scope_needed', 'external_q': 'Echo'})
    assert view['filtered_count'] == 1 and view['entries'][0]['status'] == 'crop_scope_needed'


def test_individual_lead_uses_existing_untrusted_candidate_contract_without_approving_source_or_identity(tmp_path):
    report = grin(tmp_path, [{'ACCESSION': 'PI 1', 'PLANT NAME': 'Bluecrop'}])
    plan = prepare_blueberry_identity_lead(baselines=[report], baseline_id=report['id'], name='Bluecrop',
        input_sha256=report['input_sha256'], varieties=[], candidates=[])
    candidate = plan['candidate']
    assert candidate['status'] == 'proposed' and not candidate['human_gated'] and not candidate['auto_confirmed']
    assert candidate['berry_id'] == 'berry-blueberry'
    assert candidate['source_tier'] == 'weak_noncanonical_lead'
    assert not candidate['source_id'] and not candidate['registration']['official_registry_source']
    assert not candidate['aliases'] and not candidate['breeder_owner'] and not candidate['deployment']
    assert candidate['external_collection']['references'][0]['unique_name'] == 'PI 1'
    assert candidate['id'] in plan['href']
    edited = {**candidate, 'candidate_name': 'User corrected name', 'status': 'rejected', 'human_gated': True,
              'review_notes': 'User decision'}
    original = deepcopy(edited)
    repeated = prepare_blueberry_identity_lead(baselines=[report], baseline_id=report['id'], name='Bluecrop',
        input_sha256=report['input_sha256'], varieties=[], candidates=[edited])
    assert repeated['candidate'] is None and candidate['id'] in repeated['href'] and 'User+corrected+name' in repeated['href']
    assert edited == original


@pytest.mark.parametrize('case', ['hybrid', 'stale', 'unknown'])
def test_lead_handoff_rejects_unassigned_crop_stale_snapshot_and_invented_names(tmp_path, case):
    baseline = grin(tmp_path, [{'ACCESSION': 'PI 1', 'PLANT NAME': 'Echo', 'TAXONOMY': 'Vaccinium hybr.'},
                              {'ACCESSION': 'PI 2', 'PLANT NAME': 'Bluecrop'}])
    with pytest.raises(ValueError):
        prepare_blueberry_identity_lead(baselines=[baseline], baseline_id=baseline['id'],
            name={'hybrid': 'Echo', 'stale': 'Bluecrop', 'unknown': 'Invented'}[case],
            input_sha256='wrong' if case == 'stale' else baseline['input_sha256'], varieties=[], candidates=[])


def test_lead_handoff_redirects_existing_catalog_or_multiple_candidates_without_selecting_an_identity(tmp_path):
    baseline = grin(tmp_path, [{'ACCESSION': 'PI 1', 'PLANT NAME': 'Bluecrop'}])
    args = dict(baselines=[baseline], baseline_id=baseline['id'], name='Bluecrop', input_sha256=baseline['input_sha256'])
    catalog = prepare_blueberry_identity_lead(**args,
        varieties=[{'id': 'bluecrop', 'name': 'Bluecrop', 'berry_ids': ['berry-blueberry']}], candidates=[])
    assert catalog == {'candidate': None, 'href': '/entities/variety/bluecrop'}
    candidates = [{'id': key, 'candidate_name': 'Bluecrop', 'berry_id': 'berry-blueberry', 'status': 'rejected'} for key in ['one', 'two']]
    original = deepcopy(candidates)
    plan = prepare_blueberry_identity_lead(**args, varieties=[], candidates=candidates)
    assert plan['candidate'] is None and '/varieties/candidates?' in plan['href'] and '#' not in plan['href']
    assert candidates == original


def test_post_adds_only_one_private_lead_preserves_edits_and_requires_same_origin_authoring(monkeypatch, tmp_path):
    from app.services.variety_universe.candidates import load_variety_candidates
    baseline = next(row for row in load_external_baselines(ROOT / 'data') if row['id'] == 'grin-vaccinium-cultivars')
    name = next(row['name'] for row in baseline['entries'] if row['berry_scope'] == 'blueberry')
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'DATA_DIR', ROOT / 'data')
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'variety_candidate_universe', lambda: ([], load_variety_candidates(tmp_path), {}))
    client = TestClient(main.app)
    form = {'baseline_id': baseline['id'], 'name': name, 'input_sha256': baseline['input_sha256']}
    assert client.post('/varieties/external/identity-lead', data=form, headers={'origin': 'https://wrong.example'}, follow_redirects=False).status_code == 403
    assert not list(tmp_path.rglob('*.json'))
    assert client.post('/varieties/external/identity-lead', data=form, follow_redirects=False).status_code == 303
    files = list(tmp_path.rglob('*.json'))
    assert len(files) == 1 and files[0].parent.name == 'variety_candidates'
    candidate = json.loads(files[0].read_text(encoding='utf-8'))
    candidate.update(candidate_name='User edit', status='rejected', human_gated=True, review_notes='Preserve me')
    files[0].write_text(json.dumps(candidate), encoding='utf-8')
    before = files[0].read_bytes()
    assert client.post('/varieties/external/identity-lead', data=form, follow_redirects=False).status_code == 303
    assert files[0].read_bytes() == before and len(list(tmp_path.rglob('*.json'))) == 1
    assert client.post('/varieties/external/identity-lead', data={**form, 'input_sha256': 'stale'}, follow_redirects=False).status_code == 422
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.post('/varieties/external/identity-lead', data=form, follow_redirects=False).status_code == 403
