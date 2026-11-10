"""Reconcile source-checked landscape events into the publication review inbox."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from app.services.analyst_state_io import atomic_json
from app.services.article_dedup import normalize_canonical_url
from app.services.draft_delivery import load_json
from app.services.living_workspaces import Store, now
from app.services.map_regions import public_source_url
from app.services.pipeline_lock import pipeline_lock


BERRIES = {"berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry"}
EVENT_TYPES = {"ip", "ownership", "licensing", "partnership", "commercial", "regulatory"}
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,119}\Z")
COUNTS = ("inserts", "evidence_additions", "duplicates", "unresolved_matches", "unverified", "exclusions")
PRIVATE_FOLDER = "berry_landscape_research"


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json_sha(value):
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value.strip()


def _slug(value, field):
    value = _text(value, field)
    if not SLUG.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase slug")
    return value


def _date(value, field):
    if value is None:
        return None
    value = _text(value, field)
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError(f"{field} must be YYYY-MM-DD")
    return value


def _strings(value, field):
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return list(dict.fromkeys(_text(item, field) for item in value))


def _read_packet(path):
    payload = load_json(path)
    batch_id = _slug(payload.get("batch_id"), "batch_id")
    run = payload["run"]
    provider = _text(run.get("provider"), "run.provider")
    run_id = _text(run.get("run_id"), "run.run_id")
    run_date = _date(_text(run.get("date"), "run.date"), "run.date")
    prompt = run.get("prompt")
    _text(prompt, "run.prompt")
    credits = run.get("credits_used")
    if type(credits) is not int or credits < 0:
        raise ValueError("run.credits_used must be a nonnegative integer from the run record")
    export = _text(run.get("raw_export"), "run.raw_export")
    export_path = (path.parent / export).resolve()
    if not export_path.is_relative_to(path.parent.resolve()) or export_path == path.resolve():
        raise ValueError("Raw export must be a separate file inside the packet directory")
    export_bytes = export_path.read_bytes()
    export_sha = _sha(export_bytes)
    if not export_bytes or export_sha != run.get("raw_sha256"):
        raise ValueError("Raw export is empty or its SHA-256 does not match")
    provenance = {"provider": provider, "run_id": run_id, "date": run_date, "prompt": prompt,
                  "credits_used": credits, "raw_sha256": export_sha, "raw_filename": export_path.name}
    return batch_id, provenance, export_bytes, payload


def _records(folder, *, recursive=False):
    paths = folder.rglob("*.json") if recursive else folder.glob("*.json")
    records = {}
    for path in paths:
        record = load_json(path)
        if record.get("id"):
            records[record["id"]] = record
    return records


def _url_index(records):
    result = defaultdict(set)
    for record_id, record in records.items():
        for url in (record.get("source_url"), (record.get("article") or {}).get("final_url")):
            if key := normalize_canonical_url(url):
                result[key].add(record_id)
    return result


def _create_file(path, raw):
    """Atomically install a new file without replacing another writer's file."""
    path = path.parent.resolve() / path.name
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = NamedTemporaryFile(dir=path.parent, delete=False)
    temp = Path(handle.name)
    try:
        with handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "nt":
            # Windows rename refuses to replace an existing destination.
            temp.rename(path)
        else:
            os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _draft(row, source, *, anchor, previous, batch_id, run, draft_id):
    links = []
    if anchor:
        links.append({"predicate": source["relationship"], "target_evidence_id": anchor, "status": "proposed"})
    if previous and previous != anchor:
        links.append({"predicate": "follows_up", "target_evidence_id": previous, "status": "proposed"})
    geography = row["geography_ids"]
    return {
        "id": draft_id, "record_type": "evidence", "status": "draft", "review_state": "draft",
        "evidence_role": "publication_artifact", "verification_state": "single_source",
        "source_type": source["source_type"], "media_format": "web_article",
        "title": source.get("title") or row["title"], "summary": source.get("summary") or row["summary"],
        "source_name": source["name"], "source_url": source["url"], "published_date": source["published_date"],
        "captured_date": run["date"], "event_date": row["event_date"],
        "event_type": row.get("event_type"), "landscape_event_key": row["event_key"],
        "submitted_by": "berry-landscape-intake", "berry_ids": row["berry_ids"],
        "geography_ids": geography, "entity_ids": list(dict.fromkeys(row["entity_ids"] + geography)),
        "fact_ids": [], "relationship_ids": [], "tags": row["tags"], "evidence_links": links,
        "priority": {key: {"level": "none", "rationale": ""}
                     for key in ("reading", "testing", "commercial_position", "monitoring")},
        "discovery_provenance": {"provider": run["provider"], "run_id": run["run_id"], "batch_id": batch_id,
                                 "event_key": row["event_key"], "prior_event_key": row.get("prior_event_key"),
                                 "announcement_date": row["announcement_date"], "effective_date": row["effective_date"],
                                 "raw_sha256": run["raw_sha256"]},
    }


