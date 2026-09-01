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
deterministic interpreter still proposes a phrase-aware report_type
and extracts explicit known Company/Variety/Geography names and aliases
from the request text. AI, when present, may add nuance, but a
reconciliation pass keeps obvious canonical mentions that the provider
omitted. Missing PERPLEXITY_API_KEY never blocks the feature.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.ai_gateway.untrusted_complete import UntrustedJsonResult
from app.services.berries.geography import REGIONS, geography_region
from app.services.geography_hierarchy import geography_descendants
from app.services.global_search import _fold, _names_for_entity

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


_SQ_HINTS = ("strategic question", "sq-")
_COMPARISON_RE = re.compile(r"\b(compare|comparing|comparison|versus|vs\.?)\b", re.IGNORECASE)
_MARKET_PHRASES = ("market report", "market landscape", "market overview")
_COMPETITIVE_PHRASES = ("competitive landscape", "competitor landscape")
_VARIETY_PHRASES = ("variety landscape", "genetics landscape", "cultivar landscape")
_LIST_SPLIT_RE = re.compile(r"\s*(?:,|;|\band\b|&|versus|\bvs\.?)\s+", re.IGNORECASE)
_TRAILING_SCOPE_RE = re.compile(
    r"\s+(?:in|for|across|within)\s+(?:the\s+)?(.+)$",
    re.IGNORECASE,
)
_US_GEO_RE = re.compile(r"\b(u\.?\s*s\.?a?\.?)\b", re.IGNORECASE)
_SKIP_NAME_FOLDS = frozenset(
    {
        "report",
        "market",
        "landscape",
        "competitive",
        "competitor",
        "compare",
        "comparison",
        "versus",
        "vs",
        "variety",
        "varieties",
        "genetics",
        "cultivar",
        "cultivars",
        "breeding",
        "overview",
        "blueberry",
        "strawberry",
        "raspberry",
        "blackberry",
        "company",
        "companies",
        "and",
        "the",
        "for",
        "in",
        "on",
        "of",
        "a",
        "an",
        "me",
        "build",
        "give",
        "europe",
        "americas",
        "oceania",
        "asia",
    }
)
_MIN_NAME_FOLD = 3


def _guess_report_type(text: str) -> str:
    """Phrase-aware deterministic type. A generic token such as
    ``genetics`` must not override ``competitive landscape``."""
    lowered = text.casefold()
    if _COMPARISON_RE.search(text):
        return "competitor_comparison"
    if any(phrase in lowered for phrase in _COMPETITIVE_PHRASES):
        return "competitive_landscape"
    if any(phrase in lowered for phrase in _MARKET_PHRASES):
        return "market_landscape"
    if any(phrase in lowered for phrase in _VARIETY_PHRASES):
        return "variety_genetics_landscape"
    if any(hint in lowered for hint in _SQ_HINTS):
        return "strategic_question_brief"
    if "competitive" in lowered or "competitor" in lowered:
        return "competitive_landscape"
    return "market_landscape"


def _berry_from_text(text: str, berries: dict[str, str]) -> str:
    lowered = text.casefold()
    for berry_id, label in berries.items():
        if label.casefold() in lowered or berry_id.removeprefix("berry-") in lowered:
            return label
    return ""


def _already_represented(folded: str, kept: set[str]) -> bool:
    if folded in kept:
        return True
    for item in kept:
        if item.startswith(folded + " ") or folded.startswith(item + " "):
            return True
        if folded in item.split():
            return True
    return False


