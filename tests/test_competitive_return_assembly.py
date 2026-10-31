from scripts.assemble_competitive_research_returns import parse_table, md_cell


def test_reassembly_preserves_conflicts_and_rejects_changed_original(tmp_path):
    import json
    import pytest
    from scripts.capture_competitive_web_returns import capture
    from scripts.assemble_competitive_research_returns import assemble

    downloads, output, inventory = (tmp_path / n for n in ('downloads', 'output', 'inventory'))
    downloads.mkdir()
    inventory.mkdir()
    (inventory / 'commercial-entity-inventory.json').write_text(json.dumps({
        'inventory_version': 'test-v1', 'entities': [{'entity_id': 'company-one'}]}))
    (inventory / 'capability-rubrics.json').write_text(json.dumps({
        'capabilities': [{'capability_id': 'grower.scale'}]}))
    (downloads / 'Field-Value.csv').write_text('Field,Value\nbatch_id,B01\ninventory_version,test-v1\n')
    (downloads / 'observationid-entityid.csv').write_text(
        'observation_id,entity_id,capability_id,value_or_statement,source_ids\n'
        'B01-O001,company-one,grower.scale,0.000,B01-S001\n')
    (downloads / 'observationid-entityid (1).csv').write_text(
        'observation_id,entity_id,capability_id,value_or_statement,source_ids\n'
        'B01-O001,company-one,grower.scale,Unknown,B01-S999\n')
    (downloads / 'sourceid-originalurl.csv').write_text(
        'source_id,original_url\nB01-S001,https://example.org/original\n')
    capture(downloads, output, since=0)
    first = assemble(output, inventory)
    candidate = output / 'assembled/B01/candidate-records.json'
    original_candidate = candidate.read_bytes()
    result = json.loads(original_candidate)
    observations = [r for r in result['records'] if r['record_kind'] == 'observation']
    assert {r['fields']['value_or_statement'] for r in observations} == {'Unknown', '0.000'}
    assert all(r['verification_status'] == 'pending_original_source_inspection' for r in result['records'])
    assert any('Conflicting' in r.get('reason', '') for r in result['unresolved'])
    assert any('Missing source ledger' in ' '.join(r.get('reasons', [])) for r in result['unresolved'])
    assert assemble(output, inventory) == first
    assert candidate.read_bytes() == original_candidate
    assert assemble(output, inventory, verify_existing=True) == first
    modified = json.loads(original_candidate)
    modified['records'][0]['fields']['value_or_statement'] = 'Edited candidate must not pass as original'
    candidate.write_text(json.dumps(modified), encoding='utf-8')
    with pytest.raises(ValueError, match='Derived candidates differ'):
        assemble(output, inventory, verify_existing=True)
    assert json.loads(candidate.read_text(encoding='utf-8')) == modified
    candidate.write_bytes(original_candidate)
    raw = next((output / 'raw/B01').glob('*observationid*'))
    raw.write_bytes(raw.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='Capture changed'):
        assemble(output, inventory)
    assert candidate.read_bytes() == original_candidate


def test_table_mapping_preserves_unknown_zero_precision_and_units():
    raw = b'observation_id,value_or_statement,unit_denominator_currency,\r\nB01-O001,Unknown,kg,\r\nB01-O002,0.000,USD per kg,\r\n'
    headers, rows, failed, artifacts = parse_table(raw)
    assert rows[0]["fields"]["value_or_statement"] == "Unknown"
    assert rows[1]["fields"]["value_or_statement"] == "0.000"
    assert rows[1]["fields"]["unit_denominator_currency"] == "USD per kg"
    assert "" not in headers and artifacts and not failed


def test_malformed_row_is_visible_without_losing_valid_row():
    _, rows, failed, _ = parse_table(b'observation_id,value\nB01-O001,10\nB01-O002,20,extra\n')
    assert len(rows) == 1 and len(failed) == 1
    assert failed[0]["line"] == 3
    assert failed[0]["raw_cells"] == ["B01-O002", "20", "extra"]


def test_nonempty_extra_column_is_not_silently_removed():
    headers, rows, _, artifacts = parse_table(b'id,value,\nB01-O001,10,unexpected\n')
    assert headers[-1] == ""
    assert rows[0]["fields"][""] == "unexpected"
    assert not artifacts


def test_rendered_tables_escape_source_html_and_keep_readable_newlines():
    assert md_cell('<script>unsafe</script>|a\nb') == '&lt;script&gt;unsafe&lt;/script&gt;\\|a<br>b'