def _verified_row(row, entities):
    for field in ("title", "summary"):
        row[field] = _text(row.get(field), field)
    for field in ("announcement_date", "event_date", "effective_date"):
        row[field] = _date(row.get(field), field)
    if row.get("event_type") is not None:
        row["event_type"] = _text(row["event_type"], "event_type")
        if row["event_type"] not in EVENT_TYPES:
            raise ValueError("event_type must be " + ", ".join(sorted(EVENT_TYPES)))
    for field in ("entity_ids", "geography_ids", "berry_ids", "tags"):
        row[field] = _strings(row.get(field, []), field)
    if not row["berry_ids"] or set(row["berry_ids"]) - BERRIES:
        raise ValueError("Source-checked events require one or more canonical berry IDs")
    unresolved = set(row["entity_ids"]) - entities.keys()
    unresolved.update(key for key in row["geography_ids"] if entities.get(key, {}).get("entity_type") != "geography")
    sources = row.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Source-checked events require original sources")
    for source in sources:
        source["url"] = _text(source.get("url"), "source.url")
        if not public_source_url(source["url"]):
            raise ValueError("Source-checked events require a public HTTP(S) original source URL")
        source["name"] = _text(source.get("name"), "source.name")
        source["source_type"] = _text(source.get("source_type", "article"), "source.source_type")
        source["published_date"] = _date(source.get("published_date"), "source.published_date")
        source["relationship"] = source.get("relationship", "corroborates")
        if source["relationship"] not in {"corroborates", "duplicates"}:
            raise ValueError("Source relationship must be corroborates or duplicates")
        for field in ("title", "summary"):
            if field in source:
                source[field] = _text(source[field], f"source.{field}")
    return sorted(unresolved)


