"""Competitor Pulse V1 -- live, provider-neutral company research plane.

A user must be able to open a Company and immediately see current,
sourced chatter about it WITHOUT waiting for Publication Review or
Evidence Review. This module is deliberately a LIVE RESEARCH PLANE,
structurally separate from the durable trust model built elsewhere in
this codebase:

- Never writes Evidence.
- Never mutates Company (or any other entity) truth.
- Never creates a Signal or Assessment.
- Never silently creates a canonical entity or onboards a Source.

Every result carries `trust_label = "LIVE / UNREVIEWED"` and is never
labeled or treated as Reviewed Evidence anywhere downstream. A qualifying
live result MAY optionally be pushed into the existing newsroom/
acquisition path (see `promote_hit_to_publication_draft` at the bottom
of this module, which reuses `industry_pulse.intake` verbatim) -- that
remains the only door back into durable trust, and it still goes through
the unchanged Publication Review / Evidence Review gates.

Reuses, unchanged: `industry_pulse.providers.discover` (provider-neutral
ad-hoc query), `industry_pulse.qualify.qualify_hit`/`QualificationIndex`,
`industry_pulse.dedup.dedupe_hits`/`unique_hits`. Company terms (name +
aliases + explicitly `owns`-related brand names) are never invented --
see `company_query_terms()`.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from app.services.industry_pulse.dedup import dedupe_hits, unique_hits
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import DiscoveryProvider, discover
from app.services.industry_pulse.qualify import QualificationIndex, qualify_hit

LIVE_WINDOWS = ("24h", "7d", "30d")
DEFAULT_WINDOW = "7d"
TRUST_LABEL = "LIVE / UNREVIEWED"

CATEGORY_LATEST = "LATEST DEVELOPMENTS"
CATEGORY_VARIETY = "VARIETY / GENETICS"
CATEGORY_COMMERCIAL = "COMMERCIAL / PARTNERSHIP / LICENSING"
CATEGORY_MARKET = "MARKET / PRODUCTION"
CATEGORY_PATENT = "PATENT / PBR / REGULATORY"
CATEGORY_RESEARCH = "RESEARCH"
CATEGORY_MAINSTREAM = "MAINSTREAM / BROADER CONTEXT"
CATEGORY_OTHER = "OTHER RELEVANT"

CATEGORY_ORDER = (
    CATEGORY_LATEST,
    CATEGORY_VARIETY,
    CATEGORY_COMMERCIAL,
    CATEGORY_MARKET,
    CATEGORY_PATENT,
    CATEGORY_RESEARCH,
    CATEGORY_MAINSTREAM,
    CATEGORY_OTHER,
)

# --- deterministic, explainable classification (no LLM, no opaque score) ---

_PATENT_RE = re.compile(
    r"\b(PBR|plant breeders? rights|plant patent|CPVO|USPTO|patent|granted|"
    r"registration|regulatory|recall|residue)\b",
    re.IGNORECASE,
)
_VARIETY_RE = re.compile(
    r"\b(cultivar|variet(?:y|ies)|breeding|breeder|genetics|nursery|seedless|"
    r"primocane|floricane|crispr|gene-?edit\w*)\b",
    re.IGNORECASE,
)
_COMMERCIAL_RE = re.compile(
    r"\b(acquisition|merger|partnership|joint venture|licen[cs]e|licensing|"
    r"royalty|unveils|launches?|expansion|investment|deal|agreement)\b",
    re.IGNORECASE,
)
_MARKET_RE = re.compile(
    r"\b(acreage|hectares|exports?|imports?|harvest|pricing|price|supply|"
    r"production|trade|tariff|frost|drought|crop condition|weather|yield)\b",
    re.IGNORECASE,
)
_RESEARCH_RE = re.compile(
    r"\b(university|extension|research station|field trial|study|academic|researchers?)\b",
    re.IGNORECASE,
)

_BERRY_PATTERNS: dict[str, re.Pattern[str]] = {
    "berry-blueberry": re.compile(r"\bblueberr\w*|ar[aá]ndano\w*|myrtille\w*\b", re.IGNORECASE),
    "berry-strawberry": re.compile(r"\bstrawberr\w*|fresa\w*|fraise\w*\b", re.IGNORECASE),
    "berry-raspberry": re.compile(r"\braspberr\w*|frambuesa\w*|framboise\w*\b", re.IGNORECASE),
    "berry-blackberry": re.compile(r"\bblackberr\w*|caneberr\w*|zarzamora\w*\b", re.IGNORECASE),
}

_GEOGRAPHY_PATTERNS: dict[str, re.Pattern[str]] = {
    "americas": re.compile(
        r"\b(Peru|Chile|Mexico|Canada|Brazil|California|Florida|Argentina|Colombia|United States|U\.S\.|USA)\b"
    ),
    "europe": re.compile(r"\b(Europe|Spain|UK|United Kingdom|Britain|British|England|Scotland|Netherlands|Poland|Germany|Italy|Portugal|Belgium|France|Bulgaria|Ukraine)\b"),
    "africa": re.compile(r"\b(Africa|South Africa|Morocco|Egypt|Kenya|Zimbabwe)\b"),
    "apac": re.compile(r"\b(Australia|China|Japan|Korea|New Zealand|India|Vietnam|Tasmania)\b"),
}


def detect_berry(text: str) -> str | None:
    """Best-effort explicit berry mention. Never invents; returns None when absent."""
    for berry_id, pattern in _BERRY_PATTERNS.items():
        if pattern.search(text):
            return berry_id
    return None


def detect_geography(text: str) -> str | None:
    """Best-effort explicit region mention. Never invents; returns None when absent."""
    for geography, pattern in _GEOGRAPHY_PATTERNS.items():
        if pattern.search(text):
            return geography
    return None


def categorize_hit(hit: DiscoveryHit) -> str:
    """Deterministic, keyword-based, priority-ordered. Falls back to OTHER
    RELEVANT rather than forcing a specific category when uncertain."""
    text = f"{hit.title} {hit.snippet}"
    if _PATENT_RE.search(text):
        return CATEGORY_PATENT
    if _VARIETY_RE.search(text):
        return CATEGORY_VARIETY
    if _COMMERCIAL_RE.search(text):
        return CATEGORY_COMMERCIAL
    if _MARKET_RE.search(text):
        return CATEGORY_MARKET
    if _RESEARCH_RE.search(text):
        return CATEGORY_RESEARCH
    reasons = hit.qualify_reasons or []
    has_industry_signal = any(
        reason.startswith("explicit") or "industry" in reason or "cultivar" in reason for reason in reasons
    )
    if has_industry_signal:
        return CATEGORY_LATEST
    if any(reason.startswith("named company") for reason in reasons):
        return CATEGORY_MAINSTREAM
    return CATEGORY_OTHER


# --- company term resolution: explicit only, never invented ---


def company_query_terms(
    company: dict[str, Any],
    *,
    relationships: Iterable[dict[str, Any]] = (),
    entities_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """The Company's own name + declared `aliases`, plus the name of any
    entity it explicitly `owns` (an active relationship record) that is
    itself a `brand` -- e.g. Fall Creek -> Sekoya. Never guesses a term
    that isn't backed by an existing field or relationship record."""
    terms: list[str] = []
    name = str(company.get("name") or "").strip()
    if name:
        terms.append(name)
    for alias in company.get("aliases") or []:
        alias = str(alias).strip()
        if alias and alias not in terms:
            terms.append(alias)
    if entities_by_id is not None:
        company_id = company.get("id")
        for rel in relationships:
            if rel.get("subject_id") != company_id:
                continue
            if rel.get("predicate") != "owns":
                continue
            if rel.get("status") not in (None, "active"):
                continue
            obj = entities_by_id.get(str(rel.get("object_id") or ""))
            if obj and obj.get("entity_type") == "brand":
                brand_name = str(obj.get("name") or "").strip()
                if brand_name and brand_name not in terms:
                    terms.append(brand_name)
    return terms


