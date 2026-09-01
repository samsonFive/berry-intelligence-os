"""AI-Assisted Report Builder V1 -- scope interpretation.

Turns a natural-language report request into a STRUCTURED SCOPE
PROPOSAL, then resolves every named Company/Variety/Geography against
canonical entities deterministically. An AI provider (when a credential
is configured) only ever proposes free-text guesses -- report_type, a
berry guess, a geography phrase, raw company/variety name strings, a
possible Strategic Question match, and a date window. It never emits a
canonical id itself. All id resolution happens here, via exact/alias
matching against real entities (reusing app.services.global_search's
alias index), so an unresolved or ambiguous name is always surfaced to
the analyst for explicit confirmation rather than silently guessed --
the same discipline AGENTS.md already requires for berry/scope
inference elsewhere ("Do not infer berry from title, rationale, or
company names").

Works with or without an AI provider credential: without one, a
deterministic keyword-based interpreter still proposes a report_type
and extracts obvious company/variety mentions by substring match against
known canonical names, so the feature is never blocked on a missing
PERPLEXITY_API_KEY -- it just skips the free-text nuance a model adds
for things like "Europe" -> geography phrasing or an implied date
window.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.ai_gateway.untrusted_complete import UntrustedJsonResult
from app.services.berries.geography import REGIONS, geography_region
from app.services.global_search import _fold, _names_for_entity
from app.services.variety_workspace import identity_fields

REPORT_TYPES = (
    "market_landscape",
    "competitive_landscape",
    "competitor_comparison",
    "variety_genetics_landscape",
    "strategic_question_brief",
)
REPORT_TYPE_LABELS = {
    "market_landscape": "Market Landscape",
    "competitive_landscape": "Competitive Landscape",
    "competitor_comparison": "Competitor Comparison",
    "variety_genetics_landscape": "Variety / Genetics Landscape",
    "strategic_question_brief": "Strategic Question Brief",
}

_INTERPRET_SCHEMA = {
    "type": "object",
    "properties": {
        "report_type": {"type": "string", "enum": list(REPORT_TYPES)},
        "berry_text": {"type": "string"},
        "geography_text": {"type": "string"},
        "company_names": {"type": "array", "items": {"type": "string"}},
        "variety_names": {"type": "array", "items": {"type": "string"}},
        "strategic_question_text": {"type": "string"},
        "date_window_days": {"type": ["integer", "null"]},
        "focus_notes": {"type": "string"},
    },
    "required": [
        "report_type",
        "berry_text",
        "geography_text",
        "company_names",
        "variety_names",
        "strategic_question_text",
        "date_window_days",
        "focus_notes",
    ],
    "additionalProperties": False,
}

_INTERPRET_INSTRUCTIONS = (
    "You are a strict, literal report-scope parser for a competitive-intelligence "
    "tool. Read the analyst's request and propose a structured scope. Never invent "
    "a company, variety, berry, or geography that is not stated or clearly implied "
    "in the request text -- if the request does not mention something, leave that "
    "field empty. You are NOT resolving names to any database id; just return the "
    "plain text the analyst used, exactly as written, so a separate deterministic "
    "step can match it against real records. Do not fabricate a Strategic Question "
    "id or wording that was not given."
)


@dataclass(frozen=True)
class ScopeProposal:
    report_type: str
    berry_text: str
    geography_text: str
    company_names: tuple[str, ...]
    variety_names: tuple[str, ...]
    strategic_question_text: str
    date_window_days: int | None
    focus_notes: str
    source: str  # "ai" | "keyword_fallback"


_COMPARISON_HINTS = ("compare", " vs ", " versus ", "comparison")
_SQ_HINTS = ("strategic question", "sq-")
_VARIETY_HINTS = ("variety", "genetics", "cultivar", "breeding")


def _guess_report_type(text: str) -> str:
    lowered = text.casefold()
    if any(hint in lowered for hint in _SQ_HINTS):
        return "strategic_question_brief"
    if any(hint in lowered for hint in _COMPARISON_HINTS):
        return "competitor_comparison"
    if any(hint in lowered for hint in _VARIETY_HINTS):
        return "variety_genetics_landscape"
    if "competitive" in lowered or "competitor" in lowered:
        return "competitive_landscape"
    return "market_landscape"


def _keyword_fallback_proposal(text: str, *, berries: dict[str, str]) -> ScopeProposal:
    """Deterministic, no-AI-required interpretation: proposes a report_type
    by simple keyword match and a berry by substring match against known
    berry labels. Company/variety/geography text extraction is left blank
    here -- the analyst fills those in on the scope-confirmation screen --
    rather than attempting fragile NL entity extraction without a model."""
    lowered = text.casefold()
    berry_text = ""
    for berry_id, label in berries.items():
        if label.casefold() in lowered or berry_id.removeprefix("berry-") in lowered:
            berry_text = label
            break
    return ScopeProposal(
        report_type=_guess_report_type(text),
        berry_text=berry_text,
        geography_text="",
        company_names=(),
        variety_names=(),
        strategic_question_text="",
        date_window_days=None,
        focus_notes="",
        source="keyword_fallback",
    )


def interpret_scope_text(
    text: str,
    *,
    berries: dict[str, str],
    completer: Callable[..., UntrustedJsonResult] | None,
    model: str = "anthropic/claude-haiku-4-5",
) -> ScopeProposal:
    """Propose a structured scope from natural language. `completer` is
    typically `app.services.ai_gateway.untrusted_complete.maybe_untrusted_completer()`
    -- pass None explicitly to force the deterministic fallback (used by
    tests, and automatically the case whenever no provider credential is
    configured)."""
    text = (text or "").strip()
    if not text:
        return ScopeProposal(
            report_type="market_landscape",
            berry_text="",
            geography_text="",
            company_names=(),
            variety_names=(),
            strategic_question_text="",
            date_window_days=None,
            focus_notes="",
            source="keyword_fallback",
        )
    if completer is None:
        return _keyword_fallback_proposal(text, berries=berries)
    try:
        result = completer(
            f"{_INTERPRET_INSTRUCTIONS}\n\nAnalyst request:\n{text}",
            schema=_INTERPRET_SCHEMA,
            model=model,
            max_output_tokens=500,
        )
    except Exception:
        # Any provider failure degrades to the deterministic fallback --
        # scope interpretation must never hard-fail the workspace.
        return _keyword_fallback_proposal(text, berries=berries)
    parsed = result.parsed
    report_type = parsed.get("report_type") if parsed.get("report_type") in REPORT_TYPES else _guess_report_type(text)
    return ScopeProposal(
        report_type=report_type,
        berry_text=str(parsed.get("berry_text") or ""),
        geography_text=str(parsed.get("geography_text") or ""),
        company_names=tuple(str(v) for v in (parsed.get("company_names") or []) if str(v).strip()),
        variety_names=tuple(str(v) for v in (parsed.get("variety_names") or []) if str(v).strip()),
        strategic_question_text=str(parsed.get("strategic_question_text") or ""),
        date_window_days=parsed.get("date_window_days") if isinstance(parsed.get("date_window_days"), int) else None,
        focus_notes=str(parsed.get("focus_notes") or ""),
        source="ai",
    )


@dataclass(frozen=True)
class NameResolution:
    query: str
    resolved_id: str | None
    resolved_name: str | None
    ambiguous_ids: tuple[str, ...] = ()


def _entity_name_index(entities: list[dict[str, Any]], entity_type: str) -> list[tuple[str, str, tuple[str, ...]]]:
    """[(entity_id, folded_canonical, folded_aliases)] for every entity of
    one type -- reuses global_search's own alias derivation (identical
    logic Global Search uses for the same entities) rather than a second,
    possibly-diverging name index."""
    index = []
    for entity in entities:
        if entity.get("entity_type") != entity_type or not entity.get("id"):
            continue
        canonical, aliases = _names_for_entity(entity)
        index.append((str(entity["id"]), _fold(canonical), tuple(_fold(a) for a in aliases if a)))
    return index


def resolve_entity_names(
    names: list[str],
    *,
    entities: list[dict[str, Any]],
    entity_type: str,
) -> list[NameResolution]:
    """Exact folded-name/alias match only -- no fuzzy scoring. A name that
    matches more than one canonical entity is returned ambiguous (never
    auto-picked); a name matching zero entities is returned unresolved.
    This mirrors Global Search's own exact-match tier (RANK_EXACT_CANONICAL/
    RANK_EXACT_ALIAS in app.services.global_search), just without the
    weaker text-substring tiers search also offers -- a report scope
    should not silently include an entity that only loosely matched."""
    index = _entity_name_index(entities, entity_type)
    results: list[NameResolution] = []
    for raw_name in names:
        query = raw_name.strip()
        if not query:
            continue
        folded_query = _fold(query)
        hits = [eid for eid, canonical, aliases in index if folded_query == canonical or folded_query in aliases]
        if len(hits) == 1:
            entity = next(e for e in entities if e.get("id") == hits[0])
            results.append(NameResolution(query=query, resolved_id=hits[0], resolved_name=entity.get("name") or hits[0]))
        elif len(hits) > 1:
            results.append(NameResolution(query=query, resolved_id=None, resolved_name=None, ambiguous_ids=tuple(hits)))
        else:
            results.append(NameResolution(query=query, resolved_id=None, resolved_name=None))
    return results


def _region_reverse_index(entities: list[dict[str, Any]]) -> dict[str, list[str]]:
    """region label (folded) -> [geography entity ids]. Built on demand from
    geography_region() rather than stored anywhere, since geography.py's
    own region table is intentionally one-directional (country -> region)."""
    index: dict[str, list[str]] = {}
    for entity in entities:
        if entity.get("entity_type") != "geography" or not entity.get("id"):
            continue
        region = geography_region(entity)
        if region:
            index.setdefault(_fold(region), []).append(str(entity["id"]))
    return index


@dataclass(frozen=True)
class GeographyResolution:
    query: str
    geography_ids: tuple[str, ...]
    matched_as: str  # "single" | "region" | "unresolved"


def resolve_geography_text(text: str, *, entities: list[dict[str, Any]]) -> GeographyResolution | None:
    """A geography phrase resolves one of two honest ways: an exact match
    against one canonical Geography entity (matched_as="single"), or an
    exact match against one of the five fixed region labels in
    app.services.berries.geography.REGIONS, expanded to every geography
    entity in that region (matched_as="region"). Anything else is
    "unresolved" -- never a partial/fuzzy geographic guess."""
    query = (text or "").strip()
    if not query:
        return None
    folded_query = _fold(query)
    for entity in entities:
        if entity.get("entity_type") != "geography":
            continue
        canonical, aliases = _names_for_entity(entity)
        if folded_query == _fold(canonical) or folded_query in {_fold(a) for a in aliases}:
            return GeographyResolution(query=query, geography_ids=(str(entity["id"]),), matched_as="single")
    for region in REGIONS:
        if _fold(region) == folded_query:
            ids = _region_reverse_index(entities).get(folded_query, [])
            return GeographyResolution(query=query, geography_ids=tuple(ids), matched_as="region")
    return GeographyResolution(query=query, geography_ids=(), matched_as="unresolved")


def resolve_strategic_question_text(text: str, *, questions: list[dict[str, Any]]) -> NameResolution | None:
    query = (text or "").strip()
    if not query:
        return None
    folded_query = _fold(query)
    hits = [
        q["id"]
        for q in questions
        if q.get("id") and (_fold(str(q.get("title") or "")) == folded_query or folded_query in _fold(str(q.get("title") or "")))
    ]
    if len(hits) == 1:
        title = next(q.get("title") for q in questions if q.get("id") == hits[0])
        return NameResolution(query=query, resolved_id=hits[0], resolved_name=title)
    if len(hits) > 1:
        return NameResolution(query=query, resolved_id=None, resolved_name=None, ambiguous_ids=tuple(hits))
    return NameResolution(query=query, resolved_id=None, resolved_name=None)


@dataclass(frozen=True)
class ResolvedScope:
    report_type: str
    berry_id: str | None
    geography_ids: tuple[str, ...]
    company_ids: tuple[str, ...]
    variety_ids: tuple[str, ...]
    strategic_question_id: str | None
    date_window_days: int | None
    focus_notes: str
    # Everything the analyst must confirm/fix before generation -- never
    # silently dropped.
    unresolved_companies: tuple[str, ...] = ()
    unresolved_varieties: tuple[str, ...] = ()
    ambiguous_companies: tuple[NameResolution, ...] = ()
    ambiguous_varieties: tuple[NameResolution, ...] = ()
    geography_text: str = ""
    geography_unresolved: bool = False


def resolve_scope(
    proposal: ScopeProposal,
    *,
    entities: list[dict[str, Any]],
    berries: dict[str, str],
    questions: list[dict[str, Any]],
) -> ResolvedScope:
    berry_id = None
    if proposal.berry_text:
        folded = _fold(proposal.berry_text)
        for bid, label in berries.items():
            if _fold(label) == folded or _fold(bid.removeprefix("berry-")) == folded:
                berry_id = bid
                break

    geo = resolve_geography_text(proposal.geography_text, entities=entities)
    geography_ids = geo.geography_ids if geo else ()
    geography_unresolved = bool(geo and geo.matched_as == "unresolved")

    company_res = resolve_entity_names(list(proposal.company_names), entities=entities, entity_type="company")
    variety_res = resolve_entity_names(list(proposal.variety_names), entities=entities, entity_type="variety")

    sq_res = resolve_strategic_question_text(proposal.strategic_question_text, questions=questions)

    return ResolvedScope(
        report_type=proposal.report_type,
        berry_id=berry_id,
        geography_ids=geography_ids,
        company_ids=tuple(r.resolved_id for r in company_res if r.resolved_id),
        variety_ids=tuple(r.resolved_id for r in variety_res if r.resolved_id),
        strategic_question_id=sq_res.resolved_id if sq_res else None,
        date_window_days=proposal.date_window_days,
        focus_notes=proposal.focus_notes,
        unresolved_companies=tuple(r.query for r in company_res if not r.resolved_id and not r.ambiguous_ids),
        unresolved_varieties=tuple(r.query for r in variety_res if not r.resolved_id and not r.ambiguous_ids),
        ambiguous_companies=tuple(r for r in company_res if r.ambiguous_ids),
        ambiguous_varieties=tuple(r for r in variety_res if r.ambiguous_ids),
        geography_text=proposal.geography_text,
        geography_unresolved=geography_unresolved,
    )
