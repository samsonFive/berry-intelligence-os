"""Ask Berry OS V1 -- stakeholder-facing domain intelligence orchestration.

This module composes existing canonical intelligence and the provider-neutral
live research plane.  It creates no new intelligence repository and performs
no writes.  Trust classes remain separate all the way to presentation.

The model boundary is intentionally narrow: synthesis receives public source
titles/publishers/dates and already displayed live snippets only.  Fact text,
Signal observations, Assessment rationale, private notes, article bodies, and
report prose never leave the process.  Every generated statement must cite an
ID in the packet; unsupported statements are dropped.
"""

from __future__ import annotations

import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping

from app.services.competitor_pulse import _BERRY_PATTERNS, _normalize_quotes
from app.services.evidence_claim_review import trust_tier_label
from app.services.industry_pulse.canonical_urls import preferred_url
from app.services.industry_pulse.dedup import dedupe_hits, unique_hits
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import DiscoveryProvider, discover
from app.services.industry_pulse.qualify import QualificationIndex, qualify_hit
from app.services.report_builder.scope import ResolvedScope, interpret_scope_text, resolve_scope

DEFAULT_WINDOW_DAYS = 30
MAX_PACKET_EVIDENCE = 36
MAX_LIVE_RESULTS = 24
MAX_COMPARE_COMPANIES = 5

TOPIC_TERMS: dict[str, tuple[str, ...]] = {
    "genetics": ("genetic", "genetics", "breeding", "breeder", "cultivar", "variety", "varieties"),
    "rights_ip": ("patent", "pbr", "pvp", "pvpo", "cpvo", "plant variety protection", "rights"),
    "expansion": ("expand", "expands", "expanded", "expanding", "expansion", "acreage", "hectare", "facility", "investment", "production"),
    "commercial": ("commercial", "license", "licensing", "partnership", "launch", "market", "retail"),
    "supply": ("supply", "shipment", "production", "harvest", "export", "import", "trade", "price"),
    "leadership": ("executive", "ceo", "leadership", "appoint", "hire", "director"),
    "risk": ("threat", "risk", "lawsuit", "regulation", "recall", "tariff", "disease", "weather"),
    "research": ("research", "trial", "study", "university", "innovation", "technology"),
}

_WINDOW_RE = re.compile(r"\b(?:last|past|previous)\s+(\d{1,3})\s*days?\b", re.IGNORECASE)
_COMPARE_RE = re.compile(r"\b(compare|comparison|versus|vs\.?)\b", re.IGNORECASE)
_COMPARATIVE_INTENT_RE = re.compile(
    r"\b(who\s+(?:appears\s+)?(?:is\s+)?(?:most\s+active|best\s+positioned)|"
    r"most\s+important\s+differences?|competitive\s+activity)\b",
    re.IGNORECASE,
)
_BERRY_INDUSTRY_RE = re.compile(
    r"\b(grower|farm|crop|harvest|production|cultivar|variet(?:y|ies)|breeding|"
    r"genetic\w*|nursery|export|import|acreage|hectare|yield|commercial|retail|"
    r"supply|packer|field trial|patent|PBR|PVP|seedless|fresh produce)\b",
    re.IGNORECASE,
)
_NON_CROP_BLACKBERRY_RE = re.compile(
    r"\b(BlackBerry Limited|BlackBerry stock|NYSE\s*:\s*BB|NASDAQ|smartphone|cybersecurity|price prediction)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResearchScope:
    question: str
    berry_id: str | None
    geography_ids: tuple[str, ...]
    company_ids: tuple[str, ...]
    variety_ids: tuple[str, ...]
    window_days: int
    topics: tuple[str, ...]
    intelligence_type: str
    comparison: bool
    unresolved: tuple[str, ...] = ()
    ambiguous: tuple[str, ...] = ()
    interpretation_source: str = "deterministic"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("geography_ids", "company_ids", "variety_ids", "topics", "unresolved", "ambiguous"):
            payload[key] = list(payload[key])
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ResearchScope":
        try:
            window_days = int(raw.get("window_days") or DEFAULT_WINDOW_DAYS)
        except (TypeError, ValueError):
            window_days = DEFAULT_WINDOW_DAYS
        return cls(
            question=str(raw.get("question") or ""),
            berry_id=str(raw["berry_id"]) if raw.get("berry_id") else None,
            geography_ids=tuple(str(v) for v in raw.get("geography_ids") or []),
            company_ids=tuple(dict.fromkeys(str(v) for v in raw.get("company_ids") or []))[:MAX_COMPARE_COMPANIES],
            variety_ids=tuple(str(v) for v in raw.get("variety_ids") or []),
            window_days=max(1, min(window_days, 3650)),
            topics=tuple(str(v) for v in raw.get("topics") or [] if str(v) in TOPIC_TERMS),
            intelligence_type=str(raw.get("intelligence_type") or "domain_intelligence"),
            comparison=bool(raw.get("comparison")),
            unresolved=tuple(str(v) for v in raw.get("unresolved") or []),
            ambiguous=tuple(str(v) for v in raw.get("ambiguous") or []),
            interpretation_source=str(raw.get("interpretation_source") or "deterministic"),
        )


def _topics(text: str) -> tuple[str, ...]:
    folded = text.casefold()
    return tuple(key for key, terms in TOPIC_TERMS.items() if any(_term_present(folded, term) for term in terms))


def _term_present(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term.casefold())}(?!\w)", text))