def distinctive_terms(terms: list[str]) -> list[str]:
    """Terms specific enough that matching one alone is trustworthy signal
    that a result is genuinely about this company. Some real, legitimate
    aliases are short common words/phrases that collide with unrelated
    subjects -- "Fall Creek" (a real Fall Creek Farm & Nursery alias) is
    also a Wisconsin town and an Oregon place name, so a bare match finds
    library, wildfire, and obituary stories about the town, not the
    nursery. Those short aliases still drive search RECALL (they stay in
    `terms`/the query text unchanged), but a hit that matches ONLY a
    short alias -- with no corroborating crop/industry signal -- is
    filtered as noise; see `_corroborated()`. The company's own full name
    (always `terms[0]`, per `company_query_terms()`) is always treated as
    distinctive regardless of length, since it is the entity's own
    registered identifier. Any other term counts once it has 3+ words."""
    if not terms:
        return []
    out = [terms[0]]
    for term in terms[1:]:
        if len(term.split()) >= 3:
            out.append(term)
    return out


def _mentions_company(hit: DiscoveryHit, *, company_re: "re.Pattern[str] | None") -> bool:
    """`qualify_hit` was built for industry-wide pulse, where ANY berry-
    industry story is in scope regardless of company. Company Pulse is
    narrower: a hit that Google/Perplexity returned for a company-scoped
    query but that never actually mentions the company anywhere in its
    own title/snippet (a same-topic, different-company result) is not
    "about" this company and must not qualify on crop/industry terms
    alone."""
    if company_re is None:
        return False
    return bool(company_re.search(f"{hit.title} {hit.snippet}"))


