"""Living entity dossier projection over the existing feed-first trust store.

This module does not create a second published corpus. It projects only
explicitly confirmed feed-first statements and keeps bounded research
proposals private until an analyst decision promotes one into that store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from app.services.feed_first import (
    TRUSTED_ANALYST,
    load_state,
    save_state,
    statements_for_entity,
)

REGISTRY_VERSION = "1.0.0"

# Gate 1 intentionally exercises a small Wave A/B slice of the supplied
# 75-question registry. IDs and wording are preserved verbatim.
PILOT_QUESTIONS = (
    {
        "id": "entity.identity.canonical_name",
        "section": "identity",
        "wave": "A",
        "criticality": "critical",
        "question": "What is the current canonical name?",
    },
    {
        "id": "entity.identity.entity_type",
        "section": "identity",
        "wave": "A",
        "criticality": "critical",
        "question": "Is this a company, brand, program, consortium, university unit, nursery, or other body?",
    },
    {
        "id": "entity.identity.operating_status",
        "section": "identity",
        "wave": "A",
        "criticality": "critical",
        "question": "Is the entity or program active, inactive, acquired, transferred, merged, historical, or uncertain?",
    },
    {
        "id": "entity.identity.website",
        "section": "identity",
        "wave": "A",
        "criticality": "high",
        "question": "What is the official website?",
    },
    {
        "id": "entity.activity.berry_roles",
        "section": "activity",
        "wave": "B",
        "criticality": "critical",
        "question": "For each berry, does it breed, own, license, propagate, grow, pack, market, distribute, or provide technology?",
    },
    {
        "id": "entity.geography.headquarters",
        "section": "geography",
        "wave": "B",
        "criticality": "high",
        "question": "Where is the entity headquartered?",
    },
    {
        "id": "entity.performance.plants_sold",
        "section": "performance",
        "wave": "B",
        "criticality": "high",
        "question": "How many plants are sold, delivered, or produced, and over what period?",
    },
    {
        "id": "entity.competitive.vulnerabilities",
        "section": "competitive",
        "wave": "D",
        "criticality": "high",
        "question": "What evidence-backed weaknesses and dependencies exist?",
    },
)

SECTION_ORDER = (
    ("snapshot", "Snapshot"),
    ("recent-changes", "Recent Changes"),
    ("identity-structure", "Identity & Structure"),
    ("berry-value-chain", "Berry & Value Chain"),
    ("genetics-cultivars", "Genetics & Cultivars"),
    ("geography", "Geography"),
    ("people", "People"),
    ("relationships", "Partnerships & Relationships"),
    ("scale-performance", "Scale & Performance"),
    ("history", "History"),
    ("competitive-assessment", "Competitive Assessment"),
    ("watchpoints", "Watchpoints"),
    ("evidence-gaps", "Evidence, Gaps & Conflicts"),
)

ARCHETYPE_LABELS = {
    "integrated_private_genetics": "Integrated private genetics platform",
    "specialist_breeder_nursery": "Specialist breeder / nursery",
    "public_research_program": "Public / university breeding program",
    "grower_marketer_genetics": "Grower-marketer with genetics",
    "registry_source_system": "Registry / source system",
    "operating_entity": "Operating entity",
}

QUESTION_ARCHETYPE_APPLICABILITY = {
    "entity.identity.canonical_name": set(ARCHETYPE_LABELS),
    "entity.identity.entity_type": set(ARCHETYPE_LABELS),
    "entity.identity.operating_status": set(ARCHETYPE_LABELS),
    "entity.identity.website": set(ARCHETYPE_LABELS),
    "entity.activity.berry_roles": {
        "integrated_private_genetics",
        "specialist_breeder_nursery",
        "public_research_program",
        "grower_marketer_genetics",
        "operating_entity",
    },
    "entity.geography.headquarters": set(ARCHETYPE_LABELS),
    "entity.performance.plants_sold": {
        "integrated_private_genetics",
        "specialist_breeder_nursery",
    },
    "entity.competitive.vulnerabilities": {
        "integrated_private_genetics",
        "specialist_breeder_nursery",
        "grower_marketer_genetics",
        "operating_entity",
    },
}

ARCHETYPE_SECTIONS = {
    "registry_source_system": {
        "snapshot",
        "recent-changes",
        "identity-structure",
        "geography",
        "watchpoints",
        "evidence-gaps",
    },
    "public_research_program": {
        section_id
        for section_id, _label in SECTION_ORDER
        if section_id not in {"scale-performance"}
    },
    "grower_marketer_genetics": {
        section_id
        for section_id, _label in SECTION_ORDER
        if section_id not in {"genetics-cultivars"}
    },
}


def classify_archetype(
    entity: dict[str, Any],
    profile: dict[str, Any],
) -> str:
    if profile.get("is_registry"):
        return "registry_source_system"
    roles = {str(value).casefold() for value in (entity.get("roles") or [])}
    attributes = entity.get("attributes") if isinstance(entity.get("attributes"), dict) else {}
    sector = str(attributes.get("sector") or "").casefold()
    seed_type = str(profile.get("seed_entity_type") or "").casefold()
    if "public_research" in sector or "public_research_institution" in roles or "university" in seed_type:
        return "public_research_program"
    if {"grower", "marketer"}.issubset(roles) and (
        "genetics_licensee" in roles or "breeding_joint_venture_partner" in roles
    ):
        return "grower_marketer_genetics"
    if "plant_producer" in roles and "breeder" in roles:
        return "integrated_private_genetics"
    if "breeder" in roles and ("nursery" in roles or "genetics_licensor" in roles):
        return "specialist_breeder_nursery"
    return "operating_entity"


def _question_state(
    question_id: str,
    *,
    entity: dict[str, Any],
    profile: dict[str, Any],
    statements: list[dict[str, Any]],
    archetype: str,
) -> tuple[str, str]:
    if archetype not in QUESTION_ARCHETYPE_APPLICABILITY.get(
        question_id, set(ARCHETYPE_LABELS)
    ):
        return "not_applicable", ""
    metadata = {
        "entity.identity.canonical_name": entity.get("name") or profile.get("canonical_name"),
        "entity.identity.entity_type": entity.get("entity_type") or profile.get("seed_entity_type"),
        "entity.identity.operating_status": entity.get("status") or profile.get("status"),
        "entity.identity.website": profile.get("official_website"),
        "entity.activity.berry_roles": entity.get("roles") or profile.get("crops"),
    }
    value = metadata.get(question_id)
    if value:
        if isinstance(value, list):
            rendered = ", ".join(str(item) for item in value)
        else:
            rendered = str(value)
        return "answered", rendered
    if question_id == "entity.performance.plants_sold":
        row = next(
            (
                item
                for item in statements
                if item.get("statement_type") == "quantity"
                and any(
                    token in str(item.get("statement_text") or "").casefold()
                    for token in ("plant", "nursery", "hectare")
                )
            ),
            None,
        )
        if row:
            return "answered", str(row.get("statement_text") or "")
    if question_id == "entity.geography.headquarters":
        return "not_yet_researched", ""
    if question_id == "entity.competitive.vulnerabilities":
        return "not_yet_researched", ""
    return "unknown", ""


def _statement_section(row: dict[str, Any]) -> str:
    statement_type = str(row.get("statement_type") or "")
    text = str(row.get("statement_text") or "").casefold()
    if statement_type == "quantity":
        return "scale-performance"
    if statement_type == "partnership":
        return "relationships"
    if any(token in text for token in ("cultivar", "variety", "breeding", "genetic")):
        return "genetics-cultivars"
    if row.get("geographies"):
        return "geography"
    if statement_type in {"dated_event", "launch"}:
        return "history"
    return "berry-value-chain"


def _assessment(entity_id: str, statements: list[dict[str, Any]]) -> dict[str, Any]:
    supporting = [str(row.get("id")) for row in statements if row.get("id")]
    latest = max(
        (str(row.get("updated_at") or row.get("created_at") or "") for row in statements),
        default="",
    )
    if len(supporting) < 3:
        return {
            "id": f"dossier-assessment-{entity_id}",
            "entity_id": entity_id,
            "framework": "competitive-posture-v1",
            "generated_at": latest or None,
            "state": "insufficient_evidence",
            "confidence": "low",
            "conclusion": "Competitive assessment is held until at least three confirmed, relevant statements satisfy its prerequisites.",
            "supporting_statement_ids": supporting,
            "counterevidence_ids": [],
            "prerequisite_status": f"{len(supporting)}/3 confirmed statements",
        }
    return {
        "id": f"dossier-assessment-{entity_id}",
        "entity_id": entity_id,
        "framework": "competitive-posture-v1",
        "generated_at": latest or None,
        "state": "proposed",
        "confidence": "low",
        "conclusion": "Confirmed evidence is available for analyst assessment; no competitive conclusion has been approved.",
        "supporting_statement_ids": supporting,
        "counterevidence_ids": [],
        "prerequisite_status": "minimum factual prerequisite passed",
    }


def build_dossier(
    *,
    entity_id: str,
    entity: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    state: dict[str, Any],
    people: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entity = entity or {}
    profile = profile or {}
    archetype = classify_archetype(entity, profile)
    applicable_section_ids = ARCHETYPE_SECTIONS.get(
        archetype, {section_id for section_id, _label in SECTION_ORDER}
    )
    statements = statements_for_entity(state, entity_id)
    statement_groups: dict[str, list[dict[str, Any]]] = {}
    for row in statements:
        statement_groups.setdefault(_statement_section(row), []).append(row)
    recent = sorted(
        statements,
        key=lambda row: str(row.get("confirmed_at") or row.get("updated_at") or ""),
        reverse=True,
    )
    questions = []
    for question in PILOT_QUESTIONS:
        answer_state, answer = _question_state(
            question["id"],
            entity=entity,
            profile=profile,
            statements=statements,
            archetype=archetype,
        )
        questions.append({**question, "answer_state": answer_state, "answer": answer})
    applicable = [row for row in questions if row["answer_state"] != "not_applicable"]
    answered = [row for row in applicable if row["answer_state"] == "answered"]
    conflicts = [row for row in statements if row.get("statement_state") == "conflicting"]
    stale = [row for row in questions if row["answer_state"] == "stale"]
    return {
        "entity_id": entity_id,
        "archetype": archetype,
        "archetype_label": ARCHETYPE_LABELS[archetype],
        "competitor_eligible": archetype != "registry_source_system",
        "registry_version": REGISTRY_VERSION,
        "outline": [
            {"id": sid, "label": label}
            for sid, label in SECTION_ORDER
            if sid in applicable_section_ids
        ],
        "applicable_section_ids": sorted(applicable_section_ids),
        "statements": statements,
        "statement_groups": statement_groups,
        "recent_changes": recent[:8],
        "questions": questions,
        "coverage": {
            "answered": len(answered),
            "applicable": len(applicable),
            "gaps": len(applicable) - len(answered),
            "conflicts": len(conflicts),
            "stale": len(stale),
        },
        "assessment": _assessment(entity_id, statements),
        "people": list(people or []),
        "proposals": [
            row
            for row in (state.get("research_proposals") or {}).values()
            if row.get("entity_id") == entity_id
        ],
        "research_runs": [
            row
            for row in (state.get("research_runs") or {}).values()
            if row.get("entity_id") == entity_id
        ],
    }


def _support_options(record: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    options: list[tuple[str, dict[str, Any]]] = []
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    for position, paragraph in enumerate(article.get("paragraphs") or []):
        if not isinstance(paragraph, dict):
            continue
        text = str(paragraph.get("text") or "").strip()
        if len(text) >= 40:
            options.append(
                (
                    text,
                    {
                        "medium": "article_paragraph",
                        "paragraph_index": int(
                            paragraph.get("index")
                            if paragraph.get("index") is not None
                            else position
                        ),
                        "start_offset": 0,
                        "end_offset": len(text),
                        "exact": text,
                    },
                )
            )
    summary = str(record.get("summary") or "").strip()
    if len(summary) >= 40:
        options.append(
            (
                summary,
                {
                    "medium": "summary",
                    "paragraph_index": -1,
                    "start_offset": 0,
                    "end_offset": len(summary),
                    "exact": summary,
                },
            )
        )
    title = str(record.get("title") or "").strip()
    if len(title) >= 20:
        options.append(
            (
                title,
                {
                    "medium": "headline",
                    "paragraph_index": -1,
                    "start_offset": 0,
                    "end_offset": len(title),
                    "exact": title,
                },
            )
        )
    return options


def _support_matches_question(
    question_id: str,
    text: str,
    record: dict[str, Any] | None = None,
) -> bool:
    hay = text.casefold()
    if question_id == "entity.performance.plants_sold":
        source_type = str((record or {}).get("source_type") or "").casefold()
        if source_type in {
            "patent_record",
            "plant_breeders_rights_record",
            "plant_patent",
        } or re.search(
            r"\b(?:patent|application|certificate|plant breeders?' rights?)\b",
            hay,
        ):
            return False
        quantity = (
            r"\b\d+(?:[,.]\d+)*(?:\s*(?:million|billion|thousand|m|bn|k))?\b"
        )
        plants = r"(?:[a-z][a-z-]*\s+){0,3}plants?\b"
        activity = (
            r"\b(?:sell(?:s|ing)?|sold|deliver(?:s|ed|ing)?|"
            r"produc(?:e[sd]?|ed|ing|tion)|output|capacity|"
            r"expand(?:s|ed|ing)?\s+to|reach(?:es|ed)?)\b"
        )
        return bool(
            re.search(rf"{activity}(?:\W+\w+){{0,5}}\W+{quantity}\s+{plants}", hay)
            or re.search(
                rf"{quantity}\s+{plants}(?:\W+\w+){{0,5}}\W+{activity}",
                hay,
            )
        )
    if question_id == "entity.geography.headquarters":
        return "headquarter" in hay or bool(re.search(r"\bbased in\b", hay))
    if question_id == "entity.competitive.vulnerabilities":
        return any(
            token in hay
            for token in ("dependency", "depends on", "vulnerability", "risk", "exposed to")
        )
    return True


def _source_suitability(question_id: str, record: dict[str, Any]) -> str:
    source_type = str(record.get("source_type") or "")
    if question_id == "entity.performance.plants_sold":
        if source_type in {"annual_report", "regulatory_filing"}:
            return "direct_disclosure_candidate"
        return "trade_report_candidate_needs_scope_review"
    if question_id == "entity.geography.headquarters":
        if source_type in {"company_website", "government_record", "regulatory_filing"}:
            return "direct_identity_source_candidate"
        return "secondary_identity_candidate_needs_confirmation"
    return "candidate_support_requires_analyst_review"


def launch_gap_research(
    inbox_dir: Path,
    *,
    entity_id: str,
    question_id: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    question = next((row for row in PILOT_QUESTIONS if row["id"] == question_id), None)
    if question is None:
        raise ValueError("question is not in the bounded pilot registry")
    state = load_state(inbox_dir)
    run_id = f"dossier-run-{uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat(timespec="seconds")
    candidates = [
        row
        for row in evidence
        if row.get("status") == "published"
        and entity_id in (row.get("entity_ids") or [])
        and row.get("source_url")
    ]
    supported = next(
        (
            (row, support)
            for row in candidates
            for support in _support_options(row)
            if _support_matches_question(question_id, support[0], row)
        ),
        None,
    )
    run = {
        "id": run_id,
        "entity_id": entity_id,
        "question_ids": [question_id],
        "registry_version": REGISTRY_VERSION,
        "scope": "one_entity_one_question_existing_corpus",
        "provider_calls": 0,
        "budget": "existing_corpus_only",
        "created_at": now,
        "stages": ["planned", "searched_existing_corpus"],
        "status": "completed_proposal" if supported else "searched_no_evidence",
    }
    proposal = None
    if supported:
        record, (passage, locator) = supported
        proposal_id = f"dossier-proposal-{uuid4().hex[:12]}"
        proposal = {
            "id": proposal_id,
            "run_id": run_id,
            "entity_id": entity_id,
            "question_id": question_id,
            "statement_text": passage,
            "original_proposal_text": passage,
            "statement_state": "proposed",
            "source_id": record.get("source_id"),
            "source_name": record.get("source_name") or "",
            "source_url": record.get("source_url") or "",
            "evidence_id": record.get("id"),
            "supporting_passages": [passage],
            "support_locators": [locator],
            "origin": "autonomous_gap_research",
            "source_suitability": _source_suitability(question_id, record),
            "created_at": now,
            "decision_history": [],
        }
        run["stages"].extend(["screened_support", "proposal_created"])
    runs = dict(state.get("research_runs") or {})
    runs[run_id] = run
    state["research_runs"] = runs
    if proposal:
        proposals = dict(state.get("research_proposals") or {})
        proposals[proposal["id"]] = proposal
        state["research_proposals"] = proposals
    save_state(inbox_dir, state)
    return {"run": run, "proposal": proposal}


def decide_proposal(
    inbox_dir: Path,
    *,
    proposal_id: str,
    action: str,
    text: str | None = None,
    canonical_fact_id: str | None = None,
) -> dict[str, Any] | None:
    if action not in {"approve", "amend", "reject", "defer"}:
        raise ValueError("invalid proposal action")
    state = load_state(inbox_dir)
    proposals = dict(state.get("research_proposals") or {})
    proposal = dict(proposals.get(proposal_id) or {})
    if not proposal:
        return None
    if proposal.get("statement_state") != "proposed":
        raise ValueError("proposal already decided")
    now = datetime.now(UTC).isoformat(timespec="seconds")
    history = list(proposal.get("decision_history") or [])
    next_text = str(text or "").strip()
    if action == "amend" and not next_text:
        raise ValueError("amended text is required")
    if action in {"approve", "amend"}:
        if not canonical_fact_id:
            raise ValueError("canonical Fact confirmation is required")
        statement_text = next_text if action == "amend" else str(proposal["statement_text"])
        statement = {
            "id": f"{proposal_id}::statement",
            "feed_item_id": "",
            "research_run_id": proposal["run_id"],
            "statement_text": statement_text,
            "original_extraction_text": proposal["original_proposal_text"],
            "supporting_passages": list(proposal.get("supporting_passages") or []),
            "support_locators": list(proposal.get("support_locators") or []),
            "entity_ids": [proposal["entity_id"]],
            "person_ids": [],
            "crops": [],
            "geographies": [],
            "topics": [],
            "question_ids": [proposal["question_id"]],
            "statement_type": (
                "quantity"
                if proposal["question_id"] == "entity.performance.plants_sold"
                else "captured_assertion"
            ),
            "structured_details": {},
            "importance_state": "normal",
            "statement_state": TRUSTED_ANALYST,
            "canonical_fact_id": canonical_fact_id,
            "origin": "autonomous_gap_research",
            "confidence": "analyst_confirmed_support",
            "created_at": now,
            "updated_at": now,
            "confirmed_at": now,
            "analyst_edit_history": [],
            "decision_history": [
                {
                    "at": now,
                    "action": action,
                    "from": "proposed",
                    "to": TRUSTED_ANALYST,
                    "surface": "entity_dossier_gap_review",
                }
            ],
            "source_name": proposal.get("source_name"),
            "source_url": proposal.get("source_url"),
            "evidence_id": proposal.get("evidence_id"),
        }
        statements = dict(state.get("statements") or {})
        statements.setdefault(f"research::{proposal['run_id']}", []).append(statement)
        state["statements"] = statements
        proposal["statement_state"] = "trusted_analyst"
        proposal["approved_statement_id"] = statement["id"]
        proposal["statement_text"] = statement_text
    else:
        proposal["statement_state"] = action
    history.append(
        {
            "at": now,
            "action": action,
            "from": "proposed",
            "to": proposal["statement_state"],
            "surface": "entity_dossier_gap_review",
        }
    )
    proposal["decision_history"] = history
    proposal["updated_at"] = now
    proposals[proposal_id] = proposal
    state["research_proposals"] = proposals
    save_state(inbox_dir, state)
    return proposal
