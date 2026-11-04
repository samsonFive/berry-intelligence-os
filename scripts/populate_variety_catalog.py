"""Plan/apply an additive catalog import from the existing acquired research.

No network, source approval, claim approval, review-decision mutation or paid
research. Start with a dry run and inspect counts/holds before --apply.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repositories.json.entities import EntityRepository
from app.services import operator_variety_seed, variety_research
from app.services.variety_catalog_import import apply_plan, build_plan
from app.services.variety_portfolio_coverage import load_portfolio_observations
from app.services.variety_universe.candidates import load_variety_candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'data')
    parser.add_argument('--inbox', type=Path, default=ROOT / 'inbox')
    parser.add_argument('--schemas', type=Path, default=ROOT / 'schemas')
    parser.add_argument('--snapshot', type=Path, help='Private read-only research snapshot for an offline plan')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sheet-only', action='store_true', help='Do not add other source portfolio names')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--digest', default='')
    parser.add_argument('--actor', default='')
    args = parser.parse_args()
    if args.apply:
        if args.snapshot:
            parser.error('Apply a reviewed plan to its actual runtime, not a snapshot')
        plan = json.loads(args.output.read_text(encoding='utf-8'))
        receipt = apply_plan(args.inbox, args.data, args.schemas, plan, expected_digest=args.digest, actor=args.actor)
        print(json.dumps({'added': len(receipt['added_ids']), 'counts': receipt['counts'], 'digest': receipt['plan_digest']}))
        return
    if args.snapshot:
        snapshot = json.loads(args.snapshot.read_text(encoding='utf-8-sig'))
        entities, rows, profiles = snapshot['entities'], snapshot['research']['rows'], snapshot['profiles']
        candidates = snapshot['candidates']
    else:
        entities = EntityRepository(args.data, args.schemas).list()
        rows = variety_research.index(args.inbox)['rows']
        profiles = {row['entity_id']: variety_research.profile(args.inbox, row['entity_id']) for row in rows}
        candidates = load_variety_candidates(args.inbox)
    seeds = operator_variety_seed.seed_rows(args.data, {row['id']: row for row in entities})
    plan = build_plan(entities=entities, research_rows=rows, research_profiles=profiles, seed_rows=seeds,
                      portfolio_sources=load_portfolio_observations(args.data), candidates=candidates,
                      include_portfolios=not args.sheet_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'counts': plan['counts'], 'digest': plan['digest'], 'plan': str(args.output)}))


if __name__ == '__main__':
    main()
