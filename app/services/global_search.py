"""Deterministic global intelligence search (navigation, not a trust layer).

Builds a cheap in-memory document list from already-loaded repositories.
Does not call Morning Brief, Story Thread grouping of the full feed,
variety_footprint, or collection scans. Pending/inbox documents are opt-in
and must never be written into static/public output.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.article_dedup import normalize_canonical_url, normalize_title
from app.services.patent_monitor.entity_link import _fold
from app.services.ui_context import BERRY_GLOBAL
from app.services.variety_workspace import identity_fields

GROUP_ORDER = (
    "companies",
    "varieties",
    "berries",
    "geographies",
    "intelligence",
    "story_threads",
    "signals",
    "assessments",
    "strategic_questions",
    "sources",
)
GROUP_LABELS = {
    "companies": "Companies",
    "varieties": "Varieties",
    "berries": "Berries",
    "geographies": "Geographies",
    "intelligence": "Intelligence",
    "story_threads": "Story Threads",
    "signals": "Signals",
    "assessments": "Assessments",
    "strategic_questions": "Strategic Questions",
    "sources": "Sources",
}
ENTITY_GROUP = {
    "company": "companies",
    "variety": "varieties",
    "geography": "geographies",
    "berry": "berries",
}
STATE_LABELS = {
    "trusted": "Trusted",
    "pending": "Pending",
    "story": "Story",
    "emerging_signal": "Emerging signal",
    "confirmed_signal": "Confirmed signal",
    "assessment": "Assessment",
}
# Lower is better. Pending must never outrank an equally matched trusted hit.
STATE_RANK = {
    "trusted": 0,
    "confirmed_signal": 1,
    "assessment": 1,
    "story": 2,
    "pending": 3,
    "emerging_signal": 3,
}
RANK_EXACT_CANONICAL = 100
RANK_EXACT_ALIAS = 95
RANK_LINKED_ENTITY = 88
RANK_TITLE_NAME = 80
RANK_TRUSTED_DIRECT = 70
RANK_STORY_SIGNAL = 55
RANK_WEAK_TEXT = 30

VARIETY_ROLE_PREDICATES = {"develops", "owns", "licenses", "markets", "grows"}
GEO_PREDICATES = {"operates_in", "located_in", "based_in"}
RELATED_INTEL_CAP = 12
GROUP_CAP_DEFAULT = 8


def _as_tuple(values: Any) -> tuple[str, ...]:
    if not values:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if value)


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

DATE_BASIS_LABELS = {
    "published_date": "Published",
    "observed_at": "Observed",
    "first_seen": "First seen",
    "last_updated": "Last updated",
    "evidence_published_date": "Published",
    "created_at": "Created",
    "generated_at": "Generated",
}
UNKNOWN_DATE_LABELS = {
    "evidence": "Publication date unknown",
    "story_thread": "Publication date unknown",
}
DEFAULT_UNKNOWN_DATE_LABEL = "Date unknown"
# Only these carry a genuine world-time concept. Companies/Varieties/Geographies/
# Berries/Sources/Strategic Questions never get a fabricated date (AGENTS.md rule).
DATE_BEARING_TYPES = {"evidence", "signal", "signal_candidate", "assessment", "story_thread"}


def _human_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        year, month, day = text[:10].split("-")
        return f"{_MONTHS[int(month) - 1]} {int(day)}, {year}"
    except (ValueError, IndexError):
        return text


def _format_date_display(date_iso: str, basis: str) -> str:
    label = DATE_BASIS_LABELS.get(basis, "")
    text = _human_date(date_iso)
    return f"{label} {text}".strip() if label else text


def _evidence_date(record: dict[str, Any]) -> tuple[str, str, bool]:
    """Published/observed only -- never captured_date/created_at/proposed_at.

    Mirrors app/queries/timeline.py::_evidence_row, the durable AGENTS.md rule:
    ingestion/capture time must never masquerade as publication/event time.
    """
    is_commercial = record.get("intake_type") == "commercial_observation" or bool(
        record.get("commercial_observation")
    )
    detail = record.get("commercial_observation") if isinstance(record.get("commercial_observation"), dict) else {}
    if is_commercial:
        observed = detail.get("observed_at") or ""
        if observed:
            return str(observed), "observed_at", False
        published = record.get("published_date") or ""
        return str(published), "published_date", bool(published)
    published = record.get("published_date") or ""
    return str(published), "published_date", False


def _signal_date(signal: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> tuple[str, str, bool]:
    """first_seen -> last_updated -> linked-evidence published_date (flagged fallback).

    Mirrors app/queries/timeline.py::_signal_row (TD-088 convention).
    """
    first_seen = signal.get("first_seen") or ""
    if first_seen:
        return str(first_seen), "first_seen", False
    last_updated = signal.get("last_updated") or ""
    if last_updated:
        return str(last_updated), "last_updated", False
    evidence_ids = [str(e) for e in (signal.get("evidence_ids") or []) if e]
    fallback_dates = sorted(
        evidence_by_id[e].get("published_date")
        for e in evidence_ids
        if e in evidence_by_id and evidence_by_id[e].get("published_date")
    )
    if fallback_dates:
        return str(fallback_dates[0]), "evidence_published_date", True
    return "", "", False


def _sort_rows_newest_first(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dated results newest-first, then undated results, each deterministically tied."""
    dated = [row for row in rows if row.get("date")]
    undated = [row for row in rows if not row.get("date")]
    dated.sort(
        key=lambda row: (str(row.get("date") or ""), str(row.get("title") or "").casefold(), str(row.get("id") or "")),
        reverse=True,
    )
    undated.sort(key=lambda row: (str(row.get("title") or "").casefold(), str(row.get("id") or "")))
    return dated + undated


