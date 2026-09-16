"""Deterministic Wave 2 contract gate.

The gate composes existing focused tests and repository validators.  It is
deliberately read-only with respect to canonical and runtime records: every
command is followed by a digest comparison of ``data/`` and ``inbox/``.
Generated static output is the only expected filesystem side effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "wave2-contract-regression-v1"

GROUPS: dict[str, tuple[str, ...]] = {
    "Roster and identity": (
        "tests/test_competitor_registry_v1.py",
        "tests/test_competitor_profile_v1.py",
        "tests/test_competitor_intelligence_integration_v1.py",
        "tests/test_entity_identity_integrity.py",
        "tests/test_entity_alias_recall.py",
    ),
    "Landscape": (
        "tests/test_competitor_landscape_v1.py",
        "tests/test_landscape_v2.py",
    ),
    "Daily Briefing": (
        "tests/test_daily_intelligence_briefing_slice1.py",
        "tests/test_morning_brief.py",
    ),
    "Reader": (
        "tests/test_astra_news_reader.py",
        "tests/test_intelligence_feed.py",
    ),
    "Trust": (
        "tests/test_trust_feedback.py",
        "tests/test_sync_trusted_data.py",
        "tests/repositories/test_repository_backends.py",
    ),
    "Build integrity": (
        "tests/test_build_static.py",
    ),
}

SUMMARY_RE = re.compile(r"(?P<count>\d+) passed(?:, (?P<failed>\d+) failed)?")


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        digest.update(b"<missing>")
        return digest.hexdigest()
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        digest.update(str(item.relative_to(path)).replace(os.sep, "/").encode())
        digest.update(item.read_bytes())
    return digest.hexdigest()


def _record_digests() -> dict[str, str]:
    return {name: _tree_digest(ROOT / name) for name in ("data", "inbox")}


def _count_tests(output: str) -> int:
    matches = list(SUMMARY_RE.finditer(output))
    if not matches:
        return 0
    match = matches[-1]
    return int(match.group("count")) + int(match.group("failed") or 0)


def _run(label: str, command: list[str], before: dict[str, str], temp_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    environment = os.environ.copy()
    environment.update({key: str(temp_root) for key in ("TMP", "TEMP", "TMPDIR")})
    # Route reads may advance analyst state by design, but only in this
    # disposable copy, never in the operator's live inbox.
    isolated_inbox = temp_root / "inbox"
    if (ROOT / "inbox").exists():
        shutil.copytree(ROOT / "inbox", isolated_inbox, dirs_exist_ok=True)
    environment["BIOS_INBOX_DIR"] = str(isolated_inbox)
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=environment)
    duration = time.perf_counter() - started
    after = _record_digests()
    mutated = [name for name in before if before[name] != after[name]]
    output = (completed.stdout + completed.stderr).strip()
    pagefind_missing = label == "Static build and Pagefind" and "Search index built (pagefind)." not in output
    result = {
        "label": label,
        "command": " ".join(command),
        "passed": completed.returncode == 0 and not mutated and not pagefind_missing,
        "returncode": completed.returncode,
        "test_count": _count_tests(output),
        "duration_seconds": round(duration, 3),
        "record_mutations": mutated,
        "pagefind_missing": pagefind_missing,
        "output_tail": output[-2000:],
    }
    if result["passed"] is not True:
        print(f"FAIL {label}: {result['output_tail']}", file=sys.stderr)
        if pagefind_missing:
            print(f"FAIL {label}: Pagefind did not complete; install pagefind and pagefind_bin.", file=sys.stderr)
        if mutated:
            print(f"FAIL {label}: canonical/runtime mutation detected: {mutated}", file=sys.stderr)
    else:
        print(f"PASS {label}: {result['test_count']} tests in {result['duration_seconds']}s")
    return result


def _commands(mode: str, python: str) -> Iterable[tuple[str, list[str]]]:
    for label, paths in GROUPS.items():
        if mode == "quick" and label == "Build integrity":
            continue
        yield label, [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *paths]
    yield "Record validation", [python, "scripts/validate_records.py"]
    if mode == "full":
        yield "Static build and Pagefind", [python, "scripts/build_static.py"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("quick", "full"), default="quick")
    parser.add_argument("--report", type=Path, help="Write a JSON report to this path")
    args = parser.parse_args(argv)

    initial = _record_digests()
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="wave2-contract-", dir=ROOT) as temp_dir:
        for label, command in _commands(args.mode, sys.executable):
            results.append(_run(label, command, _record_digests(), Path(temp_dir)))
            if results[-1]["returncode"] != 0 or results[-1]["record_mutations"]:
                print("Gate stopped after the first failure; fix the diagnostic and rerun.", file=sys.stderr)
                break

    final = _record_digests()
    report = {
        "mode": args.mode,
        "root": str(ROOT),
        "python": sys.executable,
        "results": results,
        "canonical_or_runtime_mutation": initial != final,
        "passed": bool(results) and len(results) == len(list(_commands(args.mode, sys.executable))) and all(r["passed"] for r in results),
    }
    report_path = args.report
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": args.mode, "passed": report["passed"], "results": len(results)}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
