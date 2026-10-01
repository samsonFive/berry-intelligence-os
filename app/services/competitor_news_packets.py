"""Private, reproducible news exports. Capture never approves or publishes news."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.services import feed_first, personal_digest
from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.article_dedup import normalize_canonical_url
from app.services.berries.landscape import SEED_FIXTURE_EVIDENCE_IDS
from app.services.feed_first_live import berry_ids_for, match_entity_ids, match_geography_ids
from app.services.industry_pulse.matrix import PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import GoogleNewsRssProvider
from app.services.industry_pulse.qualify import QualificationIndex, qualify_hit
from app.services.html_text import decode_html_text
from app.services.pipeline_lock import pipeline_lock

VERSION = "1.0"
LIST_ID = "list-competitor-registry-20260930"
FIELDS = (
    "schema_version", "external_record_id", "source_system", "record_status",
    "publish_to_landscape", "headline", "summary", "event_type", "event_date",
    "published_date", "accessed_date", "source_name", "source_url", "source_type",
    "competitor_id", "competitor_name", "related_entity_type", "related_entity_id",
    "related_entity_name", "berry", "region", "country", "topics",
    "verification_status", "confidence_level", "review_notes", "imported_at", "updated_at",
)
SAFE_JOB = re.compile(r"packet-[a-f0-9]{32}\Z")
REGISTRY_REF = "imports/competitor-coverage-registry-2026-09-21/reconciliation-matrix.json"
SUPPLEMENTAL = {"Genetics Uruguay": "company-genetics-uruguay", "Mario Aguas-Alvarado": "person-mario-aguas-alvarado"}


@lru_cache(maxsize=1)
def export_validator():
    from jsonschema import Draft202012Validator, FormatChecker
    schema = read_json(Path(__file__).resolve().parents[2] / "schemas" / "competitor-news-export.schema.json", {})
    return Draft202012Validator(schema, format_checker=FormatChecker())


def stamp(now=None):
    return (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def registry(data_dir: Path, entities: dict) -> list[dict]:
    rows = read_json(data_dir / REGISTRY_REF, {"rows": []})["rows"]
    result = []
    for row in rows:
        ids = row.get("canonical_entity_ids") or ([SUPPLEMENTAL[row["input_registry_name"]]] if row["input_registry_name"] in SUPPLEMENTAL else [])
        missing = [key for key in ids if key not in entities]
        result.append({"name": row["input_registry_name"], "entity_ids": ids,
                       "missing": missing, "notes": row.get("notes") or "",
                       "provisional": any(entities.get(key, {}).get("status") == "unverified" for key in ids)})
    return result


@serialized_write
def install_registry(inbox_dir: Path, data_dir: Path, entities: dict) -> str:
    rows = registry(data_dir, entities)
    if not rows or any(row["missing"] or not row["entity_ids"] for row in rows):
        raise ValueError("Resolve the registry's missing database entries before creating this list")
    state = feed_first.load_state(inbox_dir)
    if LIST_ID not in state["company_lists"]:
        state["company_lists"][LIST_ID] = {
            "name": "Competitor registry", "company_ids": sorted({key for row in rows for key in row["entity_ids"]}),
            "archived": False, "updated_at": stamp(), "registry_ref": REGISTRY_REF,
        }
        # Creating a group is separate from subscribing to its Digest stories.
        feed_first.save_state(inbox_dir, state)
    return LIST_ID


def path_for(inbox_dir: Path, job_id: str) -> Path:
    if not SAFE_JOB.fullmatch(job_id):
        raise ValueError("Invalid packet")
    return inbox_dir / "news_packets" / "jobs" / (job_id + ".json")


def load_job(inbox_dir, job_id):
    job = read_json(path_for(inbox_dir, job_id), None)
    if job is None:
        raise FileNotFoundError("Packet not found")
    return job


def parse_dates(start: str, end: str):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except (ValueError, TypeError):
        raise ValueError("Choose a start and end date") from None
    if first > last or last > datetime.now(UTC).date():
        raise ValueError("Choose dates in order, ending today or earlier")
    return first, last


def create_job(inbox_dir: Path, *, list_id: str, start: str, end: str, review: str, entities: dict):
    parse_dates(start, end)
    if review not in {"reviewed", "all"}:
        raise ValueError("Choose Reviewed only or All news")
    lists = {row["id"]: row for row in personal_digest.company_lists(feed_first.load_state(inbox_dir))}
    group = lists.get(list_id)
    if not group or not group.get("company_ids"):
        raise ValueError("Choose a non-empty company list")
    ids = sorted(set(group["company_ids"]))
    if len(ids) > 100 or any(key not in entities for key in ids):
        raise ValueError("Choose up to 100 database subjects; resolve missing members first")
    job_id = "packet-" + uuid4().hex
    job = {"id": job_id, "status": "queued", "created_at": stamp(),
           "scope": {"list_id": list_id, "list_name": group["name"], "entity_ids": ids,
                     "start": start, "end": end, "review": review},
           "capture": {"provider": "google_news_rss", "queries_total": len(ids), "queries_done": 0, "errors": []},
           "records": [], "validation": {"errors": [], "warnings": []}, "history": [{"at": stamp(), "action": "capture_requested"}]}
    atomic_json(path_for(inbox_dir, job_id), job)
    return job


def queries_for(scope: dict, entities: dict):
    # One bounded RSS query per subject: no API credits or credential transmission.
    start, end = date.fromisoformat(scope["start"]), date.fromisoformat(scope["end"])
    for key in scope["entity_ids"]:
        entity = entities[key]
        names = [entity["name"], *(entity.get("aliases") or [])]
        names = list(dict.fromkeys(str(name).replace('"', '').strip() for name in names if len(str(name)) >= 4))[:5]
        clause = " OR ".join('"' + name + '"' for name in names)
        # after/before are exclusive search operators; local inclusive validation is authoritative.
        text = f"({clause}) (berry OR berries OR blueberry OR strawberry OR raspberry OR blackberry OR cultivar OR horticulture) after:{start - timedelta(days=1)} before:{end + timedelta(days=1)}"
        yield PulseQuery(id=key, text=text, berry=None, geography="global", topic="competitor_news", kind="ad_hoc", hl="en-US", gl="US", ceid="US:en")


def is_reviewed(record: dict):
    return record.get("status") == "published" and not record.get("live") and not record.get("trust_state") == "LIVE" and (not record.get("auto_captured") or record.get("validated") is True)


def hit_record(hit, entities: dict, captured_at: str):
    # Retain the exact observed URL, including parameters/wrappers. Never emit a normalized URL.
    url = hit.wrapper_url if hit.provider == "google_news_rss" and hit.wrapper_url else (hit.origin_publisher_url or hit.url)
    title, snippet = decode_html_text(hit.title), decode_html_text(hit.snippet)
    text = title + " " + snippet
    return {"id": "live-" + hashlib.sha256((normalize_canonical_url(url) or url).encode()).hexdigest()[:16],
            "title": title, "summary": snippet, "source_url": url,
            "source_name": hit.origin_publisher_name or hit.source_domain, "source_type": "news_search",
            "published_date": hit.published_date, "captured_date": captured_at[:10],
            "entity_ids": match_entity_ids(text, entities.values()), "berry_ids": berry_ids_for(hit),
            "geography_ids": match_geography_ids(text, entities.values()),
            "image_url": (hit.provider_metadata or {}).get("image_url") or "",
            "editorial_topic": hit.editorial_topic,
            "status": "unreviewed", "live": True, "trust_state": "LIVE", "review_state": "UNREVIEWED"}


def iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def iso_timestamp(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp(dt) if dt.tzinfo is not None else None
    except ValueError:
        return None


def string_list(value):
    if isinstance(value, str):
        return [value] if value else []
    return [str(item) for item in value or []] if isinstance(value, (list, tuple)) else []


def build_rows(records: list[dict], scope: dict, entities: dict):
    """Project stored assignments; co-mentions are not claimed corporate relationships."""
    selected = set(scope["entity_ids"])
    rows, warnings, errors = [], [], []
    ordered = sorted(records, key=lambda row: (is_reviewed(row), str(row.get("published_date") or "")), reverse=True)
    seen_ids, seen_urls, titles = set(), {}, {}
    for record in ordered:
        item_id = str(record.get("id") or "")
        if item_id in SEED_FIXTURE_EVIDENCE_IDS:
            continue
        linked = set(record.get("entity_ids") or []) | set(record.get("company_ids") or [])
        matches = sorted(linked & selected)
        if not matches:
            continue
        published = iso_date(record.get("published_date"))
        if not published:
            warnings.append({"record_id": item_id, "code": "missing_date", "message": "Publication date missing; excluded from dated packet"})
            continue
        if not scope["start"] <= published <= scope["end"]:
            continue
        reviewed = is_reviewed(record)
        if scope["review"] == "reviewed" and not reviewed:
            continue
        url = str(record.get("source_url") or "")
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        if not item_id or not record.get("title") or parsed.scheme not in {"https", "http"} or not parsed.netloc:
            errors.append({"record_id": item_id, "code": "missing_identity", "message": "Source ID, headline or HTTP source URL missing"})
            continue
        norm = normalize_canonical_url(url) or url
        if item_id in seen_ids or norm in seen_urls:
            warnings.append({"record_id": item_id, "code": "duplicate", "message": "Duplicate stable ID or source URL; retained preferred source record", "duplicate_of": seen_urls.get(norm, item_id)})
            continue
        seen_ids.add(item_id)
        seen_urls[norm] = item_id
        title_key = (str(record["title"]).casefold().strip(), published)
        if title_key in titles:
            warnings.append({"record_id": item_id, "code": "possible_duplicate", "message": "Headline and publication date match another source; retained for review", "duplicate_of": titles[title_key]})
        titles[title_key] = item_id
        geography = [entities[key] for key in record.get("geography_ids", []) if key in entities]
        countries = [row["name"] for row in geography if (row.get("attributes") or {}).get("iso_3166_1_alpha_2") or (row.get("attributes") or {}).get("geography_type") == "country"]
        regions = [row["name"] for row in geography if row["name"] not in countries]
        base = {"schema_version": VERSION, "external_record_id": item_id, "source_system": "berry_intelligence",
                "record_status": "approved" if reviewed else "unreviewed", "publish_to_landscape": False,
                "headline": record["title"], "summary": str(record.get("summary") or ""),
                "event_type": str(record.get("event_type") or record.get("editorial_topic") or "unspecified"),
                "event_date": iso_date(record.get("event_date")), "published_date": published,
                "accessed_date": iso_date(record.get("accessed_date") or record.get("captured_date")),
                "source_name": str(record.get("source_name") or ""), "source_url": url,
                "source_type": str(record.get("source_type") or "unspecified"),
                "berry": string_list(record.get("berry_ids")), "region": regions, "country": countries,
                "topics": string_list(record.get("topics") or record.get("tags")),
                "verification_status": "source_reviewed" if reviewed else "unreviewed",
                "confidence_level": str(record["confidence_level"]) if record.get("confidence_level") is not None else None,
                "review_notes": "Source review does not verify individual claims. Summary is source-linked coverage; related entities are stored mentions, not inferred relationships.",
                "imported_at": iso_timestamp(record.get("imported_at")), "updated_at": iso_timestamp(record.get("updated_at"))}
        for key in matches:
            if entities[key].get("status") == "unverified":
                warnings.append({"record_id": item_id, "competitor_id": key, "code": "identity_pending", "message": "Competitor identity remains provisional; resolve at import review"})
            all_related = sorted((linked | set(record.get("variety_ids") or [])) - {key})
            for unknown in [other for other in all_related if other not in entities]:
                warnings.append({"record_id": item_id, "code": "unknown_entity", "message": f"Unknown related entity {unknown}; held in exception report"})
            related = [other for other in all_related if other in entities] or [None]
            for other in related:
                target = entities.get(other) or {}
                rows.append({**base, "competitor_id": key, "competitor_name": entities[key]["name"],
                             "related_entity_type": target.get("entity_type"), "related_entity_id": other,
                             "related_entity_name": target.get("name")})
    rows.sort(key=lambda row: (row["published_date"], row["external_record_id"], row["competitor_id"]), reverse=True)
    return rows, {"errors": errors, "warnings": warnings}


def capture_job(inbox_dir: Path, job_id: str, entities: dict, stored: list[dict], provider=None):
    job = load_job(inbox_dir, job_id)
    if job["status"] != "queued":
        return
    provider = provider or GoogleNewsRssProvider()
    job["status"] = "capturing"
    job["capture"]["started_at"] = stamp()
    atomic_json(path_for(inbox_dir, job_id), job)
    fresh = {}
    discovered = set()
    screened = 0
    public_roles = {"public_research_institution", "public_breeding_program", "government"}
    focused = [entity for key, entity in entities.items() if key in job["scope"]["entity_ids"]
               and not public_roles.intersection(entity.get("roles") or [])
               and (entity.get("berry_ids") or re.search(r"berr(?:y|ies)", entity["name"], re.I))]
    index = QualificationIndex.compile(
        company_names=[name for entity in focused for name in [entity["name"], *(entity.get("aliases") or [])]],
        variety_names=[entity["name"] for entity in entities.values() if entity.get("entity_type") == "variety"])
    def relevant(hit):
        qualify_hit(hit, index=index)
        return hit.qualifying and not re.search(r"stock price.*quote|quote.*history|analyst price target", hit.title, re.I)

    retained = []
    for record in stored:
        hit = DiscoveryHit(title=str(record.get("title") or ""), snippet=str(record.get("summary") or ""),
                           url=str(record.get("source_url") or ""), source_domain="", published_date=record.get("published_date"),
                           query_id="retained", query_text="", geography="global", berry=None, topic=None, provider="retained")
        if is_reviewed(record) or relevant(hit):
            retained.append(record)
    try:
        with pipeline_lock(inbox_dir, "competitor_news_export"):
            queries = list(queries_for(job["scope"], entities))
            with ThreadPoolExecutor(max_workers=4) as pool:
                pending = {pool.submit(provider.discover, query): query for query in queries}
                for future in as_completed(pending):
                    query = pending[future]
                    try:
                        for hit in future.result():
                            discovered.add(hit.wrapper_url or hit.url)
                            if not relevant(hit):
                                screened += 1
                                continue
                            record = hit_record(hit, entities, stamp())
                            fresh[record["id"]] = record
                    except Exception:
                        # Never persist raw transport errors that might expose headers or credentials.
                        job["capture"]["errors"].append({"subject_id": query.id, "message": "News search failed; retry this capture"})
                    job["capture"]["queries_done"] += 1
                    atomic_json(path_for(inbox_dir, job_id), job)
        job["capture"].update(completed_at=stamp(), discovered=len(discovered), qualifying=len(fresh), screened_results=screened)
        job["capture"]["retained_screened"] = len(stored) - len(retained)
        job["records"], job["validation"] = build_rows(retained + list(fresh.values()), job["scope"], entities)
        row_validator = export_validator().evolve(schema=export_validator().schema["properties"]["records"]["items"])
        for row in job["records"]:
            for error in row_validator.iter_errors(row):
                job["validation"]["errors"].append({"record_id": row["external_record_id"], "code": "schema", "message": "Invalid export field: " + ".".join(str(key) for key in error.path)})
        # Capture data stays private. Readable by the shared Digest, never canonical Evidence.
        atomic_json(inbox_dir / "news_packets" / "captures" / (job_id + ".json"), {"records": list(fresh.values()), "captured_at": job["capture"]["completed_at"]})
        job["status"] = "failed" if job["capture"]["errors"] or job["validation"]["errors"] else "ready"
    except Exception:
        job["status"] = "failed"
        job["capture"]["errors"].append({"message": "Capture could not finish. Another collector may be running; retry when it finishes."})
    job["history"].append({"at": stamp(), "action": "capture_" + job["status"]})
    atomic_json(path_for(inbox_dir, job_id), job)


def export_history(inbox_dir):
    return read_json(inbox_dir / "news_packets" / "history.json", {"exports": [], "last_generated": {}})


@serialized_write
def commit_export(inbox_dir: Path, job_id: str, now=None):
    now = now or datetime.now(UTC)
    job = load_job(inbox_dir, job_id)
    if job["status"] == "exported":
        record_export_receipt(inbox_dir, {"batch_id": job_id, "generated_at": job["generated_at"], "scope": job["scope"], "rows": len(job["records"])})
        return job  # idempotent retry; historical re-download is not a new generation.
    if job["status"] != "ready" or job["validation"]["errors"] or job["capture"]["errors"]:
        raise ValueError("A successful fresh capture and validation are required before export")
    completed = datetime.fromisoformat(job["capture"]["completed_at"].replace("Z", "+00:00"))
    if now - completed > timedelta(minutes=15):
        raise ValueError("Capture is over 15 minutes old. Capture and preview again before generating a new packet")
    generated = stamp(now)
    event = {"batch_id": job_id, "generated_at": generated, "scope": job["scope"], "rows": len(job["records"])}
    job.update(status="exported", generated_at=generated)
    job["history"].append({"at": generated, "action": "export_generated"})
    job["packet"] = {"schema_version": VERSION, "batch_id": job_id, "generated_at": generated,
                     "scope": job["scope"], "capture": job["capture"], "records": job["records"],
                     "validation": job["validation"], "change_history": job["history"],
                     "import_policy": "preview -> validation -> exception resolution -> upsert commit; target approval required for Landscape"}
    if next(export_validator().iter_errors(job["packet"]), None) is not None:
        raise ValueError("Packet does not match the JSON schema. Resolve its fields before exporting")
    # Packet is durable before receipt. Recovery completes the receipt on retry.
    atomic_json(path_for(inbox_dir, job_id), job)
    record_export_receipt(inbox_dir, event)
    return job


@serialized_write
def record_export_receipt(inbox_dir, event):
    history = export_history(inbox_dir)
    if not any(row["batch_id"] == event["batch_id"] for row in history["exports"]):
        history["exports"].append(event)
    list_id = event["scope"]["list_id"]
    history["last_generated"][list_id] = max(history["last_generated"].get(list_id, ""), event["generated_at"])
    atomic_json(inbox_dir / "news_packets" / "history.json", history)


def csv_file(rows, fields):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        cells = {}
        for key in fields:
            value = row.get(key)
            value = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")
            # CSV downloads are safe to open as a spreadsheet; JSON preserves original strings.
            cells[key] = "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
        writer.writerow(cells)
    return buffer.getvalue()
