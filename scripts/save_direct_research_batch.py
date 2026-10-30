"""Preserve an authored direct-source research packet against the frozen contract.

Reads JSON on stdin. Writes private content-addressed revisions, never application
records or ratings. Every entity requires its own profile and explicit gaps.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from scripts.competitive_landscape_prompt_contract import MASTER
from scripts.assemble_competitive_research_returns import md_cell

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'data/imports/competitive-landscape-2026-10-30-v1'
OUTPUT = ROOT / 'inbox/competitive_landscape/direct-research-2026-10-30'
KINDS = [
    ('profiles', 'Per-entity profile', None),
    ('observations', 'Capability evidence ledger', 'O'),
    ('relationships', 'Relationships', 'R'),
    ('people', 'People table', 'P'),
    ('jobs', 'Jobs table', 'J'),
    ('hiring_events', 'Hiring/events table', 'H'),
    ('exposures', 'Exposures', 'X'),
    ('sources', 'Source ledger', 'S'),
    ('gaps', 'Conflicts/gaps/leads', 'G'),
]


def prepare(packet, *, snapshot=SNAPSHOT):
    coverage = json.loads((snapshot / 'research-coverage-checklist.json').read_text(encoding='utf-8'))
    bid = packet['batch_id']
    batch = next((b for b in coverage['batches'] if b['batch_id'] == bid), None)
    if bid in {'R01', 'R02'}:
        batch = {'entity_ids': sorted({eid for b in coverage['batches'] for eid in b['entity_ids']})}
    if batch is None or not re.fullmatch(r'(?:B\d{2}|R0[12])', bid):
        raise ValueError('Unknown profile batch')
    expected = set(batch['entity_ids'])
    canonical_ids = {r['entity_id'] for r in json.loads(
        (snapshot / 'commercial-entity-inventory.json').read_text(encoding='utf-8'))['entities']}
    if {r['entity_id'] for r in packet['profiles']} != expected:
        raise ValueError('Profiles must match the frozen batch entities')
    if {r['entity_id'] for r in packet['gaps']} != expected:
        raise ValueError('Every entity needs explicit research gaps')
    if not packet.get('search_passes'):
        raise ValueError('Record actual search passes and limitations')
    tables = {}
    for key, label, prefix in KINDS:
        line = next(line for line in MASTER.splitlines() if label + ': ' in line)
        headers = line.split(label + ': ', 1)[1].split(' | ')
        rows = []
        for i, row in enumerate(packet.get(key, []), 1):
            unexpected = set(row) - set(headers)
            if unexpected:
                raise ValueError(f'{key}: unexpected fields {unexpected}')
            cooked = {h: row.get(h, 'Unknown') for h in headers}
            if prefix:
                cooked[headers[0]] = row.get(headers[0], f'{bid}-{prefix}{i:03}')
            rows.append(cooked)
        tables[key] = {'headers': headers, 'rows': rows}
    source_ids = {r['source_id'] for r in tables['sources']['rows']}
    cap_ids = {c['capability_id'] for c in json.loads((snapshot / 'capability-rubrics.json').read_text())['capabilities']}
    for key, table in tables.items():
        ids = [r[table['headers'][0]] for r in table['rows']]
        if len(ids) != len(set(ids)):
            raise ValueError(f'{key}: duplicate row identity')
        for row in table['rows']:
            if 'entity_id' in row and row['entity_id'] not in expected:
                raise ValueError('Record entity is outside the batch')
            if 'subject_entity_id' in row and row['subject_entity_id'] not in expected:
                raise ValueError('Relationship subject is outside the batch')
            target = row.get('object_entity_id_or_proposed_name', '')
            if re.match(r'^(company|brand|breeding_program|program|retailer)-', target) and target not in canonical_ids:
                raise ValueError('Unknown canonical relationship target; retain a proposed name instead')
            if key == 'sources' and not row['original_url'].startswith(('https://', 'http://')):
                raise ValueError('Source requires an original HTTP(S) URL')
            refs = set(re.findall(r'[BR]\d{2}-S\d+', row.get('source_ids', '')))
            if refs - source_ids:
                raise ValueError('Missing source ledger reference')
            if key == 'observations' and row['capability_id'] not in cap_ids:
                raise ValueError('Unknown capability ID')
    metadata = {'batch_id': bid, 'inventory_version': coverage['inventory_version'],
                'rubric_version': coverage['rubric_version'], 'research_date': packet['research_date'],
                'included_entity_ids': '; '.join(batch['entity_ids']),
                'people_window_start': '2024-10-30', 'people_window_end': packet['research_date'],
                'coverage_summary': packet['coverage_summary'],
                'execution_mode': 'user_authorized_direct_public_source_research_no_paid_api',
                'trust_status': 'research_return_only_no_application_import_or_ratings'}
    return {'metadata': metadata, 'search_passes': packet['search_passes'], 'tables': tables}


def save(packet, *, output=OUTPUT, snapshot=SNAPSHOT):
    prepared = prepare(packet, snapshot=snapshot)
    raw = (json.dumps(packet, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()
    dest = output / packet['batch_id'] / digest
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / 'authored-research.json'
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('Conflicting original bytes')
    path.write_bytes(raw)
    (dest / 'contract-tables.json').write_text(json.dumps(prepared, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    text = ['# ' + packet['batch_id'] + ' — direct public-source research',
            '## 1. Batch metadata',
            '\n'.join(f'- {k}: {v}' for k, v in prepared['metadata'].items()),
            'Search passes: ' + json.dumps(packet['search_passes'], ensure_ascii=False)]
    for key, label, _ in KINDS:
        t = prepared['tables'][key]
        text.extend(['## ' + label,
                     '| ' + ' | '.join(t['headers']) + ' |',
                     '| ' + ' | '.join('---' for _ in t['headers']) + ' |'])
        text.extend('| ' + ' | '.join(md_cell(str(r[h])) for h in t['headers']) + ' |' for r in t['rows'])
        if not t['rows']:
            text.append('\nNo supported records captured in these passes; see entity-specific gaps.\n')
    (dest / 'research-return.md').write_text('\n\n'.join(text)+'\n', encoding='utf-8')
    receipt = {'batch_id': packet['batch_id'], 'sha256': digest,
               'revision_path': str(dest.relative_to(output)), 'status': 'research_captured_validation_and_import_pending'}
    (output / packet['batch_id'] / 'latest.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    print(json.dumps(save(json.load(sys.stdin)), indent=2))
