"""Read-only row projection for copying research back to the original sheet."""
import json
from pathlib import Path

from app.services.variety_research import ROOT, SAFE_ID, imports

HEADERS = ["Berry", "Application Number", "Grant Number", "Application Date",
           "Grant Publication Date", "Grant Start Date", "Country", "Denomination/Status",
           "Variety Denomination", "Trade Name", "Commercial Entity", "Species LatinName",
           "Parties Concerned", "Rec Type"]
EXTRA_HEADERS = ["Commercial role (unreviewed)", "Research status", "Sources", "Earlier database coverage"]


def sheet(inbox_dir, batch_id=""):
    batches = imports(inbox_dir)
    batch = next((b for b in batches if b["id"] == batch_id), None) if batch_id else (batches[-1] if batches else None)
    if batch is None:
        return {"headers": HEADERS, "extra_headers": EXTRA_HEADERS, "rows": [], "batches": [], "batch_id": "", "counts": {}}
    if not SAFE_ID.fullmatch(batch["id"]):
        raise ValueError("Invalid research batch")
    base = Path(inbox_dir) / ROOT / "imports" / batch["id"]
    source = base / "source_sheet_rows.json"
    if not source.exists():
        return {"headers": HEADERS, "extra_headers": EXTRA_HEADERS, "rows": [], "batches": [], "batch_id": batch["id"], "counts": {}, "error": "Original sheet rows are not available in this import."}
    groups = json.loads(source.read_text(encoding="utf-8"))["groups"]
    dossiers = {}
    for entry in batch["profiles"]:
        entity_id = entry["entity_id"]
        if not SAFE_ID.fullmatch(entity_id):
            raise ValueError("Invalid profile identifier")
        profile = json.loads((base / "profiles" / (entity_id + ".json")).read_text(encoding="utf-8"))
        for dossier in profile["dossiers"]:
            dossiers[dossier["key"]] = {**dossier, "href": entry["href"]}
    for unresolved in batch.get("unresolved", []):
        dossiers.setdefault(unresolved["key"], {**unresolved, "commercial_status": "Identity unresolved", "issue": "Variety name missing; no commercial role assigned."})
    rows = {}
    for key, records in groups.items():
        dossier = dossiers.get(key, {})
        contacts = dossier.get("commercial_contacts", [])
        proposed = "; ".join(dict.fromkeys(c["name"] for c in contacts))
        roles = "\n".join(c["name"] + " — " + c["role"] + (" · " + c["territory"] if c.get("territory") else "") for c in contacts)
        sources = list(dict.fromkeys(s["url"] for s in dossier.get("sources", [])))
        for record in records:
            number = record["row"]
            if type(number) is not int or number < 2 or number in rows:
                raise ValueError("Source sheet row identifiers must be unique positive row numbers")
            fields = record["fields"]
            original = [fields.get(header, "") for header in HEADERS]
            blank = not str(original[10] or "").strip()
            issue = dossier.get("issue", "")
            status = dossier.get("commercial_status", "Commercial route unverified")
            rows[number] = {"row": number, "original": original, "proposal": proposed,
                "role": roles, "status": status, "sources": sources,
                "baseline": dossier.get("baseline_status", "Identity unresolved"),
                "summary": dossier.get("summary", ""), "issue": issue,
                "review_notes": record.get("review_notes", []), "href": dossier.get("href", ""),
                "aliases": dossier.get("aliases", []), "missing_role": blank,
                "can_fill": blank and bool(proposed) and "hold" not in status.lower(),
                "search": " ".join(str(x) for x in [*original, proposed, roles, *dossier.get("aliases", []), dossier.get("summary", "")]).casefold()}
    values = [rows[number] for number in sorted(rows)]
    return {"headers": HEADERS, "extra_headers": EXTRA_HEADERS, "rows": values,
        "batch_id": batch["id"], "batches": [{"id": b["id"], "label": b["checked_on"] + " · " + str(b["counts"]["input_rows"]) + " source rows"} for b in batches],
        "counts": {"rows": len(values), "missing_roles": sum(r["missing_role"] for r in values),
                   "proposals_for_blanks": sum(r["can_fill"] for r in values),
                   "unresolved_blanks": sum(r["missing_role"] and not r["can_fill"] for r in values)}}