def _kind_label(record: dict[str, Any]) -> str:
    if record.get("commercial_observation") or record.get("intake_type") == "commercial_observation":
        return "Commercial observation"
    if record.get("patent_filing") or record.get("source_type") in {
        "patent_record",
        "plant_breeders_rights_record",
    }:
        return "Patent / PVR"
    source_type = str(record.get("source_type") or "")
    if source_type in {"podcast", "youtube", "video"} or record.get("media_format") in {"podcast", "video"}:
        return "Spoken media"
    return "Intelligence"


@dataclass(slots=True)
class SearchDoc:
    id: str
    group: str
    object_type: str
    title: str
    href: str
    state: str
    canonical: str = ""
    aliases: tuple[str, ...] = ()
    berry_ids: tuple[str, ...] = ()
    entity_ids: tuple[str, ...] = ()
    geography_ids: tuple[str, ...] = ()
    source_id: str = ""
    date: str = ""
    date_basis: str = ""
    is_fallback_date: bool = False
    captured_date: str = ""
    open_reader: bool = False
    item_id: str = ""
    subtitle: str = ""
    kind_label: str = ""
    relevance_tier: str = ""
    private: bool = False
    haystack: str = ""
    folded_canonical: str = ""
    folded_aliases: tuple[str, ...] = ()
    related_ids: tuple[str, ...] = ()
    match_hints: tuple[str, ...] = ()


@dataclass
class SearchPools:
    entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    published_evidence: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    signals: list[dict[str, Any]] = field(default_factory=list)
    assessments: list[dict[str, Any]] = field(default_factory=list)
    strategic_questions: list[dict[str, Any]] = field(default_factory=list)
    pending_drafts: list[dict[str, Any]] = field(default_factory=list)
    signal_candidates: list[dict[str, Any]] = field(default_factory=list)
    identity_redirects: list[dict[str, Any]] = field(default_factory=list)


