"""Private, archive-first company news review packets.

This module never writes a report or canonical intelligence. The caller persists
each returned snapshot in the existing report record. Public discovery reuses
the safe reader and private source cache; only the public request labels and
date window leave the process. Report prose and archive passages are never sent
to a model. A finished bounded search is not a claim of complete news recall.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
import hashlib
import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from app.services.article_dedup import normalize_canonical_url
from app.services.report_builder.scope import resolve_entity_names
from app.services.report_builder.synthesis import SectionDraft
from app.services.topic_retrieval import normalize, plan_query, record_passages, retrieve

SCHEMA_VERSION = 1
MAX_COMPANIES = 100
ARCHIVE_SOURCE_LIMIT = 100
LEAD_SOURCE_LIMIT = 20
WEB_CAPTURE_LIMIT = 40
WEB_RETURN_LIMIT = 20
PLATFORM_CACHE_LIMIT = 150
MAX_SNAPSHOT_SOURCES = 5000
MAX_SNAPSHOT_ENTRIES = 5000
EDITABLE_ENTRY_FIELDS = frozenset({"headline", "summary", "news_angle", "qualification", "published_date", "event_date"})
_METADATA = {"title", "summary", "snippet"}
_NEWS = re.compile(r"\b(?:introduc\w*|releas\w*|launch\w*|licen[sc]\w*|patent\w*|grant\w*|filed|filing|trial\w*|results|published|announc\w*|reveal\w*|identif\w*|discover\w*|demonstrat\w*|acquir\w*|acquisit\w*|merg\w*|partner\w*|invest\w*|funding|funded|expand\w*|expansion|appoint\w*|opened|opens|opening|commission\w*|recall\w*|lawsuit\w*|litigation|bankrupt\w*|closed|closure|agreement\w*|award\w*)\b", re.I)
_BACKGROUND = re.compile(r"\b(?:growing guide|how to|current status|future directions|literature review|review of|company profile|company overview|catalogue|catalog|brochure)\b", re.I)
_PLANNED = re.compile(r"\b(?:plans? to|propos\w*|expected to|aims? to|scheduled to|will (?:open|launch|expand|acquire|complete))\b", re.I)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _key(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def _entities(entities: Mapping | Iterable[dict]) -> dict[str, dict]:
    values = entities.values() if isinstance(entities, Mapping) else entities
    return {str(row["id"]): row for row in values if isinstance(row, dict) and row.get("id")}


def _date(value: Any) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?", text):
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            pass
    return ""


def _required_date(value: Any, label: str) -> str:
    stamp = _date(value)
    if not stamp or str(value) != stamp:
        raise ValueError(f"Choose a valid {label} date (YYYY-MM-DD)")
    return stamp


def effective_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Apply report-only analyst edits without changing retained source data."""
    result = dict(entry)
    edits = entry.get("edits") if isinstance(entry.get("edits"), dict) else {}
    accepted = {key: value for key, value in edits.items() if key in EDITABLE_ENTRY_FIELDS and isinstance(value, str)}
    result.update(accepted)
    result["analyst_edited"] = bool(accepted)
    return result


