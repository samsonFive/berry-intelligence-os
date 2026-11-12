"""Plan or add the bounded official-reference seed to an explicit runtime inbox."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.brand_media_seed import install_seed, read_json
from app.services.collection_runner import CollectionLockedError


def canonical_entities(data):
    folder = Path(data) / 'entities'
    if not folder.is_dir():
        raise ValueError('Canonical entity directory is missing')
    entities = {}
    for path in sorted(folder.glob('*/*.json')):
        row = read_json(path)
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
            raise ValueError('Canonical entity record is invalid')
        if row['id'] in entities:
            raise ValueError('Canonical entity IDs must be unique')
        entities[row['id']] = row
    if not entities:
        raise ValueError('Canonical entity catalog is empty')
    return entities


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inbox', type=Path, required=True, help='Explicit destination inbox; never inferred')
    parser.add_argument('--data', type=Path, default=ROOT / 'data', help='Canonical data directory (container: /app/seed/data)')
    parser.add_argument('--seed', type=Path, help='Defaults to DATA/configuration/brand_media_seed.json')
    parser.add_argument('--apply', action='store_true', help='Create missing rows; application writers must be quiescent')
    args = parser.parse_args(argv)
    try:
        seed = args.seed or args.data / 'configuration' / 'brand_media_seed.json'
        if seed.stat().st_size > 1_000_000:
            raise ValueError('Official-reference seed exceeds 1 MB')
        payload = read_json(seed)
        result = install_seed(args.inbox, payload, entities=canonical_entities(args.data), apply=args.apply)
    except CollectionLockedError:
        print(json.dumps({'state': 'blocked', 'error': 'Another runtime writer owns the collection lease'}))
        return 1
    except (OSError, ValueError, TypeError):
        print(json.dumps({'state': 'blocked', 'error': 'Seed or existing media index failed validation; no records changed'}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