def _names_for_entity(entity: dict[str, Any]) -> tuple[str, list[str]]:
    entity_type = str(entity.get("entity_type") or "")
    if entity_type == "variety":
        identity = identity_fields(entity)
        aliases = list(identity.get("aliases") or [])
        aliases.extend(identity.get("commercial_names") or [])
        for extra in (
            identity.get("denomination"),
            identity.get("breeder_code"),
            (entity.get("attributes") or {}).get("selection_code"),
            (entity.get("attributes") or {}).get("breeder_code"),
        ):
            if extra and str(extra) not in aliases:
                aliases.append(str(extra))
        canonical = str(identity.get("canonical_name") or entity.get("name") or "")
        return canonical, [value for value in aliases if value and value.casefold() != canonical.casefold()]
    canonical = str(entity.get("name") or "")
    aliases = [str(value) for value in (entity.get("aliases") or []) if value]
    legal = str((entity.get("attributes") or {}).get("legal_name") or "").strip()
    if legal and legal.casefold() != canonical.casefold() and legal not in aliases:
        aliases.append(legal)
    return canonical, aliases


def _entity_href(entity: dict[str, Any]) -> str:
    entity_type = str(entity.get("entity_type") or "entity")
    entity_id = str(entity.get("id") or "")
    if entity_type == "variety":
        return f"/entities/variety/{entity_id}"
    if entity_type == "company":
        return f"/entities/company/{entity_id}"
    return f"/entities/{entity_type}/{entity_id}"


def _signal_href(record: dict[str, Any], *, emerging: bool) -> str:
    record_id = str(record.get("id") or "")
    if emerging:
        return f"/signals/candidates/{record_id}"
    return f"/signals/{record_id}"


def _signal_state(record: dict[str, Any], *, emerging: bool) -> str:
    if emerging:
        return "emerging_signal"
    status = str(record.get("status") or "").strip().lower()
    if status in {"proposed"}:
        return "confirmed_signal"
    return "confirmed_signal"


