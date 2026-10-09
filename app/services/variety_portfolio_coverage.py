"""Read-only reconciliation of enumerated primary portfolios, never a trust store.

Uses the existing candidate builder and identity resolver. Observations live in
the established imports namespace, contain no article bodies, and never create
Evidence, roles or canonical varieties. Human inbox decisions win on replay.
"""
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from app.services import company_directory
from app.services.source_body import classify_source_body
from app.services.variety_universe.coverage import BERRY_LABELS, BERRY_ORDER
from app.services.variety_universe.identity import fold_identity, resolve_identity
from app.services.variety_universe.registry_import import build_candidate


def _key(row):
    return fold_identity(row.get("candidate_name", "")), row.get("berry_id", "")


def _coded_label_keys(sources):
    """Labels tied to different literal codes cannot be one candidate key."""
    labels = {}
    for source in sources:
        for row in source["names"]:
            code = row.get("denomination") or row.get("breeder_code")
            label = row.get("trade_name") or row["candidate_name"]
            if code:
                labels.setdefault((fold_identity(label), row["berry_id"]), set()).add(fold_identity(code))
    return {key for key, codes in labels.items() if len(codes) > 1}


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
        if not isinstance(payload, dict) or payload.get("kind") != "unreviewed_portfolio_name_observations":
            raise ValueError("Unknown portfolio observation format")
        if not isinstance(payload.get("sources"), list):
            raise ValueError("Portfolio observations need a source list")
        for source in payload.get("sources", []):
            if not isinstance(source, dict):
                raise ValueError("Portfolio source must be an object")
            if any(not isinstance(source.get(key), str) or not source[key].strip()
                   for key in ("id", "title", "url", "checked_on", "source_type", "enumerated_scope", "limitations")):
                raise ValueError("Portfolio source needs its identity, date and bounded page scope")
            if any(not isinstance(source.get(key), list) for key in ("company_ids", "berry_ids", "names")):
                raise ValueError("Portfolio source needs explicit company, berry and name lists")
            if any(not isinstance(cid, str) or not cid.strip() for cid in source["company_ids"]) or any(
                    not isinstance(berry, str) or berry not in BERRY_ORDER for berry in source["berry_ids"]):
                raise ValueError("Portfolio source needs valid company and berry identifiers")
            checked = date.fromisoformat(source["checked_on"])
            if source.get("published_date"):
                date.fromisoformat(source["published_date"])
            url = urlsplit(source["url"])
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
                raise ValueError("Portfolio source needs a public HTTP(S) URL")
            if source["capture_status"] not in {"names_enumerated", "unreadable", "partial"}:
                raise ValueError("Unknown portfolio capture status")
            if any(not isinstance(row, dict) or row.get("berry_id") not in BERRY_ORDER
                   or not isinstance(row.get("candidate_name"), str) or not row["candidate_name"].strip()
                   or any(key in row and not isinstance(row[key], str) for key in
                          ("denomination", "breeder_code", "trade_name", "display_label", "portfolio_context"))
                   or (row.get("product_url") and not _public_url(row["product_url"])) for row in source["names"]):
                raise ValueError("Portfolio names need an explicit berry and name")
            accounting = source.get("accounting")
            warnings = source.get("review_warnings", [])
            if not isinstance(warnings, list) or len(warnings) > 8 or any(
                    not isinstance(message, str) or not message.strip() or len(message) > 1000
                    for message in warnings):
                raise ValueError("Source review warnings need short, nonempty text")
            from app.services.variety_photos import compatible, validate_photo
            for name in source["names"]:
                if "photos" in name:
                    if not isinstance(name["photos"], list) or len(name["photos"]) > 12:
                        raise ValueError("Keep at most 12 attributed photos per source name")
                    for raw in name["photos"]:
                        if not compatible(validate_photo(raw), name, candidate=True):
                            raise ValueError("Photo caption identity must match the source name and berry")
            if accounting is not None:
                if not isinstance(accounting, dict) or any(
                        type(accounting.get(key)) is not int or accounting[key] < 0
                        for key in ("observed_items",)) or (
                        "reported_items" in accounting and (type(accounting["reported_items"]) is not int or accounting["reported_items"] < 0)):
                    raise ValueError("Portfolio accounting needs nonnegative item counts")
                if not isinstance(accounting.get("exclusions"), list) or any(
                        not isinstance(row, dict) or not isinstance(row.get("label"), str) or not row["label"].strip()
                        or not isinstance(row.get("reason"), str) or not row["reason"].strip()
                        or (row.get("url") and not _public_url(row["url"])) for row in accounting["exclusions"]):
                    raise ValueError("Excluded items need a label and reason")
                if "reported_scope" in accounting and (
                        "reported_items" not in accounting or not isinstance(accounting["reported_scope"], str)
                        or not accounting["reported_scope"].strip()):
                    raise ValueError("A stated total needs its nonempty scope label")
            note = source.get("company_site_note")
            if note is not None and (not isinstance(note, dict) or not note.get("reason") or
                    note.get("company_id") not in source["company_ids"] or any(
                    not _public_url(note.get(key, "")) for key in ("stored_url", "suggested_url", "reference_url"))):
                raise ValueError("Company site discrepancies need attributable public URLs")
            old = latest.get(source["id"])
            if old is None or checked >= date.fromisoformat(old["checked_on"]):
                latest[source["id"]] = source
    return list(latest.values())


