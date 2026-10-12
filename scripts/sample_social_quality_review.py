"""Offline, private, reproducible review sampling; never creates gold labels."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.social_intelligence.presentation import readable_in_english


CRITERIA = ('fruit_relevance', 'berry_identity', 'author_role', 'translation_meaning',
            'aspect_attribution', 'entity_links', 'retailer_relation', 'geography_basis',
            'publication_date', 'media_source_fidelity')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                   separators=(',', ':')).encode()).hexdigest()


def perspective(row):
    role = row['payload'].get('content_role', 'unknown')
    if role in ('company_owned', 'trade'):
        return 'corporate'
    if role in ('consumer', 'recipe', 'creator', 'disclosed_sponsorship'):
        return 'consumer'
    return 'unclear'


def build_packet(records, limit=30):
    if not 1 <= limit <= 100:
        raise ValueError('Sample limit must be 1..100')
    if len({r['id'] for r in records}) != len(records):
        raise ValueError('Duplicate evidence IDs')
    candidates = sorted((r for r in records if r['payload'].get('mode') in ('live', 'imported')),
                        key=lambda r: r['id'])
    groups = defaultdict(list)
    for row in candidates:
        p = row['payload']
        key = (perspective(row), p['language'], p['source'], readable_in_english(p))
        groups[key].append(row)
    # Round-robin strata, stable hash order within each stratum: no newest-only
    # or exclusively English/corporate selection. This is not population weighting.
    for values in groups.values():
        values.sort(key=lambda r: digest({'id': r['id'], 'seed': 'social-quality-v1'}))
    selected = []
    depth = 0
    while len(selected) < min(limit, len(candidates)):
        for key in sorted(groups):
            if depth < len(groups[key]) and len(selected) < limit:
                selected.append(groups[key][depth])
        depth += 1
    cases = []
    for row in selected:
        p = row['payload']
        cases.append({**row, 'snapshot_sha256': digest(row), 'perspective': perspective(row),
                      'readable_in_english': readable_in_english(p),
                      'review': {criterion: None for criterion in CRITERIA},
                      'reviewer': None, 'reviewer_kind': None, 'notes': None})
    summary = {'candidate_count': len(candidates), 'selected_count': len(cases),
               'by_perspective': dict(Counter(c['perspective'] for c in cases)),
               'by_language': dict(Counter(c['payload']['language'] for c in cases)),
               'by_source': dict(Counter(c['payload']['source'] for c in cases)),
               'readable_count': sum(c['readable_in_english'] for c in cases),
               'graded_cases': 0, 'accuracy': None, 'recall': None}
    return {'version': 'social-quality-v1', 'candidate_snapshot_sha256': digest(candidates),
            'method': 'Deterministic stratified audit, not a representative accuracy/recall sample',
            'summary': summary, 'cases': cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=30)
    args = parser.parse_args()
    private = (ROOT / 'inbox').resolve()
    if not args.output.resolve().is_relative_to(private):
        parser.error('Raw review output must remain under private inbox/')
    if args.output.exists():
        parser.error('Existing review packet will not be overwritten; choose a new output')
    with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = [{'id': i, 'payload': json.loads(p), 'analysis': json.loads(a)}
                for i, p, a in db.execute('SELECT id,payload,analysis FROM observations WHERE removed=0')]
    packet = build_packet(rows, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(packet, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps(packet['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