def build_search_documents(pools: SearchPools, *, include_private: bool) -> list[SearchDoc]:
    entities_by_id = {str(row["id"]): row for row in pools.entities if row.get("id")}
    evidence_by_id = {str(row["id"]): row for row in pools.published_evidence if row.get("id")}
    related: dict[str, set[str]] = defaultdict(set)
    for rel in pools.relationships:
        subject = str(rel.get("subject_id") or "")
        obj = str(rel.get("object_id") or "")
        predicate = str(rel.get("predicate") or "")
        if not subject or not obj:
            continue
        related[subject].add(obj)
        related[obj].add(subject)
        if predicate in VARIETY_ROLE_PREDICATES | GEO_PREDICATES:
            related[subject].add(obj)
            related[obj].add(subject)

    from app.services.entity_identity import canonical_entity_id, retired_entity_ids

    retired = retired_entity_ids(pools.entities, redirects=pools.identity_redirects)
    docs: list[SearchDoc] = []
    seen: set[str] = set()

    def add(doc: SearchDoc) -> None:
        if not doc.id or doc.id in seen:
            return
        seen.add(doc.id)
        docs.append(doc)

    for entity in pools.entities:
        entity_id = str(entity.get("id") or "")
        entity_type = str(entity.get("entity_type") or "")
        group = ENTITY_GROUP.get(entity_type)
        if not entity_id or not group or entity_id in retired:
            continue
        entity_id = canonical_entity_id(
            entity_id, entities=entities_by_id, redirects=pools.identity_redirects
        )
        if not entity_id or entity_id in seen:
            continue
        canonical, aliases = _names_for_entity(entity)
        folded_aliases = tuple(_fold(alias) for alias in aliases if _fold(alias))
        haystack = " ".join(
            [
                canonical,
                " ".join(aliases),
                str(entity.get("description") or ""),
            ]
        )
        add(
            SearchDoc(
                id=entity_id,
                group=group,
                object_type=entity_type,
                title=canonical,
                href=_entity_href(entity),
                state="trusted",
                canonical=canonical,
                aliases=tuple(aliases),
                berry_ids=_as_tuple(entity.get("berry_ids")),
                entity_ids=(entity_id,),
                geography_ids=_as_tuple(entity.get("geography_ids")),
                date="",
                subtitle=entity_type.replace("_", " ").title(),
                kind_label=entity_type.replace("_", " ").title(),
                haystack=haystack,
                folded_canonical=_fold(canonical),
                folded_aliases=folded_aliases,
                related_ids=tuple(sorted(related.get(entity_id) or ())),
                match_hints=tuple(aliases),
            )
        )

    source_names = {str(row.get("id") or ""): str(row.get("name") or row.get("label") or "") for row in pools.sources}
    for source in pools.sources:
        source_id = str(source.get("id") or "")
        if not source_id:
            continue
        title = str(source.get("name") or source.get("label") or source_id)
        aliases = [str(value) for value in (source.get("aliases") or []) if value]
        haystack = " ".join(
            [
                title,
                " ".join(aliases),
                source_id,
                str(source.get("url") or ""),
                str(source.get("description") or ""),
                " ".join(str(value) for value in (source.get("entity_types") or []) if value),
            ]
        )
        add(
            SearchDoc(
                id=source_id,
                group="sources",
                object_type="source",
                title=title,
                href=f"/sources#source-{source_id}",
                state="trusted",
                canonical=title,
                aliases=tuple(aliases),
                berry_ids=_as_tuple(source.get("berry_ids")),
                source_id=source_id,
                subtitle="Source health (collection, not recall)",
                kind_label="Source",
                haystack=haystack,
                folded_canonical=_fold(title),
                folded_aliases=tuple(_fold(alias) for alias in aliases if _fold(alias)),
            )
        )

    def add_evidence(record: dict[str, Any], *, private: bool) -> None:
        record_id = str(record.get("id") or "")
        if not record_id:
            return
        title = str(record.get("title") or record_id)
        source_id = str(record.get("source_id") or "")
        kind = _kind_label(record)
        date, date_basis, is_fallback_date = _evidence_date(record)
        state = "pending" if private or record.get("status") != "published" else "trusted"
        href = f"/intelligence/{record_id}"
        entity_ids = _as_tuple(record.get("entity_ids"))
        geography_ids = tuple(
            dict.fromkeys(
                [
                    *(_as_tuple(record.get("geography_ids"))),
                    *[
                        value
                        for value in entity_ids
                        if (entities_by_id.get(value) or {}).get("entity_type") == "geography"
                    ],
                ]
            )
        )
        haystack = " ".join(
            [
                title,
                str(record.get("summary") or ""),
                str(record.get("why_it_matters") or ""),
                " ".join(str(tag) for tag in (record.get("tags") or []) if tag),
                str(record.get("source_name") or source_names.get(source_id) or ""),
                source_id,
            ]
        )
        add(
            SearchDoc(
                id=record_id,
                group="intelligence",
                object_type="evidence",
                title=title,
                href=href,
                state=state,
                canonical=title,
                berry_ids=_as_tuple(record.get("berry_ids")),
                entity_ids=entity_ids,
                geography_ids=geography_ids,
                source_id=source_id,
                date=date,
                date_basis=date_basis,
                is_fallback_date=is_fallback_date,
                captured_date=str(record.get("captured_date") or ""),
                open_reader=True,
                item_id=record_id,
                subtitle=kind,
                kind_label=kind,
                relevance_tier=str(record.get("relevance_tier") or ""),
                private=private or state == "pending",
                haystack=haystack,
                folded_canonical=_fold(title),
                related_ids=entity_ids + geography_ids,
            )
        )

    for record in pools.published_evidence:
        add_evidence(record, private=False)

    if include_private:
        for record in pools.pending_drafts:
            add_evidence(record, private=True)
        for cluster in _cheap_pending_threads(pools.pending_drafts):
            add(cluster)

    for signal in pools.signals:
        signal_id = str(signal.get("id") or "")
        if not signal_id:
            continue
        title = str(signal.get("title") or signal_id)
        haystack = " ".join(
            [
                title,
                str(signal.get("observation") or ""),
                str(signal.get("why_it_might_matter") or ""),
            ]
        )
        signal_date, signal_date_basis, signal_is_fallback = _signal_date(signal, evidence_by_id)
        add(
            SearchDoc(
                id=signal_id,
                group="signals",
                object_type="signal",
                title=title,
                href=_signal_href(signal, emerging=False),
                state=_signal_state(signal, emerging=False),
                canonical=title,
                berry_ids=_as_tuple(signal.get("berry_ids") or signal.get("market_ids")),
                entity_ids=_as_tuple(signal.get("entity_ids")),
                date=signal_date,
                date_basis=signal_date_basis,
                is_fallback_date=signal_is_fallback,
                subtitle=str(signal.get("status") or "Signal"),
                kind_label="Signal",
                haystack=haystack,
                folded_canonical=_fold(title),
                related_ids=_as_tuple(signal.get("entity_ids")),
            )
        )

    if include_private:
        for candidate in pools.signal_candidates:
            candidate_id = str(candidate.get("id") or "")
            if not candidate_id:
                continue
            title = str(candidate.get("title") or candidate.get("pattern_type") or candidate_id)
            haystack = " ".join(
                [
                    title,
                    str(candidate.get("summary") or ""),
                    str(candidate.get("pattern_type") or ""),
                ]
            )
            candidate_date = str(candidate.get("generated_at") or candidate.get("created_at") or "")
            candidate_basis = "generated_at" if candidate.get("generated_at") else ("created_at" if candidate.get("created_at") else "")
            add(
                SearchDoc(
                    id=candidate_id,
                    group="signals",
                    object_type="signal_candidate",
                    title=title,
                    href=_signal_href(candidate, emerging=True),
                    state="emerging_signal",
                    canonical=title,
                    berry_ids=_as_tuple(candidate.get("berry_ids")),
                    entity_ids=_as_tuple(candidate.get("entity_ids")),
                    date=candidate_date,
                    date_basis=candidate_basis,
                    subtitle="Signal candidate — not a trusted Signal",
                    kind_label="Emerging signal",
                    private=True,
                    haystack=haystack,
                    folded_canonical=_fold(title),
                    related_ids=_as_tuple(candidate.get("entity_ids")),
                )
            )

    for assessment in pools.assessments:
        assessment_id = str(assessment.get("id") or "")
        if not assessment_id:
            continue
        title = str(assessment.get("title") or assessment_id)
        haystack = " ".join(
            [
                title,
                str(assessment.get("rationale") or ""),
                str(assessment.get("why_it_matters") or ""),
            ]
        )
        add(
            SearchDoc(
                id=assessment_id,
                group="assessments",
                object_type="assessment",
                title=title,
                href=f"/assessments/{assessment_id}",
                state="assessment",
                canonical=title,
                berry_ids=_as_tuple(assessment.get("market_ids") or assessment.get("berry_ids")),
                entity_ids=_as_tuple(assessment.get("entity_ids")),
                date=str(assessment.get("created_at") or ""),
                date_basis="created_at",
                is_fallback_date=False,
                subtitle="Assessment",
                kind_label="Assessment",
                haystack=haystack,
                folded_canonical=_fold(title),
                related_ids=_as_tuple(assessment.get("entity_ids")),
            )
        )

    for sq in pools.strategic_questions:
        sq_id = str(sq.get("id") or "")
        if not sq_id:
            continue
        title = str(sq.get("title") or sq_id)
        haystack = " ".join([title, str(sq.get("description") or "")])
        add(
            SearchDoc(
                id=sq_id,
                group="strategic_questions",
                object_type="strategic_question",
                title=title,
                href=f"/strategic-questions/{sq_id}",
                state=str(sq.get("status") or ""),
                canonical=title,
                berry_ids=_as_tuple(sq.get("berry_ids")),
                date="",
                subtitle="Strategic Question",
                kind_label="Strategic Question",
                haystack=haystack,
                folded_canonical=_fold(title),
            )
        )

    return docs


