"""Validate/import tier snapshots idempotently. Dry run unless --apply.

Existing source: --data-dir data. Additional authorized snapshots use --source
JSON with source, snapshot_date, rows[{canonical_entity_id|spreadsheet_label,
berry_tier, regions, effective_date}]. Ambiguous exact aliases are held, never
fuzzy matched. Runtime imports are private SQLite objects with history.
"""
import argparse
import json
from pathlib import Path

from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.global_watchlist import import_tiers, tier_report
from app.services.competitor_registry import load_latest_snapshot, load_reconciliation_matrix
from app.services.living_workspaces import Store


def reconcile(snapshot, entities):
    aliases = {}
    for key, entity in entities.items():
        for alias in [entity.get('name'), *(entity.get('aliases') or [])]:
            if alias:
                aliases.setdefault(alias.strip().casefold(), set()).add(key)
    rows = []
    for row in snapshot.get('rows', []):
        row = dict(row)
        if not row.get('canonical_entity_id'):
            matches = aliases.get(str(row.get('spreadsheet_label') or '').strip().casefold(), set())
            if len(matches) == 1:
                row['canonical_entity_id'] = next(iter(matches))
            elif len(matches) > 1:
                row['alias_conflicts'] = sorted(matches)
        rows.append(row)
    return {'rows': rows, 'snapshot_date': snapshot['snapshot_date']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=resolve_data_dir())
    parser.add_argument('--inbox-dir', type=Path, default=resolve_inbox_dir())
    parser.add_argument('--source', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    entities = {r['id']: r for path in (args.data_dir / 'entities').glob('*/*.json')
                if isinstance(r := json.loads(path.read_text(encoding='utf-8')), dict) and r.get('id')}
    snapshot = json.loads(args.source.read_text(encoding='utf-8')) if args.source else load_latest_snapshot(args.data_dir)
    if snapshot is None:
        raise SystemExit('No tier source available. Entities remain explicitly unassigned.')
    if not snapshot.get('source') or not snapshot.get('snapshot_date'):
        raise SystemExit('Source identity and snapshot_date are required')
    from datetime import date
    date.fromisoformat(snapshot['snapshot_date'])
    matrix = reconcile(snapshot, entities) if args.source else load_reconciliation_matrix(args.data_dir)
    report = import_tiers(Store(args.inbox_dir), snapshot, matrix, entities) if args.apply else tier_report(snapshot, matrix, entities)
    content = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(content, encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('source', 'snapshot_date', 'review_state', 'source_row_count')}))
    print(f"Unique assignments: {len(report['assignments'])}; unmatched: {len(report['unmatched'])}; conflicts: {len(report['conflicts'])}; applied: {args.apply}")


if __name__ == '__main__':
    main()