def _identity_pair_notes(sources):
    """Literal source pair discrepancies, not alias decisions or a new resolver."""
    codes, labels, label_mentions = {}, {}, {}
    for source in sources:
        companies = tuple(sorted(source.get("company_ids", [])))
        for row in source["names"]:
            code = row.get("denomination") or row.get("breeder_code")
            label = row.get("trade_name") or row["candidate_name"]
            mention_label = label or row["candidate_name"]
            label_mentions.setdefault((row["berry_id"], fold_identity(mention_label)), []).append(
                (source["id"], _key(row), code))
            if code and label:
                scope = (companies, row["berry_id"])
                codes.setdefault((*scope, fold_identity(code)), set()).add(label)
                labels.setdefault((*scope, fold_identity(label)), set()).add(code)
    notes = {}
    for source in sources:
        companies = tuple(sorted(source.get("company_ids", [])))
        for row in source["names"]:
            scope = (companies, row["berry_id"])
            code = row.get("denomination") or row.get("breeder_code")
            label = row.get("trade_name") or row["candidate_name"]
            messages = []
            paired_labels = codes.get((*scope, fold_identity(code or "")), set())
            paired_codes = labels.get((*scope, fold_identity(label or "")), set())
            if len({fold_identity(value) for value in paired_labels}) > 1:
                messages.append("This code appears with multiple labels: " + ", ".join(sorted(paired_labels)) + ". Check the pairing before accepting aliases.")
            if len({fold_identity(value) for value in paired_codes}) > 1:
                messages.append("This label appears with multiple codes: " + ", ".join(sorted(paired_codes)) + ". Keep the identities unresolved until reviewed.")
            # A code-bearing release and an uncoded name in another source are
            # separate leads until a human resolves them. Different companies
            # alone do not establish different identities or breeder roles.
            mention_label = label or row["candidate_name"]
            mentions = label_mentions.get((row["berry_id"], fold_identity(mention_label)), [])
            other_mentions = [m for m in mentions if (m[0] != source["id"] or m[1] != _key(row)
                              or (code and m[2] and fold_identity(code) != fold_identity(m[2])))
                              and (m[1] != _key(row) or (code and m[2] and fold_identity(code) != fold_identity(m[2])))]
            if (code and any(not m[2] for m in other_mentions)) or (
                    not code and any(m[2] for m in other_mentions)):
                messages.append("This name appears with a code in one source and without it in another. "
                                "Check whether they refer to the same variety before combining the records.")
            different_codes = {m[2] for m in other_mentions if code and m[2]
                               and fold_identity(m[2]) != fold_identity(code)}
            if different_codes:
                messages.append("Different sources pair this name with different codes: " +
                                ", ".join(sorted({code, *different_codes})) +
                                ". Check the original records before accepting aliases.")
            notes[(source["id"], _key(row), label or "")] = messages
    return notes


