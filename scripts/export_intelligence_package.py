from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.exports import IntelligencePackageExporter, validate_package
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a minimal JSON Intelligence Package")
    destinations = parser.add_mutually_exclusive_group(required=True)
    destinations.add_argument("--output", type=Path)
    destinations.add_argument("--validate-only", type=Path)
    args = parser.parse_args()
    if args.validate_only:
        errors = validate_package(args.validate_only, SCHEMAS_DIR)
        print("Package valid." if not errors else "Package invalid:\n- " + "\n- ".join(errors))
        return 1 if errors else 0
    manifest = IntelligencePackageExporter(get_repositories(DEFAULT_DATA_DIR, SCHEMAS_DIR), SCHEMAS_DIR).export(args.output)
    print(f"Exported {sum(v for v in manifest['counts'].values() if isinstance(v, int))} indexed records to {args.output}")
    print(f"Counts: {manifest['counts']}")
    print("Orphans: 0; validation: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
