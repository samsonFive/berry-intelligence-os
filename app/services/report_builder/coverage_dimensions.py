"""Report Quality & Public Gap Research V1 -- deterministic per-dimension
coverage states.

Every dimension resolves to one of three explicit states -- AVAILABLE,
PARTIAL, or MISSING -- via a fixed rule this module documents inline,
never an invented numeric "quality score" and never an LLM judgment call
(no model is imported or called anywhere in this file; classification is
plain count thresholds plus substring matching against Evidence `tags`/
`source_type`, all of which already exist as real, stored fields --
nothing here is inferred from prose or free-text summaries).

Each dimension also carries `researchable`: whether an analyst may send
this specific gap to the existing public-research pathway
(report_builder.perplexity_gap_research). Only genuinely public,
factual, external-market-context dimensions are researchable (production
volume, acreage, trade flows, market structure, seasonality, commercial
deployment, ownership/licensing, public trial/registration data). This
system's own interpretive work product -- Signals, Assessments,
counterevidence, unresolved Strategic Question gaps, and this system's
own entity/geography/evidence coverage completeness -- is never
researchable: a public web search cannot produce this analyst team's own
Signals or Assessments, and "we haven't resolved this Company yet" is a
data-modeling gap, not a public fact to look up.

When a dimension is researchable and not AVAILABLE, `research_question`
holds a fixed, deterministic template filled only with the same public
labels already permitted through PublicQueryContext (berry/geography
names) -- never Evidence/Signal/Assessment content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

AVAILABLE = "AVAILABLE"
PARTIAL = "PARTIAL"
MISSING = "MISSING"

# A dimension backed by a plain count is AVAILABLE at >= AVAILABLE_MIN,
# PARTIAL at >= PARTIAL_MIN, MISSING at 0. One fixed rule, applied the
# same way everywhere in this module -- not tuned per dimension.
AVAILABLE_MIN = 3
PARTIAL_MIN = 1


@dataclass(frozen=True)
class CoverageDimension:
    key: str
    label: str
    status: str
    count: int
    explanation: str
    researchable: bool
    research_question: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "count": self.count,
            "explanation": self.explanation,
            "researchable": self.researchable,
            "research_question": self.research_question,
        }


def _status_for_count(count: int) -> str:
    if count >= AVAILABLE_MIN:
        return AVAILABLE
    if count >= PARTIAL_MIN:
        return PARTIAL
    return MISSING


def _count_dimension(
    key: str,
    label: str,
    count: int,
    *,
    noun: str,
    researchable: bool = False,
    research_question: str | None = None,
) -> CoverageDimension:
    status = _status_for_count(count)
    if status == AVAILABLE:
        explanation = f"{count} {noun} available for this scope."
    elif status == PARTIAL:
        explanation = f"Only {count} {noun} available for this scope (thin coverage)."
    else:
        explanation = f"No {noun} captured for this scope yet."
    return CoverageDimension(
        key=key,
        label=label,
        status=status,
        count=count,
        explanation=explanation,
        researchable=researchable,
        research_question=research_question if (researchable and status != AVAILABLE) else None,
    )


# key -> lowercase substrings matched against an Evidence record's own
# `tags` (case-insensitive substring match) or `source_type`. Tags in
# this corpus are real, stored acquisition-query keywords (e.g. "Berry
# acreage expansion", "Peru blueberry export", "Chile blueberry season")
# -- matching against them is a fixed, auditable rule over real data,
# never a guess.
_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "production_acreage": ("acreage", "harvest forecast", "production"),
    "trade_import_export": ("export", "import", "tariff", "gain report"),
    "market_structure": ("market", "retail sales", "category growth", "consumption trend"),
    "seasonality": ("season", "harvest forecast"),
    "commercial_deployment": (
        "acquisition",
        "nursery partnership",
        "joint venture",
        "retail sales",
    ),
    "ownership_licensing": (
        "license",
        "licensing",
        "plant variety protection",
        "intellectual-property",
        "exclusive variety license",
    ),
    "trial_research_evidence": ("trial", "research", "university", "extension", "breeding program"),
}
_SOURCE_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "market_structure": ("market_analysis_report", "market_data_service", "industry_association_report"),
    "commercial_deployment": ("company_catalog", "brand_website", "marketer_website"),
    "trial_research_evidence": ("university_trial_report", "extension_publication", "research_program_publication"),
}
_STRUCTURED_FLAG_DIMENSION: dict[str, str] = {
    "trade_import_export": "has_trade_observation",
    "commercial_deployment": "has_commercial_observation",
}

_RESEARCH_QUESTIONS: dict[str, str] = {
    "production_acreage": "What is the estimated production volume and planted acreage for {scope}?",
    "trade_import_export": "What are the recent import/export trade volumes for {scope}?",
    "market_structure": "What is the current market/industry structure (major players, market size, growth trends) for {scope}?",
    "seasonality": "What is the typical growing/harvest season and seasonality pattern for {scope}?",
    "commercial_deployment": "What recent commercial deployments, retail launches, or market entries are publicly reported for {scope}?",
    "ownership_licensing": "What are the publicly known ownership, breeding rights, or licensing arrangements for {scope}?",
    "trial_research_evidence": "What public trial, extension, or academic research results are available for {scope}?",
    "registrations": "What plant variety protection / breeders' rights registrations are publicly recorded for {scope}?",
}

_TOPIC_LABELS: dict[str, str] = {
    "production_acreage": "Production volume & acreage",
    "trade_import_export": "Trade / import-export data",
    "market_structure": "Market / industry structure",
    "seasonality": "Seasonality",
    "commercial_deployment": "Commercialization / deployment",
    "ownership_licensing": "Ownership / licensing",
    "trial_research_evidence": "Trial / research evidence",
}


def _matching_topic_count(signals: list[dict[str, Any]], key: str) -> int:
    tag_needles = _TAG_KEYWORDS.get(key, ())
    source_needles = _SOURCE_TYPE_KEYWORDS.get(key, ())
    structured_flag = _STRUCTURED_FLAG_DIMENSION.get(key)
    matched = 0
    for row in signals:
        tags_text = " | ".join(row.get("tags") or []).lower()
        source_type = str(row.get("source_type") or "").lower()
        if structured_flag and row.get(structured_flag):
            matched += 1
            continue
        if tag_needles and any(needle in tags_text for needle in tag_needles):
            matched += 1
            continue
        if source_needles and source_type in source_needles:
            matched += 1
            continue
    return matched


def _scope_label(*, berry_label: str, geography_labels: tuple[str, ...]) -> str:
    bits = [berry_label] if berry_label else []
    bits.extend(geography_labels)
    return ", ".join(bit for bit in bits if bit) or "this scope"


def _topic_dimension(
    key: str,
    packet: dict[str, Any],
    *,
    scope_label: str,
) -> CoverageDimension:
    signals = packet.get("evidence_topic_signals") or []
    count = _matching_topic_count(signals, key)
    template = _RESEARCH_QUESTIONS.get(key)
    question = template.format(scope=scope_label) if template else None
    return _count_dimension(
        key,
        _TOPIC_LABELS[key],
        count,
        noun="Evidence record(s) covering this topic",
        researchable=True,
        research_question=question,
    )


def _geography_coverage_dimension(packet: dict[str, Any]) -> CoverageDimension | None:
    scope_geo = packet.get("geography_ids") or []
    if not scope_geo:
        return None
    contributing = set(packet.get("contributing_geography_ids") or [])
    scope_geo_set = set(scope_geo)
    count = len(contributing & scope_geo_set)
    total = len(scope_geo_set)
    if count == 0:
        status, explanation = MISSING, "No Evidence found for any geography in this scope."
    elif count < total:
        status = PARTIAL
        explanation = f"Evidence found for {count} of {total} geographies in this scope."
    else:
        status = AVAILABLE
        explanation = f"Evidence found for all {total} geography(ies) in this scope."
    return CoverageDimension(
        key="geography_coverage",
        label="Geography coverage",
        status=status,
        count=count,
        explanation=explanation,
        researchable=False,
    )


def _variety_registration_dimension(packet: dict[str, Any], *, scope_label: str) -> CoverageDimension:
    varieties = packet.get("varieties") or []
    count = sum(int(v.get("rights_count") or 0) for v in varieties)
    return _count_dimension(
        "registrations",
        "Registrations (breeders' rights / PVP)",
        count,
        noun="rights filing(s)",
        researchable=True,
        research_question=_RESEARCH_QUESTIONS["registrations"].format(scope=scope_label),
    )


def _variety_deployment_dimension(packet: dict[str, Any]) -> CoverageDimension:
    varieties = packet.get("varieties") or []
    count = sum(int(v.get("commercial_observation_count") or 0) for v in varieties)
    return _count_dimension("deployment", "Deployment (commercial observations)", count, noun="commercial observation(s)")


def _variety_agronomic_attributes_dimension(packet: dict[str, Any]) -> CoverageDimension:
    varieties = packet.get("varieties") or []
    count = 0
    for v in varieties:
        for obs in v.get("top_observations") or []:
            if obs.get("trait_names"):
                count += 1
                break
    return _count_dimension("agronomic_attributes", "Agronomic / product attributes", count, noun="variety(ies) with recorded traits")


def _company_minimum_presence_dimension(packet: dict[str, Any]) -> CoverageDimension:
    """COMPETITOR_COMPARISON only: does every explicitly-selected Company
    in scope have at least minimal Evidence presence in the packet? Not
    researchable -- this is a completeness gate on this system's own
    entity resolution, not a public fact."""
    companies = packet.get("companies") or []
    return CoverageDimension(
        key="minimum_evidence_presence",
        label="Minimum evidence presence (selected companies)",
        status=AVAILABLE if companies else MISSING,
        count=len(companies),
        explanation=(
            f"{len(companies)} selected Company(ies) resolved with packet presence."
            if companies
            else "None of the selected Companies resolved with any packet presence."
        ),
        researchable=False,
    )


_NON_RESEARCHABLE_COUNT_DIMS: dict[str, tuple[str, str]] = {
    "recent_evidence": ("Recent Evidence", "evidence_count"),
    "key_companies": ("Key Companies", "company_count"),
    "variety_genetics": ("Variety / genetics context", "trusted_variety_count"),
    "candidate_varieties": ("Candidate varieties", "variety_candidate_count"),
    "signals": ("Signals", "signal_count"),
    "assessments": ("Assessments", "assessment_count"),
}


def _non_researchable_count_dimension(key: str, counts: dict[str, int]) -> CoverageDimension:
    label, count_key = _NON_RESEARCHABLE_COUNT_DIMS[key]
    return _count_dimension(key, label, int(counts.get(count_key) or 0), noun=label.lower())


# Per report_type, the ordered dimension key list. Every key must be
# handled by _build_dimension() below.
DIMENSION_KEYS_BY_REPORT_TYPE: dict[str, tuple[str, ...]] = {
    "market_landscape": (
        "recent_evidence",
        "key_companies",
        "production_acreage",
        "trade_import_export",
        "variety_genetics",
        "market_structure",
        "seasonality",
        "signals",
        "assessments",
    ),
    "competitive_landscape": (
        "key_companies",
        "geography_coverage",
        "recent_evidence",
        "variety_genetics",
        "commercial_deployment",
        "ownership_licensing",
        "signals",
        "assessments",
    ),
    "competitor_comparison": (
        "minimum_evidence_presence",
        "recent_evidence",
        "geography_coverage",
        "variety_genetics",
    ),
    "variety_genetics_landscape": (
        "variety_genetics",
        "candidate_varieties",
        "ownership_licensing",
        "registrations",
        "deployment",
        "agronomic_attributes",
        "trial_research_evidence",
    ),
    "strategic_question_brief": (
        "recent_evidence",
        "signals",
        "assessments",
    ),
}

_TOPIC_KEYS = frozenset(_TOPIC_LABELS)


def report_coverage_dimensions(
    packet: dict[str, Any],
    *,
    report_type: str,
    counts: dict[str, int],
    berry_label: str = "",
    geography_labels: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """The single deterministic entry point: packet + report_type + the
    already-computed plain counts (from report_coverage()) -> an ordered
    list of CoverageDimension.as_dict(). No LLM call anywhere in this
    function or anything it calls."""
    keys = DIMENSION_KEYS_BY_REPORT_TYPE.get(report_type, ())
    if not keys:
        return []
    scope_label = _scope_label(berry_label=berry_label, geography_labels=geography_labels)
    dimensions: list[CoverageDimension] = []
    for key in keys:
        if key in _TOPIC_KEYS:
            dimensions.append(_topic_dimension(key, packet, scope_label=scope_label))
        elif key == "geography_coverage":
            dim = _geography_coverage_dimension(packet)
            if dim is not None:
                dimensions.append(dim)
        elif key == "registrations":
            dimensions.append(_variety_registration_dimension(packet, scope_label=scope_label))
        elif key == "deployment":
            dimensions.append(_variety_deployment_dimension(packet))
        elif key == "agronomic_attributes":
            dimensions.append(_variety_agronomic_attributes_dimension(packet))
        elif key == "minimum_evidence_presence":
            dimensions.append(_company_minimum_presence_dimension(packet))
        elif key in _NON_RESEARCHABLE_COUNT_DIMS:
            dimensions.append(_non_researchable_count_dimension(key, counts))
    return [d.as_dict() for d in dimensions]