def resolve_roster(roster: str | Iterable[str], *, entities: Mapping | Iterable[dict], company_ids: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Reuse canonical exact/alias resolution; no fuzzy identity guessing."""
    entity_map = _entities(entities)
    # A comma can be part of a legal company name. Text rosters are one name
    # per line (or semicolon); selected lists already supply separate values.
    names = re.split(r"[\n\r;]+", roster) if isinstance(roster, str) else list(roster)
    clean: list[str] = []
    for raw in names:
        if not isinstance(raw, str):
            raise ValueError("Company names must be text")
        name = re.sub(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", "", raw).strip()
        if not name:
            continue
        if len(name) > 200 or any(ord(ch) < 32 for ch in name) or not normalize(name):
            raise ValueError("Use company names of at most 200 characters")
        if normalize(name) not in {normalize(n) for n in clean}:
            clean.append(name)
    resolutions = resolve_entity_names(clean, entities=list(entity_map.values()), entity_type="company")
    resolved = {row.resolved_id for row in resolutions if row.resolved_id}
    for identifier in dict.fromkeys(company_ids):
        entity = entity_map.get(str(identifier))
        if not entity or entity.get("entity_type") != "company":
            raise ValueError("Choose companies from the company directory")
        if identifier not in resolved:
            clean.append(str(entity.get("name") or identifier))
            resolutions.append(resolve_entity_names([clean[-1]], entities=[entity], entity_type="company")[0])
            resolved.add(identifier)
    if not clean:
        raise ValueError("Choose a company list or enter at least one company")
    if len(clean) > MAX_COMPANIES:
        raise ValueError(f"A company news review accepts at most {MAX_COMPANIES} requested companies; split the roster rather than truncating it")
    companies = []
    for row in resolutions:
        resolution = "resolved" if row.resolved_id else "ambiguous" if row.ambiguous_ids else "unresolved"
        directory = entity_map.get(row.resolved_id) or {}
        identity_status = str(directory.get("status") or "") if directory else "unresolved"
        identity_required = bool(row.resolved_id and (identity_status == "unverified" or (directory.get("attributes") or {}).get("identity_review_required")))
        companies.append({
            "key": _key("company-", normalize(row.query)), "requested_name": row.query,
            "company_id": row.resolved_id, "canonical_name": row.resolved_name or "",
            "resolution": resolution, "candidate_ids": list(row.ambiguous_ids),
            "identity_status": identity_status, "identity_verification_required": identity_required,
            "archive_status": "pending", "web_status": "pending", "disposition": "pending",
            "notes": [], "counts": {}, "completed_at": "",
        })
    return companies


def create_review(roster: str | Iterable[str], *, entities: Mapping | Iterable[dict], from_date: str, through_date: str,
                  berry_id: str | None = None, topic: str = "", source_scope: str = "combined", as_of: str | None = None,
                  company_ids: Iterable[str] = ()) -> dict[str, Any]:
    start = _required_date(from_date, "start")
    end = _required_date(through_date, "end")
    cutoff = _required_date(as_of or date.today().isoformat(), "as-of")
    if start > end or end > cutoff:
        raise ValueError("Use a start date on or before the end date, and an end date on or before the as-of date")
    if cutoff > date.today().isoformat():
        raise ValueError("The as-of date cannot be in the future")
    if berry_id not in {None, "", "berry-strawberry", "berry-blueberry", "berry-raspberry", "berry-blackberry"}:
        raise ValueError("Choose a supported berry or all berries")
    if source_scope not in {"archive", "combined"}:
        raise ValueError("Choose archive-only or archive plus web research")
    if not isinstance(topic, str) or len(topic) > 500:
        raise ValueError("Keep the public research focus within 500 characters")
    companies = resolve_roster(roster, entities=entities, company_ids=company_ids)
    return {
        "schema_version": SCHEMA_VERSION, "from_date": start, "through_date": end, "as_of": cutoff,
        "berry_id": berry_id or "", "topic": topic.strip(), "source_scope": source_scope,
        "created_at": _now(), "completed_at": "", "status": "pending", "companies": companies,
        "sources": [], "entries": [], "completed_company_count": 0, "has_gaps": False,
        "bounds": {"companies": MAX_COMPANIES, "archive_sources_per_company": ARCHIVE_SOURCE_LIMIT,
                   "additional_leads_per_company": LEAD_SOURCE_LIMIT, "web_capture_candidates_per_company": WEB_CAPTURE_LIMIT,
                   "web_returned_sources_per_company": WEB_RETURN_LIMIT, "snapshot_sources": MAX_SNAPSHOT_SOURCES,
                   "snapshot_entries": MAX_SNAPSHOT_ENTRIES, "platform_cache_candidates_per_query": PLATFORM_CACHE_LIMIT},
        "method_note": "Platform archive first, then bounded public gap research for each requested company. Publication dates define the inclusive window; capture dates never substitute. Source statements remain attributed and require editorial review. Search completion does not establish exhaustive recall.",
    }


def prepare_archive_records(records: Mapping | Iterable[dict], inbox_dir: Path) -> list[dict]:
    """Hydrate already stored reader/transcript material once on explicit run.

    No fetch, translation, transcription, model call or canonical write occurs.
    """
    from app.services.feed_first_reader import capture_path, load_capture, merge_capture
    from app.services.media_reader import SPOKEN, stored_media, transcript_headers
    values = records.values() if isinstance(records, Mapping) else records
    headers = transcript_headers(inbox_dir)
    output = []
    for raw in values:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        if _excluded_primary_input(raw):
            # Retain the exclusion marker for run accounting, without reading
            # another private article/transcript body for derived/test input.
            output.append(raw)
            continue
        capture = load_capture(inbox_dir, str(raw["id"]))
        row = merge_capture(raw, capture)
        try:
            path = capture_path(inbox_dir, str(raw["id"]))
            if capture is None and (path.exists() or path.is_symlink()):
                row = {**row, "_company_news_archive_issue": "stored_capture_unavailable"}
        except OSError:
            row = {**row, "_company_news_archive_issue": "stored_capture_unavailable"}
        if row.get("media_format") in SPOKEN or row.get("source_type") == "industry_podcast":
            if not row.get("discovered_item_id"):
                matches = [h["item_id"] for h in headers if h.get("parent_evidence_id") == row["id"] and h.get("source_id") == row.get("source_id")]
                if len(matches) == 1:
                    row = {**row, "discovered_item_id": matches[0]}
            row = stored_media(row, inbox_dir)
            if row.get("transcript_read_error"):
                row = {**row, "_company_news_archive_issue": "stored_transcript_unavailable"}
        output.append(row)
    return output


def next_company_key(snapshot: dict[str, Any]) -> str | None:
    return next((row["key"] for row in snapshot.get("companies", []) if row.get("disposition") == "pending"), None)


def _names(company: dict, entities: dict) -> list[str]:
    entity = entities.get(company.get("company_id")) or {}
    return list(dict.fromkeys(str(v) for v in [company["requested_name"], company.get("canonical_name"), *(entity.get("aliases") or [])] if v))


def _mentions(text: str, names: Iterable[str]) -> bool:
    folded = normalize(text)
    for name in names:
        literal = normalize(name)
        if not literal:
            continue
        # CJK scripts do not use spaces as word boundaries. Latin names still
        # require whole-token boundaries (CIV cannot match "civil").
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", literal):
            if literal in folded:
                return True
        elif re.search(r"(?<!\w)" + re.escape(literal) + r"(?!\w)", folded):
            return True
    return False


def _company_match(row: dict, company: dict, names: list[str]) -> bool:
    if company.get("company_id") and company["company_id"] in (row.get("entity_ids") or []):
        return True
    return _mentions(" ".join(p for _, p in record_passages(row)), names)


def _excluded_primary_input(row: dict) -> bool:
    """Derived commentary and explicit test data are not publisher sources.

    Workspace captures retain original-source context for their own review
    workflow, but their title may be an analyst's private interpretation. The
    underlying publication remains eligible through its original record/cache.
    """
    social = row.get("social_observation") or {}
    def explicit_marker(value):
        return isinstance(value, str) and value.casefold() in {"demo", "fixture", "illustrative", "synthetic"}
    return bool(
        row.get("workspace_capture") or row.get("source_type") == "analyst_note" or explicit_marker(row.get("source_type"))
        or any(row.get(key) for key in ("is_demo", "demo", "illustrative", "fixture", "is_fixture"))
        or explicit_marker(row.get("data_class")) or explicit_marker(row.get("mode"))
        or explicit_marker(row.get("record_type"))
        or (isinstance(social, dict) and explicit_marker(social.get("mode")))
    )


def _query(snapshot: dict, company: dict) -> str:
    name = company.get("canonical_name") or company["requested_name"]
    crop = str(snapshot.get("berry_id") or "").removeprefix("berry-")
    return " ".join(filter(None, [name, crop, snapshot.get("topic")]))


def _scope_lead(row: dict, snapshot: dict) -> dict | None:
    """A literal company hit is retained when language/scope cannot be parsed."""
    stamp = _date(row.get("published_date"))
    if stamp and not (snapshot["from_date"] <= stamp <= snapshot["through_date"]):
        return None
    crop = snapshot.get("berry_id", "").removeprefix("berry-")
    declared = set(row.get("berry_ids") or [])
    known_crops = set(normalize(" ".join(p for _, p in record_passages(row))).split()) & {"strawberry", "blueberry", "raspberry", "blackberry"}
    if crop and ((declared and snapshot["berry_id"] not in declared) or (known_crops and crop not in known_crops)):
        return None
    return {**row, "passage": "", "passage_locator": "", "support_status": "scope_unverified"}


def _platform_cache(inbox_dir: Path, plan, names: list[str]) -> tuple[list[dict], dict]:
    """Reuse existing public captures, including literal native-script names.

    The shared FTS search remains primary. SQLite's unicode tokenizer treats
    an unspaced Japanese/Chinese sentence as one token; a bounded literal read
    fallback retains those company candidates without inventing a new index.
    Every fallback row passes the existing public-URL and body-hash contract.
    """
    from app.services.research_source_cache import cached_sources, _path, MAX_RECORD_BYTES
    from app.services.feed_first_reader import is_public_http_url
    rows, status = cached_sources(inbox_dir, plan, limit=PLATFORM_CACHE_LIMIT)
    diagnostics = {"status": status, "candidates": len(rows), "bounded": len(rows) >= PLATFORM_CACHE_LIMIT, "literal_candidates": 0}
    script_names = [normalize(n) for n in names if re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", n)]
    if script_names:
        try:
            path = _path(inbox_dir)
            if path.is_file():
                patterns = ["%" + name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%" for name in script_names]
                clauses = " OR ".join("(f.title LIKE ? ESCAPE '\\' OR f.body LIKE ? ESCAPE '\\')" for _ in patterns)
                parameters = [value for pattern in patterns for value in (pattern, pattern)]
                with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3) as db:
                    raw_rows = db.execute("SELECT s.record FROM source_search f JOIN sources s ON f.url=s.url WHERE " + clauses + " ORDER BY s.rowid DESC LIMIT ?", [*parameters, PLATFORM_CACHE_LIMIT + 1]).fetchall()
                diagnostics["literal_candidates"] = len(raw_rows)
                diagnostics["bounded"] = diagnostics["bounded"] or len(raw_rows) > PLATFORM_CACHE_LIMIT
                for (raw,) in raw_rows[:PLATFORM_CACHE_LIMIT]:
                    try:
                        if not isinstance(raw, str) or len(raw.encode()) > MAX_RECORD_BYTES:
                            raise ValueError("Capture size or type is invalid")
                        row = json.loads(raw)
                        paragraphs = (row.get("article") or {}).get("paragraphs") or []
                        body = "\n".join(str(p.get("text") or "") for p in paragraphs if isinstance(p, dict))
                        if not is_public_http_url(row.get("source_url")) or not body or hashlib.sha256(body.encode()).hexdigest() != row.get("source_version"):
                            raise ValueError("Capture provenance is invalid")
                        rows.append({**row, "trust_class": "LIVE / UNREVIEWED", "research_cache_reused": True})
                    except (ValueError, TypeError, AttributeError):
                        diagnostics["status"] = "unavailable"
        except (OSError, ValueError, sqlite3.Error):
            diagnostics["status"] = "unavailable"
    unique = {}
    for row in rows:
        identity = normalize_canonical_url(row.get("source_url")) or str(row.get("id"))
        unique.setdefault(identity, {**row, "_company_news_archive_cache": True})
    return list(unique.values()), diagnostics


def _capture_observer(rows: list[dict]) -> Callable:
    """Observe existing safe-reader results before query-language ranking.

    This does not issue extra requests or bypass the reader. It preserves a
    citation/verification lead when the shared matcher cannot interpret an
    otherwise inspected source, instead of silently losing native-script news.
    """
    from app.services.open_research_copy import fetch_topic_source
    from app.services.feed_first_reader import is_public_http_url
    lock = threading.Lock()
    def fetch(url):
        captured = fetch_topic_source(url)
        if isinstance(captured, dict):
            passages = captured.get("passages") or []
            if isinstance(passages, list) and all(isinstance(p, str) for p in passages):
                canonical = captured.get("canonical_url") or url
                if not is_public_http_url(canonical):
                    canonical = url
                locators = captured.get("passage_locators") or []
                row = {"id": _key("web-", str(canonical)), "title": captured.get("headline") or str(canonical),
                       "source_url": canonical, "published_date": captured.get("published_date") or "",
                       "publication_date_basis": captured.get("published_date_basis") or "unknown",
                       "source_name": str(canonical).split("/")[2] if "://" in str(canonical) else "Source",
                       "article": {"paragraphs": [{"index": i, "text": p, **({"locator": locators[i]} if i < len(locators) else {})} for i, p in enumerate(passages)]},
                       "capture_status": captured.get("availability") or "metadata_only",
                       "source_version": hashlib.sha256("\n".join(passages).encode()).hexdigest() if passages else "",
                       "capture_provenance": {k: captured[k] for k in ("method", "copy_scope", "original_url", "original_capture_status", "original_capture_reason") if k in captured}}
                with lock:
                    rows.append(row)
        return captured
    return fetch


def _source(row: dict, *, origin: str, company: dict, snapshot: dict) -> dict:
    from app.services.evidence_claim_review import trust_tier_label
    from app.services.feed_first_reader import is_public_http_url
    from app.services.research_source_holds import source_quote_hold
    url = str(row.get("source_url") or row.get("url") or "")
    # An invalid URL remains an internal Evidence citation, never an external link.
    url = url if is_public_http_url(url) else ""
    owned = [(loc, text) for loc, text in record_passages(row) if loc not in _METADATA]
    passage = str(row.get("passage") or "")
    locator = str(row.get("passage_locator") or "")
    body_supported = bool(passage and locator and locator not in _METADATA and row.get("support_status") == "body_supported")
    version = str(row.get("source_version") or "")
    cached_public = bool(row.get("_company_news_archive_cache"))
    if origin == "archive" and not cached_public:
        version = hashlib.sha256("\n\n".join(text for _, text in owned).encode()).hexdigest() if owned else ""
    body_supported = body_supported and bool(version)
    publication = _date(row.get("published_date"))
    date_basis = str(row.get("publication_date_basis") or row.get("published_date_basis") or ("stored_publication_date" if publication else "unknown"))
    nonpublication_date = bool(re.search(r"(?:captur(?:ed|e)?|retriev(?:ed|al)?|access(?:ed)?|search)[_-]?(?:date|at|time|metadata|result|hit)|last_modified|date_modified|updated_at|page_updated", date_basis, re.I))
    if nonpublication_date:
        publication = ""
    event_raw = row.get("event_date") or row.get("occurred_date") or ""
    event_date = _date(event_raw)
    event_text = event_date or str(event_raw).strip()[:200]
    capture_status = str(row.get("capture_status") or (row.get("reader_capture") or {}).get("availability") or ("stored" if owned else "metadata_only"))
    hold = row.get("source_review_hold") or row.get("_company_news_source_review_hold") or (source_quote_hold(row) or {}).get("reason")
    notes = []
    if nonpublication_date:
        notes.append("Capture, retrieval, search or page-modification timing is not accepted as an original publication date.")
    if row.get("published_date") and not publication:
        notes.append("The retained source lists publication timing as " + str(row["published_date"])[:120] + "; this is not an exact publication date.")
    for field in ("qualification", "does_not_prove", "date_qualification"):
        if isinstance(row.get(field), str) and row[field].strip():
            notes.append(row[field].strip()[:1500])
    provenance = deepcopy(row.get("capture_provenance") or row.get("reader_capture") or {})
    if not isinstance(provenance, dict):
        raise ValueError("Malformed source provenance")
    if provenance.get("copy_scope") and provenance["copy_scope"] != "full_source":
        notes.append("Inspected copy scope: " + str(provenance["copy_scope"]) + "; the excerpt does not establish omitted source material.")
    if capture_status in {"partial", "excerpt_only"}:
        notes.append("Only part of the source was inspected; omitted material has not been verified.")
    if row.get("translated") or row.get("translation"):
        notes.append("The inspected text is a translated source capture; consult the original wording when checking quotations.")
    if cached_public:
        notes.append("A previously captured public source was reused from the platform cache; it remains unreviewed.")
    eligibility = "dated_finding"
    if hold or row.get("support_status") == "source_review_hold" or (row.get("support_status") == "scope_unverified" and owned):
        eligibility = "scope_unverified"
        notes.append(str(hold or "The current matcher did not establish the requested scope. Language or subject scope requires analyst verification; this is not evidence of no qualifying development."))
    if capture_status in {"blocked", "unavailable", "failed", "robots_denied", "paywall"}:
        eligibility = "blocked"
        notes.append("The source could not be inspected; discovery metadata cannot substantiate report prose.")
    elif not body_supported and eligibility == "dated_finding":
        eligibility = "metadata_only"
        notes.append("Only metadata or an unsupported passage is available; inspect the source before including its claims.")
    if eligibility == "dated_finding" and not publication:
        eligibility = "undated"
        notes.append("Original publication date is unknown; capture date is not used as a replacement.")
    elif eligibility == "dated_finding" and not (snapshot["from_date"] <= publication <= snapshot["through_date"]):
        eligibility = "date_outside_window"
        notes.append("Original publication date falls outside the requested inclusive window.")
    if company.get("identity_verification_required"):
        eligibility = "identity_unresolved"
        notes.append("An exact directory name matched, but the directory identity is unverified or requires identity review. Matching source material is retained as a lead; this report did not approve the company identity.")
    elif company["resolution"] != "resolved":
        eligibility = "identity_unresolved"
        notes.append("Requested company identity is unresolved or ambiguous; no canonical association was inferred.")
    title = str(row.get("title") or "Untitled source")
    if eligibility == "dated_finding" and _BACKGROUND.search(title):
        eligibility = "background"
        notes.append("This passage is background or does not establish a new company development.")
    elif eligibility == "dated_finding" and row.get("relevance") != "direct" and not _NEWS.search(title + " " + passage):
        eligibility = "editorial_verification"
        notes.append("Newsworthiness could not be established automatically. Verify the wording or language before deciding whether this is a new development; missing English keywords are not evidence of no event.")
    reproduced_year = re.search(r"\b((?:19|20)\d{2})\s+(?:study|research|paper)\b", passage, re.I)
    if eligibility == "dated_finding" and row.get("relevance") == "background" and reproduced_year and publication and reproduced_year[1] < publication[:4]:
        eligibility = "background"
        notes.append("This source reproduces or discusses older research; the article publication date does not re-date the underlying study.")
    if event_date and not (snapshot["from_date"] <= event_date <= snapshot["through_date"]):
        notes.append(f"The source explicitly dates the underlying event {event_date}; publication and event timing differ.")
        if event_date < snapshot["from_date"] and eligibility == "dated_finding":
            eligibility = "background"
    if event_text and not event_date:
        notes.append("Reported event timing is qualified text, not an exact verified date: " + event_text + ".")
    elif not event_date:
        notes.append("Event timing is not independently established; the retained date is the source publication date.")
    if _PLANNED.search(title + " " + passage):
        notes.append("The source describes plans or expected activity; completion is not established.")
    if re.search(r"\b(?:patent|application|filing|pvr|pbr)\b", title + " " + passage, re.I):
        notes.append("Preserve the source's filing/application/grant distinction; a filing does not establish a granted right.")
    if origin == "web":
        notes.append("Public web capture is unreviewed and does not create trusted Evidence.")
    trust = trust_tier_label(row) if origin == "archive" and not cached_public and row.get("status") == "published" else "PENDING / UNREVIEWED" if origin == "archive" and not cached_public else "LIVE / UNREVIEWED"
    identity = normalize_canonical_url(url) or str(row.get("id") or title)
    source_id = _key("cns-", identity + "|" + version)
    archive_type = "public_research_cache" if cached_public else "published_evidence" if origin == "archive" and row.get("status") == "published" else "stored_platform_source" if origin == "archive" else ""
    capture_channel = "public_research_cache" if cached_public or row.get("research_cache_reused") else "public_web_capture" if origin == "web" else "stored_reader_capture" if row.get("reader_capture") else "stored_transcript" if row.get("transcript") else "stored_platform_record"
    platform_matches = []
    if origin == "archive" and not cached_public and row.get("id"):
        platform_matches.append({"record_id": str(row["id"]), "trust_class": trust,
            "archive_source_type": archive_type, "capture_channel": capture_channel,
            "source_version": version, "published_date": publication, "publication_date_basis": date_basis,
            **{field: str(row[field]) for field in ("retrieved_at", "captured_at", "captured_date") if row.get(field)}})
    return {
        "id": source_id, "title": title, "url": url, "source_url": url, "source_name": str(row.get("source_name") or "Source"),
        "published_date": publication, "publication_date_basis": date_basis,
        "publication_date_text": str(row.get("published_date") or ""),
        "event_date": event_text, "origin": origin, "trust_class": trust,
        "archive_source_type": archive_type, "capture_channel": capture_channel,
        "platform_matches": platform_matches,
        "excerpt": passage if body_supported and not hold else "", "passage": passage if body_supported and not hold else "",
        "passage_locator": locator if body_supported and not hold else "", "source_version": version,
        "source_version_basis": "stored_source_passages" if origin == "archive" and not cached_public else "public_capture",
        "capture_status": capture_status, "capture_provenance": provenance,
        "retrieved_at": str(row.get("retrieved_at") or row.get("captured_at") or row.get("captured_date") or _now()), "evidence_id": str(row.get("id") or "") if origin == "archive" and not cached_public else "",
        "research_cache_reused": bool(cached_public or row.get("research_cache_reused")),
        "eligibility": eligibility, "qualification": " ".join(notes), "company_keys": [company["key"]],
        "company_context": {company["key"]: {"eligibility": eligibility, "qualification": " ".join(notes), "origin": origin, "public_cache_reused": cached_public}},
    }


def _merge_source_trace(preferred: dict, *observations: dict) -> dict:
    """Keep exact-URL platform pointers when a fresh body replaces metadata.

    The pointers describe retained records, not independent confirmation,
    original first-seen time, or the trust of the preferred source text.
    They are observed matches, not an inventory of every stored duplicate.
    Public research-cache captures are never canonical/platform record matches.
    """
    matches = {}
    for source in observations:
        for match in source.get("platform_matches", []):
            key = tuple(str(match.get(field) or "") for field in
                ("record_id", "trust_class", "capture_channel", "source_version"))
            matches.setdefault(key, deepcopy(match))
    preferred["platform_matches"] = list(matches.values())
    preferred["research_cache_reused"] = any(source.get("research_cache_reused") for source in observations)
    if matches and preferred.get("origin") == "web":
        note = "This URL was already retained in the platform; the fresh capture is report-only and remains unreviewed."
        if note not in preferred["qualification"]:
            preferred["qualification"] += " " + note
        for context in preferred.get("company_context", {}).values():
            if note not in context.get("qualification", ""):
                context["qualification"] = (context.get("qualification", "") + " " + note).strip()
    return preferred


def _short_excerpt(text: str, limit: int = 200) -> str:
    words = text.split()
    excerpt = " ".join(words[:25])
    if len(words) <= 25 and len(excerpt) <= limit:
        return excerpt
    part = excerpt[:limit]
    endings = list(re.finditer(r"[.!?](?:[\"”’])?(?=\s|$)", part))
    if endings and endings[-1].end() > 60:
        return part[:endings[-1].end()]
    return (part.rsplit(" ", 1)[0] if " " in part and len(part) < len(excerpt) else part) + "…"


def _entry(source: dict, company: dict) -> dict:
    development = source["eligibility"] == "dated_finding"
    return {
        "id": _key("cne-", company["key"] + "|" + source["id"]), "company_key": company["key"],
        "company_id": company.get("company_id"), "headline": source["title"], "published_date": source["published_date"],
        "event_date": source["event_date"], "summary": (f"{source['source_name']} reports: “{_short_excerpt(source['excerpt'])}”" if development else ""),
        "news_angle": _news_angle(source) if development else "Research lead requiring verification.",
        "qualification": source["qualification"], "source_ids": [source["id"]], "included": development,
        "entry_type": "development" if development else "lead", "review_status": "unreviewed", "edits": {},
    }


def _news_angle(source: dict) -> str:
    """Editorial questions, never an invented commercial-impact conclusion."""
    text = source["title"] + " " + source["excerpt"]
    if re.search(r"\b(?:patent|application|filing|pvr|pbr|grant)\b", text, re.I):
        return "Which rights stage was reported, and what territory or licence scope is documented?"
    if re.search(r"\b(?:cultivar|variety|genetics|licen[sc]\w*|breeding)\b", text, re.I):
        return "Which varieties or genetics become available, to whom, and on what terms?"
    if re.search(r"\b(?:trial|research|study|experiment|results)\b", text, re.I):
        return "What was measured, where, and how far can the reported results be generalized?"
    if re.search(r"\b(?:recall|lawsuit|litigation|bankrupt\w*)\b", text, re.I):
        return "What is the confirmed scope, timing and affected operation of the reported risk?"
    if re.search(r"\b(?:retail\w*|marketing|distribut\w*|supermarket|export\w*)\b", text, re.I):
        return "Which retail or distribution change is documented, and what scale or markets are confirmed?"
    if re.search(r"\b(?:acquir\w*|acquisition|merg\w*|invest\w*|expand\w*|expansion|appoint\w*|opened|closed)\b", text, re.I):
        return "What ownership, capacity or operating change was announced, and has it completed?"
    return "What changed for this company, and which commercial effects are supported by the source?"


def _update_status(snapshot: dict) -> dict:
    pending = [r for r in snapshot["companies"] if r.get("disposition") == "pending"]
    snapshot["completed_company_count"] = len(snapshot["companies"]) - len(pending)
    snapshot["has_gaps"] = any(r.get("disposition") != "has_findings" for r in snapshot["companies"])
    if pending:
        snapshot["status"] = "in_progress" if snapshot["completed_company_count"] else "pending"
        snapshot["completed_at"] = ""
    else:
        snapshot["status"] = "partial" if any(r.get("archive_status") in {"failed", "partial"} or r.get("web_status") in {"failed", "partial", "blocked"} for r in snapshot["companies"]) else "complete"
        snapshot["completed_at"] = _now()
    return snapshot


def research_one_company(snapshot: dict[str, Any], company_key: str, *, entities: Mapping | Iterable[dict],
                         archive_records: Mapping | Iterable[dict], inbox_dir: Path, data_dir: Path | None = None,
                         discoverer: Callable | None = None, force: bool = False,
                         excluded_source_urls: Iterable[str] = ()) -> dict[str, Any]:
    """One bounded, resumable company step; all caller-owned input is untouched."""
    result = deepcopy(snapshot)
    company = next((r for r in result.get("companies", []) if r.get("key") == company_key), None)
    if company is None:
        raise ValueError("Company is not in this review")
    if company.get("disposition") != "pending" and not force:
        return result
    entity_map = _entities(entities)
    names = _names(company, entity_map)
    query = _query(result, company)
    plan = replace(plan_query(query), start=None, end=None)
    date_suffix = f" from {result['from_date']} through {result['through_date']}"
    dated_plan = replace(plan, raw_query=plan.raw_query + date_suffix,
                         interpreted_query=plan.interpreted_query + date_suffix,
                         start=result["from_date"], end=result["through_date"])
    company["notes"] = []
    if company.get("identity_verification_required"):
        company["notes"].append("Exact directory match retained: company identity remains unverified. Public-source matches are research leads until the existing identity review resolves this gap.")
    company["counts"] = {"archive_records_scanned": 0, "archive_matched": 0, "archive_retained": 0, "archive_overflow": 0,
                         "web_candidates": 0, "web_retained": 0, "web_budget_excluded": 0, "web_queries": 0,
                         "deleted_source_exclusions": 0, "archive_source_errors": 0, "web_source_errors": 0,
                         "archive_non_source_exclusions": 0, "web_non_source_exclusions": 0}
    company["source_errors"] = []
    failed_source_keys = set()
    def source_error(row, origin, exc):
        identity = str(row.get("id") or row.get("source_url") or "unknown") if isinstance(row, dict) else "invalid-record"
        key = _key("source-", identity)
        if (origin, key) in failed_source_keys:
            return
        failed_source_keys.add((origin, key))
        company["counts"][origin + "_source_errors"] += 1
        if len(company["source_errors"]) < 20:
            # A stable opaque reference, never raw exception/provider text.
            company["source_errors"].append({"source_key": key, "origin": origin, "error_type": type(exc).__name__})
    excluded = {key for url in [*excluded_source_urls, *result.get("excluded_source_urls", [])] if url and (key := normalize_canonical_url(url))}
    def eligible(row):
        if normalize_canonical_url(row.get("source_url") or row.get("url")) in excluded:
            company["counts"]["deleted_source_exclusions"] += 1
            return False
        return True
    retained: list[dict] = []
    def retain_rows(rows, origin):
        for raw in rows:
            try:
                retained.append(_source(raw, origin=origin, company=company, snapshot=result))
            except Exception as exc:
                source_error(raw, origin, exc)
    def company_rows(rows, origin):
        matched = []
        for raw in rows:
            try:
                if not isinstance(raw, dict):
                    raise ValueError("Malformed source record")
                if _excluded_primary_input(raw):
                    company["counts"][origin + "_non_source_exclusions"] += 1
                    continue
                record_passages(raw)  # Check body shape even for an entity-ID match.
                if _company_match(raw, company, names) and eligible(raw):
                    matched.append(raw)
            except Exception as exc:
                source_error(raw, origin, exc)
        return matched
    values = list(archive_records.values()) if isinstance(archive_records, Mapping) else list(archive_records)
    try:
        cached, cache_diagnostics = _platform_cache(Path(inbox_dir), plan, names)
        values.extend(cached)
        company["counts"]["archive_public_cache_candidates"] = cache_diagnostics["candidates"]
        company["counts"]["archive_literal_cache_candidates"] = cache_diagnostics["literal_candidates"]
        company["counts"]["archive_records_scanned"] = len(values)
        candidates = [{**r, "_company_news_source_review_hold": r.get("source_review_hold")} for r in company_rows(values, "archive")]
        hydration_issues = sum(bool(r.get("_company_news_archive_issue")) for r in candidates)
        try:
            matches = retrieve(candidates, plan, entities=entity_map, limit=len(candidates) + 1)
        except Exception:
            matches = []
            for raw in candidates:
                try:
                    matches.extend(retrieve([raw], plan, entities=entity_map, limit=1))
                except Exception as exc:
                    source_error(raw, "archive", exc)
        dated = [r for r in matches if _date(r.get("published_date")) and result["from_date"] <= _date(r["published_date"]) <= result["through_date"]]
        leads = [r for r in matches if not _date(r.get("published_date"))]
        matched_keys = {normalize_canonical_url(r.get("source_url")) or str(r.get("id")) for r in matches}
        for row in candidates:
            identity = normalize_canonical_url(row.get("source_url")) or str(row.get("id"))
            if identity in matched_keys:
                continue
            # Preserve literal company matches which the shared matcher cannot
            # interpret (including untranslated scripts) as verification leads.
            # No article claim or crop/event interpretation is generated.
            if lead := _scope_lead(row, result):
                leads.append(lead)
        company["counts"]["archive_matched"] = len(dated)
        overflow = max(0, len(dated) - ARCHIVE_SOURCE_LIMIT) + max(0, len(leads) - LEAD_SOURCE_LIMIT)
        retain_rows([*dated[:ARCHIVE_SOURCE_LIMIT], *leads[:LEAD_SOURCE_LIMIT]], "archive")
        company["counts"].update(archive_retained=len(retained), archive_overflow=overflow)
        company["archive_status"] = "partial" if overflow or hydration_issues or company["counts"]["archive_source_errors"] or cache_diagnostics["status"] == "unavailable" or cache_diagnostics["bounded"] else "complete"
        if cache_diagnostics["status"] == "unavailable" or cache_diagnostics["bounded"]:
            company["notes"].append("The platform public-source cache was unavailable or reached its candidate bound; this is incomplete archive coverage, not a zero-finding result.")
        company["counts"]["archive_source_read_issues"] = hydration_issues
        if hydration_issues:
            company["notes"].append(f"{hydration_issues} stored source captures or transcripts could not be read; available metadata is not treated as inspected source text.")
        if overflow:
            company["notes"].append(f"Archive bound reached: {overflow} matching sources were not retained; narrow the window or split this company's review.")
    except Exception as exc:
        company["archive_status"] = "failed"
        company["notes"].append("Archive research failed (" + type(exc).__name__ + "); this is not a zero-finding result.")
    if result.get("archive_index_unavailable") and company["archive_status"] == "complete":
        company["archive_status"] = "partial"
        company["notes"].append("Part of the retained platform-source index was unavailable. Available records were searched, but archive coverage is incomplete.")
    full_budget = len(result.get("sources", [])) >= MAX_SNAPSHOT_SOURCES or len(result.get("entries", [])) >= MAX_SNAPSHOT_ENTRIES
    if result["source_scope"] == "combined" and full_budget:
        company["web_status"] = "partial"
        company["notes"].append("The saved review source/entry budget is full; web research was not started. Split the roster or narrow the date window in a new version.")
    elif result["source_scope"] == "combined":
        captured_rows: list[dict] = []
        use_observer = discoverer is None
        if discoverer is None:
            from app.services.topic_discovery import discover_topic
            discoverer = discover_topic
        audit: list[dict] = []
        try:
            options = {"inbox_dir": Path(inbox_dir), "entities": entity_map,
                       "constraints": {"public_labels": [company.get("canonical_name") or company["requested_name"], result.get("berry_id", "").removeprefix("berry-")],
                                       "required_label_groups": [names]}, "capture_audit": audit.extend}
            if data_dir is not None:
                options["data_dir"] = Path(data_dir)
            if use_observer:
                options["fetcher"] = _capture_observer(captured_rows)
            web = discoverer(dated_plan, **options)
            web_rows = company_rows(web.get("items", []), "web")
            retain_rows(web_rows, "web")
            # Successful captures excluded by explicit date matching can still
            # supply honest undated leads, without another provider request.
            from app.services.research_source_cache import cached_sources
            history, history_status = cached_sources(Path(inbox_dir), plan)
            history = company_rows(history, "web")
            undated = [r for r in history if not _date(r.get("published_date"))]
            undated_matches = retrieve(undated, plan, entities=entity_map, limit=LEAD_SOURCE_LIMIT + 1)
            returned_urls = {normalize_canonical_url(r.get("url")) or r["id"] for r in retained}
            extra_leads = list(undated_matches)
            extra_urls = {normalize_canonical_url(r.get("source_url")) or str(r.get("id")) for r in extra_leads}
            for row in [*captured_rows, *history]:
                identity = normalize_canonical_url(row.get("source_url")) or str(row.get("id"))
                if identity in returned_urls or identity in extra_urls or not _company_match(row, company, names) or not eligible(row):
                    continue
                if lead := _scope_lead(row, result):
                    extra_leads.append(lead)
                    extra_urls.add(identity)
            retain_rows(extra_leads[:LEAD_SOURCE_LIMIT], "web")
            capture_counts = Counter(str(r.get("capture_status") or "unknown") for r in audit)
            unretained = sum(r.get("capture_status") in {"full", "partial", "excerpt_only"} and r.get("retained") is False for r in audit)
            candidate_count = int(web.get("candidate_count") or 0)
            failures = bool(web.get("failures"))
            bounded = candidate_count > WEB_CAPTURE_LIMIT or len(web.get("items") or []) >= WEB_RETURN_LIMIT or capture_counts["budget_excluded"] > 0 or len(extra_leads) > LEAD_SOURCE_LIMIT or len(history) >= 150
            incomplete = web.get("status") in {"partial", "failed", "blocked", "unavailable"} or failures or bounded or unretained or company["counts"]["web_source_errors"] or history_status == "unavailable" or web.get("history_status") == "unavailable"
            company["web_status"] = "blocked" if web.get("status") == "blocked" else "failed" if web.get("status") in {"failed", "unavailable"} else "partial" if incomplete else "complete"
            company["counts"].update(web_candidates=candidate_count, web_retained=len(web_rows) + min(len(extra_leads), LEAD_SOURCE_LIMIT),
                                     web_queries=int(web.get("queries_this_request") or 0), web_budget_excluded=capture_counts["budget_excluded"],
                                     web_capture_statuses=dict(capture_counts), web_unretained_captures=unretained)
            company["discovery"] = {key: deepcopy(web.get(key)) for key in ("status", "provider", "cache_hit", "candidate_count", "capture_count", "queries_this_request", "history_status", "fallback_used", "credit_free_only") if key in web}
            if incomplete:
                company["notes"].append("Public gap research is incomplete or reached a bounded source limit; retained findings do not establish full company coverage.")
            if unretained:
                company["notes"].append(f"{unretained} inspected public candidates could not be verified inside the requested identity, language, crop or date scope. This was not interpreted as evidence of no new activity.")
            blocked = sum(n for label, n in capture_counts.items() if label in {"blocked", "failed", "unavailable", "metadata_only", "snippet_only"})
            if blocked:
                company["notes"].append(f"{blocked} public candidates could not supply inspected source text; metadata alone was not narrated as a finding.")
                if company["web_status"] == "complete":
                    company["web_status"] = "partial"
        except Exception as exc:
            company["web_status"] = "failed"
            company["notes"].append("Public gap research failed (" + type(exc).__name__ + "); this is not a zero-finding result.")
    else:
        company["web_status"] = "not_requested"
        company["notes"].append("Archive-only scope: no web research was requested.")
    if company["counts"]["deleted_source_exclusions"]:
        company["notes"].append("Previously deleted sources were excluded from this report, including equivalent archive/web URLs.")
    for origin in ("archive", "web"):
        if company["counts"][origin + "_source_errors"]:
            company["notes"].append(f"{company['counts'][origin + '_source_errors']} {origin} source records could not be parsed. Valid findings were retained; malformed records do not count as no-hit results.")
        if company["counts"][origin + "_non_source_exclusions"]:
            company["notes"].append(f"Excluded {company['counts'][origin + '_non_source_exclusions']} derived workspace/analyst records or explicit illustrative/test inputs from primary news sourcing; original publications remain eligible separately.")
    # Prefer the platform source snapshot for a same-URL duplicate. Other
    # companies may cite the same retained source without creating duplicates.
    deduped: dict[str, dict] = {}
    for source in retained:
        identity = normalize_canonical_url(source.get("url")) or source["id"]
        old = deduped.get(identity)
        if old is None:
            deduped[identity] = source
        else:
            preferred = source if old["eligibility"] != "dated_finding" and source["eligibility"] == "dated_finding" else old
            deduped[identity] = _merge_source_trace(preferred, old, source)
    selected = list(deduped.values())
    source_map = {s["id"]: s for s in result.get("sources", [])}
    available = max(0, MAX_SNAPSHOT_SOURCES - len(source_map))
    bounded_selected = []
    for source in selected:
        if source["id"] in source_map or available:
            bounded_selected.append(source)
            if source["id"] not in source_map:
                available -= 1
    budget_excluded = len(selected) - len(bounded_selected)
    selected = bounded_selected
    company["counts"]["snapshot_source_budget_excluded"] = budget_excluded
    if budget_excluded:
        company["archive_status"] = "partial"
        company["notes"].append(f"Saved review source budget reached: {budget_excluded} matching sources could not be retained. This company's coverage is incomplete.")
    editorial_leads = sum(s["eligibility"] in {"editorial_verification", "scope_unverified"} for s in selected)
    if editorial_leads:
        company["counts"]["editorial_verification_leads"] = editorial_leads
        company["notes"].append(f"{editorial_leads} sources need language, scope or editorial verification. They were retained as excluded leads, not classified as evidence of no new activity.")
        if any(s["origin"] == "archive" and s["eligibility"] in {"editorial_verification", "scope_unverified"} for s in selected):
            company["archive_status"] = "partial"
        if any(s["origin"] == "web" and s["eligibility"] in {"editorial_verification", "scope_unverified"} for s in selected):
            company["web_status"] = "partial"
    for source in selected:
        if source["id"] in source_map:
            old = source_map[source["id"]]
            keys = list(dict.fromkeys([*old.get("company_keys", []), company_key]))
            contexts = {**old.get("company_context", {}), **source.get("company_context", {})}
            if old.get("eligibility") != "dated_finding" and source.get("eligibility") == "dated_finding":
                source_map[source["id"]] = source
            source_map[source["id"]].update(company_keys=keys, company_context=contexts)
            _merge_source_trace(source_map[source["id"]], old, source)
        else:
            source_map[source["id"]] = source
    result["sources"] = list(source_map.values())
    previous = {e["id"]: e for e in result.get("entries", [])}
    current_entries = [_entry(s, company) for s in selected]
    # Conservative source-event grouping reuses the platform's existing logic;
    # multiple citations never imply independent confirmation.
    from app.services.research_event_groups import event_groups
    grouped_rows = [{**s, "published_date": s["published_date"], "article": {"paragraphs": [{"text": s["excerpt"]}]}} for s in selected if s["eligibility"] == "dated_finding"]
    try:
        groups = event_groups(grouped_rows, entity_map)
    except Exception as exc:
        groups = []
        company["archive_status"] = "partial"
        company["notes"].append("Related-source grouping was unavailable (" + type(exc).__name__ + "); individual source rows were retained and independence was not inferred.")
    removed_entries = set()
    for group in groups:
        if len(group["member_ids"]) < 2:
            continue
        members = [e for e in current_entries if e["source_ids"][0] in group["member_ids"]]
        first = members[0]
        first["source_ids"] = list(group["member_ids"])
        first["qualification"] += " Related coverage was grouped conservatively; source independence is not established."
        removed_entries.update(e["id"] for e in members[1:])
    for entry in current_entries:
        if entry["id"] in removed_entries:
            continue
        # Explicit retries preserve analyst overrides and inclusion decisions.
        if entry["id"] in previous:
            old = previous[entry["id"]]
            entry.update({key: deepcopy(old[key]) for key in ("edits", "included", "review_status", "edit_revision", "edited_at", "manual_qualification") if key in old})
        elif len(previous) >= MAX_SNAPSHOT_ENTRIES:
            removed_entries.add(entry["id"])
            company["counts"]["snapshot_entry_budget_excluded"] = company["counts"].get("snapshot_entry_budget_excluded", 0) + 1
            company["archive_status"] = "partial"
            continue
        previous[entry["id"]] = entry
    result["entries"] = list(previous.values())
    development_count = sum(e["entry_type"] == "development" and e["id"] not in removed_entries for e in current_entries)
    lead_count = sum(e["entry_type"] == "lead" and e["id"] not in removed_entries for e in current_entries)
    if company["counts"].get("snapshot_entry_budget_excluded"):
        company["notes"].append("Saved review entry budget reached; matching sources were retained but not all could become report rows. Split this review before treating coverage as complete.")
    company["counts"].update(developments=development_count, leads=lead_count,
                             archive_retained=sum(s["origin"] == "archive" for s in selected),
                             web_retained=sum(s["origin"] == "web" for s in selected))
    if company.get("identity_verification_required"):
        company["disposition"] = "identity_unresolved"
    elif company["resolution"] == "ambiguous":
        company["disposition"] = "identity_ambiguous"
    elif company["resolution"] == "unresolved":
        company["disposition"] = "identity_unresolved"
    elif company["archive_status"] in {"partial", "failed"} or company["web_status"] in {"partial", "failed"}:
        company["disposition"] = "incomplete"
    elif company["web_status"] == "blocked" and not development_count:
        company["disposition"] = "blocked"
    else:
        company["disposition"] = "has_findings" if development_count else "leads_only" if lead_count else "no_qualifying_findings"
    company["completed_at"] = _now()
    return _update_status(result)


def review_packet(snapshot: dict[str, Any]) -> dict[str, Any]:
    """The source trace for the existing Report Builder; no live resolution."""
    sources = snapshot.get("sources", [])
    return {"report_type": "company_news_review", "berry_id": snapshot.get("berry_id"), "company_news_review": snapshot,
            "companies": [{"id": c.get("company_id") or c["key"], "name": c.get("canonical_name") or c["requested_name"]} for c in snapshot.get("companies", [])],
            "source_trace": [{**s, "href": s.get("url") or ("/evidence/" + s["evidence_id"] if s.get("evidence_id") else ""), "date": s.get("published_date", ""), "trust": s.get("trust_class", "")} for s in sources],
            "known_ids": {s["id"] for s in sources}, "recent_developments": [], "signals": [], "assessments": [], "varieties": [], "variety_candidates": []}


def review_sections(snapshot: dict[str, Any]) -> list[SectionDraft]:
    """Deterministic attributed narrative from the same rows as the workbook."""
    sections = []
    for company in snapshot.get("companies", []):
        entries = [effective_entry(e) for e in snapshot.get("entries", []) if e.get("company_key") == company["key"] and e.get("included")]
        text = "\n\n".join(f"{e['headline']} ({e.get('published_date') or 'publication date unverified'})\n{e.get('summary') or ''}\n{e.get('news_angle') or ''}\nQualification: {e.get('qualification') or ''}\n" + " ".join("[" + sid + "]" for sid in e.get("source_ids", [])) for e in entries)
        if not text:
            text = "No included dated finding in this saved review. Outcome: " + str(company.get("disposition", "pending")).replace("_", " ") + "."
        if company.get("notes"):
            text += "\n\nResearch qualifications: " + " ".join(company["notes"])
        sections.append(SectionDraft("news_" + company["key"], company.get("canonical_name") or company["requested_name"], text,
                                     tuple(dict.fromkeys(sid for e in entries for sid in e.get("source_ids", []))), "structured", None, None))
    scope = f"Publication window: {snapshot['from_date']} through {snapshot['through_date']} inclusive. As of {snapshot['as_of']}. Source scope: {snapshot['source_scope']}.\n{snapshot.get('method_note', '')}"
    sections.append(SectionDraft("scope_method", "Scope and source qualifications", scope, (), "structured", None, None))
    return sections
