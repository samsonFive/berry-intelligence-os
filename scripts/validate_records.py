from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def validate_folder(schema_name: str, folder: Path) -> list[str]:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for path in sorted(folder.rglob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        for error in validator.iter_errors(record):
            errors.append(f"{path.relative_to(ROOT)}: {error.message}")
    return errors


def main() -> int:
    errors = []
    errors += validate_folder("evidence.schema.json", ROOT / "data" / "evidence")
    errors += validate_folder("entity.schema.json", ROOT / "data" / "entities")
    errors += validate_folder("fact.schema.json", ROOT / "data" / "facts")
    errors += validate_folder("relationship.schema.json", ROOT / "data" / "relationships")
    errors += validate_folder("strategic-question.schema.json", ROOT / "data" / "strategic-questions")
    errors += validate_folder("signal.schema.json", ROOT / "data" / "signals")
    # New V2 core objects (docs/v2/03-DOMAIN-MODEL.md, BL-010/BL-011). No data/
    # folder exists yet for either -- validate_folder() handles a missing
    # folder as zero records, same as signals did before any were staged.
    errors += validate_folder("assessment.schema.json", ROOT / "data" / "assessments")
    errors += validate_folder("recommendation.schema.json", ROOT / "data" / "recommendations")
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("All validated records passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