def _window_days(text: str, proposed: int | None) -> int:
    match = _WINDOW_RE.search(text)
    if match:
        return max(1, min(int(match.group(1)), 3650))
    folded = text.casefold()
    if "today" in folded or "right now" in folded or "currently" in folded:
        return 7
    if "this week" in folded:
        return 7
    if "this month" in folded:
        return 30
    if "this year" in folded:
        return 365
    return max(1, min(int(proposed or DEFAULT_WINDOW_DAYS), 3650))


def _has_explicit_window(text: str) -> bool:
    folded = text.casefold()
    return bool(
        _WINDOW_RE.search(text)
        or any(term in folded for term in ("today", "right now", "currently", "this week", "this month", "this year"))
    )


def _mentioned_berry(text: str, berries: Mapping[str, str]) -> str | None:
    folded = text.casefold()
    irregular = {
        "blueberries": "blueberry",
        "strawberries": "strawberry",
        "raspberries": "raspberry",
        "blackberries": "blackberry",
    }
    for berry_id, label in berries.items():
        names = {str(label).casefold(), str(berry_id).removeprefix("berry-").casefold()}
        names.update(plural for plural, singular in irregular.items() if singular in names)
        if any(_term_present(folded, name) for name in names):
            return str(berry_id)
    return None


def _mentioned_order(ids: tuple[str, ...], text: str, entities: Mapping[str, dict[str, Any]]) -> tuple[str, ...]:
    """Preserve the stakeholder's comparison order, not alias-length scan order."""
    folded = text.casefold()

    def position(entity_id: str) -> tuple[int, str]:
        entity = entities.get(entity_id) or {}
        positions = [
            folded.find(str(name).casefold())
            for name in [entity.get("name"), *(entity.get("aliases") or [])]
            if name and folded.find(str(name).casefold()) >= 0
        ]
        return (min(positions) if positions else len(folded), entity_id)

    return tuple(sorted(ids, key=position))


def interpret_research_scope(
    question: str,
    *,
    berries: dict[str, str],
    entities: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    previous: ResearchScope | None = None,
) -> ResearchScope:
    """Fast deterministic interpretation using the already-proven report parser.

    Follow-ups carry forward omitted dimensions.  An explicitly mentioned new
    geography/berry replaces the prior one; a new company is added when the
    wording is comparative, otherwise it becomes the new company scope.
    """
    clean = _normalize_quotes(" ".join((question or "").split()))
    proposal = interpret_scope_text(clean, berries=berries, completer=None, entities=entities)
    resolved = resolve_scope(
        proposal,
        entities=entities,
        berries=berries,
        questions=questions,
        relationships=relationships,
    )
    mentioned_topics = _topics(clean)
    entity_index = {str(row.get("id")): row for row in entities if row.get("id")}
    company_ids = _mentioned_order(resolved.company_ids, clean, entity_index)
    variety_ids = resolved.variety_ids
    geography_ids = resolved.geography_ids
    berry_id = resolved.berry_id or _mentioned_berry(clean, berries)
    comparison = bool(_COMPARE_RE.search(clean) or _COMPARATIVE_INTENT_RE.search(clean) or len(company_ids) > 1)

    if previous:
        if company_ids:
            if comparison or "what about" in clean.casefold():
                company_ids = tuple(dict.fromkeys((*previous.company_ids, *company_ids)))
        else:
            company_ids = previous.company_ids
        variety_ids = variety_ids or previous.variety_ids
        geography_ids = geography_ids or previous.geography_ids
        berry_id = berry_id or previous.berry_id
        if not mentioned_topics:
            mentioned_topics = previous.topics
        comparison = comparison or (previous.comparison and len(company_ids) > 1)

    unresolved = tuple(dict.fromkeys((*resolved.unresolved_companies, *resolved.unresolved_varieties)))
    if comparison and not company_ids and _COMPARATIVE_INTENT_RE.search(clean):
        unresolved = tuple(
            value for value in unresolved
            if not str(value).casefold().startswith("competitive activity")
        )
    ambiguous = tuple(
        f"{row.query}: {', '.join(row.ambiguous_ids)}"
        for row in (*resolved.ambiguous_companies, *resolved.ambiguous_varieties)
    )
    if resolved.geography_unresolved and resolved.geography_text:
        unresolved += (resolved.geography_text,)

    if comparison or len(company_ids) > 1:
        intelligence_type = "company_comparison"
    elif "rights_ip" in mentioned_topics:
        intelligence_type = "ip_genetics"
    elif "supply" in mentioned_topics or "expansion" in mentioned_topics:
        intelligence_type = "market_and_supply"
    elif company_ids:
        intelligence_type = "competitor"
    else:
        intelligence_type = "domain_intelligence"

    return ResearchScope(
        question=clean,
        berry_id=berry_id,
        geography_ids=tuple(geography_ids),
        company_ids=tuple(company_ids[:MAX_COMPARE_COMPANIES]),
        variety_ids=tuple(variety_ids),
        window_days=(
            previous.window_days
            if previous and not _has_explicit_window(clean) and resolved.date_window_days is None
            else _window_days(clean, resolved.date_window_days)
        ),
        topics=mentioned_topics,
        intelligence_type=intelligence_type,
        comparison=comparison or len(company_ids) > 1,
        unresolved=unresolved,
        ambiguous=ambiguous,
    )


