import pytest
from scripts.sample_social_quality_review import build_packet
import hashlib
import json
import sqlite3
from scripts import sample_social_quality_review as sampler


def row(i, role='unknown', language='en', mode='live'):
    return {'id': str(i), 'payload': {'source': 'linkedin', 'language': language,
            'mode': mode, 'content_role': role, 'text': 'blueberries'}, 'analysis': {}}


def test_sample_reproducible_private_snapshot_and_no_gold_invention():
    rows = [row(i) for i in range(40)] + [row('corporate', 'trade'), row('consumer', 'consumer', 'es'), row('fixture', mode='fixture')]
    packet = build_packet(rows, 6)
    assert packet == build_packet(list(reversed(rows)), 6)
    assert packet['summary']['candidate_count'] == 42
    assert {'corporate', 'consumer', 'unclear'} == set(packet['summary']['by_perspective'])
    assert packet['summary']['graded_cases'] == 0
    assert packet['summary']['accuracy'] is None
    assert all(all(v is None for v in c['review'].values()) for c in packet['cases'])
    assert all(c['payload']['mode'] != 'fixture' for c in packet['cases'])
    rows[0]['payload']['text'] = 'changed source'
    assert build_packet(rows, 6)['candidate_snapshot_sha256'] != packet['candidate_snapshot_sha256']


def test_duplicate_ids_and_unbounded_sample_fail():
    with pytest.raises(ValueError, match='Duplicate'):
        build_packet([row(1), row(1)])
    with pytest.raises(ValueError, match='1..100'):
        build_packet([], 101)
    assert build_packet([])['summary']['selected_count'] == 0


def test_cli_private_output_readonly_database_and_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(sampler, 'ROOT', tmp_path)
    database = tmp_path / 'observations.sqlite3'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE observations(id TEXT,payload TEXT,analysis TEXT,removed INTEGER)')
        record = row('one')
        db.execute('INSERT INTO observations VALUES(?,?,?,0)',
                   (record['id'], json.dumps(record['payload']), '{}'))
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    output = tmp_path / 'inbox' / 'packet.json'
    monkeypatch.setattr(sampler.sys, 'argv', ['sample', '--database', str(database), '--output', str(output)])
    sampler.main()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        sampler.main()
    assert output.read_bytes() == original
    public = tmp_path / 'artifacts' / 'packet.json'
    monkeypatch.setattr(sampler.sys, 'argv', ['sample', '--database', str(database), '--output', str(public)])
    with pytest.raises(SystemExit):
        sampler.main()
    assert not public.exists()