def _corroborated(hit: DiscoveryHit, *, distinctive_re: "re.Pattern[str] | None") -> bool:
    """True if a QUALIFY-marked hit has a signal beyond a bare short-alias
    company-name match: an explicit crop/industry/cultivar reason (from
    qualify_hit's own reasons), or a match against the company's
    distinctive name(s)."""
    reasons = hit.qualify_reasons or []
    if any(not reason.startswith("named company") for reason in reasons):
        return True
    if distinctive_re is not None and distinctive_re.search(f"{hit.title} {hit.snippet}"):
        return True
    return False


def build_query_text(terms: list[str]) -> str:
    quoted = [f'"{term}"' if " " in term else term for term in terms]
    return "(" + " OR ".join(quoted) + ")" if quoted else ""


# --- display item: a thin, live-only wrapper. Never mutates DiscoveryHit's
# shared dataclass shape, which other Industry Pulse callers also rely on. ---


@dataclass
class CompanyPulseItem:
    title: str
    url: str
    publisher: str
    published_date: str | None
    captured_at: str
    snippet: str
    category: str
    berry: str | None
    geography: str | None
    provider: str
    provider_query_provenance: list[str]
    qualify_reasons: list[str] = field(default_factory=list)
    trust_label: str = TRUST_LABEL

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _to_display_item(hit: DiscoveryHit, *, captured_at: str) -> CompanyPulseItem:
    text = f"{hit.title} {hit.snippet}"
    publisher = hit.origin_publisher_name or hit.source_domain or "Unknown publisher"
    url = hit.origin_publisher_url or hit.url
    return CompanyPulseItem(
        title=hit.title,
        url=url,
        publisher=str(publisher),
        published_date=hit.published_date,
        captured_at=captured_at,
        snippet=hit.snippet,
        category=categorize_hit(hit),
        berry=hit.berry or detect_berry(text),
        geography=detect_geography(text),
        provider=hit.provider,
        provider_query_provenance=[hit.provider],
        qualify_reasons=list(hit.qualify_reasons or []),
    )


# --- live run ---


@dataclass
class PulseRunResult:
    company_id: str
    company_name: str
    query_terms: list[str]
    window: str
    searched_at: str
    latency_seconds: float
    items: list[CompanyPulseItem]
    grouped: dict[str, list[CompanyPulseItem]]
    provider_telemetry: dict[str, dict[str, int]]
    raw_hit_count: int
    qualifying_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "company_name": self.company_name,
            "query_terms": self.query_terms,
            "window": self.window,
            "searched_at": self.searched_at,
            "latency_seconds": self.latency_seconds,
            "items": [item.as_dict() for item in self.items],
            "grouped": {k: [item.as_dict() for item in v] for k, v in self.grouped.items()},
            "provider_telemetry": self.provider_telemetry,
            "raw_hit_count": self.raw_hit_count,
            "qualifying_count": self.qualifying_count,
        }


