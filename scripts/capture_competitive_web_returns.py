"""Preserve explicit Perplexity UI exports; never publish or score research.

Only the observed export filename families and files newer than the first
known export are eligible. Unknown/multiple batch matches are reported.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "inbox/competitive_landscape/web-research-2026-10-30"
CSV_PREFIXES = (
    "Field-Value", "batchid-inventoryversion", "entityid-resolvedname",
    "observationid-entityid", "relationshipid-subjectentityid", "personid-nameoriginal",
    "jobid-entityid", "eventid-personidorunknown", "exposureid-entityid",
    "sourceid-originalurl", "gapid-entityid",
    "CapabilityIDs-B05treatment",
)


def inspect_csv(raw):
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    if not rows or not rows[0]:
        raise ValueError("Empty CSV")
    headers = rows[0]
    widths = sorted({len(r) for r in rows})
    body = raw.decode("utf-8-sig")
    batches = set(re.findall(r"\b(B\d{2})-[A-Z]\d+\b", body))
    batches.update(re.findall(r"\b(B\d{2})\b", " ".join(headers)))
    if [h.casefold() for h in headers[:2]] == ["field", "value"]:
        batches.update(r[1] for r in rows[1:] if len(r) > 1 and r[0] == "batch_id")
    if "batch_id" in headers:
        idx = headers.index("batch_id")
        batches.update(r[idx] for r in rows[1:] if len(r) > idx and re.fullmatch(r"B\d{2}", r[idx]))
    warnings = []
    if len(widths) != 1:
        warnings.append("Nonuniform row widths; retain every raw row for resolution")
    if headers[-1] == "" and all(r[-1:] == [""] for r in rows):
        warnings.append("UI export adds an empty trailing column; preserved in original bytes")
    return {"batch_ids": sorted(batches), "headers": headers, "row_count": len(rows)-1,
            "column_count": len(headers), "row_widths": widths, "warnings": warnings}


def capture(downloads, output, *, since):
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "capture-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {
        "inventory_version": "competitive-landscape-2026-10-30-v1",
        "capture_status": "raw_web_returns_not_source_validated",
        "files": {}, "unresolved": [],
    }
    counts = {"captured_files": 0, "already_present": 0, "unresolved_files": 0, "parse_errors": 0}
    # This is a download-artifact reader, not browser-profile or session access.
    for path in sorted(downloads.iterdir()):
        if not path.is_file() or path.stat().st_mtime < since:
            continue
        csv_candidate = path.suffix.lower() == ".csv" and path.name.casefold().startswith(tuple(p.casefold() for p in CSV_PREFIXES))
        pdf_candidate = path.suffix.lower() == ".pdf" and re.match(r"^B\d{2} (?:—|-) ", path.name)
        if not (csv_candidate or pdf_candidate):
            continue
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest in manifest["files"]:
            counts["already_present"] += 1
            continue
        try:
            detail = inspect_csv(raw) if csv_candidate else {
                "batch_ids": [path.name[:3]], "warnings": ["Original PDF retained; wide tables may clip. Use CSV/UI text for import."]}
        except (UnicodeError, ValueError, csv.Error) as exc:
            manifest["unresolved"].append({"source_path": str(path), "sha256": digest, "reason": str(exc)})
            counts["parse_errors"] += 1
            continue
        ids = detail["batch_ids"]
        if len(ids) != 1:
            counts["unresolved_files"] += 1
        folder = output / "raw" / (ids[0] if len(ids) == 1 else "unresolved")
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / (digest[:16] + "-" + path.name)
        if dest.exists() and dest.read_bytes() != raw:
            raise ValueError("Refusing to overwrite a conflicting capture")
        dest.write_bytes(raw)
        manifest["files"][digest] = {"source_path": str(path), "capture_path": str(dest.relative_to(output)),
            "sha256": digest, "captured_at": datetime.now(timezone.utc).isoformat(),
            "source_mtime": path.stat().st_mtime, "format": path.suffix.lower().lstrip("."),
            "source_validation": "pending", "application_import": "pending", **detail}
        counts["captured_files"] += 1
    temporary = manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    os.replace(temporary, manifest_path)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", type=Path, default=Path("C:/Users/Johnny/Downloads"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--since-export", type=Path, default=Path("C:/Users/Johnny/Downloads/B01 — Identity research.pdf"))
    args = parser.parse_args()
    print(json.dumps(capture(args.downloads, args.output, since=args.since_export.stat().st_mtime-60), indent=2))