def reconcile_portfolios(*, sources, varieties, entities, candidates, today=None):
    """Account for each explicitly enumerated name, retaining source/code identity.

    A shared trade name is not an identity key when a denomination is recorded.
    Exact matches use the existing resolver; ambiguous matches require review.
    """
    today = today or date.today()
    entity_index = {row["id"]: row for row in entities}
    canonical_ids = {row["id"] for row in varieties}
    coded_labels = _coded_label_keys(sources)
    def candidate_key(row):
        code = row.get("denomination") or row.get("breeder_code")
        return (fold_identity(code), row["berry_id"]) if code and _key(row) in coded_labels else _key(row)
    existing = {candidate_key(row): row for row in candidates}
    source_rows, additions = [], []
    provenance = {}
    pair_notes = _identity_pair_notes(sources)
    for source in sources:
        names = []
        companies = [{"entity_id": cid, "name": entity_index[cid]["name"],
                      "href": "/entities/" + entity_index[cid]["entity_type"] + "/" + cid}
                     for cid in source.get("company_ids", []) if cid in entity_index]
        for observation in source.get("names", []):
            query = {k: observation.get(k, "") for k in ("candidate_name", "denomination", "breeder_code", "berry_id")}
            result = resolve_identity(query, varieties)
            exact_ids = {row["variety_id"] for row in result["matches"] if row["reason"] == "exact_identity_string"}
            catalog_id = next(iter(exact_ids)) if len(exact_ids) == 1 else None
            identity_notes = pair_notes.get((source["id"], _key(observation),
                                            observation.get("trade_name") or observation["candidate_name"]), [])
            if identity_notes:
                catalog_id = None
            candidate = existing.get(candidate_key(observation))
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
                         "checked_on": source["checked_on"], "source_type": source["source_type"],
                         "companies": companies, **observation,
                         "identity_notes": identity_notes}
            if source.get("published_date"):
                reference["published_date"] = source["published_date"]
            if source.get("review_warnings"):
                reference["review_warnings"] = list(source["review_warnings"])
            provenance.setdefault(candidate_key(observation), []).append(reference)
            if status == "needs_review" and candidate is None:
                lead = observation
                if candidate_key(observation) != _key(observation):
                    lead = {**observation, "candidate_name": observation.get("denomination") or observation["breeder_code"],
                            "trade_name": observation.get("trade_name") or observation["candidate_name"]}
                candidate = build_candidate({**lead, "source_id": source["id"], "source_url": source["url"],
                    "source_label": source["title"], "source_type": source["source_type"],
                    "source_tier": {"nursery_catalog": "tier_2_nursery_catalog",
                                    "breeder_catalog": "tier_1_breeder_catalog",
                                    "breeder_program_report": "tier_1_breeder_catalog",
                                    "breeder_release_record": "tier_1_breeder_catalog",
                                    "technical_sheet": "tier_2_technical_sheet",
                                    "plant_patent": "tier_1_patent_pvr",
                                    "national_register": "tier_1_national_register",
                                    "conference_presentation": "tier_3_conference"}.get(
                                        source["source_type"], "weak_noncanonical_lead"),
                    "knowledge": {"origin": "primary_portfolio_observation"}},
                    varieties=varieties, discovered_at=source.get("observed_at"))
                # A portfolio reference is provenance, not an official registry.
                # This is derived-only; never replace an operator's stored row.
                candidate = {**candidate, "persisted": False, "discovered_from": "primary_portfolio",
                             "registration": {**candidate["registration"], "official_registry_source": ""}}
                additions.append(candidate)
                existing[candidate_key(observation)] = candidate
            labels = {"catalog_match": "Catalog match", "needs_review": "Needs identity review",
                      "previously_rejected": "Previously rejected", "distinct_awaiting_catalog": "Distinct · catalog entry pending"}
            names.append({**observation, "identity_notes": identity_notes, "catalog_id": catalog_id,
                          "candidate_id": candidate.get("id") if candidate else None,
                          "identity_key": candidate_key(observation), "status": status, "label": labels[status],
                          "href": "/entities/variety/" + catalog_id if catalog_id else
                                  "/varieties/candidates?" + urlencode({"q": observation["candidate_name"], "berry": observation["berry_id"]})})
        checked = date.fromisoformat(source["checked_on"])
        age = (today - checked).days
        freshness = "Check date in future" if age < 0 else "Recheck due" if age > 90 else "Checked recently"
        if source["capture_status"] == "unreadable" and age >= 0:
            freshness = "Retry due" if age > 90 else "Attempted recently"
        accounting = source.get("accounting")
        accounting_view = None
        if accounting is not None:
            accounted = len(names) + len(accounting["exclusions"])
            issues = []
            if accounted != accounting["observed_items"]:
                issues.append("Captured names and exclusions do not account for every observed item.")
            if accounting.get("reported_items") is not None and accounting["reported_items"] != accounting["observed_items"]:
                if accounting.get("reported_scope"):
                    issues.append(f"This page shows {accounting['observed_items']} items but reports "
                                  f"{accounting['reported_items']} {accounting['reported_scope']}. "
                                  "Check the remaining lists and their scope before calling the portfolio complete.")
                else:
                    issues.append("The source’s stated total differs from the captured item count; check pagination and scope.")
            accounting_view = {**accounting, "accounted_items": accounted, "issues": issues}
        source_rows.append({**source, "names": names, "companies": companies,
                            "accounting_view": accounting_view,
                            "needs_follow_up": source["capture_status"] != "names_enumerated" or bool(accounting_view and accounting_view["issues"]) or bool(source.get("review_warnings")),
                            "identity_issues": sorted({message for name in names for message in name["identity_notes"]}),
                            "age_days": age, "freshness": freshness,
                            "matched": sum(row["status"] == "catalog_match" for row in names),
                            "needs_review": sum(row["status"] == "needs_review" for row in names),
                            "closed": sum(row["status"] == "previously_rejected" for row in names),
                            "awaiting_catalog": sum(row["status"] == "distinct_awaiting_catalog" for row in names)})
    visible = [{**row, "portfolio_sources": provenance.get(candidate_key(row), []),
                "portfolio_review_warnings": sorted({message for ref in provenance.get(candidate_key(row), []) for message in ref.get("review_warnings", [])}),
                "portfolio_identity_notes": sorted({message for ref in provenance.get(candidate_key(row), []) for message in ref["identity_notes"]})}
               for row in [*candidates, *additions]]
    return source_rows, visible