def _cheap_pending_threads(drafts: list[dict[str, Any]]) -> list[SearchDoc]:
    """Exact URL / exact normalized-title clusters only. Not full thread grouping."""

    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_title: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for draft in drafts:
        if not draft.get("id"):
            continue
        url = normalize_canonical_url(draft.get("source_url") or (draft.get("article") or {}).get("final_url"))
        title = normalize_title(draft.get("title"))
        if url:
            by_url[url].append(draft)
        if title:
            by_title[title].append(draft)
    clusters: list[SearchDoc] = []
    seen: set[frozenset[str]] = set()
    for bucket in (*by_url.values(), *by_title.values()):
        ids = [str(row.get("id")) for row in bucket if row.get("id")]
        key = frozenset(ids)
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        primary = sorted(bucket, key=lambda row: _evidence_date(row)[0], reverse=True)[0]
        primary_id = str(primary.get("id") or "")
        primary_date, primary_date_basis, primary_is_fallback = _evidence_date(primary)
        entity_ids = tuple(dict.fromkeys(eid for row in bucket for eid in _as_tuple(row.get("entity_ids"))))
        berry_ids = tuple(dict.fromkeys(bid for row in bucket for bid in _as_tuple(row.get("berry_ids"))))
        title = str(primary.get("title") or primary_id)
        clusters.append(
            SearchDoc(
                id=f"thread-{primary_id}",
                group="story_threads",
                object_type="story_thread",
                title=title,
                href=f"/threads/{primary_id}",
                state="story",
                canonical=title,
                berry_ids=berry_ids,
                entity_ids=entity_ids,
                date=primary_date,
                date_basis=primary_date_basis,
                is_fallback_date=primary_is_fallback,
                captured_date=str(primary.get("captured_date") or ""),
                subtitle=f"Developing story · {len(key)} items · organizational only",
                kind_label="Story thread",
                private=True,
                haystack=" ".join([title, " ".join(entity_ids)]),
                folded_canonical=_fold(title),
                related_ids=entity_ids,
            )
        )
    return clusters


