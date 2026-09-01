"""AI-Assisted Report Builder V1 -- grounded section synthesis.

The model receives ONLY a compact digest of the bounded intelligence
packet (id/type/title/date/trust per item) -- never unrestricted
repository access, never the full packet, never prior report text. Every
section's returned citation_ids are validated against the packet's own
known_ids before anything is rendered or persisted; an invalid,
missing, or absent citation degrades that section to the fixed phrase
"Insufficient sourced intelligence." rather than presenting an
ungrounded claim.

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
        ("signals", "Signals", ("signal_count",), True),
        ("assessments", "Assessments / Strategic Implications", ("assessment_count",), True),
        ("known_gaps", "Known Gaps", (), False),
        ("sources", "Sources", (), False),
    ],
    "variety_genetics_landscape": [
        ("executive_summary", "Executive Summary", (), True),
        ("scope_method", "Scope & Method", (), False),
        ("variety_landscape", "Variety / Genetics Landscape", ("trusted_variety_count", "variety_candidate_count"), True),
        ("recent_developments", "Recent Developments", ("evidence_count",), True),
        ("signals", "Signals", ("signal_count",), True),
        ("assessments", "Assessments / Strategic Implications", ("assessment_count",), True),
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
        ("signals", "Signals", ("signal_count",), True),
        ("assessments", "Assessments / Strategic Implications", ("assessment_count",), True),
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
        ("what_we_know", "What We Know", ("fact_count", "evidence_count"), True),
        ("signals", "Signals", ("signal_count",), True),
        ("assessments", "Assessments", ("assessment_count",), True),
        ("tensions", "Tensions / Counterevidence", (), False),
        ("gaps", "Intelligence Gaps", (), False),
        ("implications", "Implications", ("assessment_count",), True),
        ("sources", "Sources", (), False),
    ],
}

STRUCTURED_SECTIONS = {"scope_method", "known_gaps", "sources", "comparison_table", "question", "tensions", "gaps", "evidence_appendix"}

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


def _digest_line(item: dict[str, Any]) -> str | None:
    item_id = item.get("id")
    if not item_id:
        return None
    parts = [str(item_id)]
    for key in ("title", "name", "statement", "observation", "rationale", "date", "status", "confidence", "trust"):
        value = item.get(key)
        if value:
            parts.append(str(value)[:160])
    return " | ".join(parts)


def _grounding_digest(packet: dict[str, Any], section_id: str) -> list[str]:
    """Compact, id-tagged fact lines for one section -- the ONLY packet
    content ever sent to the model. Which packet buckets feed a section is
    fixed here, not inferred by the model."""
    buckets: dict[str, list[str]] = {
        "market_context": ["recent_developments", "companies"],
        "key_actors": ["companies"],
        "variety_landscape": ["varieties", "variety_candidates"],
        "variety_genetics": ["varieties", "variety_candidates"],
        "recent_developments": ["recent_developments"],
        "recent_activity": ["recent_developments"],
        "signals": ["signals"],
        "assessments": ["assessments"],
        "company_profiles": ["companies"],
        "differences": ["companies", "varieties"],
        "what_we_know": [],  # strategic question packet shape, handled by caller
        "implications": [],
        "executive_summary": ["companies", "varieties", "recent_developments", "signals", "assessments"],
    }
    lines: list[str] = []
    if packet.get("strategic_question") is not None:
        sq = packet["strategic_question"]
        if section_id in {"what_we_know", "executive_summary"}:
            for f in sq.get("facts") or []:
                lines.append(f"{f['id']} | {f.get('statement','')[:200]}")
        if section_id in {"signals", "executive_summary"}:
            for s in sq.get("signals") or []:
                lines.append(f"{s['id']} | {s.get('title','')} | {s.get('observation','')[:160]}")
        if section_id in {"assessments", "implications", "executive_summary"}:
            for a in sq.get("assessments") or []:
                lines.append(f"{a['id']} | {a.get('title','')} | {a.get('rationale','')[:200]}")
        return lines[:40]

    for bucket in buckets.get(section_id, []):
        for item in packet.get(bucket) or []:
            line = _digest_line(item)
            if line:
                lines.append(line)
    return lines[:40]


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
            drafts.append(SectionDraft(section_id, title, "", (), "structured", None, None))
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