def source_content_coverage(records):
    """Body-free availability counts; acquisition is separate from name recall.

    Only stored published records count. Pending content and primary portfolio
    snapshots have different populations and never enter this denominator.
    The existing reader classifier rejects access screens and keeps partial
    articles and transcripts distinct from complete article text.
    """
    states = {}
    for record in records:
        if record.get("status") != "published":
            continue
        state = classify_source_body(record)["state"]
        states[state] = states.get(state, 0) + 1
    return {
        "published_sources": sum(states.values()),
        "full_articles": states.get("body_available", 0),
        "partial_articles": states.get("body_partial", 0),
        "transcripts": states.get("transcript_available", 0),
        "readable_sources": sum(states.get(key, 0) for key in ("body_available", "body_partial", "transcript_available")),
        "access_screens": states.get("interstitial", 0),
        "descriptions_only": states.get("description_only", 0),
        "access_limited": states.get("access_limited", 0),
        "body_unavailable": states.get("body_unavailable", 0),
    }


def portfolio_coverage(*, data_dir, sources, varieties, entities, candidates, filters=None, today=None, company_catalog=None):
    filters = filters or {}
    today = today or date.today()
    berry = filters.get("berry", "")
    if berry and berry not in BERRY_ORDER:
        raise ValueError("Choose a supported berry")
    q = str(filters.get("q", "")).strip().casefold()
    company = str(filters.get("company", "")).strip()
    source_rows, visible = reconcile_portfolios(sources=sources, varieties=varieties, entities=entities, candidates=candidates, today=today)
    selected = [row for row in source_rows if (not berry or berry in row.get("berry_ids", []) or any(name["berry_id"] == berry for name in row["names"]))
                and (not company or company in row.get("company_ids", []))
                and (not q or q in " ".join([row["title"], *(c["name"] for c in row["companies"])]).casefold())]
    if berry:
        selected = [{**row, "names": [n for n in row["names"] if n["berry_id"] == berry],
                     "identity_issues": sorted({message for n in row["names"] if n["berry_id"] == berry for message in n["identity_notes"]}),
                     "matched": sum(n["status"] == "catalog_match" and n["berry_id"] == berry for n in row["names"]),
                     "needs_review": sum(n["status"] == "needs_review" and n["berry_id"] == berry for n in row["names"]),
                     "closed": sum(n["status"] == "previously_rejected" and n["berry_id"] == berry for n in row["names"]),
                     "awaiting_catalog": sum(n["status"] == "distinct_awaiting_catalog" and n["berry_id"] == berry for n in row["names"])} for row in selected]
    registry_path = data_dir / "imports/competitor-coverage-registry-2026-09-21/reconciliation-matrix.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))["rows"] if registry_path.is_file() else []
    photo_path = data_dir / "imports/variety-operator-seed-2026-09-30/rows.json"
    photo_rows = json.loads(photo_path.read_text(encoding="utf-8"))["rows"] if photo_path.is_file() else []
    index = {row["id"]: row for row in entities}
    # Reuse directory resolution for official_website, top-level fields and the
    # existing seed roster. The live caller supplies its analyst-edited catalog;
    # the offline audit has only public fields and never loads private overrides.
    company_catalog = company_directory.catalog(index) if company_catalog is None else company_catalog
    subjects = []
    for row in registry:
        ids = row.get("canonical_entity_ids") or []
        all_linked = [source for source in source_rows if set(source.get("company_ids", [])) & set(ids)]
        linked = [source for source in selected if set(source.get("company_ids", [])) & set(ids)]
        named_sources = [source for source in linked if source["capture_status"] == "names_enumerated" and source["names"]]
        source_status = ("names_found" if named_sources else "partial" if any(
            source["capture_status"] != "unreadable" for source in linked) else "unreadable" if linked else "not_started")
        profile_rows = [company_catalog[cid] for cid in ids if cid in company_catalog]
        edited_websites = [profile["website"] for profile in profile_rows if profile.get("website_edited")]
        websites = edited_websites if edited_websites else [row.get("website", "")] + [profile.get("website", "") for profile in profile_rows]
        website = next((url for url in websites if _public_url(url)), "")
        preferred = next((s for s in linked if s["capture_status"] == "names_enumerated"), None)
        partial = next((s for s in linked if s["capture_status"] == "partial"), None)
        if preferred:
            starting_url, starting_label = preferred["url"], "Checked page ↗"
        elif partial:
            starting_url, starting_label = partial["url"], "Partial page ↗"
        elif website:
            starting_url, starting_label = website, "Website ↗"
        else:
            starting_url = linked[0]["url"] if linked else ""
            starting_label = "Attempted source ↗"
        scope = sorted({berry for cid in ids for berry in index.get(cid, {}).get("berry_ids", []) if berry in BERRY_ORDER}
                       | {berry for source in all_linked for berry in source.get("berry_ids", [])}
                       | {photo["berry_id"] for photo in photo_rows if set(photo.get("company_ids", [])) & set(ids)})
        subjects.append({"name": row["input_registry_name"], "entity_ids": ids, "website": website,
                         "starting_url": starting_url, "starting_label": starting_label,
                         "site_notes": [s["company_site_note"] for s in linked if s.get("company_site_note")],
                         "berry_ids": scope, "berries": ", ".join(BERRY_LABELS[berry] for berry in scope) or "Scope needs checking",
                         "resolution": row["resolution_status"], "sources": linked,
                         "checked": bool(named_sources), "source_status": source_status,
                         "named_occurrences": sum(len(source["names"]) for source in linked),
                         "has_source_gaps": any(source["needs_follow_up"] for source in linked),
                         "href": "/entities/" + index[ids[0]]["entity_type"] + "/" + ids[0] if ids and ids[0] in index else ""})
    selected_subjects = [row for row in subjects if (not berry or berry in row["berry_ids"] or not row["berry_ids"])
                         and (not company or company in row["entity_ids"])
                         and (not q or q in row["name"].casefold() or row["sources"])]
    all_names = [name for source in selected for name in source["names"]]
    return {"sources": selected, "subjects": selected_subjects,
            "filters": {"berry": berry, "q": filters.get("q", ""), "company": company},
            "company_name": index.get(company, {}).get("name", "Selected company") if company else "",
            "summary": {"source_sections": len(selected), "readable_sections": sum(s["capture_status"] == "names_enumerated" for s in selected),
                        "unreadable_sections": sum(s["capture_status"] == "unreadable" for s in selected),
                        "follow_up_sections": sum(s["needs_follow_up"] for s in selected),
                        "names": len(all_names), "catalog_matches": sum(n["status"] == "catalog_match" for n in all_names),
                        "needs_review": sum(n["status"] == "needs_review" for n in all_names),
                        "registry_entries": len(selected_subjects), "registry_entries_checked": sum(s["checked"] for s in selected_subjects),
                        "registry_entries_partial_checks": sum(s["source_status"] == "partial" for s in selected_subjects),
                        "registry_entries_unavailable": sum(s["source_status"] == "unreadable" for s in selected_subjects),
                        "registry_entries_not_started": sum(s["source_status"] == "not_started" for s in selected_subjects)},
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
