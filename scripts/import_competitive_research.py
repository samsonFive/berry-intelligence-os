"""Import preserved research into the existing private analyst workspace.

Dry run by default. This never fetches, publishes, extracts Atomic Evidence,
guesses canonical identities, or chooses a numerical capability rating.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from app.runtime_config import resolve_data_dir, resolve_inbox_dir

from app.services import competitive_evaluation as evaluation
from app.services.analyst_state_io import atomic_json

ROOT = Path(__file__).resolve().parents[1]
DIRECT = resolve_inbox_dir(ROOT) / 'competitive_landscape/direct-research-2026-10-30'
WEB = resolve_inbox_dir(ROOT) / 'competitive_landscape/web-research-2026-10-30'


def inputs():
    if (WEB / 'capture-manifest.json').exists():
        from scripts.assemble_competitive_research_returns import assemble
        assemble(WEB, verify_existing=True)
    for folder in sorted((WEB / 'assembled').glob('B*')):
        path = folder / 'candidate-records.json'
        if path.exists():
            raw = path.read_bytes()
            yield folder.name, json.loads(raw), hashlib.sha256(raw).hexdigest(), str(path)
    for pointer in sorted(DIRECT.glob('[BR]*/latest.json')):
        revision = json.loads(pointer.read_text(encoding='utf-8'))
        from scripts.assemble_competitive_research_returns import retained_path
        folder = retained_path(DIRECT, revision['revision_path'])
        if not folder.is_relative_to(DIRECT.resolve()):
            raise ValueError('Research revision escaped its private capture folder')
        original = (folder / 'authored-research.json').read_bytes()
        sha = hashlib.sha256(original).hexdigest()
        if sha != revision['sha256']:
            raise ValueError('Original research hash mismatch')
        # Rebuild from the authored original so edited derived tables cannot add claims.
        from scripts.save_direct_research_batch import prepare
        prepared = prepare(json.loads(original))
        stored = json.loads((folder / 'contract-tables.json').read_text(encoding='utf-8'))
        if prepared != stored:
            raise ValueError('Derived contract tables do not match the original')
        yield revision['batch_id'], prepared, sha, str(folder / 'authored-research.json')


def run(*, apply=False, inbox_dir=None, checks=None, reviews=None):
    inbox_dir = inbox_dir or resolve_inbox_dir(ROOT)
    entities = {}
    for path in (resolve_data_dir(ROOT) / 'entities').rglob('*.json'):
        entity = json.loads(path.read_text(encoding='utf-8'))
        entities[entity['id']] = entity
    summary = {'mode': 'applied_private_workspace' if apply else 'dry_run', 'batches': [],
               'trust_effect': 'No publication or Atomic Evidence decisions; no numeric ratings selected'}
    totals = Counter()
    prepared = list(inputs())
    if reviews:
        from app.services.competitive_research_review import reviewed_payload
        if {r.get('batch_id') for r in reviews} - {item[0] for item in prepared}:
            raise ValueError('Mapping review refers to an unavailable research batch')
        prepared = [(bid,reviewed_payload(bid,payload,reviews),sha,path) for bid,payload,sha,path in prepared]
    for bid, payload, sha, path in prepared:
        rows = evaluation.unpack_return(payload)
        item = {'batch_id': bid, 'original_path': path, 'sha256': sha, 'candidate_rows': len(rows)}
        if apply:
            report = evaluation.import_return(inbox_dir, batch_id=bid, payload=payload,
                       original_sha256=sha, entities=entities, source_checks=(checks or {}).get(bid, {}))
            item.update(report_id=report['id'], counts=report['counts'], replayed=report.get('replayed', False),
                        upstream_warnings=len(report['upstream_issues']), failed_rows=len(report['failed_rows']))
            totals.update(report['counts'])
        summary['batches'].append(item)
    summary['totals'] = dict(totals)
    if apply:
        atomic_json(Path(inbox_dir) / 'competitive_landscape/import-summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--inbox', type=Path, default=resolve_inbox_dir(ROOT))
    parser.add_argument('--source-checks', type=Path, help='Explicit original-source inspection decisions, grouped by batch/source ID')
    parser.add_argument('--mapping-reviews', type=Path, default=resolve_inbox_dir(ROOT) / 'competitive_landscape/research-mapping-reviews.json', help='Private, explicit hash-bound mapping reviews; originals remain unchanged')
    args = parser.parse_args()
    checks = json.loads(args.source_checks.read_text(encoding='utf-8')) if args.source_checks else None
    reviews = json.loads(args.mapping_reviews.read_text(encoding='utf-8')) if args.mapping_reviews.exists() else None
    result = run(apply=args.apply, inbox_dir=args.inbox, checks=checks, reviews=reviews)
    print(json.dumps({'mode': result['mode'], 'batches': len(result['batches']),
                      'candidate_rows': sum(b['candidate_rows'] for b in result['batches']),
                      'totals': result['totals'], 'trust_effect': result['trust_effect']}, indent=2))
