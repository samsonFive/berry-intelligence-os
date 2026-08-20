"""Presentation layer for untrusted Signal candidates.

Consumes app.services.signal_candidates and source_independence. Ranking
uses stored metadata only — no opaque AI score, no candidate regeneration,
and no writes to data/signals/. A human CONFIRM marks the candidate
reviewed; it does not create a trusted Signal.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.services.intelligence_feed import TRUST_LABELS, is_berry_direct, trust_state
from app.services.signal_candidates import (
    PATTERN_CONTRADICTION,
    PATTERN_PRIMARY_PLUS_FOLLOWUP,
    REVIEW_DECISIONS,
    apply_review_decision,
    candidates_dir,
    load_candidates,
)
from app.services.source_independence import independence_report
from app.services.story_threads import expand_with_related, group_story_threads, threads_by_item_id

EMERGING_LIMIT = 7
EMERGING_STATUSES = {"proposed", "disputed"}
OPEN_STATUSES = {"proposed", "disputed", "deferred", "confirmed"}
DISPLAY_PREDICATES = ("corroborates", "follows_up", "same_signal", "duplicates", "contradicts")
PREDICATE_LABELS = {
    "corroborates": "CORROBORATES",
    "follows_up": "FOLLOWS UP",
    "same_signal": "SAME SIGNAL",
    "duplicates": "DUPLICATES",
    "contradicts": "CONTRADICTS",
}
STATUS_LABELS = {
    "proposed": "Proposed",
    "confirmed": "Confirmed",
    "deferred": "Deferred",
    "disputed": "Disputed",
    "dismissed": "Dismissed",
}
CONFIDENCE_LABELS = {"low": "Low", "medium": "Medium", "high": "High"}
PATTERN_LABELS = {
    "multi_source_corroboration": "multi-source corroboration",
    "primary_source_plus_followup": "primary source plus follow-up",
    "repeated_company_activity": "repeated activity",
    "contradiction": "contradiction",
}
TRIAGE_BUCKETS = (
    ("review_now", "Review now"),
    ("review_soon", "Review soon"),
    ("low_confidence", "Low confidence"),
    ("same_origin_weak", "Same-origin / weak"),
    ("deferred", "Deferred"),
)
CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}


def persist_reviewed_candidate(candidate: dict[str, Any], *, inbox_dir: Path) -> Path:
    """Write a candidate after apply_review_decision().

    persist_candidates() is additive and never overwrites a file that may
    already carry a human decision. This is the matching write for review.
    """

    target = candidates_dir(inbox_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{candidate['id']}.json"
    path.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def apply_and_persist_decision(
    candidate: dict[str, Any],
    *,
    decision: str,
    reviewer: str,
    notes: str | None = None,
    inbox_dir: Path,
) -> dict[str, Any]:
    updated = apply_review_decision(candidate, decision=decision, reviewer=reviewer, notes=notes)
    persist_reviewed_candidate(updated, inbox_dir=inbox_dir)
    return updated


def candidate_by_id(inbox_dir: Path, candidate_id: str) -> dict[str, Any] | None:
    for candidate in load_candidates(inbox_dir):
        if candidate.get("id") == candidate_id:
            return candidate
    return None


def _parse_day(value: Any) -> date | None:
    raw = str(value or "")[:10]
    if len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _entity_name(entity_id: str, entities: dict[str, dict[str, Any]]) -> str:
    entity = entities.get(entity_id) or {}
    return str(entity.get("name") or entity_id or "Unknown subject")


def _primary_subject(candidate: dict[str, Any], entities: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    entity_id = str(candidate.get("primary_entity_id") or "")
    if not entity_id:
        ids = list(candidate.get("entity_ids") or [])
        entity_id = str(ids[0]) if ids else ""
    if not entity_id:
        return None
    entity = entities.get(entity_id) or {}
    kind = str(entity.get("entity_type") or "topic")
    return {
        "id": entity_id,
        "name": str(entity.get("name") or entity_id),
        "entity_type": kind,
        "href": f"/entities/{kind}/{entity_id}" if kind in {"company", "variety", "geography", "person"} else "",
        "label": kind.replace("_", " "),
    }


def _supporting_records(candidate: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for evidence_id in candidate.get("supporting_evidence_ids") or []:
        record = evidence_by_id.get(str(evidence_id))
        if record:
            records.append(record)
        else:
            records.append({"id": evidence_id, "title": evidence_id})
    return records


def _latest_day(records: list[dict[str, Any]]) -> date | None:
    days = [_parse_day(r.get("published_date") or r.get("captured_date")) for r in records]
    known = [day for day in days if day]
    return max(known) if known else None


def _berry_direct(candidate: dict[str, Any], records: list[dict[str, Any]]) -> bool:
    if candidate.get("berry_ids"):
        return True
    return any(is_berry_direct(record) for record in records)


def _watch_match(
    candidate: dict[str, Any],
    subject: dict[str, Any] | None,
    watch_entities: set[str],
) -> str:
    if not watch_entities:
        return ""
    primary_id = str((subject or {}).get("id") or candidate.get("primary_entity_id") or "")
    if primary_id and primary_id in watch_entities:
        return "primary"
    for entity_id in candidate.get("entity_ids") or []:
        if str(entity_id) in watch_entities:
            return "mention"
    return ""


def _has_patent(records: list[dict[str, Any]]) -> bool:
    return any(
        record.get("source_type") == "patent_record"
        or record.get("intake_type") == "patent_filing"
        or isinstance(record.get("patent_filing"), dict)
        for record in records
    )


def _rank_tuple(
    *,
    candidate: dict[str, Any],
    records: list[dict[str, Any]],
    berry_direct: bool,
    watch_match: str,
    subject: dict[str, Any] | None,
    today: date,
) -> tuple:
    """Deterministic sort key from stored fields. Higher is more urgent."""

    status = str(candidate.get("status") or "proposed")
    confidence = str(candidate.get("signal_confidence") or "low")
    independence = candidate.get("independence") or {}
    independent = int(independence.get("independent_source_count") or 0)
    latest = _latest_day(records)
    recency = (today - latest).days if latest else 999
    contradiction = str(candidate.get("pattern_type") or "") == PATTERN_CONTRADICTION or status == "disputed"
    primary_kind = str((subject or {}).get("entity_type") or "")
    return (
        1 if contradiction else 0,
        CONFIDENCE_RANK.get(confidence, 0),
        independent,
        1 if berry_direct else 0,
        2 if watch_match == "primary" else 1 if watch_match == "mention" else 0,
        2 if primary_kind == "company" else 1 if primary_kind else 0,
        len(records),
        1 if _has_patent(records) else 0,
        -recency,
        str(candidate.get("id") or ""),
    )


def _triage_bucket(
    *,
    candidate: dict[str, Any],
    independent: int,
    berry_direct: bool,
    watch_match: str,
    recency_days: int,
    subject: dict[str, Any] | None,
) -> str | None:
    status = str(candidate.get("status") or "proposed")
    if status == "deferred":
        return "deferred"
    if status in {"dismissed", "confirmed"}:
        return None
    pattern = str(candidate.get("pattern_type") or "")
    confidence = str(candidate.get("signal_confidence") or "low")
    if independent <= 1 or pattern == PATTERN_PRIMARY_PLUS_FOLLOWUP:
        return "same_origin_weak"
    contradiction = pattern == PATTERN_CONTRADICTION or status == "disputed"
    if contradiction:
        return "review_now"
    if confidence == "low":
        return "low_confidence"
    subject_kind = str((subject or {}).get("entity_type") or "")
    focused_subject = subject_kind in {"company", "variety", "brand"}
    recent = recency_days <= 90
    if (
        confidence in {"medium", "high"}
        and independent >= 2
        and recent
        and focused_subject
        and (berry_direct or watch_match == "primary")
    ):
        return "review_now"
    return "review_soon"


def _deterministic_label(candidate: dict[str, Any], subject: dict[str, Any] | None) -> str:
    pattern = PATTERN_LABELS.get(str(candidate.get("pattern_type") or ""), "emerging pattern")
    name = (subject or {}).get("name") or "Unscoped"
    return f"{name}: {pattern}"


def present_candidate(
    candidate: dict[str, Any],
    *,
    evidence_by_id: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    watch_entities: set[str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    records = _supporting_records(candidate, evidence_by_id)
    subject = _primary_subject(candidate, entities)
    independence = candidate.get("independence") or independence_report(records)
    berry_direct = _berry_direct(candidate, records)
    watch_match = _watch_match(candidate, subject, watch_entities or set())
    latest = _latest_day(records)
    day = today or date.today()
    recency_days = (day - latest).days if latest else 999
    status = str(candidate.get("status") or "proposed")
    confidence = str(candidate.get("signal_confidence") or "low")
    independent = int(independence.get("independent_source_count") or 0)
    evidence_count = int(independence.get("total_evidence_count") or len(records))
    label = _deterministic_label(candidate, subject)
    return {
        **candidate,
        "independence": independence,
        "label": label,
        "href": f"/signals/candidates/{candidate.get('id')}",
        "status_label": STATUS_LABELS.get(status, status.replace("_", " ").title()),
        "confidence_label": CONFIDENCE_LABELS.get(confidence, confidence.title()),
        "pattern_label": PATTERN_LABELS.get(str(candidate.get("pattern_type") or ""), "emerging pattern"),
        "primary_subject": subject,
        "why_it_may_matter": candidate.get("reason") or "",
        "does_not_prove": list(candidate.get("does_not_prove") or []),
        "support_label": f"{evidence_count} Evidence · {independent} independent origin{'s' if independent != 1 else ''}",
        "evidence_count": evidence_count,
        "independent_source_count": independent,
        "berry_direct": berry_direct,
        "watch_match": watch_match,
        "latest_date": latest.isoformat() if latest else "",
        "recency_days": recency_days,
        "rank": _rank_tuple(
            candidate=candidate,
            records=records,
            berry_direct=berry_direct,
            watch_match=watch_match,
            subject=subject,
            today=day,
        ),
        "triage_bucket": _triage_bucket(
            candidate=candidate,
            independent=independent,
            berry_direct=berry_direct,
            watch_match=watch_match,
            recency_days=recency_days,
            subject=subject,
        ),
        "is_emerging": status in EMERGING_STATUSES,
    }


def present_candidates(
    inbox_dir: Path,
    *,
    evidence_by_id: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    watch_entities: set[str] | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    presented = [
        present_candidate(
            candidate,
            evidence_by_id=evidence_by_id,
            entities=entities,
            watch_entities=watch_entities,
            today=today,
        )
        for candidate in load_candidates(inbox_dir)
        if candidate.get("id")
    ]
    presented.sort(key=lambda row: row.get("rank") or (), reverse=True)
    return presented


def emerging_signals(presented: list[dict[str, Any]], *, limit: int = EMERGING_LIMIT) -> list[dict[str, Any]]:
    """Bounded morning-brief set: current review-now first, then recent
    same-origin teaching cases, then other recent candidates. Stale high
    independent-count clusters stay in Review Soon instead of crowding
    the brief."""

    emerging = [row for row in presented if row.get("is_emerging")]
    buckets = (
        lambda row: row.get("triage_bucket") == "review_now",
        lambda row: row.get("triage_bucket") == "same_origin_weak" and int(row.get("recency_days") or 999) <= 90,
        lambda row: row.get("triage_bucket") == "review_soon" and int(row.get("recency_days") or 999) <= 180,
    )
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for predicate in buckets:
        for row in emerging:
            row_id = str(row.get("id") or "")
            if not row_id or row_id in seen or not predicate(row):
                continue
            seen.add(row_id)
            ordered.append(row)
            if len(ordered) >= limit:
                return ordered
    return ordered


def triage_groups(presented: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = []
    counts: dict[str, int] = {}
    for key, label in TRIAGE_BUCKETS:
        entries = [row for row in presented if row.get("triage_bucket") == key]
        counts[key] = len(entries)
        buckets.append({"key": key, "label": label, "count": len(entries), "entries": entries})
    counts["total"] = len(presented)
    counts["open"] = sum(1 for row in presented if str(row.get("status") or "") in OPEN_STATUSES)
    return {"buckets": buckets, "counts": counts}


def open_signals_for_entity(
    entity_id: str,
    presented: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    matching = [
        row
        for row in presented
        if str(row.get("status") or "") in OPEN_STATUSES
        and (
            str(row.get("primary_entity_id") or "") == entity_id
            or entity_id in {str(eid) for eid in (row.get("entity_ids") or [])}
        )
    ]
    return {
        "emerging": [row for row in matching if str(row.get("status") or "") in EMERGING_STATUSES],
        "confirmed": [row for row in matching if str(row.get("status") or "") == "confirmed"],
        "deferred": [row for row in matching if str(row.get("status") or "") == "deferred"],
    }


def _evidence_href(record: dict[str, Any]) -> str:
    record_id = str(record.get("id") or "")
    if not record_id:
        return ""
    return f"/intelligence/{record_id}"


def present_evidence_support(
    record: dict[str, Any],
    *,
    thread: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trust = record.get("trust") or trust_state(record)
    return {
        "id": record.get("id"),
        "title": record.get("title") or record.get("id"),
        "href": _evidence_href(record),
        "source_name": record.get("source_name") or record.get("source_id") or "",
        "source_id": record.get("source_id") or "",
        "date": record.get("published_date") or record.get("captured_date") or "",
        "trust": trust,
        "trust_label": TRUST_LABELS.get(str(trust), str(trust).replace("_", " ").title()),
        "source_authority": record.get("source_authority") or "",
        "source_url": record.get("source_url") or record.get("canonical_url") or "",
        "story_thread": (
            {
                "id": thread.get("id"),
                "title": thread.get("title"),
                "href": thread.get("href"),
                "source_count": thread.get("source_count"),
            }
            if thread and int(thread.get("source_count") or 0) > 1
            else None
        ),
    }


def present_independence(
    candidate: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records = _supporting_records(candidate, evidence_by_id)
    report = candidate.get("independence") or independence_report(records)
    clusters = []
    for cluster in report.get("clusters") or []:
        ids = [str(eid) for eid in (cluster.get("evidence_ids") or [])]
        members = [evidence_by_id.get(eid) or {"id": eid, "title": eid} for eid in ids]
        origin = members[0] if members else {}
        clusters.append(
            {
                "origin_label": cluster.get("origin_label")
                or origin.get("source_name")
                or origin.get("source_id")
                or origin.get("id"),
                "origin": present_evidence_support(origin),
                "reprints": [present_evidence_support(member) for member in members[1:]],
                "document_count": len(members),
            }
        )
    total = int(report.get("total_evidence_count") or len(records))
    independent = int(report.get("independent_source_count") or 0)
    return {
        "total_evidence_count": total,
        "independent_source_count": independent,
        "clusters": clusters,
        "same_origin_collapsed": total > independent,
        "headline": f"{total} document{'s' if total != 1 else ''} · {independent} independent origin{'s' if independent != 1 else ''}",
    }


def present_stored_relationships(
    records: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    known_ids = {str(record.get("id") or "") for record in records if record.get("id")}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        source_id = str(record.get("id") or "")
        for link in record.get("evidence_links") or []:
            if not isinstance(link, dict):
                continue
            predicate = str(link.get("predicate") or "")
            if predicate not in DISPLAY_PREDICATES:
                continue
            target_id = str(link.get("target_evidence_id") or link.get("target_id") or "")
            if not target_id:
                continue
            key = (predicate, source_id, target_id)
            if key in seen:
                continue
            seen.add(key)
            target = evidence_by_id.get(target_id) or {"id": target_id, "title": target_id}
            rows.append(
                {
                    "predicate": predicate,
                    "predicate_label": PREDICATE_LABELS[predicate],
                    "status": link.get("status") or "",
                    "notes": link.get("notes") or "",
                    "from_id": source_id,
                    "from_title": record.get("title") or source_id,
                    "from_href": _evidence_href(record),
                    "target_id": target_id,
                    "target_title": target.get("title") or target_id,
                    "target_href": _evidence_href(target),
                    "within_signal": target_id in known_ids,
                }
            )
    rows.sort(key=lambda row: (DISPLAY_PREDICATES.index(row["predicate"]), row["from_id"], row["target_id"]))
    return rows


def related_story_threads(
    records: list[dict[str, Any]],
    extra: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    universe = expand_with_related(list(records), extra)
    threads = group_story_threads(universe)
    related = []
    seen: set[str] = set()
    by_id = threads_by_item_id(threads)
    for record in records:
        thread = by_id.get(str(record.get("id") or ""))
        if not thread or int(thread.get("source_count") or 0) <= 1:
            continue
        thread_id = str(thread.get("id") or "")
        if thread_id in seen:
            continue
        seen.add(thread_id)
        related.append(thread)
    return related


def present_review(
    candidate: dict[str, Any],
    *,
    evidence_by_id: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    extra_records: list[dict[str, Any]] | None = None,
    watch_entities: set[str] | None = None,
) -> dict[str, Any]:
    card = present_candidate(
        candidate,
        evidence_by_id=evidence_by_id,
        entities=entities,
        watch_entities=watch_entities,
    )
    records = _supporting_records(candidate, evidence_by_id)
    extra = list(extra_records or [])
    threads = related_story_threads(records, extra)
    by_member = {}
    for thread in threads:
        for member_id in thread.get("member_ids") or []:
            by_member[str(member_id)] = thread
    supporting = [
        present_evidence_support(record, thread=by_member.get(str(record.get("id") or "")))
        for record in records
    ]
    return {
        **card,
        "supporting_evidence": supporting,
        "independence_view": present_independence(candidate, evidence_by_id),
        "relationships": present_stored_relationships(records, evidence_by_id),
        "story_threads": threads,
        "review_decisions": REVIEW_DECISIONS,
    }


def candidates_for_thread(member_ids: set[str], presented: list[dict[str, Any]]) -> list[dict[str, Any]]:
    related = []
    for row in presented:
        support = {str(eid) for eid in (row.get("supporting_evidence_ids") or [])}
        if support & member_ids and str(row.get("status") or "") != "dismissed":
            related.append(row)
    return related
