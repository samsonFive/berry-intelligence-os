"""Deterministic, untrusted Signal-candidate generation.

Corroboration + Signal Formation mission (2026-08-19). Proposes -- never
trusts -- multi-evidence intelligence patterns for human review. This
module never writes to data/signals/ (the trusted store); candidates are
plain dicts a caller persists to an untrusted location (mirroring every
other acquisition pipeline in this project: inbox/ is proposed,
data/ is published, and nothing here crosses that line on its own).

Core rule this module exists to enforce (the mission's own words): a
Signal is not merely two articles about the same topic. A candidate only
forms when Evidence sharing strong entity alignment within a real time
window either (a) comes from >=2 genuinely independent origins --
app/services/source_independence.py's clustering, not a raw evidence
count -- or (b) is anchored by one clearly primary-source record (a
company's own newsroom, a patent registry, or explicit source_authority
"high") plus at least one other record providing real context/follow-up,
even if that follow-up shares the same underlying origin. Case (b) is
never treated as equal-strength to case (a): its signal_confidence is
capped lower and its does_not_prove always states that no second origin
has corroborated it yet.

Deterministic entity/date clustering only -- no keyword search, no
opaque scoring, no LLM judgment. Every candidate traces to exactly the
Evidence ids and independence reasoning that produced it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.services.source_independence import independence_report

CORROBORATION_WINDOW_DAYS = 45
REPEATED_ACTIVITY_WINDOW_DAYS = 240
MIN_REPEATED_EVENTS = 3

PATTERN_MULTI_SOURCE = "multi_source_corroboration"
PATTERN_PRIMARY_PLUS_FOLLOWUP = "primary_source_plus_followup"
PATTERN_REPEATED_ACTIVITY = "repeated_company_activity"
PATTERN_CONTRADICTION = "contradiction"

DOES_NOT_PROVE_BY_PATTERN: dict[str, tuple[str, ...]] = {
    PATTERN_MULTI_SOURCE: (
        "that the underlying development is commercially significant",
        "market adoption, revenue impact, or strategic intent beyond what each source states",
    ),
    PATTERN_PRIMARY_PLUS_FOLLOWUP: (
        "independent corroboration -- no second, separately-originating source has confirmed this yet",
        "that trade-press repetition adds confirming weight beyond the primary source itself",
    ),
    PATTERN_REPEATED_ACTIVITY: (
        "a coordinated strategy -- repeated filings/announcements may be routine breeding-program cadence, not a new initiative",
        "acreage, launch timing, or market outcome for any individual filing in the pattern",
    ),
    PATTERN_CONTRADICTION: (
        "which trusted claim is correct -- a contradiction is a flag for review, not a resolution",
    ),
}


def _parse_date(value: Any) -> "date | None":
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _is_patent(record: dict[str, Any]) -> bool:
    return bool(
        record.get("source_type") == "patent_record"
        or record.get("intake_type") == "patent_filing"
        or isinstance(record.get("patent_filing"), dict)
    )


def _is_primary(record: dict[str, Any]) -> bool:
    """A record whose own authority stands independent of any corroboration
    -- a company's own newsroom (linked_competitor source or matching
    source_name), a patent/government registry, or an explicit high
    source_authority."""
    if _is_patent(record):
        return True
    if record.get("source_authority") == "high":
        return True
    source_id = str(record.get("source_id") or "")
    return "newsroom" in source_id


def _dated_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in records if r.get("id") and _parse_date(r.get("published_date")) is not None]


# Real false positive found auditing real candidate output (Signal-
# Candidate Calibration, 2026-08-19): grouping by a shared trait-*
# entity id linked Fall Creek's high-chill field-forum coverage to
# Costa Group's unrelated BluGenix variety launch -- two competing
# companies' two unrelated announcements, joined only because both
# happened to reference the same generic agronomic characteristic
# ("postharvest shelf life"). A trait is a claimed characteristic, not
# an actor a developing pattern is *about* -- unlike a shared company,
# variety, brand, or patent id, two records sharing a trait id say
# nothing about whether they concern the same underlying development.
# Excluded from clustering entirely, not just down-weighted: "entity
# overlap too broad" is exactly the false-positive class this guards
# against, per the mission's own list of known risk categories.
EXCLUDED_ENTITY_PREFIXES = ("trait-",)


def _entity_groups(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for entity_id in record.get("entity_ids") or []:
            if entity_id.startswith(EXCLUDED_ENTITY_PREFIXES):
                continue
            groups.setdefault(entity_id, []).append(record)
    return groups


def _within_window(records: list[dict[str, Any]], *, window_days: int) -> list[list[dict[str, Any]]]:
    """Split a same-entity record list into clusters whose published_date
    all fall within window_days of each other (simple greedy sort-and-scan,
    deterministic given the input order)."""
    dated = sorted(records, key=lambda r: _parse_date(r["published_date"]))
    clusters: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for record in dated:
        record_date = _parse_date(record["published_date"])
        if current and (record_date - _parse_date(current[0]["published_date"])).days > window_days:
            clusters.append(current)
            current = []
        current.append(record)
    if current:
        clusters.append(current)
    return [c for c in clusters if len(c) >= 2]


SPOKEN_MEDIA_FORMATS = ("podcast", "video", "conference_video")


def _has_untranscribed_spoken_media(records: list[dict[str, Any]]) -> bool:
    """True when the cluster leans on a podcast/video record with no
    actual transcript -- real case found auditing real candidate output
    (Signal-Candidate Calibration, 2026-08-19): the one real spoken-media
    Evidence in this dataset (a Lucentlands podcast interview with Fall
    Creek's CEO) has transcript={"status": "not_available"} -- its
    summary/why_it_matters is built entirely from the publisher's own
    Apple Podcasts episode description, not a verified transcript quote.
    That is real, independently-reported Evidence (a genuine interview,
    not a reprint), but weaker evidentiary grounding than a transcribed
    record, and a Signal candidate should say so rather than silently
    treat it as equally strong."""
    for record in records:
        if record.get("media_format") not in SPOKEN_MEDIA_FORMATS:
            continue
        status = (record.get("transcript") or {}).get("status")
        if status != "ready":
            return True
    return False


def _does_not_prove(pattern_type: str, records: list[dict[str, Any]]) -> list[str]:
    items = list(DOES_NOT_PROVE_BY_PATTERN.get(pattern_type, ()))
    if _has_untranscribed_spoken_media(records):
        items.append(
            "verified spoken content -- at least one podcast/video record here has no transcript; "
            "its summary reflects the publisher's own episode description, not a checked quote"
        )
    return items


def _signal_confidence(pattern_type: str, independent_source_count: int, records: list[dict[str, Any]]) -> str:
    """Deterministic, conservative confidence -- never source_authority
    (how authoritative one document is) and never a single record's
    information_confidence (how well one record supports its own claim).
    This is specifically confidence in the *multi-source pattern*, and it
    is capped by independence: PRIMARY_PLUS_FOLLOWUP can never reach
    "high" no matter how many follow-ups pile onto the same origin,
    because piling on same-origin repeats is exactly the inflation this
    module exists to prevent. CONTRADICTION is always "low" -- a flagged
    disagreement is not itself a confirmed pattern. An untranscribed
    spoken-media record in the cluster also caps confidence below "high":
    "HIGH should normally require genuinely independent support and
    strong alignment" (mission requirement) -- a publisher-description-only
    podcast record is real Evidence but not strong alignment on its own."""
    if pattern_type == PATTERN_PRIMARY_PLUS_FOLLOWUP:
        return "low"
    if pattern_type == PATTERN_CONTRADICTION:
        return "low"
    untranscribed_cap = _has_untranscribed_spoken_media(records)
    if independent_source_count >= 4 and not untranscribed_cap:
        return "high"
    if independent_source_count >= 2:
        return "medium"
    return "low"


def _candidate(
    *,
    pattern_type: str,
    entity_id: str,
    records: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    report = independence_report(records)
    berry_ids = sorted({b for r in records for b in (r.get("berry_ids") or [])})
    geography_ids = sorted({g for r in records for g in (r.get("geography_ids") or [])})
    all_entity_ids = sorted({e for r in records for e in (r.get("entity_ids") or [])})
    record_ids = sorted(r["id"] for r in records)
    # A real deterministic bug this fixes (found auditing real VPS output,
    # 2026-08-19): the same (pattern_type, entity_id) pair recurs across
    # multiple genuinely distinct evidence clusters -- Fall Creek alone
    # produced 9 separate real multi_source_corroboration clusters, all
    # colliding onto one id under the old scheme. persist_candidates()'s
    # additive-only "never overwrite an existing file" rule then silently
    # dropped 8 of them as if they were re-generations of the same
    # candidate, when they were 8 different real signals. The fingerprint
    # is over the evidence id set specifically (not a random uuid) so the
    # same real cluster always reproduces the same id across runs --
    # required for "never overwrite a reviewed file" to mean anything.
    fingerprint = hashlib.sha256("|".join(record_ids).encode("utf-8")).hexdigest()[:8]
    candidate_id = "sigcand-" + "-".join(
        [pattern_type.replace("_", "-"), entity_id.replace("company-", ""), fingerprint]
    )
    return {
        "id": candidate_id,
        "record_type": "signal_candidate",
        "status": "proposed",
        "pattern_type": pattern_type,
        "primary_entity_id": entity_id,
        "entity_ids": all_entity_ids,
        "berry_ids": berry_ids,
        "geography_ids": geography_ids,
        "supporting_evidence_ids": record_ids,
        "independence": report,
        "signal_confidence": _signal_confidence(pattern_type, report["independent_source_count"], records),
        "reason": reason,
        "does_not_prove": _does_not_prove(pattern_type, records),
        "generated_by": "signal_candidates.generate_candidates",
        "reviewer": None,
        "review_notes": None,
    }


def generate_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic Signal candidates from real Evidence (trusted +
    pending; caller decides which to include). Every candidate is
    reproducible from its supporting_evidence_ids and independence report
    alone -- nothing here is a black box."""
    dated = _dated_records(records)
    by_entity = _entity_groups(dated)
    candidates: list[dict[str, Any]] = []
    seen_id_sets: set[frozenset] = set()

    for entity_id, entity_records in by_entity.items():
        for cluster in _within_window(entity_records, window_days=CORROBORATION_WINDOW_DAYS):
            report = independence_report(cluster)
            id_set = frozenset(r["id"] for r in cluster)
            if id_set in seen_id_sets:
                continue
            if report["independent_source_count"] >= 2:
                seen_id_sets.add(id_set)
                candidates.append(
                    _candidate(
                        pattern_type=PATTERN_MULTI_SOURCE,
                        entity_id=entity_id,
                        records=cluster,
                        reason=(
                            f"{len(cluster)} Evidence record(s) naming {entity_id} within "
                            f"{CORROBORATION_WINDOW_DAYS} days, from {report['independent_source_count']} "
                            "independently-originating sources."
                        ),
                    )
                )
            elif report["independent_source_count"] == 1 and any(_is_primary(r) for r in cluster) and len(cluster) >= 2:
                seen_id_sets.add(id_set)
                candidates.append(
                    _candidate(
                        pattern_type=PATTERN_PRIMARY_PLUS_FOLLOWUP,
                        entity_id=entity_id,
                        records=cluster,
                        reason=(
                            f"A primary-source record about {entity_id} plus {len(cluster) - 1} follow-up "
                            "record(s) that trace to the same underlying origin -- not yet independently corroborated."
                        ),
                    )
                )

        for cluster in _within_window(entity_records, window_days=REPEATED_ACTIVITY_WINDOW_DAYS):
            report = independence_report(cluster)
            if report["independent_source_count"] < MIN_REPEATED_EVENTS:
                continue
            id_set = frozenset(r["id"] for r in cluster)
            if id_set in seen_id_sets:
                continue
            seen_id_sets.add(id_set)
            candidates.append(
                _candidate(
                    pattern_type=PATTERN_REPEATED_ACTIVITY,
                    entity_id=entity_id,
                    records=cluster,
                    reason=(
                        f"{report['independent_source_count']} independently-dated events naming {entity_id} "
                        f"within {REPEATED_ACTIVITY_WINDOW_DAYS} days -- a repeated pattern, not one-off news."
                    ),
                )
            )

    candidates.extend(_contradiction_candidates(records))
    return candidates


def _contradiction_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Structural contradiction detection only: an explicit evidence_links
    entry with predicate="contradicts" pointing at another record in this
    same set. Never inferred from free text -- if no formal contradicts
    link has been proposed (via app/services/patent_monitor/corroboration.py
    or an equivalent), no contradiction candidate is produced, even if two
    records plausibly disagree. Under-detecting is the safe failure mode
    here, not over-detecting."""
    by_id = {r["id"]: r for r in records if r.get("id")}
    seen_pairs: set[frozenset] = set()
    out: list[dict[str, Any]] = []
    for record in records:
        for link in record.get("evidence_links") or []:
            if not isinstance(link, dict) or link.get("predicate") != "contradicts":
                continue
            target_id = link.get("target_evidence_id")
            target = by_id.get(target_id)
            if not target:
                continue
            pair_key = frozenset({record["id"], target_id})
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            cluster = [record, target]
            shared_entities = sorted(set(record.get("entity_ids") or []) & set(target.get("entity_ids") or []))
            primary_entity = shared_entities[0] if shared_entities else (record.get("entity_ids") or [None])[0]
            out.append(
                _candidate(
                    pattern_type=PATTERN_CONTRADICTION,
                    entity_id=primary_entity or "unscoped",
                    records=cluster,
                    reason=(
                        f"{target_id} carries an explicit contradicts link back to {record['id']} "
                        f"({link.get('notes') or 'no notes recorded'}) -- flagged for review, not resolved."
                    ),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Persistence and human review -- data/service seams only. This module
# deliberately does not add any app.main route, template, or "thread" UI;
# Cursor's Story Threads (or any other presentation layer) is expected to
# read inbox/signal_candidates/*.json directly and call
# apply_review_decision() when an analyst acts on one. A CONFIRM decision
# does not itself create a trusted Signal -- it marks the candidate
# reviewed and ready; an analyst still creates the real Signal through the
# existing /signals form (or Cursor's own UI for it), citing the same
# supporting_evidence_ids. This keeps exactly one human-authored path into
# data/signals/, matching every other trust gate in this project.
# ---------------------------------------------------------------------------

REVIEW_DECISIONS = ("confirm", "edit", "defer", "dismiss", "dispute")

_DECISION_TO_STATUS = {
    "confirm": "confirmed",
    "edit": "proposed",
    "defer": "deferred",
    "dismiss": "dismissed",
    "dispute": "disputed",
}


class SignalCandidateError(ValueError):
    pass


def apply_review_decision(
    candidate: dict[str, Any],
    *,
    decision: str,
    reviewer: str,
    notes: str | None = None,
) -> dict[str, Any]:
    """Pure state transition -- returns a new dict, never mutates the
    input. "edit" is a no-op on status (the candidate stays "proposed"
    for further review) but always records who touched it and why; it
    exists so a human can leave a correction/note on a candidate without
    forcing an immediate confirm/dismiss decision."""
    if decision not in REVIEW_DECISIONS:
        raise SignalCandidateError(f"unknown review decision: {decision!r}")
    if not reviewer or not reviewer.strip():
        raise SignalCandidateError("reviewer is required for any review decision")
    updated = {**candidate}
    updated["status"] = _DECISION_TO_STATUS[decision]
    updated["reviewer"] = reviewer.strip()
    updated["review_notes"] = (notes or "").strip() or None
    updated["reviewed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return updated


def candidates_dir(inbox_dir: Path) -> Path:
    return inbox_dir / "signal_candidates"


def persist_candidates(candidates: list[dict[str, Any]], *, inbox_dir: Path) -> list[Path]:
    """Write each candidate to its own file, additive only -- an existing
    candidate file (which may carry a human's review decision) is never
    overwritten by a later generation run. Mirrors every other pending-
    artifact store in this project (inbox/evidence/, inbox/discovered_media/):
    untrusted, environment-local, never in data/."""
    target_dir = candidates_dir(inbox_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for candidate in candidates:
        path = target_dir / f"{candidate['id']}.json"
        if path.is_file():
            continue
        path.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written


def load_candidates(inbox_dir: Path) -> list[dict[str, Any]]:
    target_dir = candidates_dir(inbox_dir)
    if not target_dir.is_dir():
        return []
    out = []
    for path in sorted(target_dir.glob("*.json")):
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out
