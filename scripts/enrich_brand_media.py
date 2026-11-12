"""Bounded, offline reuse and authorized media intake. No provider calls."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import brand_media as media
from app.services.pipeline_lock import pipeline_lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inbox', type=Path, required=True, help='Isolated runtime inbox, never defaults to production')
    parser.add_argument('--data', type=Path, default=ROOT / 'seed/data' if (ROOT / 'seed/data').is_dir() else ROOT / 'data')
    parser.add_argument('--entity', action='append', default=[])
    parser.add_argument('--limit', type=int, default=500)
    parser.add_argument('--reuse-social', action='store_true')
    parser.add_argument('--accounts', type=Path, help='Official account mappings; defaults to configuration under --data')
    parser.add_argument('--upload', type=Path, help='Authorized local raster file')
    parser.add_argument('--metadata', type=Path, help='Upload provenance, identity, classification and explicit usage policy JSON')
    parser.add_argument('--decision', type=Path, help='JSON with asset_id, changes and reviewer')
    parser.add_argument('--official-html', type=Path, help='Already acquired HTML from a verified official page; no network fetching')
    parser.add_argument('--verified-page-url', help='Original official page associated with --official-html')
    args = parser.parse_args()
    entities = {r['id']: r for path in (args.data / 'entities').glob('*/*.json')
                if (r := json.loads(path.read_text(encoding='utf-8'))).get('id')}
    result = {}
    with pipeline_lock(args.inbox, 'brand_media_reuse'):
        if args.reuse_social:
            accounts = json.loads((args.accounts or args.data / 'configuration/brand_media_accounts.json').read_text(encoding='utf-8'))['accounts']
            result['reuse'] = media.reuse_social(args.inbox, entities, accounts=accounts, entity_ids=args.entity, limit=args.limit)
        if args.upload:
            if not args.metadata:
                parser.error('--upload requires --metadata')
            row = media.authorized_upload(args.inbox, json.loads(args.metadata.read_text(encoding='utf-8')), args.upload.read_bytes(), entities=entities)
            result['uploaded_asset_id'] = row['id']
        if args.official_html:
            if not args.verified_page_url or len(args.entity) != 1 or args.entity[0] not in entities:
                parser.error('--official-html requires --verified-page-url and one existing --entity')
            from app.services.brand_media_discovery import extract_candidates
            candidates = extract_candidates(args.official_html.read_text(encoding='utf-8'), verified_page_url=args.verified_page_url,
                                            expected_entity_name=entities[args.entity[0]]['name'])
            result['official_discovery'] = media.register_discovery(args.inbox, args.entity[0], candidates, entities=entities)
        if args.decision:
            decision = json.loads(args.decision.read_text(encoding='utf-8'))
            result['decided_asset_id'] = media.decide(args.inbox, decision['asset_id'], decision['changes'], reviewer=decision['reviewer'], entities=entities)['id']
        result['counts'] = media.operational_counts(args.inbox)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
