"""Import structured EU/UK/South Africa variety-universe rows into inbox candidates.

Never writes data/entities. Does not schedule collection. Reads a fixture of
already-parsed public registry/catalog rows.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.variety_universe.registry_import import import_registry_rows, load_registry_rows

DEFAULT_FIXTURE = (
    ROOT / "data" / "imports" / "variety-universe-eu-uk-sa-v1" / "registry_rows.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--inbox", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox or resolve_inbox_dir(ROOT)
    varieties = [
        entity
        for entity in get_repositories(data_dir, ROOT / "schemas").entities.list()
        if entity.get("entity_type") == "variety"
    ]
    rows = load_registry_rows(args.fixture)
    result = import_registry_rows(rows, varieties=varieties, inbox_dir=inbox_dir)
    print(
        "variety-universe import: "
        f"input={result['input_count']} written={result['written_count']} "
        f"rejected={result['rejected_count']} distinct={result['distinct_new']} "
        f"possible_alias={result['possible_alias']} unknown={result['unknown']} "
        f"exact_canonical_duplicates={result['exact_canonical_duplicates']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