def _merge_name_tuples(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """Prefer longer known aliases; drop compare-list fragments they cover."""
    ranked = sorted(
        (str(raw).strip() for group in groups for raw in group if str(raw).strip()),
        key=lambda query: (len(_fold(query).split()), len(_fold(query))),
        reverse=True,
    )
    kept: set[str] = set()
    out: list[str] = []
    for query in ranked:
        folded = _fold(query)
        if not folded or _already_represented(folded, kept):
            continue
        kept.add(folded)
        out.append(query)
    return tuple(out)


def _name_phrase_index(
    entities: list[dict[str, Any]], entity_type: str
) -> list[tuple[str, str, tuple[str, ...]]]:
    """(folded_phrase, surface, entity_ids) longest-first. Same folded
    phrase hitting more than one id stays together so callers can mark
    ambiguous instead of first-match."""
    buckets: dict[str, dict[str, Any]] = {}
    for entity in entities:
        if entity.get("entity_type") != entity_type or not entity.get("id"):
            continue
        entity_id = str(entity["id"])
        canonical, aliases = _names_for_entity(entity)
        for surface in (canonical, *aliases):
            folded = _fold(surface)
            if len(folded) < _MIN_NAME_FOLD or folded in _SKIP_NAME_FOLDS:
                continue
            bucket = buckets.setdefault(folded, {"surface": surface, "ids": set()})
            bucket["ids"].add(entity_id)
            if len(surface) > len(bucket["surface"]):
                bucket["surface"] = surface
    phrases = [
        (folded, row["surface"], tuple(sorted(row["ids"])))
        for folded, row in buckets.items()
    ]
    phrases.sort(key=lambda row: (len(row[0].split()), len(row[0])), reverse=True)
    return phrases


def _scan_known_phrases(text: str, phrases: list[tuple[str, str, tuple[str, ...]]]) -> tuple[str, ...]:
    tokens = _fold(text).split()
    if not tokens:
        return ()
    consumed = [False] * len(tokens)
    found: list[str] = []
    seen: set[str] = set()
    for folded, surface, _ids in phrases:
        ptoks = folded.split()
        width = len(ptoks)
        if width == 0 or width > len(tokens):
            continue
        index = 0
        while index <= len(tokens) - width:
            window = slice(index, index + width)
            if not any(consumed[window]) and tokens[window] == ptoks:
                if folded not in seen:
                    found.append(surface)
                    seen.add(folded)
                for pos in range(index, index + width):
                    consumed[pos] = True
                index += width
            else:
                index += 1
    return tuple(found)


def _split_compare_names(blob: str) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for part in _LIST_SPLIT_RE.split(blob):
        query = part.strip(" .;:")
        folded = _fold(query)
        if not query or len(folded) < _MIN_NAME_FOLD or folded in _SKIP_NAME_FOLDS or folded in seen:
            continue
        seen.add(folded)
        names.append(query)
    return tuple(names)


def _comparison_name_list(text: str) -> tuple[str, ...]:
    """Comma/and lists after compare/versus. Unknown items stay as text."""
    match = re.search(r"\b(?:compare|comparing|comparison of)\s+(.+)$", text, re.IGNORECASE)
    blob = ""
    if match:
        blob = match.group(1)
    else:
        versus = re.search(r"(.+?)\s+(?:versus|\bvs\.?)\s+(.+)$", text, re.IGNORECASE)
        if versus:
            blob = f"{versus.group(1)}, {versus.group(2)}"
    if not blob:
        return ()
    geo_tail = _TRAILING_SCOPE_RE.search(blob)
    if geo_tail:
        blob = blob[: geo_tail.start()]
    return _split_compare_names(blob)


def _geography_from_text(text: str, *, entities: list[dict[str, Any]] | None) -> str:
    """Exact region label, canonical Geography name/alias, or an honest
    U.S. surface. Never expands a region into member countries."""
    folded = _fold(text)
    tokens = folded.split()
    region_hits = [region for region in REGIONS if _fold(region) and _fold(region) in folded]
    geo_hits: list[str] = []
    if entities:
        phrases = _name_phrase_index(entities, "geography")
        geo_hits = list(_scan_known_phrases(text, phrases))
    if geo_hits:
        return geo_hits[0]
    if region_hits:
        return max(region_hits, key=lambda row: len(_fold(row)))
    us_match = _US_GEO_RE.search(text)
    if us_match and "united states" not in folded:
        return us_match.group(1)
    if tokens and "united states" in folded:
        return "United States"
    return ""


def extract_known_mentions(
    text: str,
    *,
    berries: dict[str, str],
    entities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deterministic mentions from analyst text. Exact folded name/alias
    only -- no fuzzy resolution, no candidate Varieties."""
    rows = [row for row in (entities or []) if row.get("entity_type") in {"company", "variety", "geography"}]
    companies = _merge_name_tuples(
        _scan_known_phrases(text, _name_phrase_index(rows, "company")),
        _comparison_name_list(text),
    )
    varieties = _scan_known_phrases(text, _name_phrase_index(rows, "variety"))
    return {
        "berry_text": _berry_from_text(text, berries),
        "geography_text": _geography_from_text(text, entities=rows),
        "company_names": companies,
        "variety_names": varieties,
    }


def _keyword_fallback_proposal(
    text: str,
    *,
    berries: dict[str, str],
    entities: list[dict[str, Any]] | None = None,
) -> ScopeProposal:
    """Deterministic interpretation when no AI credential is available."""
    extracted = extract_known_mentions(text, berries=berries, entities=entities)
    return ScopeProposal(
        report_type=_guess_report_type(text),
        berry_text=extracted["berry_text"],
        geography_text=extracted["geography_text"],
        company_names=extracted["company_names"],
        variety_names=extracted["variety_names"],
        strategic_question_text="",
        date_window_days=None,
        focus_notes="",
        source="keyword_fallback",
    )


def _reconcile_with_canonical_mentions(
    proposal: ScopeProposal,
    text: str,
    *,
    berries: dict[str, str],
    entities: list[dict[str, Any]] | None,
) -> ScopeProposal:
    """Keep AI report_type; fill in obvious canonical names the provider dropped."""
    extracted = extract_known_mentions(text, berries=berries, entities=entities)
    return ScopeProposal(
        report_type=proposal.report_type,
        berry_text=proposal.berry_text or extracted["berry_text"],
        geography_text=proposal.geography_text or extracted["geography_text"],
        company_names=_merge_name_tuples(proposal.company_names, extracted["company_names"]),
        variety_names=_merge_name_tuples(proposal.variety_names, extracted["variety_names"]),
        strategic_question_text=proposal.strategic_question_text,
        date_window_days=proposal.date_window_days,
        focus_notes=proposal.focus_notes,
        source=proposal.source,
    )


def interpret_scope_text(
    text: str,
    *,
    berries: dict[str, str],
    completer: Callable[..., UntrustedJsonResult] | None,
    entities: list[dict[str, Any]] | None = None,
    model: str = "anthropic/claude-haiku-4-5",
) -> ScopeProposal:
    """Propose a structured scope from natural language. `completer` is
    typically `app.services.ai_gateway.untrusted_complete.maybe_untrusted_completer()`
    -- pass None explicitly to force the deterministic fallback (used by
    tests, and automatically the case whenever no provider credential is
    configured). `entities` is the trusted catalog used for exact
    name/alias extraction; inbox Variety candidates are never passed in."""
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
        return _keyword_fallback_proposal(text, berries=berries, entities=entities)
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
        return _keyword_fallback_proposal(text, berries=berries, entities=entities)
    parsed = result.parsed
    report_type = parsed.get("report_type") if parsed.get("report_type") in REPORT_TYPES else _guess_report_type(text)
    proposal = ScopeProposal(
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
    return _reconcile_with_canonical_mentions(proposal, text, berries=berries, entities=entities)


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
    selected_id: str | None = None
    descendant_ids: tuple[str, ...] = ()


def resolve_geography_text(
    text: str,
    *,
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
) -> GeographyResolution | None:
    """A geography phrase resolves one of two honest ways: an exact match
    against one canonical Geography entity (matched_as="single" --
    expanded to include every canonical descendant via stored "part_of"
    Relationship records, e.g. Europe -> Spain/Portugal/UK/Germany/
    Netherlands, resolved once here rather than per record), or an exact
    match against one of the five fixed region labels in
    app.services.berries.geography.REGIONS, expanded to every geography
    entity carrying that free-text label (matched_as="region" -- the
    pre-hierarchy fallback, kept only for labels with no canonical
    entity match, e.g. "Latin America"). Anything else is "unresolved"
    -- never a partial/fuzzy geographic guess. A geography with no
    stored descendants (most of the corpus today) resolves exactly as
    before -- fully backward compatible."""
    query = (text or "").strip()
    if not query:
        return None
    folded_query = _fold(query)
    for entity in entities:
        if entity.get("entity_type") != "geography":
            continue
        canonical, aliases = _names_for_entity(entity)
        if folded_query == _fold(canonical) or folded_query in {_fold(a) for a in aliases}:
            selected_id = str(entity["id"])
            descendants = tuple(sorted(geography_descendants(selected_id, relationships=relationships or [])))
            geo_ids = tuple(dict.fromkeys([selected_id, *descendants]))
            return GeographyResolution(
                query=query, geography_ids=geo_ids, matched_as="single",
                selected_id=selected_id, descendant_ids=descendants,
            )
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
    geography_descendant_ids: tuple[str, ...] = ()


def resolve_scope(
    proposal: ScopeProposal,
    *,
    entities: list[dict[str, Any]],
    berries: dict[str, str],
    questions: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
) -> ResolvedScope:
    berry_id = None
    if proposal.berry_text:
        folded = _fold(proposal.berry_text)
        for bid, label in berries.items():
            if _fold(label) == folded or _fold(bid.removeprefix("berry-")) == folded:
                berry_id = bid
                break

    geo = resolve_geography_text(proposal.geography_text, entities=entities, relationships=relationships)
    geography_ids = geo.geography_ids if geo else ()
    geography_unresolved = bool(geo and geo.matched_as == "unresolved")
    geography_descendant_ids = geo.descendant_ids if geo else ()

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
        geography_descendant_ids=geography_descendant_ids,
    )
