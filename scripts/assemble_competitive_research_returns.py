"""Reassemble UI CSV exports as traceable Markdown and untrusted candidates.

Original bytes remain in the capture manifest. This does not inspect citations,
write application entities/evidence, assign ratings, or overwrite analyst work.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = ROOT / "inbox/competitive_landscape/web-research-2026-10-30"
INVENTORY = ROOT / "data/imports/competitive-landscape-2026-10-30-v1"
KINDS = {"entity_id": "profile", "observation_id": "observation", "relationship_id": "relationship",
         "person_id": "person", "job_id": "job", "event_id": "hiring_event", "exposure_id": "exposure",
         "source_id": "source", "gap_id": "gap"}


def parse_table(raw):
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    if not rows:
        raise ValueError("Empty table")
    headers, body = rows[0], rows[1:]
    artifacts = []
    if headers[-1:] == [""] and all(r[-1:] == [""] for r in rows):
        headers, body = headers[:-1], [r[:-1] for r in body]
        artifacts.append("Uniform empty trailing UI-export column excluded from candidate mapping; raw bytes retained")
    accepted, failed = [], []
    for line, cells in enumerate(body, 2):
        if len(cells) != len(headers) or len(headers) != len(set(headers)):
            failed.append({"line": line, "raw_cells": cells, "reason": "Row width or duplicate header requires resolution"})
        else:
            accepted.append({"line": line, "fields": dict(zip(headers, cells))})
    return headers, accepted, failed, artifacts


def md_cell(value):
    return html.escape(value, quote=False).replace("|", "\\|").replace("\r\n", "\n").replace("\n", "<br>")


def assemble(capture_dir, inventory_dir=INVENTORY, *, verify_existing=False):
    capture_dir = Path(capture_dir)
    manifest = json.loads((capture_dir / "capture-manifest.json").read_text(encoding="utf-8"))
    inventory = json.loads((inventory_dir / "commercial-entity-inventory.json").read_text(encoding="utf-8"))
    capabilities = json.loads((inventory_dir / "capability-rubrics.json").read_text(encoding="utf-8"))
    entity_ids = {r["entity_id"] for r in inventory["entities"]}
    cap_ids = {r["capability_id"] for r in capabilities["capabilities"]}
    batches = {}
    for sha, entry in manifest["files"].items():
        original = (capture_dir / entry['capture_path']).resolve()
        if not original.is_relative_to(capture_dir.resolve()):
            raise ValueError('Original capture escaped its private folder')
        if hashlib.sha256(original.read_bytes()).hexdigest() != sha:
            raise ValueError(f'Capture changed: {original}')
        if entry["format"] != "csv" or len(entry["batch_ids"]) != 1:
            continue
        bid = entry["batch_ids"][0]
        batches.setdefault(bid, []).append((sha, entry))
    summaries = []
    for bid, entries in sorted(batches.items()):
        result = {"batch_id": bid, "inventory_version": inventory["inventory_version"],
                  "status": "candidate_records_only_original_source_validation_pending",
                  "metadata": {}, "records": [], "failed": [], "unresolved": [], "input_sha256": []}
        sections = []
        source_ids = set()
        identity = {}
        for sha, entry in entries:
            path = capture_dir / entry["capture_path"]
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError(f"Capture changed: {path}")
            headers, rows, failed, artifacts = parse_table(raw)
            result["input_sha256"].append(sha)
            kind = KINDS.get(headers[0], "support_context")
            if [h.casefold() for h in headers[:2]] == ["field", "value"]:
                result["metadata"].update({r["fields"][headers[0]]: r["fields"][headers[1]] for r in rows})
                kind = "metadata"
            elif headers[0] == "batch_id":
                if len(rows) == 1:
                    result["metadata"].update(rows[0]["fields"])
                kind = "metadata"
            result["failed"].extend({"source_sha256": sha, **r} for r in failed)
            sections.append(f"## {kind} — {sha[:12]}\n\nOriginal: `{entry['capture_path']}`. " + " ".join(artifacts) + "\n\n" +
                "| " + " | ".join(map(md_cell, headers)) + " |\n| " + " | ".join("---" for _ in headers) + " |\n" +
                "\n".join("| " + " | ".join(md_cell(r["fields"][h]) for h in headers) + " |" for r in rows))
            if kind == "metadata":
                continue
            for row in rows:
                fields = row["fields"]
                local_id = fields.get(headers[0]) or f"row-{row['line']}"
                key = kind + ":" + local_id
                record = {"record_kind": kind, "local_id": local_id, "fields": fields,
                          "source_sha256": sha, "source_line": row["line"],
                          "verification_status": "pending_original_source_inspection"}
                if key in identity and identity[key]["fields"] != fields:
                    result["unresolved"].append({"key": key, "reason": "Conflicting candidate versions retained", "source_sha256": sha})
                elif key in identity:
                    continue
                identity[key] = record
                result["records"].append(record)
                if kind == "source":
                    source_ids.add(fields.get("source_id"))
        for record in result["records"]:
            fields = record["fields"]
            problems = []
            if fields.get("entity_id") and fields["entity_id"] not in entity_ids:
                problems.append("Entity identity requires resolution")
            if record["record_kind"] == "observation" and fields.get("capability_id") not in cap_ids:
                problems.append("Capability mapping requires resolution")
            refs = set(re.findall(r"B\d{2}-S\d+", fields.get("source_ids", "")))
            if refs - source_ids:
                problems.append("Missing source ledger references: " + ", ".join(sorted(refs-source_ids)))
            if problems:
                result["unresolved"].append({"key": record["record_kind"]+":"+record["local_id"], "reasons": problems})
        if result["metadata"].get("inventory_version") not in {None, inventory["inventory_version"]}:
            result["unresolved"].append({"reason": "Returned inventory version differs from frozen inventory"})
        if not result["metadata"]:
            result["unresolved"].append({"reason": "Metadata is prose or not captured as a table; inspect original return"})
        out = capture_dir / "assembled" / bid
        if verify_existing:
            if json.loads((out / 'candidate-records.json').read_text(encoding='utf-8')) != result:
                raise ValueError(f'Derived candidates differ from original captured CSVs: {bid}')
        else:
            out.mkdir(parents=True, exist_ok=True)
            (out / "candidate-records.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            (out / "research-tables.md").write_text(f"# {bid} — captured research tables\n\nSource validation pending. "
                f"Inventory `{inventory['inventory_version']}`. Machine-generated from preserved CSV exports; no ratings or trusted claims created.\n\n" + "\n\n".join(sections)+"\n", encoding="utf-8")
        summaries.append({"batch_id": bid, "tables": len(entries), "candidate_records": len(result["records"]),
                          "sources": len(source_ids), "failed_rows": len(result["failed"]), "unresolved": len(result["unresolved"])})
    if not verify_existing:
        (capture_dir / "assembly-summary.json").write_text(json.dumps(summaries, indent=2)+"\n", encoding="utf-8")
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, default=DEFAULT_CAPTURE)
    args = parser.parse_args()
    print(json.dumps(assemble(args.capture_dir), indent=2))
