"""Read-only reconciliation of enumerated primary portfolios, never a trust store.

Uses the existing candidate builder and identity resolver. Observations live in
the established imports namespace, contain no article bodies, and never create
Evidence, roles or canonical varieties. Human inbox decisions win on replay.
"""
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from app.services.variety_universe.coverage import BERRY_LABELS, BERRY_ORDER
from app.services.variety_universe.identity import fold_identity, resolve_identity
from app.services.variety_universe.registry_import import build_candidate


def _key(row):
    return fold_identity(row.get("candidate_name", "")), row.get("berry_id", "")


def load_portfolio_observations(data_dir: Path):
    try:
        return _load_portfolio_observations(data_dir)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise ValueError("Stored portfolio observations failed validation; check the dated observations file.") from exc


def _load_portfolio_observations(data_dir: Path):
    """Latest dated observation per section; no network or persisted side effects."""
    latest = {}
    for path in sorted((data_dir / "imports").glob("variety-portfolio-observations-*/observations.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("kind") != "unreviewed_portfolio_name_observations":
            raise ValueError("Unknown portfolio observation format")
        for source in payload.get("sources", []):
            if any(not isinstance(source.get(key), str) or not source[key].strip()
                   for key in ("id", "title", "url", "checked_on", "source_type", "enumerated_scope", "limitations")):
                raise ValueError("Portfolio source needs its identity, date and bounded page scope")
            if any(not isinstance(source.get(key), list) for key in ("company_ids", "berry_ids", "names")):
                raise ValueError("Portfolio source needs explicit company, berry and name lists")
            checked = date.fromisoformat(source["checked_on"])
            url = urlsplit(source["url"])
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
                raise ValueError("Portfolio source needs a public HTTP(S) URL")
            if source["capture_status"] not in {"names_enumerated", "unreadable", "partial"}:
                raise ValueError("Unknown portfolio capture status")
            if any(row.get("berry_id") not in BERRY_ORDER or not row.get("candidate_name") for row in source.get("names", [])):
                raise ValueError("Portfolio names need an explicit berry and name")
            old = latest.get(source["id"])
            if old is None or checked >= date.fromisoformat(old["checked_on"]):
                latest[source["id"]] = source
    return list(latest.values())


def reconcile_portfolios(*, sources, varieties, entities, candidates, today=None):
    """Account for each explicitly enumerated name, retaining source/code identity.

    A shared trade name is not an identity key when a denomination is recorded.
    Exact matches use the existing resolver; ambiguous matches require review.
    """
    today = today or date.today()
    entity_index = {row["id"]: row for row in entities}
    canonical_ids = {row["id"] for row in varieties}
    existing = {_key(row): row for row in candidates}
    source_rows, additions = [], []
    provenance = {}
    for source in sources:
        names = []
        companies = [{"entity_id": cid, "name": entity_index[cid]["name"]}
                     for cid in source.get("company_ids", []) if cid in entity_index]
        for observation in source.get("names", []):
            query = {k: observation.get(k, "") for k in ("candidate_name", "denomination", "breeder_code", "berry_id")}
            result = resolve_identity(query, varieties)
            exact_ids = {row["variety_id"] for row in result["matches"] if row["reason"] == "exact_identity_string"}
            catalog_id = next(iter(exact_ids)) if len(exact_ids) == 1 else None
            candidate = existing.get(_key(observation))
            if candidate and candidate.get("human_gated") and candidate.get("identity_state") == "confirmed_same":
                match_id = candidate.get("candidate_canonical_match")
                compatible = any(row["id"] == match_id and observation["berry_id"] in row.get("berry_ids", []) for row in varieties)
                if match_id in canonical_ids and compatible:
                    catalog_id = match_id
            status = "catalog_match" if catalog_id else "needs_review"
            if not catalog_id and candidate and candidate.get("status") == "rejected":
                status = "previously_rejected"
            elif not catalog_id and candidate and candidate.get("human_gated") and candidate.get("identity_state") == "distinct":
                status = "distinct_awaiting_catalog"
            reference = {"id": source["id"], "title": source["title"], "url": source["url"],
                         "checked_on": source["checked_on"], "companies": companies, **observation}
            provenance.setdefault(_key(observation), []).append(reference)
            if status == "needs_review" and candidate is None:
                candidate = build_candidate({**observation, "source_id": source["id"], "source_url": source["url"],
                    "source_label": source["title"], "source_type": source["source_type"],
                    "source_tier": "tier_1_breeder_catalog", "knowledge": {"origin": "primary_portfolio_observation"}},
                    varieties=varieties, discovered_at=source.get("observed_at"))
                candidate = {**candidate, "persisted": False, "discovered_from": "primary_portfolio"}
                additions.append(candidate)
                existing[_key(observation)] = candidate
            labels = {"catalog_match": "Catalog match", "needs_review": "Needs identity review",
                      "previously_rejected": "Previously rejected", "distinct_awaiting_catalog": "Distinct · catalog entry pending"}
            names.append({**observation, "catalog_id": catalog_id, "status": status, "label": labels[status],
                          "href": "/entities/variety/" + catalog_id if catalog_id else
                                  "/varieties/candidates?" + urlencode({"q": observation["candidate_name"], "berry": observation["berry_id"]})})
        checked = date.fromisoformat(source["checked_on"])
        age = (today - checked).days
        freshness = "Check date in future" if age < 0 else "Recheck due" if age > 90 else "Checked recently"
        if source["capture_status"] == "unreadable" and age >= 0:
            freshness = "Retry due" if age > 90 else "Attempted recently"
        source_rows.append({**source, "names": names, "companies": companies,
                            "age_days": age, "freshness": freshness,
                            "matched": sum(row["status"] == "catalog_match" for row in names),
                            "needs_review": sum(row["status"] == "needs_review" for row in names),
                            "closed": sum(row["status"] == "previously_rejected" for row in names),
                            "awaiting_catalog": sum(row["status"] == "distinct_awaiting_catalog" for row in names)})
    visible = [{**row, "portfolio_sources": provenance.get(_key(row), [])} for row in [*candidates, *additions]]
    return source_rows, visible


def portfolio_coverage(*, data_dir, sources, varieties, entities, candidates, filters=None, today=None):
    filters = filters or {}
    today = today or date.today()
    source_rows, visible = reconcile_portfolios(sources=sources, varieties=varieties, entities=entities, candidates=candidates, today=today)
    registry_path = data_dir / "imports/competitor-coverage-registry-2026-09-21/reconciliation-matrix.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))["rows"] if registry_path.is_file() else []
    photo_path = data_dir / "imports/variety-operator-seed-2026-09-30/rows.json"
    photo_rows = json.loads(photo_path.read_text(encoding="utf-8"))["rows"] if photo_path.is_file() else []
    index = {row["id"]: row for row in entities}
    subjects = []
    for row in registry:
        ids = row.get("canonical_entity_ids") or []
        linked = [source for source in source_rows if set(source.get("company_ids", [])) & set(ids)]
        websites = [row.get("website", "")] + [str((index.get(cid, {}).get("attributes") or {}).get("website") or "") for cid in ids]
        website = next((url for url in websites if _public_url(url)), "")
        scope = sorted({berry for cid in ids for berry in index.get(cid, {}).get("berry_ids", []) if berry in BERRY_ORDER}
                       | {berry for source in linked for berry in source.get("berry_ids", [])}
                       | {photo["berry_id"] for photo in photo_rows if set(photo.get("company_ids", [])) & set(ids)})
        subjects.append({"name": row["input_registry_name"], "entity_ids": ids, "website": website,
                         "berry_ids": scope, "berries": ", ".join(BERRY_LABELS[berry] for berry in scope) or "Scope needs checking",
                         "resolution": row["resolution_status"], "sources": linked,
                         "checked": bool(linked) and any(source["capture_status"] == "names_enumerated" for source in linked),
                         "href": "/entities/" + index[ids[0]]["entity_type"] + "/" + ids[0] if ids and ids[0] in index else ""})
    berry = filters.get("berry", "")
    if berry and berry not in BERRY_ORDER:
        raise ValueError("Choose a supported berry")
    q = str(filters.get("q", "")).strip().casefold()
    selected = [row for row in source_rows if (not berry or berry in row.get("berry_ids", []) or any(name["berry_id"] == berry for name in row["names"]))
                and (not q or q in " ".join([row["title"], *(c["name"] for c in row["companies"])]).casefold())]
    selected_subjects = [row for row in subjects if (not berry or berry in row["berry_ids"] or not row["berry_ids"])
                         and (not q or q in row["name"].casefold())]
    all_names = [name for source in selected for name in source["names"]]
    return {"sources": selected, "subjects": selected_subjects, "filters": {"berry": berry, "q": filters.get("q", "")},
            "summary": {"source_sections": len(selected), "readable_sections": sum(s["capture_status"] == "names_enumerated" for s in selected),
                        "unreadable_sections": sum(s["capture_status"] == "unreadable" for s in selected),
                        "names": len(all_names), "catalog_matches": sum(n["status"] == "catalog_match" for n in all_names),
                        "needs_review": sum(n["status"] == "needs_review" for n in all_names),
                        "registry_entries": len(selected_subjects), "registry_entries_checked": sum(s["checked"] for s in selected_subjects)},
            "by_berry": [{"id": berry_id, "label": BERRY_LABELS[berry_id],
                          "names": sum(n["berry_id"] == berry_id for n in all_names),
                          "matched": sum(n["berry_id"] == berry_id and n["status"] == "catalog_match" for n in all_names)} for berry_id in BERRY_ORDER],
            "visible_candidates": visible}


def _public_url(value):
    try:
        url = urlsplit(value)
        return url.scheme in {"http", "https"} and bool(url.hostname) and not (url.username or url.password)
    except ValueError:
        return False