def _record_date(record: Mapping[str, Any]) -> str:
    for key in ("published_date", "event_date", "effective_date", "created_at", "first_seen"):
        value = str(record.get(key) or "")
        if value:
            return value[:10]
    return ""


def _within_window(record: Mapping[str, Any], window_days: int, *, today: date) -> bool:
    stamp = _record_date(record)
    if not stamp:
        return True
    try:
        return date.fromisoformat(stamp) >= today - timedelta(days=window_days)
    except ValueError:
        return True


def _matches_scope(record: Mapping[str, Any], scope: ResearchScope) -> bool:
    linked = set(record.get("entity_ids") or []) | set(record.get("geography_ids") or [])
    selected = set(scope.company_ids) | set(scope.variety_ids) | set(scope.geography_ids)
    if selected and linked.intersection(selected):
        return True
    if scope.berry_id and scope.berry_id in set(record.get("berry_ids") or record.get("market_ids") or []):
        return True
    return not selected and not scope.berry_id


def _topic_rank(record: Mapping[str, Any], topics: tuple[str, ...]) -> int:
    if not topics:
        return 0
    text = " ".join(
        str(record.get(key) or "") for key in ("title", "source_type", "intake_type", "tags")
    ).casefold()
    return sum(1 for topic in topics if any(_term_present(text, term) for term in TOPIC_TERMS[topic]))


def _evidence_row(record: dict[str, Any]) -> dict[str, Any]:
    intake = str(record.get("intake_type") or "")
    structured_kind = ""
    source_type = str(record.get("source_type") or "")
    if record.get("patent_filing") or intake == "patent_filing" or source_type == "patent_record":
        structured_kind = "PATENT"
    elif (
        record.get("cpvo_filing")
        or intake in {"pvr_filing", "pvp_filing"}
        or source_type == "plant_breeders_rights_record"
    ):
        structured_kind = "PBR / PVP"
    elif record.get("commercial_observation"):
        structured_kind = "MARKET OBSERVATION"
    elif record.get("trade_observation"):
        structured_kind = "TRADE OBSERVATION"
    return {
        "id": record.get("id"),
        "title": record.get("title") or record.get("id"),
        "source_name": record.get("source_name") or "",
        "date": _record_date(record),
        "href": f"/evidence/{record.get('id')}",
        "reader_href": f"/intelligence/{record.get('id')}",
        "trust_class": trust_tier_label(record),
        "structured_kind": structured_kind,
        "entity_ids": list(record.get("entity_ids") or []),
        "geography_ids": list(record.get("geography_ids") or []),
    }