_QUOTE_VARIANTS = str.maketrans({
    "’": "'",  # right single quotation mark (curly apostrophe)
    "‘": "'",  # left single quotation mark
    "“": '"',  # left double quotation mark
    "”": '"',  # right double quotation mark
})


def _normalize_quotes(text: str) -> str:
    """Google News (and other providers) return titles with typographic
    "smart quotes" (U+2019 etc.), while company names/aliases in this
    system's own entity records use plain ASCII apostrophes. Without this,
    a real, exact mention of e.g. "Driscoll's" in a headline silently
    fails to match the "Driscoll's" company-name regex -- found via the
    mission's own manual-web-challenge acceptance step, where real
    Driscoll's lawsuit/leadership coverage was missing from live results
    despite Google News RSS having already returned it."""
    return text.translate(_QUOTE_VARIANTS)


def _discover_and_qualify(
    terms: list[str],
    *,
    window: str,
    providers: Iterable[DiscoveryProvider],
) -> tuple[list[DiscoveryHit], dict[str, dict[str, int]]]:
    """Shared by `run_company_pulse` (page render) and
    `find_live_hit_by_url` (the optional promote action) so both run the
    exact same live query/qualify/dedup logic. Stateless -- nothing here
    is cached between calls."""
    terms = [_normalize_quotes(term) for term in terms]
    query_text = build_query_text(terms)
    all_hits: list[DiscoveryHit] = []
    telemetry: dict[str, dict[str, int]] = {}
    if query_text:
        for provider in providers:
            errors = 0
            hits: list[DiscoveryHit] = []
            try:
                hits = discover(query_text, date_window=window, geography="global", provider=provider)
            except Exception:  # noqa: BLE001 -- one provider failing must not fail the page
                errors = 1
            for hit in hits:
                hit.title = _normalize_quotes(hit.title)
                hit.snippet = _normalize_quotes(hit.snippet)
            telemetry[provider.name] = {"hits_returned": len(hits), "errors": errors}
            all_hits.extend(hits)

    index = QualificationIndex.compile(company_names=terms)
    distinctive_index = QualificationIndex.compile(company_names=distinctive_terms(terms))
    for hit in all_hits:
        qualify_hit(hit, index=index)
        if not hit.qualifying:
            continue
        if not _mentions_company(hit, company_re=index.company_re):
            hit.qualifying = False
            hit.qualify_reasons = list(hit.qualify_reasons) + ["does not literally mention this company"]
            hit.qualify_reason = f"REJECT: {hit.qualify_reasons[-1]}"
            continue
        if not _corroborated(hit, distinctive_re=distinctive_index.company_re):
            hit.qualifying = False
            hit.qualify_reasons = list(hit.qualify_reasons) + [
                "ambiguous short company-name alias without corroborating industry/crop signal"
            ]
            hit.qualify_reason = f"REJECT: {hit.qualify_reasons[-1]}"
    dedupe_hits(all_hits)
    return all_hits, telemetry


def run_company_pulse(
    company: dict[str, Any],
    *,
    relationships: Iterable[dict[str, Any]] = (),
    entities_by_id: dict[str, dict[str, Any]] | None = None,
    window: str = DEFAULT_WINDOW,
    providers: Iterable[DiscoveryProvider] = (),
    now: datetime | None = None,
) -> PulseRunResult:
    """Live, read-only. Queries `providers` (typically Google News RSS and,
    when available, Perplexity) with the company's own name/aliases/owned
    brand, qualifies, deduplicates, and categorizes. Writes nothing."""
    if window not in LIVE_WINDOWS:
        raise ValueError(f"unsupported window: {window}")
    now = now or datetime.now(timezone.utc)
    started = time.monotonic()

    terms = company_query_terms(company, relationships=relationships, entities_by_id=entities_by_id)
    all_hits, telemetry = _discover_and_qualify(terms, window=window, providers=providers)

    qualifying_hits = [hit for hit in unique_hits(all_hits) if hit.qualifying]
    qualifying_hits.sort(key=lambda h: h.published_date or "", reverse=True)

    captured_at = now.isoformat()
    items = [_to_display_item(hit, captured_at=captured_at) for hit in qualifying_hits]

    grouped: dict[str, list[CompanyPulseItem]] = {category: [] for category in CATEGORY_ORDER}
    for item in items:
        grouped[item.category].append(item)
    grouped = {category: rows for category, rows in grouped.items() if rows}

    return PulseRunResult(
        company_id=str(company.get("id") or ""),
        company_name=str(company.get("name") or ""),
        query_terms=terms,
        window=window,
        searched_at=captured_at,
        latency_seconds=round(time.monotonic() - started, 3),
        items=items,
        grouped=grouped,
        provider_telemetry=telemetry,
        raw_hit_count=len(all_hits),
        qualifying_count=len(items),
    )


