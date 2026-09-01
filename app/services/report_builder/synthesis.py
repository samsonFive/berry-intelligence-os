"""AI-Assisted Report Builder V1 -- grounded section synthesis.

PROVIDER SECURITY BOUNDARY (do not weaken without explicit, separate
authorization -- see docs/v2 Report Builder closure mission notes):
the model NEVER receives Assessment rationale/why_it_matters, Signal
observation/why_it_might_matter, Fact statement text, report prose
(generated or analyst-edited), or any Evidence field beyond
id/title/source_name/date. Those are this system's own proprietary
analytical judgments and internal notes, not public source material,
and must never leave the process boundary to a third-party AI provider
-- even for "grounded" synthesis. Only two kinds of content are ever
sent: (1) Evidence title/source_name/date (this system's own trust
model already requires published Evidence to be sourced from public
trade press/patent/registry material -- see app/services/chronology.py
and the Evidence schema), and (2) Company/Variety/Variety-candidate
NAMES (public labels, the same names already shown on this system's own
public entity pages). `_public_evidence_line()`/`_public_entity_line()`
are the only two formatters allowed to build a digest line, and
`_grounding_digest()` is the only place allowed to call them -- there is
no other path from a packet into a prompt string in this module.

Consequently, Signals, Assessments, and Strategic-Question Facts/
Assessments are never narrated by the model: those sections render
deterministically instead (see `_structured_prose()`), listing the
same id/title/date/status metadata already visible elsewhere on this
system's own trusted pages, with no free-text analytical content
transmitted anywhere.

Every section's returned citation_ids are validated against the
packet's own known_ids before anything is rendered or persisted; an
invalid, missing, or absent citation degrades that section to the
fixed phrase "Insufficient sourced intelligence." rather than
presenting an ungrounded claim.

Generated prose is REPORT OUTPUT, never canonical intelligence: nothing
in this module writes Evidence, Signal, Assessment, Strategic Question,
or trusted Variety data, and a section's prose is stored on the report
record only, never fed back into the trust repositories.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services.ai_gateway.untrusted_complete import UntrustedJsonResult
from app.services.report_builder.coverage import report_coverage

INSUFFICIENT = "Insufficient sourced intelligence."

UNAVAILABLE = (
    "AI draft unavailable -- no provider credential configured for this environment. "
    "Add source material and write this section manually."
)

# section_id -> (title, coverage keys that must have at least one item for
# an AI draft to be attempted at all; empty tuple = always attempt when any
# grounding exists in the packet as a whole).
SECTION_DEFS: dict[str, list[tuple[str, str, tuple[str, ...], bool]]] = {
    "market_landscape": [
        ("executive_summary", "Executive Summary", (), True),
        ("scope_method", "Scope & Method", (), False),
        ("market_context", "Market / Competitive Context", ("evidence_count",), True),
        ("variety_landscape", "Variety / Genetics Landscape", ("trusted_variety_count", "variety_candidate_count"), True),
        ("recent_developments", "Recent Developments", ("evidence_count",), True),
        ("signals", "Signals", ("signal_count",), False),
        ("assessments", "Assessments / Strategic Implications", ("assessment_count",), False),
        ("known_gaps", "Known Gaps", (), False),
        ("sources", "Sources", (), False),
    ],
    "variety_genetics_landscape": [
        ("executive_summary", "Executive Summary", (), True),
        ("scope_method", "Scope & Method", (), False),
        ("variety_landscape", "Variety / Genetics Landscape", ("trusted_variety_count", "variety_candidate_count"), True),
        ("recent_developments", "Recent Developments", ("evidence_count",), True),
        ("signals", "Signals", ("signal_count",), False),
        ("assessments", "Assessments / Strategic Implications", ("assessment_count",), False),
        ("known_gaps", "Known Gaps", (), False),
        ("sources", "Sources", (), False),
    ],
    "competitive_landscape": [
        ("executive_summary", "Executive Summary", (), True),
        ("scope_method", "Scope & Method", (), False),
        ("market_context", "Market / Competitive Context", ("evidence_count",), True),
        ("key_actors", "Key Actors", ("company_count",), True),
        ("variety_landscape", "Variety / Genetics Landscape", ("trusted_variety_count", "variety_candidate_count"), True),
        ("recent_developments", "Recent Developments", ("evidence_count",), True),
        ("signals", "Signals", ("signal_count",), False),
        ("assessments", "Assessments / Strategic Implications", ("assessment_count",), False),
        ("known_gaps", "Known Gaps", (), False),
        ("sources", "Sources", (), False),
    ],
    "competitor_comparison": [
        ("executive_summary", "Executive Summary", (), True),
        ("comparison_scope", "Comparison Scope", (), False),
        ("comparison_table", "Comparison Table", (), False),
        ("company_profiles", "Company-by-Company Profiles", ("company_count",), True),
        ("variety_genetics", "Variety / Genetics Positions", ("trusted_variety_count", "variety_candidate_count"), True),
        ("recent_activity", "Recent Activity", ("evidence_count",), True),
        ("differences", "Key Similarities / Differences", ("company_count",), True),
        ("evidence_appendix", "Evidence Appendix", (), False),
    ],
    "strategic_question_brief": [
        ("question", "Question", (), False),
        ("what_we_know", "What We Know", ("fact_count", "evidence_count"), False),
        ("signals", "Signals", ("signal_count",), False),
        ("assessments", "Assessments", ("assessment_count",), False),
        ("tensions", "Tensions / Counterevidence", (), False),
        ("gaps", "Intelligence Gaps", (), False),
        ("implications", "Implications", ("assessment_count",), False),
        ("sources", "Sources", (), False),
    ],
}

# Every section here renders deterministically from packet/coverage data --
# never sent to, or narrated by, an AI provider. Signals/Assessments/
# Facts (and Strategic-Question "what_we_know"/"implications", which are
# Fact/Assessment-shaped) are here specifically because their substantive
# content is this system's own proprietary analysis (see module docstring).
STRUCTURED_SECTIONS = {
    "scope_method", "known_gaps", "sources", "comparison_table", "question",
    "tensions", "gaps", "evidence_appendix", "signals", "assessments",
    "what_we_know", "implications",
}

_SYNTH_SCHEMA = {
    "type": "object",
    "properties": {
        "prose": {"type": "string"},
        "citation_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["prose", "citation_ids"],
    "additionalProperties": False,
}

_SYNTH_INSTRUCTIONS = (
    "You are drafting one section of an internal competitive-intelligence report. "
    "You may state ONLY what is directly supported by the numbered facts below -- "
    "never add outside knowledge, never speculate beyond the given facts, and never "
    "invent a company, variety, date, or figure not present in them. Every citation_ids "
    "entry must be one of the ids listed with the facts. If the given facts do not "
    "support a substantive section, return an empty prose string and an empty "
    "citation_ids array rather than padding with generic language."
)


def _public_evidence_line(item: dict[str, Any]) -> str | None:
    """Evidence title/source_name/date only -- this system's own trust
    model already requires published Evidence to originate from public
    trade press/patent/registry material. Never the summary/why_it_
    matters/article body."""
    item_id = item.get("id")
    if not item_id:
        return None
    parts = [str(item_id)]
    for key in ("title", "source_name", "date"):
        value = item.get(key)
        if value:
            parts.append(str(value)[:160])
    return " | ".join(parts)


def _public_entity_line(item: dict[str, Any]) -> str | None:
    """A Company/Variety/Variety-candidate NAME only -- a public label
    already shown on this system's own public entity pages, never any
    free-text field."""
    item_id = item.get("id")
    if not item_id:
        return None
    name = item.get("name") or item.get("candidate_name") or ""
    return f"{item_id} | {name}"[:170] if name else str(item_id)


# section_id -> [(packet_bucket, line_formatter), ...]. This table is the
# only thing that decides what reaches _grounding_digest()'s output, and
# every formatter it references is one of the two safe functions above.
_DIGEST_SOURCES: dict[str, list[tuple[str, Any]]] = {
    "market_context": [("recent_developments", _public_evidence_line), ("companies", _public_entity_line)],
    "key_actors": [("companies", _public_entity_line)],
    "variety_landscape": [("varieties", _public_entity_line), ("variety_candidates", _public_entity_line)],
    "variety_genetics": [("varieties", _public_entity_line), ("variety_candidates", _public_entity_line)],
    "recent_developments": [("recent_developments", _public_evidence_line)],
    "recent_activity": [("recent_developments", _public_evidence_line)],
    "company_profiles": [("companies", _public_entity_line)],
    "differences": [("companies", _public_entity_line), ("varieties", _public_entity_line)],
    "executive_summary": [
        ("companies", _public_entity_line),
        ("varieties", _public_entity_line),
        ("recent_developments", _public_evidence_line),
    ],
}


def _grounding_digest(packet: dict[str, Any], section_id: str) -> list[str]:
    """Compact, id-tagged fact lines for one section -- the ONLY packet
    content ever sent to the model, and only ever Evidence title/source/
    date or Company/Variety names (see module docstring and
    _DIGEST_SOURCES). Strategic Question packets never reach this
    function at all -- every SQ-brief narrative section is structured."""
    lines: list[str] = []
    for bucket, formatter in _DIGEST_SOURCES.get(section_id, []):
        for item in packet.get(bucket) or []:
            line = formatter(item)
            if line:
                lines.append(line)
    return lines[:40]


def _human_join(labels: list[str]) -> str:
    return ", ".join(labels) if labels else ""


def _structured_prose(packet: dict[str, Any], coverage: dict[str, Any], section_id: str) -> str:
    """Deterministic rendering for every STRUCTURED_SECTIONS entry --
    never blank, never sent to or written by an AI provider. Signals/
    Assessments/Facts list only their own id/title/date/status metadata
    here, the same fields already visible on this system's own trusted
    pages; their rationale/observation/statement text is deliberately
    omitted (see module docstring)."""
    sq = packet.get("strategic_question")

    if section_id == "sources":
        rows = packet.get("source_trace") or (sq or {}).get("source_trace") or []
        return "\n".join(f"[{r.get('id')}] {r.get('title') or r.get('id')} — {r.get('source_name') or ''} ({r.get('date') or 'date unknown'})" for r in rows) or "No sourced Evidence in this packet."

    if section_id == "evidence_appendix":
        rows = packet.get("source_trace") or []
        return "\n".join(f"[{r.get('id')}] {r.get('title') or r.get('id')} — {r.get('source_name') or ''} ({r.get('date') or 'date unknown'})" for r in rows) or "No sourced Evidence in this packet."

    if section_id == "known_gaps" or section_id == "gaps":
        gaps = coverage.get("gaps") or []
        return "\n".join(f"- {g}" for g in gaps) or "No structural gaps identified for this scope."

    if section_id == "signals":
        rows = (sq or packet).get("signals") or []
        return "\n".join(f"[{r.get('id')}] {r.get('title') or r.get('id')} — {r.get('status') or 'status unstated'}" for r in rows) or "No Signals captured for this scope."

    if section_id == "assessments":
        rows = (sq or packet).get("assessments") or []
        return "\n".join(f"[{r.get('id')}] {r.get('title') or r.get('id')} — confidence {r.get('confidence') or 'unstated'}{' (AI proposed)' if r.get('ai_proposed') else ''}" for r in rows) or "No Assessments captured for this scope."

    if section_id == "what_we_know" and sq is not None:
        rows = sq.get("facts") or []
        return "\n".join(f"[{r.get('id')}] {r.get('classification') or 'fact'} — {r.get('event_date') or 'date unstated'}" for r in rows) or "No Facts established for this question yet."

    if section_id == "implications" and sq is not None:
        rows = sq.get("assessments") or []
        return "\n".join(f"[{r.get('id')}] {r.get('title') or r.get('id')} — confidence {r.get('confidence') or 'unstated'}" for r in rows) or "No analyst Assessment captured for this question yet."

    if section_id == "question" and sq is not None:
        return sq.get("title") or ""

    if section_id == "tensions" and sq is not None:
        lines = []
        for row in sq.get("assessment_counterevidence") or []:
            lines.append(f"{row.get('assessment_title')}: {len(row.get('counterevidence_items') or [])} counterevidence item(s)")
        for row in sq.get("evidence_contradictions") or []:
            lines.append(f"{row.get('evidence_title')} contradicts {row.get('target_title')}")
        return "\n".join(lines) or "No recorded tensions or counterevidence for this question."

    if section_id == "comparison_table":
        rows = packet.get("companies") or []
        return "\n".join(f"{r.get('name')} — {r.get('evidence_count', 0)} Evidence, {r.get('signal_count', 0)} Signals" for r in rows) or "No Companies resolved for this comparison."

    if section_id == "comparison_scope" or section_id == "scope_method":
        return f"Report type: {packet.get('report_type')}. Berry: {packet.get('berry_id') or 'not scoped'}."

    return ""


@dataclass(frozen=True)
class SectionDraft:
    section_id: str
    title: str
    prose: str
    citation_ids: tuple[str, ...]
    status: str  # "ai_draft" | "structured" | "unsupported" | "unavailable"
    provider: str | None
    model: str | None


def generate_report_sections(
    packet: dict[str, Any],
    *,
    report_type: str,
    completer: Callable[..., UntrustedJsonResult] | None,
    model: str = "anthropic/claude-haiku-4-5",
) -> list[SectionDraft]:
    coverage = report_coverage(packet)
    counts = coverage["counts"]
    known_ids = packet.get("known_ids") or set()
    section_defs = SECTION_DEFS.get(report_type, SECTION_DEFS["market_landscape"])

    drafts: list[SectionDraft] = []
    for section_id, title, required_counts, is_narrative in section_defs:
        if section_id in STRUCTURED_SECTIONS or not is_narrative:
            drafts.append(SectionDraft(section_id, title, _structured_prose(packet, coverage, section_id), (), "structured", None, None))
            continue

        if required_counts and not any(counts.get(key, 0) > 0 for key in required_counts):
            drafts.append(SectionDraft(section_id, title, INSUFFICIENT, (), "unsupported", None, None))
            continue

        if completer is None:
            drafts.append(SectionDraft(section_id, title, UNAVAILABLE, (), "unavailable", None, None))
            continue

        digest = _grounding_digest(packet, section_id)
        if not digest:
            drafts.append(SectionDraft(section_id, title, INSUFFICIENT, (), "unsupported", None, None))
            continue

        prompt = (
            f"{_SYNTH_INSTRUCTIONS}\n\nSection: {title}\n\nNumbered facts (id | fields):\n"
            + "\n".join(f"- {line}" for line in digest)
        )
        try:
            result = completer(prompt, schema=_SYNTH_SCHEMA, model=model, max_output_tokens=600)
        except Exception:
            drafts.append(SectionDraft(section_id, title, UNAVAILABLE, (), "unavailable", None, None))
            continue

        prose = str(result.parsed.get("prose") or "").strip()
        raw_citations = [str(c) for c in (result.parsed.get("citation_ids") or [])]
        valid_citations = tuple(c for c in raw_citations if c in known_ids)
        if not prose or not valid_citations:
            drafts.append(SectionDraft(section_id, title, INSUFFICIENT, (), "unsupported", result.provider, result.model))
            continue
        drafts.append(SectionDraft(section_id, title, prose, valid_citations, "ai_draft", result.provider, result.model))

    return drafts
