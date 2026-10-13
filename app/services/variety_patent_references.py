"""Read-only original filing links; never a current-rights assessment."""
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from app.services.variety_portfolio_coverage import reconcile_portfolios
from app.services.variety_universe.coverage import BERRY_ORDER


def load_registry_filing_observations(data_dir: Path):
    """Project existing numbered import references into the same identity checks.

    No acquisition, candidate import, registry-adapter change or canonical
    update. Deployment/program leads and unnumbered rows are not filings.
    Only the stored reference's capture date is used, never today's date.
    """
    sources = {}
    try:
        for path in sorted((data_dir / "imports").glob("variety-universe-*/registry_rows.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
                raise ValueError("Registry references need their stored row list")
            for row in payload["rows"]:
                if not isinstance(row, dict):
                    raise ValueError("Registry reference must be an object")
                if row.get("source_type") not in {"plant_breeders_rights_record", "patent_record"}:
                    continue
                if not (row.get("application_number") or row.get("grant_number")):
                    continue
                url = _public_url(row.get("source_url"))
                if not url or row.get("berry_id") not in BERRY_ORDER:
                    continue
                knowledge = row.get("knowledge") or {}
                if not isinstance(knowledge, dict):
                    raise ValueError("Registry reference knowledge must be an object")
                captured = knowledge.get("checked_on") or payload.get("acquired_at")
                if not isinstance(captured, str):
                    raise ValueError("Numbered registry reference needs its capture date")
                checked = (date.fromisoformat(captured) if len(captured) == 10 else datetime.fromisoformat(captured.replace("Z", "+00:00")).date()).isoformat()
                name = row.get("candidate_name") or row.get("denomination")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Numbered registry reference needs its original name")
                keys = ("denomination", "breeder_code", "trade_name", "application_number", "grant_number", "application_date")
                if any(row.get(key) is not None and not isinstance(row[key], str) for key in keys):
                    raise ValueError("Registry reference names, numbers and dates must remain text")
                grant_date = row.get("grant_date") or row.get("granting_date") or ""
                if not isinstance(grant_date, str):
                    raise ValueError("Registry grant date must remain text")
                for value in (grant_date, row.get("application_date")):
                    if value:
                        date.fromisoformat(value)
                digest = hashlib.sha256(json.dumps([row.get("source_id"), url, name, row["berry_id"],
                    row.get("application_number"), row.get("grant_number"), checked], ensure_ascii=False).encode()).hexdigest()[:20]
                context = "Imported register reference captured " + checked + ". Numbers and dates describe that stored record; current legal status, party roles and additional aliases are not approved."
                sources[digest] = {
                    "id": "registry-reference-" + digest,
                    "title": str(row.get("source_label") or "Register reference") + " · " + name,
                    "url": url, "checked_on": checked, "source_type": "national_register",
                    "company_ids": [], "berry_ids": [row["berry_id"]], "capture_status": "names_enumerated",
                    "enumerated_scope": "Single numbered imported register result, not a complete registry",
                    "limitations": context, "imported_registry_reference": True,
                    "names": [{"candidate_name": name, "berry_id": row["berry_id"],
                               **{key: row.get(key) or "" for key in keys},
                               "grant_date": grant_date, "portfolio_context": context}],
                }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("Imported filing references failed validation; check the stored register snapshot.") from exc
    return list(sources.values())


def _public_url(value):
    if not isinstance(value, str):
        return ""
    try:
        parts = urlsplit(value)
        return value if parts.scheme in {"http", "https"} and parts.hostname and not parts.username and not parts.password else ""
    except ValueError:
        return ""


def original_patent_references(*, variety, varieties, entities, candidates, sources):
    """Use existing identity decisions and source/code ambiguity handling.

    Only exact catalog associations reach a profile. A reference remains
    unreviewed; source text, grant metadata and linked figures approve nothing.
    No corpus-body hydration, footprints, acquisition or persistent writes.
    """
    rights = [s for s in sources if s.get("source_type") in {"plant_patent", "national_register"}]
    if not rights:
        return []
    # Keep cross-source code/label conflicts visible even if a conflicting
    # observation is not itself a patent or register record.
    rows, _ = reconcile_portfolios(sources=sources, varieties=varieties,
                                  entities=entities, candidates=candidates,
                                  source_ids={s["id"] for s in rights})
    source_ids = {s["id"] for s in rights}
    refs = {}
    for source in rows:
        if source["id"] not in source_ids:
            continue
        for name in source["names"]:
            if name.get("catalog_id") != variety["id"]:
                continue
            url = _public_url(source["url"])
            if not url:
                continue
            capture = source.get("capture_reference") or {}
            key = (url, name.get("grant_number") or name.get("application_number") or "")
            refs[key] = {
                "source_id": source["id"], "title": source["title"], "url": url,
                "number": name.get("grant_number") or name.get("application_number") or "",
                "published_date": source.get("published_date") or name.get("grant_date") or "",
                "checked_on": source["checked_on"],
                "document_url": _public_url(name.get("product_url")) or _public_url(capture.get("original_pdf_url")),
                "claim_url": _public_url(capture.get("claim_url")),
                "figures_url": _public_url(capture.get("figures_url")),
                "context": name.get("portfolio_context") or source["limitations"],
                "reference_kind": "register" if source.get("imported_registry_reference") else "filing",
                "application_number": name.get("application_number") or "",
                "application_date": name.get("application_date") or "",
                "grant_number": name.get("grant_number") or "",
                "date_label": "Grant date" if source.get("imported_registry_reference") and not source.get("published_date") else "Published",
            }
    return sorted(refs.values(), key=lambda r: (r["published_date"], r["checked_on"], r["title"]), reverse=True)
