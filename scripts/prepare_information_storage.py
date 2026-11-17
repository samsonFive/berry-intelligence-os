"""Validate the runtime's source store before container startup.

This command never migrates records or repairs activation markers. Legacy
runtimes keep their intake directory; activated runtimes use one records store.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from app.services.information_storage import InformationStorageError, enabled, information_directory


def prepare_runtime_information(data_dir: Path, inbox_dir: Path) -> Path:
    data, inbox = Path(data_dir).resolve(), Path(inbox_dir).resolve()
    data_active = enabled(data_dir=data)
    inbox_active = enabled(inbox_dir=inbox)
    if data_active != inbox_active:
        raise InformationStorageError(
            "Data and inbox activation do not match; resume or roll back the migration before startup"
        )
    # Validate both absolute bindings even when each is individually active.
    if enabled(data_dir=data, inbox_dir=inbox) != data_active:
        raise InformationStorageError("Data and inbox do not share one information store")
    directory = information_directory(data_dir=data, inbox_dir=inbox) if data_active else information_directory(inbox_dir=inbox)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--inbox-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        prepare_runtime_information(args.data_dir, args.inbox_dir)
    except (InformationStorageError, OSError) as exc:
        print(f"Information storage startup blocked: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