def _plan(payload, batch_id, run, data_dir, inbox_dir, registered):
    trusted = {key: row for key, row in _records(data_dir / "evidence").items()
               if row.get("status") == "published"}
    pending = _records(inbox_dir / "evidence")
    entities = _records(data_dir / "entities", recursive=True)
    existing = {**pending, **trusted}
    urls = _url_index(existing)
    anchors = defaultdict(set)
    for record_id, record in existing.items():
        provenance = record.get("discovery_provenance") or {}
        if provenance.get("event_key") and record.get("status") != "rejected" and not any(
            link.get("predicate") in {"corroborates", "duplicates"} for link in record.get("evidence_links", [])
        ):
            anchors[provenance["event_key"]].add(record_id)
    for ledger in registered:
        for item in ledger["outcomes"]:
            if item.get("anchor_id") in existing and existing[item["anchor_id"]].get("status") != "rejected":
                anchors[item["event_key"]].add(item["anchor_id"])

    def lead(outcome, row, reason, follow_up):
        return {"outcome": outcome, "event_key": row["event_key"], "title": row.get("title"),
                "reason": reason, "follow_up": follow_up, "source_urls": [
                    source["url"] for source in row.get("sources", []) if public_source_url(source.get("url"))
                ]}

    outcomes, drafts = [], {}
    seen = set()
    for raw_row in payload["events"]:
        row = deepcopy(raw_row)
        event_key = _slug(row.get("event_key"), "event_key")
        if event_key in seen:
            raise ValueError(f"Repeated event_key {event_key}. Combine its sources into one row.")
        seen.add(event_key)
        status = row.get("status")
        if status in {"unverified", "excluded"}:
            reason = _text(row.get("reason"), "reason")
            follow_up = _text(row.get("follow_up"), "follow_up") if status == "unverified" else None
            outcomes.append(lead("unverified" if status == "unverified" else "exclusions", row, reason, follow_up))
            continue
        if status != "verified":
            raise ValueError(f"Unknown status {status!r} for {event_key}")
        if unresolved := _verified_row(row, entities):
            outcomes.append(lead("unresolved_matches", row, ", ".join(unresolved),
                                 "Confirm canonical identities or queue a new entity for review."))
            continue

        explicit_id = row.get("existing_evidence_id")
        if explicit_id and (explicit_id not in existing or existing[explicit_id].get("status") == "rejected"):
            outcomes.append(lead("unresolved_matches", row, "Existing evidence ID was not found",
                                 "Confirm the event match against the feed or pending queue."))
            continue
        matches = set(anchors[event_key])
        if explicit_id:
            matches.add(explicit_id)
        source_keys = [normalize_canonical_url(source["url"]) for source in row["sources"]]
        if not matches and source_keys[0] in urls:
            candidates = urls[source_keys[0]]
            if any(key in drafts or (existing[key].get("discovery_provenance") or {}).get("event_key")
                   not in (None, event_key) for key in candidates):
                outcomes.append(lead("unresolved_matches", row, "Primary publication supports another event",
                                     "Verify a separate event source or record the additional claim in review."))
                continue
            matches.update(key for key in candidates if existing[key].get("status") != "rejected")
        if len(matches) > 1:
            outcomes.append(lead("unresolved_matches", row, "More than one existing anchor matches",
                                 "Choose the underlying event before attaching corroboration."))
            continue
        anchor = next(iter(matches), None)
        prior = row.get("prior_event_key")
        prior_matches = anchors[_slug(prior, "prior_event_key")] if prior else set()
        if prior and len(prior_matches) != 1:
            outcomes.append(lead("unresolved_matches", row, "Prior milestone has no unique evidence anchor",
                                 "Resolve the earlier milestone before linking the follow-up."))
            continue
        previous = next(iter(prior_matches), None)
        for source, source_key in zip(row["sources"], source_keys):
            if source_key in urls:
                outcomes.append({"outcome": "duplicates", "event_key": event_key, "anchor_id": anchor,
                                 "source_url": source["url"], "matched_ids": sorted(urls[source_key])})
                continue
            draft_id = "ev-berry-landscape-" + _sha(source_key.encode("utf-8"))[:24]
            if draft_id in existing or draft_id in drafts:
                raise ValueError(f"Conflicting evidence ID {draft_id}")
            draft = _draft(row, source, anchor=anchor, previous=previous, batch_id=batch_id, run=run, draft_id=draft_id)
            outcome = "evidence_additions" if anchor else "inserts"
            anchor = anchor or draft_id
            drafts[draft_id] = draft
            anchors[event_key].add(anchor)
            urls[source_key].add(draft_id)
            outcomes.append({"outcome": outcome, "event_key": event_key, "anchor_id": anchor,
                             "draft_id": draft_id, "source_url": source["url"], "source_relationship": source["relationship"]})
    return outcomes, drafts


def _report(mode, batch_id, outcomes, **extra):
    counts = Counter(item["outcome"] for item in outcomes)
    return {"mode": mode, "batch_id": batch_id, "counts": {key: counts[key] for key in COUNTS},
            "outcomes": outcomes, **extra}