def _match_rank(doc: SearchDoc, *, query: str, folded_query: str) -> tuple[int, str]:
    if not query:
        return 0, ""
    if folded_query and doc.folded_canonical and folded_query == doc.folded_canonical:
        return RANK_EXACT_CANONICAL, "canonical"
    if folded_query and folded_query in doc.folded_aliases:
        return RANK_EXACT_ALIAS, "alias"
    names = [doc.canonical, *doc.aliases, *doc.match_hints]
    if any(query == str(name).strip().casefold() for name in names if name):
        return RANK_EXACT_ALIAS if query != doc.canonical.casefold() else RANK_EXACT_CANONICAL, "name"
    title_hay = " ".join([doc.canonical, *doc.aliases, doc.title])
    if query in title_hay.casefold() or (folded_query and folded_query in _fold(title_hay)):
        return RANK_TITLE_NAME, "title"
    hay = doc.haystack.casefold()
    if query in hay or (folded_query and folded_query in _fold(doc.haystack)):
        if doc.group in {"signals", "story_threads"}:
            return RANK_STORY_SIGNAL, "text"
        if doc.group == "intelligence" and doc.state == "trusted" and doc.relevance_tier != "adjacent":
            return RANK_TRUSTED_DIRECT, "text"
        return RANK_WEAK_TEXT, "text"
    return 0, ""


def _in_berry(doc: SearchDoc, berry: str) -> bool:
    if berry == BERRY_GLOBAL or not berry:
        return True
    return berry in doc.berry_ids


