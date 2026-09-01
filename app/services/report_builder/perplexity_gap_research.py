"""AI-Assisted Report Builder V1 -- Perplexity public gap research.

Explicit, analyst-opt-in only ("Research missing public information").
This module is the ONLY place in the Report Builder allowed to call an
external network provider with a free-text query, and it enforces a
hard content boundary before doing so:

ALLOWED to leave this process: the berry label, geography label(s),
public Company/Variety names, and a short research question the
analyst is shown before sending (built from public labels only).

NEVER allowed to leave this process: Evidence summaries/titles/text,
Assessment rationale, Signal observations, Fact statements, report
section prose (generated or edited), or any other packet/report
content. `build_public_query()` is the single choke point every caller
must go through -- it only ever reads from a fixed allow-list of public
label fields, never from the packet or report record as a whole, so
there is no path for private content to reach it by accident.

Findings return as sourced, citation-bearing RESEARCH PROPOSALS. They
are appended to a report's `external_research_appendix` (see
reports_store.append_research_appendix) and are never merged into
`sections`, never treated as citable grounding for AI synthesis, and
never become Evidence/Signal/Assessment/Strategic Question -- promoting
one into canonical intelligence, if ever desired, is only possible
through the existing Publication/Evidence trust workflow (an analyst
would manually author a new Evidence draft citing the same public URL),
exactly like Signal Candidates and Variety Candidates are never
silently promoted (AGENTS.md)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services.ai_gateway.results import ResearchResponse

DEFAULT_RESEARCH_MODEL = "sonar"


@dataclass(frozen=True)
class PublicQueryContext:
    berry_label: str
    geography_labels: tuple[str, ...]
    company_names: tuple[str, ...]
    variety_names: tuple[str, ...]
    question: str


def build_public_query(context: PublicQueryContext) -> str:
    """The single choke point for what may be sent externally -- every
    field here is a plain label/name already public on this system's own
    entity pages, plus the analyst's own typed research question. No
    Evidence/Assessment/Signal/Fact content, and no report section text,
    is ever concatenated into this string."""
    scope_bits = [context.berry_label] if context.berry_label else []
    scope_bits.extend(context.geography_labels)
    scope_bits.extend(context.company_names)
    scope_bits.extend(context.variety_names)
    scope_text = ", ".join(bit for bit in scope_bits if bit)
    question = context.question.strip()
    if scope_text and question:
        return f"{question} (context: {scope_text})"
    return question or scope_text


@dataclass(frozen=True)
class ResearchProposal:
    title: str
    url: str
    snippet: str
    source: str = "perplexity_public_research"
    reviewed: bool = False


def research_public_gaps(
    context: PublicQueryContext,
    *,
    research_client_factory: Callable[[], Any] | None,
    model: str = DEFAULT_RESEARCH_MODEL,
) -> tuple[list[ResearchProposal], str]:
    """Returns (proposals, status_message). `research_client_factory`
    typically constructs a `PerplexityResearchClient` with a resolved API
    key -- pass None to skip cleanly when no credential is configured
    (the caller shows status_message rather than failing the workspace)."""
    query = build_public_query(context)
    if not query.strip():
        return [], "No public scope or question to research."
    if research_client_factory is None:
        return [], "Public gap research is unavailable -- no provider credential configured for this environment."
    client = research_client_factory()
    try:
        response: ResearchResponse = client.research(query, model=model, web_enabled=True, citations=True)
    except Exception as exc:  # noqa: BLE001 - surfaced as a status message, never raised into the route
        return [], f"Public gap research failed: {type(exc).__name__}."
    proposals = [
        ResearchProposal(title=citation.title or citation.url, url=citation.url, snippet=response.content[:400])
        for citation in response.citations
    ]
    if not proposals:
        return [], "No citable public sources were found for this query."
    return proposals, f"Found {len(proposals)} public source(s). Unreviewed -- treat as a research lead, not a citable fact."
