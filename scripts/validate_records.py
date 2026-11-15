from __future__ import annotations

import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def validate_folder(schema_name: str, folder: Path) -> list[str]:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for path in sorted(folder.rglob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        for error in validator.iter_errors(record):
            label = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
            errors.append(f"{label}: {error.message}")
    return errors


def main() -> int:
    from app.runtime_config import resolve_data_dir
    from app.services.information_storage import enabled, information_directory
    data_dir = resolve_data_dir(ROOT)
    errors = []
    if enabled(data_dir=data_dir):
        folder = information_directory(data_dir=data_dir)
        errors += validate_folder("information_record.schema.json", folder)
        validator = Draft202012Validator(json.loads((ROOT / "schemas/evidence.schema.json").read_text(encoding="utf-8")), format_checker=FormatChecker())
        for path in sorted(folder.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") == "published" or record.get("storage_origin") == "canonical":
                errors += [f"{path.name}: {error.message}" for error in validator.iter_errors(record)]
    else:
        errors += validate_folder("evidence.schema.json", data_dir / "evidence")
    errors += validate_folder("entity.schema.json", data_dir / "entities")
    errors += validate_folder("fact.schema.json", data_dir / "facts")
    errors += validate_folder("relationship.schema.json", data_dir / "relationships")
    errors += validate_folder("strategic-question.schema.json", data_dir / "strategic-questions")
    errors += validate_folder("signal.schema.json", data_dir / "signals")
    # New V2 core objects (docs/v2/03-DOMAIN-MODEL.md, BL-010/BL-011). No data/
    # folder exists yet for either -- validate_folder() handles a missing
    # folder as zero records, same as signals did before any were staged.
    errors += validate_folder("assessment.schema.json", data_dir / "assessments")
    errors += validate_folder("recommendation.schema.json", data_dir / "recommendations")
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("All validated records passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