def _workspace_page(inbox_dir, ledger, *, rollback=False):
    leads = [row for row in ledger["outcomes"] if row["outcome"] in {"unverified", "unresolved_matches"}]
    if not leads:
        return None
    store = Store(inbox_dir)
    batch_id = ledger["batch_id"]
    page_id = f"wp-berry-landscape-{batch_id}"
    actor = "berry-landscape-intake"
    with store.transaction() as db:
        page = store.get(page_id, db)
        if rollback and page and page.get("landscape_batch_id") == batch_id and page["version"] == 1:
            page["blocks"] = [store.block("paragraph", "Batch rolled back. The original leads remain in the batch audit.")]
            page["landscape_batch_rolled_back"] = True
            store.put(db, "page", page, actor, expected=1)
        if page or rollback:
            protected = bool(rollback and page and not page.get("landscape_batch_rolled_back"))
            return {"href": f"/workspaces/{page_id}", "protected": protected}
        blocks = [store.block("heading", "Unverified research leads")]
        for row in leads:
            text = f"Unverified — {row['title'] or row['event_key']}\n{row['reason']}\nNext step — {row['follow_up']}"
            if row["source_urls"]:
                text += "\n" + "\n".join(row["source_urls"])
            blocks.append(store.block("paragraph", text))
        store.put(db, "page", {"id": page_id, "title": f"Landscape research leads · {batch_id}",
                               "parent_id": None, "blocks": blocks, "landscape_batch_id": batch_id,
                               "feed": {"mode": "any", "paused": True}, "dismissed": [], "created_at": now()}, actor)
    return {"href": f"/workspaces/{page_id}", "protected": False}


def reconcile(packet, *, data_dir, inbox_dir, mode="dry_run"):
    """Preview or stage drafts. Never write canonical entities, events or evidence."""
    packet, data_dir, inbox_dir = map(Path, (packet, data_dir, inbox_dir))
    if mode not in {"dry_run", "apply", "rollback"}:
        raise ValueError("Unknown reconciliation mode")
    if (data_dir / "evidence").resolve() == (inbox_dir / "evidence").resolve():
        raise ValueError("The review inbox must be separate from canonical evidence")
    batch_id, run, export_bytes, payload = _read_packet(packet)
    digest = _json_sha(payload)
    base = inbox_dir / PRIVATE_FOLDER
    folder = base / batch_id
    ledger_path = folder / "ledger.json"
    if mode == "dry_run":
        return _reconcile(payload, batch_id, run, digest, export_bytes, data_dir, inbox_dir, base, folder, ledger_path, mode)
    with pipeline_lock(inbox_dir, "berry_landscape_intake"):
        return _reconcile(payload, batch_id, run, digest, export_bytes, data_dir, inbox_dir, base, folder, ledger_path, mode)