def _result_payload(doc: SearchDoc, *, rank: int, matched_as: str, in_context: bool) -> dict[str, Any]:
    matched_label = ""
    if matched_as == "alias" and doc.canonical:
        if doc.object_type == "variety":
            matched_label = f"Commercial / alias name of {doc.canonical}"
        else:
            matched_label = f"{doc.canonical} (alias match)"
    date_display = ""
    date_secondary = ""
    if doc.object_type in DATE_BEARING_TYPES:
        if doc.date:
            date_display = _format_date_display(doc.date, doc.date_basis)
        else:
            date_display = UNKNOWN_DATE_LABELS.get(doc.object_type, DEFAULT_UNKNOWN_DATE_LABEL)
            if doc.captured_date:
                date_secondary = f"Captured {_human_date(doc.captured_date)}"
    return {
        "id": doc.id,
        "group": doc.group,
        "object_type": doc.object_type,
        "title": doc.title,
        "canonical_name": doc.canonical,
        "aliases": list(doc.aliases),
        "matched_as": matched_as,
        "matched_label": matched_label,
        "subtitle": doc.subtitle,
        "href": doc.href,
        "state": doc.state,
        "state_label": STATE_LABELS.get(doc.state, doc.state),
        "open_reader": bool(doc.open_reader),
        "item_id": doc.item_id or (doc.id if doc.open_reader else ""),
        "date": doc.date,
        "date_basis": doc.date_basis,
        "is_fallback_date": bool(doc.is_fallback_date),
        "date_display": date_display,
        "date_secondary": date_secondary,
        "kind_label": doc.kind_label,
        "private": bool(doc.private),
        "rank": rank,
        "in_berry_context": in_context,
        "source_id": doc.source_id,
    }


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(row.get("rank") or 0),
        STATE_RANK.get(str(row.get("state") or ""), 9),
        str(row.get("date") or ""),
        str(row.get("title") or "").casefold(),
    )