def assemble_research_packet(
    scope: ResearchScope,
    *,
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    market_context_provider: Callable[[ResearchScope], list[dict[str, Any]]] | None = None,
    developments_provider: Callable[[ResearchScope], list[dict[str, Any]]] | None = None,
    radar_provider: Callable[[ResearchScope], list[dict[str, Any]]] | None = None,
    competitive_moves_provider: Callable[[ResearchScope], list[dict[str, Any]]] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Assemble only relevant canonical layers; never query everything blindly."""
    today = today or date.today()
    selected = [
        row for row in published_evidence
        if _matches_scope(row, scope) and _within_window(row, scope.window_days, today=today)
    ]
    selected.sort(key=lambda row: (_topic_rank(row, scope.topics), _record_date(row)), reverse=True)
    selected = selected[:MAX_PACKET_EVIDENCE]
    evidence_rows = [_evidence_row(row) for row in selected]
    evidence_ids = {str(row["id"]) for row in evidence_rows if row.get("id")}

    company_ids = list(scope.company_ids)
    variety_ids = list(scope.variety_ids)
    inferred_company_counts: dict[str, int] = {}
    for record in selected:
        for entity_id in record.get("entity_ids") or []:
            entity = entities.get(str(entity_id))
            if entity and entity.get("entity_type") == "company" and entity_id not in company_ids:
                company_ids.append(entity_id)
                inferred_company_counts[str(entity_id)] = inferred_company_counts.get(str(entity_id), 0) + 1
            elif entity and entity.get("entity_type") == "company":
                inferred_company_counts[str(entity_id)] = inferred_company_counts.get(str(entity_id), 0) + 1
            if entity and entity.get("entity_type") == "variety" and entity_id not in variety_ids:
                if scope.berry_id and scope.berry_id not in set(entity.get("berry_ids") or []):
                    continue
                variety_ids.append(entity_id)

    if not scope.company_ids:
        company_ids.sort(key=lambda value: (-inferred_company_counts.get(str(value), 0), str(value)))

    for relationship in relationships:
        if relationship.get("subject_id") not in company_ids:
            continue
        candidate_id = str(relationship.get("object_id") or "")
        candidate = entities.get(candidate_id)
        if not candidate or candidate.get("entity_type") != "variety":
            continue
        if scope.berry_id and scope.berry_id not in set(candidate.get("berry_ids") or []):
            continue
        if candidate_id not in variety_ids:
            variety_ids.append(candidate_id)

    company_rows = [
        {"id": cid, "name": entities[cid].get("name") or cid, "href": f"/entities/company/{cid}",
         "berry_ids": list(entities[cid].get("berry_ids") or [])}
        for cid in company_ids if cid in entities
    ][:MAX_COMPARE_COMPANIES if scope.comparison else 10]
    variety_rows = [
        {"id": vid, "name": entities[vid].get("name") or vid, "href": f"/entities/variety/{vid}",
         "berry_ids": list(entities[vid].get("berry_ids") or [])}
        for vid in variety_ids if vid in entities
    ][:20]

    relevant_entity_ids = set(company_ids) | set(variety_ids) | set(scope.geography_ids)
    relationship_rows = []
    for row in relationships:
        if row.get("subject_id") not in relevant_entity_ids and row.get("object_id") not in relevant_entity_ids:
            continue
        subject = entities.get(str(row.get("subject_id") or ""), {})
        obj = entities.get(str(row.get("object_id") or ""), {})
        relationship_rows.append({
            "id": row.get("id"),
            "subject_id": row.get("subject_id"),
            "subject_name": subject.get("name") or row.get("subject_id"),
            "predicate": row.get("predicate") or "related to",
            "object_id": row.get("object_id"),
            "object_name": obj.get("name") or row.get("object_id"),
            "evidence_ids": [eid for eid in row.get("evidence_ids") or [] if eid in evidence_ids],
        })
    relationship_rows = relationship_rows[:30]

    fact_rows = []
    for row in facts:
        if not _matches_scope(row, scope):
            continue
        if scope.topics and _topic_rank({"title": row.get("statement") or ""}, scope.topics) == 0:
            continue
        citations = [str(eid) for eid in row.get("evidence_ids") or [] if str(eid) in evidence_ids]
        if not citations:
            continue
        fact_rows.append({
            "id": row.get("id"), "statement": row.get("statement") or "", "classification": row.get("classification") or "fact",
            "date": _record_date(row), "source_ids": citations, "trust_class": "TRUSTED FACT",
        })
    fact_rows = fact_rows[:12]

    signal_rows = []
    for row in signals:
        if not _matches_scope(row, scope):
            continue
        signal_rows.append({
            "id": row.get("id"), "title": row.get("title") or row.get("id"),
            "status": row.get("status") or "", "strength": row.get("strength") or "",
            "entity_ids": list(row.get("entity_ids") or []),
            "source_ids": [str(eid) for eid in row.get("evidence_ids") or [] if str(eid) in evidence_ids],
            "href": f"/signals/{row.get('id')}", "trust_class": "SIGNAL",
        })

    assessment_rows = []
    for row in assessments:
        if not _matches_scope(row, scope):
            continue
        assessment_rows.append({
            "id": row.get("id"), "title": row.get("title") or row.get("id"),
            "confidence": row.get("confidence") or "", "ai_proposed": bool(row.get("ai_proposed")),
            "entity_ids": list(row.get("entity_ids") or []),
            "source_ids": [str(eid) for eid in row.get("evidence_ids") or [] if str(eid) in evidence_ids],
            "href": f"/assessments/{row.get('id')}", "trust_class": "ASSESSMENT",
        })

    rights_rows = [row for row in evidence_rows if row.get("structured_kind") in {"PATENT", "PBR / PVP"}]
    market_rows = [row for row in evidence_rows if row.get("structured_kind") in {"MARKET OBSERVATION", "TRADE OBSERVATION"}]
    if market_context_provider is not None:
        market_rows.extend(market_context_provider(scope) or [])
    development_rows: list[dict[str, Any]] = []
    radar_fn = developments_provider or radar_provider
    if radar_fn is not None:
        development_rows = list(radar_fn(scope) or [])[:6]
    move_rows: list[dict[str, Any]] = []
    if competitive_moves_provider is not None:
        move_rows = list(competitive_moves_provider(scope) or [])[:12]

    layers = ["TRUSTED_EVIDENCE", "COMPANIES", "RELATIONSHIPS"]
    if variety_rows or any(topic in scope.topics for topic in ("genetics", "rights_ip")):
        layers.extend(["VARIETIES", "PBR_RIGHTS", "PATENTS"])
    if market_rows or any(topic in scope.topics for topic in ("supply", "expansion", "commercial")):
        layers.append("MARKET_REALITY")
    if development_rows:
        layers.append("EMERGING_RADAR")
        layers.append("RADAR_DEVELOPMENTS")
    if move_rows:
        layers.append("COMPETITIVE_MOVES")
    if signal_rows:
        layers.append("SIGNALS")
    if assessment_rows:
        layers.append("ASSESSMENTS")

    gaps: list[str] = []
    if not evidence_rows:
        gaps.append("No trusted or approved-source Evidence matched this scope and time window.")
    if any(topic in scope.topics for topic in ("genetics", "rights_ip")) and not rights_rows:
        gaps.append("No structured PBR/PVP or patent record matched this scope and time window.")
    elif "rights_ip" in scope.topics and rights_rows and not any(row.get("date") for row in rights_rows):
        gaps.append("Matching IP records are undated in this packet, so no new filing or grant can be established for the window.")
    if any(topic in scope.topics for topic in ("supply", "expansion")) and not market_rows:
        gaps.append("No structured market, production, price, shipment, or trade observation matched this scope.")
    if not signal_rows:
        gaps.append("No reviewed Signal is linked to this scope.")
    if not assessment_rows:
        gaps.append("No reviewed analyst Assessment is linked to this scope.")

    return {
        "scope": scope.as_dict(),
        "requested_layers": layers,
        "evidence": evidence_rows,
        "facts": fact_rows,
        "companies": company_rows,
        "varieties": variety_rows,
        "geographies": [
            {"id": gid, "name": (entities.get(gid) or {}).get("name") or gid, "href": f"/entities/geography/{gid}"}
            for gid in scope.geography_ids
        ],
        "relationships": relationship_rows,
        "rights_ip": rights_rows,
        "market_context": market_rows,
        "radar_developments": development_rows,
        "competitive_moves": move_rows,
        "signals": signal_rows,
        "assessments": assessment_rows,
        "coverage_gaps": gaps,
        "source_index": {
            row["id"]: row
            for row in [*evidence_rows, *market_rows, *development_rows, *move_rows]
            if row.get("id")
        },
    }


def comparison_candidate_ids(
    scope: ResearchScope,
    *,
    packet: Mapping[str, Any],
    entities: Mapping[str, dict[str, Any]],
    relationships: Iterable[Mapping[str, Any]],
    live: Mapping[str, Any] | None = None,
) -> list[str]:
    """Choose up to five evidence-visible Companies for an ambient compare.

    Explicit stakeholder selections always win. For "who appears active" or
    geography comparisons, candidates are ranked on visible row coverage. A
    genetics request additionally requires a canonical Company→Variety role,
    avoiding financial owners that merely co-occur in acquisition coverage.
    """
    if scope.company_ids:
        return list(scope.company_ids[:MAX_COMPARE_COMPANIES])
    scores: dict[str, int] = {}

    def add(rows: Iterable[Mapping[str, Any]], weight: int) -> None:
        for row in rows:
            ids = list(row.get("company_ids") or row.get("entity_ids") or [])
            if row.get("company_id"):
                ids.append(row["company_id"])
            for entity_id in ids:
                entity_id = str(entity_id)
                if (entities.get(entity_id) or {}).get("entity_type") == "company":
                    scores[entity_id] = scores.get(entity_id, 0) + weight

    add(packet.get("evidence") or [], 2)
    add(packet.get("rights_ip") or [], 3)
    add(packet.get("radar_developments") or [], 4)
    add(packet.get("competitive_moves") or [], 5)
    add((live or {}).get("items") or [], 5)

    if "genetics" in scope.topics or "rights_ip" in scope.topics:
        operational: set[str] = set()
        for relationship in relationships:
            company_id = str(relationship.get("subject_id") or "")
            variety = entities.get(str(relationship.get("object_id") or "")) or {}
            if (entities.get(company_id) or {}).get("entity_type") != "company" or variety.get("entity_type") != "variety":
                continue
            if scope.berry_id and scope.berry_id not in set(variety.get("berry_ids") or []):
                continue
            operational.add(company_id)
        if operational:
            scores = {company_id: score for company_id, score in scores.items() if company_id in operational}

    return [
        company_id
        for company_id, _score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:MAX_COMPARE_COMPANIES]
    ]


def _query_text(scope: ResearchScope, entities: Mapping[str, dict[str, Any]]) -> str:
    parts: list[str] = []
    companies = [entities[c].get("name") for c in scope.company_ids if c in entities]
    if companies:
        parts.append("(" + " OR ".join(f'\"{name}\"' for name in companies if name) + ")")
    if scope.berry_id:
        parts.append(scope.berry_id.removeprefix("berry-"))
    elif not companies or re.search(r"\bberr(?:y|ies)\b", scope.question, re.IGNORECASE):
        parts.append("(berry OR berries OR blueberry OR strawberry OR raspberry OR blackberry)")
    geos = [entities[g].get("name") for g in scope.geography_ids if g in entities]
    if geos:
        parts.append("(" + " OR ".join(str(name) for name in geos[:8] if name) + ")")
    for topic in scope.topics[:3]:
        terms = TOPIC_TERMS[topic][:4]
        parts.append("(" + " OR ".join(terms) + ")")
    return " ".join(parts) or scope.question


def _semantic_expansion_text(scope: ResearchScope, entities: Mapping[str, dict[str, Any]]) -> str:
    anchors = [entities[c].get("name") for c in scope.company_ids if c in entities]
    if scope.berry_id:
        anchors.append(scope.berry_id.removeprefix("berry-"))
    topic_terms: list[str] = []
    for topic in scope.topics or ("risk", "expansion"):
        topic_terms.extend(TOPIC_TERMS[topic][:3])
    return " ".join(str(v) for v in [*anchors, *topic_terms, "emerging development"] if v)


def _provider_call(provider: DiscoveryProvider, query: str, scope: ResearchScope) -> tuple[str, list[DiscoveryHit], str | None]:
    try:
        hits = discover(
            query,
            date_window="30d" if scope.window_days > 7 else "7d",
            geography="global",
            berry=scope.berry_id.removeprefix("berry-") if scope.berry_id else None,
            topic=scope.topics[0] if scope.topics else "research_desk",
            provider=provider,
        )
        return provider.name, hits, None
    except Exception as exc:  # one provider must never blank the result
        return provider.name, [], type(exc).__name__


def _mentions_any_company(hit: DiscoveryHit, scope: ResearchScope, entities: Mapping[str, dict[str, Any]]) -> bool:
    if not scope.company_ids:
        return True
    text = _normalize_quotes(f"{hit.title} {hit.snippet}").casefold()
    for company_id in scope.company_ids:
        entity = entities.get(company_id) or {}
        for name in [entity.get("name"), *(entity.get("aliases") or [])]:
            if name and _normalize_quotes(str(name)).casefold() in text:
                return True
    return False


def _matches_explicit_dimensions(hit: DiscoveryHit, scope: ResearchScope, entities: Mapping[str, dict[str, Any]]) -> bool:
    text = _normalize_quotes(f"{hit.title} {hit.snippet}")
    if scope.berry_id:
        pattern = _BERRY_PATTERNS.get(scope.berry_id)
        if pattern is not None and not pattern.search(text):
            return False
        if not scope.company_ids and not _BERRY_INDUSTRY_RE.search(text):
            return False
        if scope.berry_id == "berry-blackberry" and _NON_CROP_BLACKBERRY_RE.search(text):
            return False
    if scope.geography_ids:
        folded = text.casefold()
        names = [
            str(name)
            for geography_id in scope.geography_ids
            for name in [
                (entities.get(geography_id) or {}).get("name"),
                *((entities.get(geography_id) or {}).get("aliases") or []),
            ]
            if name
        ]
        if names and not any(_term_present(folded, name) for name in names):
            return False
    return True


def _live_id(url: str) -> str:
    return "live-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def run_live_research(
    scope: ResearchScope,
    *,
    providers: Iterable[DiscoveryProvider],
    entities: dict[str, dict[str, Any]],
    sources: Iterable[dict[str, Any]] = (),
    background_hits: Iterable[DiscoveryHit] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run one bounded query per available provider plus one Exa expansion."""
    now = now or datetime.now(timezone.utc)
    started = time.monotonic()
    query = _query_text(scope, entities)
    raw: list[DiscoveryHit] = []
    telemetry: dict[str, dict[str, int]] = {}
    failures: list[dict[str, str]] = []
    provider_list = list(providers)
    if provider_list:
        with ThreadPoolExecutor(max_workers=min(6, len(provider_list))) as pool:
            futures = [pool.submit(_provider_call, provider, query, scope) for provider in provider_list]
            for future in as_completed(futures):
                name, hits, error = future.result()
                telemetry[name] = {"queries": 1, "hits": len(hits), "errors": 1 if error else 0}
                raw.extend(hits)
                if error:
                    failures.append({"provider": name, "error": error})

    direct_urls = {preferred_url(hit) for hit in raw}
    related_urls: set[str] = set()
    exa = next((p for p in provider_list if getattr(p, "name", "") == "exa"), None)
    if exa is not None:
        name, hits, error = _provider_call(exa, _semantic_expansion_text(scope, entities), scope)
        telemetry.setdefault(name, {"queries": 0, "hits": 0, "errors": 0})
        telemetry[name]["queries"] += 1
        telemetry[name]["hits"] += len(hits)
        telemetry[name]["errors"] += 1 if error else 0
        for hit in hits:
            url = preferred_url(hit)
            if url not in direct_urls:
                related_urls.add(url)
        raw.extend(hits)
        if error:
            failures.append({"provider": name, "error": error})

    # CatchAll is cache-only here.  It is never submitted from request time.
    folded_terms = {token for token in re.findall(r"[a-z0-9]+", query.casefold()) if len(token) > 3}
    cached_count = 0
    for hit in background_hits:
        text = f"{hit.title} {hit.snippet}".casefold()
        if folded_terms and not folded_terms.intersection(re.findall(r"[a-z0-9]+", text)):
            continue
        raw.append(hit)
        cached_count += 1
    if cached_count:
        telemetry["newscatcher_catchall_cache"] = {"queries": 0, "hits": cached_count, "errors": 0}

    company_names = [
        str(value)
        for row in entities.values() if row.get("entity_type") == "company"
        for value in [row.get("name"), *(row.get("aliases") or [])] if value
    ]
    variety_names = [
        str(value)
        for row in entities.values() if row.get("entity_type") == "variety"
        for value in [row.get("name"), *(row.get("aliases") or [])] if value
    ]
    index = QualificationIndex.compile(company_names=company_names, variety_names=variety_names, sources=sources)
    for hit in raw:
        hit.title = _normalize_quotes(hit.title)
        hit.snippet = _normalize_quotes(hit.snippet)
        qualify_hit(hit, index=index)
        if not _mentions_any_company(hit, scope, entities) or not _matches_explicit_dimensions(hit, scope, entities):
            hit.qualifying = False
    dedupe_hits(raw)

    rows: list[dict[str, Any]] = []
    threshold = now.date() - timedelta(days=scope.window_days)
    for hit in unique_hits(raw):
        if not hit.qualifying:
            continue
        if hit.published_date:
            try:
                if date.fromisoformat(hit.published_date[:10]) < threshold:
                    continue
            except ValueError:
                pass
        url = preferred_url(hit)
        rows.append({
            "id": _live_id(url), "title": hit.title, "url": url,
            "source_name": hit.origin_publisher_name or hit.source_domain or "Unknown publisher",
            "date": hit.published_date or "", "snippet": hit.snippet,
            "provider": hit.provider, "trust_class": "LIVE / UNREVIEWED",
            "related_emerging": url in related_urls,
        })
    rows.sort(key=lambda row: (row["date"], row["title"]), reverse=True)
    rows = rows[:MAX_LIVE_RESULTS]
    return {
        "query": query,
        "items": rows,
        "telemetry": telemetry,
        "failures": failures,
        "latency_seconds": round(time.monotonic() - started, 3),
        "semantic_expansion_used": exa is not None,
    }


_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "source_ids"],
                "additionalProperties": False,
            },
        },
        "implications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "source_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["findings", "implications"],
    "additionalProperties": False,
}