# --- "What should I know?" synthesis: public retrieved material only ---
#
# SECURITY BOUNDARY (mirrors app/services/report_builder/synthesis.py):
# only title, publisher, date, and the live search snippet -- already
# public, already displayed to the user -- are ever sent. Assessment
# rationale, Signal observations, private notes, internal Facts, and
# report/strategy prose are never sent, because they are never even in
# scope of this function: it only ever receives the same `items` list
# already rendered on the page.

_BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "statements": {
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
    "required": ["statements"],
    "additionalProperties": False,
}

_BRIEF_INSTRUCTIONS = (
    "You are drafting a short current-intelligence briefing about one company, for an "
    "internal strategy team. You may state ONLY what is directly supported by the "
    "numbered public news items below -- never add outside knowledge, never speculate, "
    "never invent a fact, date, or figure not present in them. Every statement's "
    "source_ids must reference one or more of the ids listed below. If the items do not "
    "support a substantive briefing, return an empty statements array."
)


@dataclass(frozen=True)
class BriefStatement:
    text: str
    source_ids: tuple[str, ...]


def _digest_line(item_id: str, item: CompanyPulseItem) -> str:
    parts = [item_id, item.title, item.publisher, item.published_date or "date unknown"]
    if item.snippet:
        parts.append(item.snippet[:200])
    return " | ".join(str(p) for p in parts if p)[:320]


def generate_current_brief(
    items: list[CompanyPulseItem],
    *,
    completer: Callable[..., Any] | None,
    model: str = "anthropic/claude-haiku-4-5",
) -> tuple[BriefStatement, ...]:
    """`items` must be exactly the display-ready, already-rendered result
    set. Returns () when unavailable or ungrounded; callers show a plain
    "no current briefing available" message rather than inventing prose."""
    if completer is None or not items:
        return ()
    indexed = {f"live-{i}": item for i, item in enumerate(items[:25])}
    digest = [_digest_line(item_id, item) for item_id, item in indexed.items()]
    prompt = (
        f"{_BRIEF_INSTRUCTIONS}\n\nNumbered public items (id | title | publisher | date | snippet):\n"
        + "\n".join(f"- {line}" for line in digest)
    )
    try:
        result = completer(prompt, schema=_BRIEF_SCHEMA, model=model, max_output_tokens=500)
    except Exception:  # noqa: BLE001 -- synthesis failure must not break the live page
        return ()
    statements: list[BriefStatement] = []
    for row in result.parsed.get("statements") or []:
        text = str(row.get("text") or "").strip()
        raw_ids = [str(s) for s in (row.get("source_ids") or [])]
        valid_ids = tuple(s for s in raw_ids if s in indexed)
        if text and valid_ids:
            statements.append(BriefStatement(text=text, source_ids=valid_ids))
    return tuple(statements)


# --- optional bridge back into durable trust: unchanged Publication Review ---


def find_live_hit_by_url(
    company: dict[str, Any],
    *,
    relationships: Iterable[dict[str, Any]] = (),
    entities_by_id: dict[str, dict[str, Any]] | None = None,
    window: str,
    providers: Iterable[DiscoveryProvider],
    url: str,
) -> DiscoveryHit | None:
    """Re-runs the same live query used to render the page and returns the
    one qualifying, deduplicated hit matching `url`, or None. Used only by
    the optional "send to Publication Review" action -- deliberately
    stateless; no raw provider result is ever cached between the page
    render and this call."""
    terms = company_query_terms(company, relationships=relationships, entities_by_id=entities_by_id)
    all_hits, _telemetry = _discover_and_qualify(terms, window=window, providers=providers)
    for hit in unique_hits(all_hits):
        if hit.qualifying and (hit.origin_publisher_url or hit.url) == url:
            return hit
    return None
