import copy
import json

import pytest

from scripts.save_direct_research_batch import prepare, save


@pytest.fixture
def direct_packet(tmp_path):
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    files = {
        'research-coverage-checklist.json': {
            'inventory_version': 'test-v1', 'rubric_version': 'test-r1',
            'batches': [{'batch_id': 'B16', 'entity_ids': ['company-one', 'company-two']}]},
        'commercial-entity-inventory.json': {'entities': [
            {'entity_id': 'company-one'}, {'entity_id': 'company-two'}]},
        'capability-rubrics.json': {'capabilities': [{'capability_id': 'breeder.program'}]},
    }
    for name, data in files.items():
        (snapshot / name).write_text(json.dumps(data), encoding='utf-8')
    packet = {
        'batch_id': 'B16', 'research_date': '2026-10-30',
        'coverage_summary': 'Test only', 'search_passes': [{'purpose': 'Inspected original'}],
        'profiles': [{'entity_id': 'company-one', 'resolved_name': 'García'},
                     {'entity_id': 'company-two'}],
        'sources': [{'source_id': 'B16-S001', 'original_url': 'https://example.org/original'}],
        'observations': [{'entity_id': 'company-one', 'capability_id': 'breeder.program',
                          'value_or_statement': '0.000', 'source_ids': 'B16-S001'}],
        'gaps': [{'entity_id': 'company-one'}, {'entity_id': 'company-two'}],
    }
    return snapshot, packet


def test_revision_preserves_unicode_unknown_precision_and_original(direct_packet, tmp_path):
    snapshot, packet = direct_packet
    output = tmp_path / 'private'
    first = save(packet, output=output, snapshot=snapshot)
    assert save(packet, output=output, snapshot=snapshot) == first
    original = output / first['revision_path'] / 'authored-research.json'
    assert json.loads(original.read_text(encoding='utf-8')) == packet
    tables = json.loads((original.parent / 'contract-tables.json').read_text(encoding='utf-8'))
    assert tables['tables']['profiles']['rows'][0]['resolved_name'] == 'García'
    row = tables['tables']['observations']['rows'][0]
    assert row['value_or_statement'] == '0.000'
    assert row['destination_scope'] == 'Unknown'
    changed = copy.deepcopy(packet)
    changed['observations'][0]['value_or_statement'] = 'Unknown'
    second = save(changed, output=output, snapshot=snapshot)
    assert second['sha256'] != first['sha256']
    assert json.loads(original.read_text(encoding='utf-8')) == packet
    assert 'no_application_import_or_ratings' in tables['metadata']['trust_status']


@pytest.mark.parametrize('mutation', ['missing_profile', 'missing_gap', 'missing_source', 'unknown_capability', 'unknown_target', 'unexpected_field'])
def test_contract_rejects_lossy_or_misidentified_records(direct_packet, mutation):
    snapshot, packet = direct_packet
    if mutation == 'missing_profile':
        packet['profiles'].pop()
    elif mutation == 'missing_gap':
        packet['gaps'].pop()
    elif mutation == 'missing_source':
        packet['sources'] = []
    elif mutation == 'unknown_capability':
        packet['observations'][0]['capability_id'] = 'invented.capability'
    elif mutation == 'unknown_target':
        packet['relationships'] = [{'subject_entity_id': 'company-one',
                                   'object_entity_id_or_proposed_name': 'company-guessed'}]
    else:
        packet['observations'][0]['accidentally_dropped_field'] = 'keep me'
    with pytest.raises(ValueError):
        prepare(packet, snapshot=snapshot)