def _reconcile(payload, batch_id, run, digest, export_bytes, data_dir, inbox_dir, base, folder, ledger_path, mode):
    ledgers = [load_json(path) for path in base.glob("*/ledger.json")]
    ledger = load_json(ledger_path) if ledger_path.exists() else None
    if ledger and ledger["packet_sha256"] != digest:
        raise ValueError("Batch ID already belongs to a different reviewed packet")
    snapshot = folder / "reviewed-packet.json"
    retained = folder / "raw-export"
    if snapshot.exists() and _json_sha(load_json(snapshot)) != digest:
        raise ValueError("Retained reviewed packet does not match its input")
    if retained.exists() and _sha(retained.read_bytes()) != run["raw_sha256"]:
        raise ValueError("Retained raw export does not match its SHA-256")
    for other in ledgers:
        if other["batch_id"] != batch_id and (other["run"]["provider"], other["run"]["run_id"]) == (run["provider"], run["run_id"]):
            raise ValueError(f"Run already recorded in batch {other['batch_id']}")
    evidence_dir = inbox_dir / "evidence"
    if mode == "rollback":
        if not ledger:
            raise ValueError("No staged batch to roll back")
        return _rollback(ledger, ledger_path, data_dir, inbox_dir)
    if mode == "apply" and ledger and ledger["state"] in {"rolled_back", "rollback_partial"}:
        raise ValueError("Batch was rolled back. Review and use a new run packet for any restaging.")
    if mode == "apply" and ledger and not snapshot.exists():
        atomic_json(snapshot, payload)
    if mode == "apply" and ledger and ledger["state"] == "preparing":
        for draft_id, fingerprint in ledger["draft_sha256"].items():
            path = evidence_dir / f"{draft_id}.json"
            if path.exists():
                # A reviewer may have edited a draft during an interrupted stage.
                # Its presence settles the write, and rollback protects the edit.
                continue
            if not (data_dir / "evidence" / path.name).exists():
                staged = folder / "staged" / path.name
                if _json_sha(load_json(staged)) != fingerprint:
                    raise ValueError(f"Staged draft hash mismatch {draft_id}")
                _create_file(path, staged.read_bytes())
        ledger["workspace"] = _workspace_page(inbox_dir, ledger)
        ledger["state"] = "staged"
        atomic_json(ledger_path, ledger)
        return _report("applied", batch_id, ledger["outcomes"], run=run, workspace=ledger["workspace"])

    outcomes, drafts = _plan(payload, batch_id, run, data_dir, inbox_dir, ledgers)
    if mode == "dry_run" or ledger:
        return _report("replayed" if mode == "apply" else mode, batch_id, outcomes, run=run,
                       workspace=ledger.get("workspace") if ledger else None)

    # Save the raw run and immutable planned writes before changing the inbox.
    folder.mkdir(parents=True, exist_ok=True)
    if not retained.exists():
        _create_file(retained, export_bytes)
    atomic_json(snapshot, payload)
    for draft_id, draft in drafts.items():
        atomic_json(folder / "staged" / f"{draft_id}.json", draft)
    ledger = _report("apply", batch_id, outcomes, run=run, packet_sha256=digest, state="preparing",
                     draft_sha256={key: _json_sha(value) for key, value in drafts.items()})
    atomic_json(ledger_path, ledger)
    return _reconcile(payload, batch_id, run, digest, export_bytes, data_dir, inbox_dir, base, folder, ledger_path, mode)


def _rollback(ledger, ledger_path, data_dir, inbox_dir):
    folder = ledger_path.parent
    evidence_dir = inbox_dir / "evidence"
    trusted_dir = data_dir / "evidence"
    if ledger["state"] == "rolled_back":
        return {"mode": "rollback", "batch_id": ledger["batch_id"], "removed_drafts": [], "protected_drafts": []}
    removed, protected = [], []
    trusted_urls = _url_index(_records(trusted_dir))
    for draft_id, digest in ledger["draft_sha256"].items():
        path = evidence_dir / f"{draft_id}.json"
        staged = load_json(folder / "staged" / path.name)
        archived = folder / "rolled-back" / path.name
        if (trusted_dir / path.name).exists() or normalize_canonical_url(staged["source_url"]) in trusted_urls:
            protected.append(draft_id)
        elif path.exists():
            if _json_sha(load_json(path)) != digest:
                protected.append(draft_id)
                continue
            archived.parent.mkdir(exist_ok=True)
            path.replace(archived)
            removed.append(draft_id)
        elif archived.exists():
            removed.append(draft_id)
    workspace = _workspace_page(inbox_dir, ledger, rollback=True)
    ledger["state"] = "rollback_partial" if protected or (workspace and workspace["protected"]) else "rolled_back"
    ledger["rollback"] = {"removed_drafts": removed, "protected_drafts": protected, "workspace": workspace}
    atomic_json(ledger_path, ledger)
    return {"mode": "rollback", "batch_id": ledger["batch_id"], **ledger["rollback"]}