_ANSWER_INSTRUCTIONS = (
    "Draft concise berry-industry strategy findings using ONLY the numbered public source lines. "
    "Every statement must cite one or more listed source IDs. Do not invent figures, motives, market share, "
    "commercial success, or intent. Implications must use cautious language such as may/could and are AI synthesis, "
    "not reviewed analyst Assessments. Return empty arrays when the sources do not support substance."
)


def _public_digest(packet: dict[str, Any], live: dict[str, Any]) -> list[str]:
    lines = []
    for row in packet.get("evidence") or []:
        lines.append(f"{row['id']} | {row['title']} | {row['source_name']} | {row['date'] or 'date unknown'}")
    for row in live.get("items") or []:
        line = f"{row['id']} | {row['title']} | {row['source_name']} | {row['date'] or 'date unknown'}"
        if row.get("snippet"):
            line += f" | {str(row['snippet'])[:220]}"
        lines.append(line)
    return lines[:48]


def _validated_generated(rows: Iterable[Mapping[str, Any]], known_ids: set[str], kind: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        text = " ".join(str(row.get("text") or "").split())
        ids = [str(v) for v in row.get("source_ids") or [] if str(v) in known_ids]
        if text and ids:
            out.append({"text": text, "source_ids": ids, "kind": kind})
    return out


def compose_research_answer(
    packet: dict[str, Any],
    *,
    live: dict[str, Any] | None = None,
    completer: Callable[..., Any] | None = None,
    model: str = "anthropic/claude-haiku-4-5",
) -> dict[str, Any]:
    """Create a source-grounded answer. Unsupported generated claims vanish."""
    live = live or {"items": [], "latency_seconds": 0.0, "semantic_expansion_used": False}
    sources = dict(packet.get("source_index") or {})
    for row in live.get("items") or []:
        sources[row["id"]] = row
    known_ids = set(sources)

    findings: list[dict[str, Any]] = []
    rights_ids = {row["id"] for row in packet.get("rights_ip") or [] if row.get("id")}
    if "rights_ip" in set((packet.get("scope") or {}).get("topics") or []):
        for row in packet.get("rights_ip") or []:
            findings.append({"text": row["title"], "source_ids": [row["id"]], "kind": "STRUCTURED IP RECORD"})
    for row in packet.get("facts") or []:
        ids = [source_id for source_id in row.get("source_ids") or [] if source_id in known_ids]
        if rights_ids and "rights_ip" in set((packet.get("scope") or {}).get("topics") or []) and not rights_ids.intersection(ids):
            continue
        if row.get("statement") and ids:
            findings.append({"text": row["statement"], "source_ids": ids, "kind": "FACT"})
    packet_developments = [
        *(packet.get("competitive_moves") or []),
        *(packet.get("radar_developments") or []),
    ]
    seen_developments: set[str] = set()
    for row in [*packet_developments, *(live.get("items") or [])]:
        row_id = str(row.get("id") or "")
        if not row_id or row_id in seen_developments:
            continue
        seen_developments.add(row_id)
        findings.append({"text": row["title"], "source_ids": [row["id"]], "kind": "OBSERVED DEVELOPMENT"})
    if len(findings) < 3:
        for row in packet.get("evidence") or []:
            findings.append({"text": row["title"], "source_ids": [row["id"]], "kind": row["trust_class"]})
            if len(findings) >= 5:
                break
    findings = findings[:7]

    implications: list[dict[str, Any]] = []
    digest = _public_digest(packet, live)
    if completer is not None and digest:
        prompt = _ANSWER_INSTRUCTIONS + "\n\nPublic sources (id | title | publisher | date | snippet):\n- " + "\n- ".join(digest)
        try:
            result = completer(prompt, schema=_ANSWER_SCHEMA, model=model, max_output_tokens=900)
            generated_findings = _validated_generated(result.parsed.get("findings") or [], known_ids, "OBSERVED DEVELOPMENT")
            generated_implications = _validated_generated(result.parsed.get("implications") or [], known_ids, "POSSIBLE IMPLICATION")
            if generated_findings:
                findings = generated_findings[:7]
            implications = generated_implications[:5]
        except Exception:
            pass

    current = [row for row in live.get("items") or [] if not row.get("related_emerging")]
    weak = [row for row in live.get("items") or [] if row.get("related_emerging")]
    weak.extend(row for row in packet.get("signals") or [] if row.get("status") != "confirmed")
    return {
        "findings": findings,
        "current_developments": current,
        "implications": implications,
        "competitive_context": {"companies": packet.get("companies") or [], "relationships": packet.get("relationships") or []},
        "rights_ip": packet.get("rights_ip") or [],
        "market_context": packet.get("market_context") or [],
        "radar_developments": packet.get("radar_developments") or [],
        "competitive_moves": packet.get("competitive_moves") or [],
        "signals": packet.get("signals") or [],
        "assessments": packet.get("assessments") or [],
        "weak_signals": weak,
        "gaps": packet.get("coverage_gaps") or [],
        "sources": list(sources.values()),
        "ai_synthesis": bool(implications),
        "latency_seconds": live.get("latency_seconds") or 0.0,
    }
