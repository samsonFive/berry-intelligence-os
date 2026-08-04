#!/usr/bin/env python3
"""Import the blueberry public pilot package into trusted data/.

Three deliberately separate steps, so that "AI proposes; a human approves"
(WELCOME.md principle 5) is enforced by the tooling rather than by convention:

    --dry-run   report exactly what would be written. Writes nothing. (default)
    --apply     write records into data/ with status 'in_review'.
                They are NOT visible in the feed yet.
    --approve   flip staged evidence from 'in_review' to 'published'.
                This is the human-approval gate; run it only after review.

Writes are all-or-nothing: the package is validated and every destination path
is checked for collisions before any file is created.

Usage:
    python scripts/import_package.py --dry-run
    python scripts/import_package.py --apply
    python scripts/import_package.py --approve
    python scripts/import_package.py --approve --only ev-foo,ev-bar
    python scripts/import_package.py --rollback
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]
DATA = REPO / "data"

ENTITY_DIR_TO_TYPE = {
    "companies": "company", "varieties": "variety", "geographies": "geography",
    "people": "person", "berries": "berry", "brands": "brand",
    "breeding-programs": "breeding_program", "traits": "trait",
    "patents": "patent", "retailers": "retailer", "products": "product",
    "sources": "source",
}
# app/main.py::entity_folder() -- override map, else type + "s"
TYPE_TO_DATA_DIR = {
    "company": "companies", "variety": "varieties", "geography": "geographies",
    "person": "people", "berry": "berries",
}

# Folders that map onto validated repository record types.
IMPORTABLE = {
    "evidence": "evidence",
    "facts": "facts",
    "relationships": "relationships",
    "strategic-questions": "strategic-questions",
}
# signals/ is intentionally excluded: no schema exists yet (see P-7).
DEFERRED = {"signals"}

MANIFEST = PKG / "manifest.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def plan() -> tuple[list[tuple[Path, Path]], list[str]]:
    """Return [(src, dest)] plus any collision problems."""
    moves: list[tuple[Path, Path]] = []

    ent_root = PKG / "entities"
    if ent_root.exists():
        for sub in sorted(p for p in ent_root.iterdir() if p.is_dir()):
            etype = ENTITY_DIR_TO_TYPE.get(sub.name)
            if etype is None:
                continue
            dest_dir = DATA / "entities" / TYPE_TO_DATA_DIR.get(etype, f"{etype}s")
            for src in sorted(sub.rglob("*.json")):
                moves.append((src, dest_dir / src.name))

    for pkg_dir, data_dir in IMPORTABLE.items():
        root = PKG / pkg_dir
        if not root.exists():
            continue
        for src in sorted(root.rglob("*.json")):
            moves.append((src, DATA / data_dir / src.name))

    problems = [f"destination already exists: {d.relative_to(REPO)}"
                for _s, d in moves if d.exists()]
    return moves, problems


def run_validator() -> bool:
    print("Running package validation...")
    r = subprocess.run([sys.executable, str(PKG / "scripts" / "validate_package.py")],
                       capture_output=True, text=True)
    print(r.stdout.rstrip())
    if r.stderr.strip():
        print(r.stderr.rstrip(), file=sys.stderr)
    return r.returncode == 0


def cmd_dry_run() -> int:
    ok = run_validator()
    moves, problems = plan()

    print(f"\n--- DRY RUN --- {len(moves)} file(s) would be written\n")
    by_dest: dict[str, int] = {}
    for _s, d in moves:
        by_dest[str(d.parent.relative_to(REPO))] = by_dest.get(str(d.parent.relative_to(REPO)), 0) + 1
    for dest, n in sorted(by_dest.items()):
        print(f"  {dest:45s} {n:4d} file(s)")

    deferred = [d for d in DEFERRED if (PKG / d).exists()
                and any((PKG / d).rglob("*.json"))]
    if deferred:
        for d in deferred:
            n = len(list((PKG / d).rglob("*.json")))
            print(f"\n  DEFERRED (no schema): {d}/  {n} record(s) -- see "
                  f"proposed-schema-enhancements.md P-7")

    if problems:
        print("\nCOLLISIONS:")
        for p in problems:
            print(f"  - {p}")
    print(f"\nValidation: {'PASS' if ok else 'FAIL'}")
    print("Nothing was written. Re-run with --apply to import.")
    return 0 if (ok and not problems) else 1


def cmd_apply() -> int:
    if not run_validator():
        print("\nAborted: package validation failed.")
        return 1
    moves, problems = plan()
    if problems:
        print("\nAborted: destination collisions:")
        for p in problems:
            print(f"  - {p}")
        return 1

    for _s, d in moves:
        d.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        for src, dest in moves:
            shutil.copy2(src, dest)
            written.append(dest)
    except Exception as exc:                       # noqa: BLE001
        print(f"\nWrite failed ({exc}); rolling back {len(written)} file(s).")
        for p in written:
            p.unlink(missing_ok=True)
        return 1

    print(f"\nImported {len(written)} file(s) into data/.")
    print("All evidence is status='in_review' and is NOT yet in the feed.")
    print("Review it, then run:  python scripts/import_package.py --approve")
    return 0


def cmd_approve(only: list[str] | None) -> int:
    staged = [p for p in sorted((DATA / "evidence").glob("*.json"))
              if p.stem in {s.stem for s in (PKG / "evidence").glob("*.json")}]
    if only:
        staged = [p for p in staged if p.stem in set(only)]
    if not staged:
        print("Nothing to approve. Run --apply first, or check --only ids.")
        return 1

    n = 0
    for path in staged:
        rec = load(path)
        if rec.get("status") != "in_review":
            continue
        rec["status"] = "published"
        path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        n += 1
    print(f"Approved {n} evidence record(s) -> status='published'.")
    print("They will now appear in the feed and on entity pages.")
    return 0


def cmd_rollback() -> int:
    moves, _ = plan()
    removed = 0
    for _src, dest in moves:
        if dest.exists():
            dest.unlink()
            removed += 1
    print(f"Removed {removed} imported file(s) from data/.")
    print("Note: this removes files this package created. It does not restore "
          "any pre-existing record that was overwritten (--apply refuses to "
          "overwrite, so none should exist).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--approve", action="store_true")
    g.add_argument("--rollback", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated evidence ids")
    args = ap.parse_args()

    only = [s.strip() for s in args.only.split(",") if s.strip()] or None

    if args.apply:
        return cmd_apply()
    if args.approve:
        return cmd_approve(only)
    if args.rollback:
        return cmd_rollback()
    return cmd_dry_run()


if __name__ == "__main__":
    sys.exit(main())