def search_documents(
    docs: Iterable[SearchDoc],
    query: str,
    *,
    berry: str = BERRY_GLOBAL,
    include_private: bool = False,
    include_global: bool = True,
    limit_per_group: int = GROUP_CAP_DEFAULT,
    sort: str = "newest",
) -> dict[str, Any]:
    sort = sort if sort in {"newest", "relevance"} else "newest"
    needle = (query or "").strip()
    folded_query = _fold(needle)
    hits: dict[str, dict[str, Any]] = {}
    docs_by_id = {doc.id: doc for doc in docs}

    for doc in docs_by_id.values():
        if doc.private and not include_private:
            continue
        rank, matched_as = _match_rank(doc, query=needle.casefold(), folded_query=folded_query)
        if rank <= 0:
            continue
        hits[doc.id] = {
            "doc": doc,
            "rank": rank,
            "matched_as": matched_as,
        }

    exact_entities = [
        bundle["doc"]
        for bundle in hits.values()
        if bundle["doc"].object_type in {"company", "variety", "geography", "source"}
        and bundle["rank"] >= RANK_TITLE_NAME
    ]
    geo_exact_ids = {doc.id for doc in exact_entities if doc.object_type == "geography"}
    if geo_exact_ids:
        hits = {
            hit_id: bundle
            for hit_id, bundle in hits.items()
            if bundle["doc"].group != "intelligence"
            or bundle["matched_as"] != "text"
            or any(
                geo_id in bundle["doc"].geography_ids or geo_id in bundle["doc"].entity_ids
                for geo_id in geo_exact_ids
            )
        }
    related_added = 0
    intel_counts: dict[str, int] = defaultdict(int)
    for entity in exact_entities:
        related_ids = set(entity.related_ids)
        if entity.object_type == "source":
            related_ids.update(
                doc.id
                for doc in docs_by_id.values()
                if doc.group == "intelligence" and doc.source_id == entity.id
            )
        else:
            related_ids.update(
                doc.id
                for doc in docs_by_id.values()
                if entity.id in doc.entity_ids or entity.id in doc.geography_ids or entity.id in doc.related_ids
            )
        candidates = []
        for related_id in related_ids:
            related_doc = docs_by_id.get(related_id)
            if related_doc is None or related_doc.id == entity.id:
                continue
            if related_doc.private and not include_private:
                continue
            if related_doc.group == "intelligence" and entity.object_type == "geography":
                if entity.id not in related_doc.geography_ids and entity.id not in related_doc.entity_ids:
                    continue
            candidates.append(related_doc)
        candidates.sort(key=lambda doc: (doc.group != "intelligence", doc.date), reverse=True)
        for related_doc in candidates:
            current = hits.get(related_doc.id)
            linked_rank = RANK_LINKED_ENTITY
            if related_doc.group == "intelligence" and related_doc.state == "trusted":
                linked_rank = max(linked_rank, RANK_TRUSTED_DIRECT)
            if related_doc.group in {"signals", "story_threads"}:
                linked_rank = max(linked_rank, RANK_STORY_SIGNAL)
            if current is None or current["rank"] < linked_rank:
                hits[related_doc.id] = {
                    "doc": related_doc,
                    "rank": linked_rank,
                    "matched_as": current["matched_as"] if current else "linked",
                }
                related_added += 1
                if related_doc.group == "intelligence":
                    intel_counts[entity.id] += 1

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
        key: {"in_context": [], "also_global": []} for key in GROUP_ORDER
    }
    alias_resolutions: list[dict[str, str]] = []
    for bundle in hits.values():
        doc = bundle["doc"]
        in_context = _in_berry(doc, berry)
        payload = _result_payload(doc, rank=bundle["rank"], matched_as=bundle["matched_as"], in_context=in_context)
        if bundle["matched_as"] == "alias" and doc.object_type in {"company", "variety"}:
            alias_resolutions.append(
                {
                    "query": needle,
                    "canonical_id": doc.id,
                    "canonical_name": doc.canonical,
                    "object_type": doc.object_type,
                }
            )
        bucket = "in_context" if in_context else "also_global"
        if bucket == "also_global" and not include_global:
            continue
        grouped[doc.group][bucket].append(payload)

    groups = []
    total = 0
    exact_groups = 0
    for group_id in GROUP_ORDER:
        # Relevance rank decides which results make the cut (selection);
        # `sort` only decides the order they are then displayed in.
        in_context = sorted(grouped[group_id]["in_context"], key=_sort_key)[:limit_per_group]
        also_global = sorted(grouped[group_id]["also_global"], key=_sort_key)[:limit_per_group]
        if sort == "newest":
            in_context = _sort_rows_newest_first(in_context)
            also_global = _sort_rows_newest_first(also_global)
        if not in_context and not also_global:
            continue
        if any(int(row.get("rank") or 0) >= RANK_EXACT_ALIAS for row in in_context + also_global):
            exact_groups += 1
        total += len(in_context) + len(also_global)
        groups.append(
            {
                "id": group_id,
                "label": GROUP_LABELS[group_id],
                "in_context": in_context,
                "also_global": also_global,
            }
        )

    empty = total == 0
    ambiguous = exact_groups > 1 and any(
        group["id"] in {"companies", "varieties", "geographies"}
        and any(int(row.get("rank") or 0) >= RANK_EXACT_ALIAS for row in group["in_context"] + group["also_global"])
        for group in groups
    )
    return {
        "q": needle,
        "berry": berry,
        "include_private": include_private,
        "include_global": include_global,
        "sort": sort,
        "empty": empty,
        "ambiguous": ambiguous,
        "alias_resolutions": alias_resolutions,
        "groups": groups,
        "result_count": total,
        "related_added": related_added,
    }


def search_global(
    query: str,
    pools: SearchPools,
    *,
    berry: str = BERRY_GLOBAL,
    include_private: bool = False,
    include_global: bool = True,
    limit_per_group: int = GROUP_CAP_DEFAULT,
    sort: str = "newest",
    documents: list[SearchDoc] | None = None,
) -> dict[str, Any]:
    docs = documents if documents is not None else build_search_documents(pools, include_private=include_private)
    return search_documents(
        docs,
        query,
        berry=berry,
        include_private=include_private,
        include_global=include_global,
        limit_per_group=limit_per_group,
        sort=sort,
    )
