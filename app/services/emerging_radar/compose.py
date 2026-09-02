"""Radar ranking, sections, market/trusted context, watchlist seam.

No opaque importance score. Reasons are inspectable strings.
LIVE developments never mutate Evidence, Signals, or Assessments.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from app.services.emerging_radar.cluster import is_social_host
from app.services.emerging_radar.models import (
    SECTION_DEFS,
    TRUST_ASSESSMENT,
    TRUST_EVIDENCE,
    TRUST_LIVE,
    Development,
    RadarEdition,
)
from app.services.market_reality.research_desk import market_reality_for
from app.services.watchlist import load_watches

WATCH_EVENT_SCHEMA = "radar-watchlist-event-v1"

GOOGLE_STACK_PROVIDERS = frozenset({"google_news_rss", "specialist_rss"})

GENETICS_TYPES = frozenset({"VARIETY_LAUNCH", "GENETICS_INNOVATION"})
COMPETITOR_TYPES = frozenset({"LEADERSHIP", "PARTNERSHIP", "LICENSING"})
MARKET_TYPES = frozenset({"PRODUCTION_EXPANSION", "MARKET_ACCESS", "SUPPLY_CHANGE", "RETAIL_PROGRAM"})
REGULATORY_TYPES = frozenset({"PBR", "PATENT", "REGULATORY", "LEGAL"})
BOARD_LIMIT = 36
SECTION_CAPS = {
    "emerging_now": 6,
    "worth_watching": 8,
    "genetics_varieties": 8,
    "competitor_moves": 8,
    "market_supply": 8,
    "regulatory_ip": 6,
    "weak_signals": 6,
    "recently_corroborated": 6,
}


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def radar_reasons(
    development: Development,
    *,
    watches: Iterable[dict[str, Any]] = (),
    today: date | None = None,
) -> tuple[str, ...]:
    today = today or datetime.now(timezone.utc).date()
    reasons: list[str] = []
    if development.watchlist_matches or _watch_hits(development, watches):
        reasons.append("Watchlist match")
    if development.event_type in GENETICS_TYPES or development.variety_ids:
        reasons.append("New Variety/genetics event")
    if development.company_ids:
        reasons.append("First appearance of canonical competitor" if development.source_count == 1 else "Canonical competitor named")
    if development.geography_ids and development.company_ids:
        reasons.append("Geography named for Company/Variety")
    if development.independent_source_count >= 2:
        reasons.append("Multiple independent sources")
    if development.corroboration in {"OFFICIAL + PRESS", "REGISTRY + PRESS", "COMPANY CLAIM + INDEPENDENT REPORT"}:
        reasons.append("Primary-source corroboration")
    if development.event_type in {"PBR", "PATENT"}:
        reasons.append("Patent/PBR linkage")
    if development.provenance == ("exa",) or (
        "exa" in development.provenance and not any(name in GOOGLE_STACK_PROVIDERS for name in development.provenance)
    ):
        reasons.append("Exa-only semantic discovery")
    if development.event_type in {"PRODUCTION_EXPANSION", "SUPPLY_CHANGE", "MARKET_ACCESS"}:
        reasons.append("Strong market-reality change")
    event_day = _parse_day(development.event_date or development.latest_update)
    if event_day and (today - event_day).days <= 3:
        reasons.append("Recent event")
    if not reasons:
        reasons.append("Named industry development in the live window")
    return tuple(dict.fromkeys(reasons))


def _watch_hits(development: Development, watches: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    owned = {
        "company": set(development.company_ids),
        "variety": set(development.variety_ids),
        "geography": set(development.geography_ids),
        "strategic_question": set(development.company_ids) | set(development.variety_ids) | set(development.geography_ids) | set(development.berry_ids),
    }
    for watch in watches:
        watch_type = str(watch.get("watch_type") or "")
        object_id = str(watch.get("object_id") or "")
        if object_id and object_id in owned.get(watch_type, set()):
            matches.append({"watch_type": watch_type, "object_id": object_id})
    return matches


def apply_watchlist(developments: list[Development], watches: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for development in developments:
        matches = tuple(_watch_hits(development, watches))
        development.watchlist_matches = matches
        for match in matches:
            events.append(
                {
                    "schema": WATCH_EVENT_SCHEMA,
                    "event_type": "watchlist_development_match",
                    "development_id": development.id,
                    "title": development.title,
                    "watch_type": match["watch_type"],
                    "object_id": match["object_id"],
                    "first_seen": development.first_seen,
                    "latest_update": development.latest_update,
                    "corroboration": development.corroboration,
                    "trust_state": TRUST_LIVE,
                }
            )
    return events


def attach_market_context(
    developments: list[Development],
    *,
    repo: Any | None,
) -> None:
    if repo is None:
        return
    for development in developments:
        rows: list[dict[str, Any]] = []
        berry_ids = development.berry_ids or (None,)
        geography_ids = development.geography_ids or (None,)
        seen: set[tuple[str, str]] = set()
        for berry_id in berry_ids:
            for geography_id in geography_ids:
                if not berry_id and not geography_id:
                    continue
                payload = market_reality_for(repo, berry_id=berry_id, geography_id=geography_id)
                for series, change in (payload.get("change_by_series") or {}).items():
                    lvp = change.get("latest_vs_previous") if isinstance(change, dict) else None
                    if not lvp or lvp.get("pct_change") is None:
                        continue
                    if abs(float(lvp["pct_change"])) < 5:
                        continue
                    key = (str(lvp.get("metric")), str(lvp.get("latest_period")))
                    if key in seen:
                        continue
                    seen.add(key)
                    sign = "+" if lvp["pct_change"] > 0 else ""
                    rows.append(
                        {
                            "metric": lvp.get("metric"),
                            "label": f"{lvp.get('metric')} {sign}{round(lvp['pct_change'], 1)}%",
                            "latest_period": lvp.get("latest_period"),
                            "pct_change": lvp.get("pct_change"),
                            "series": series,
                        }
                    )
        if rows:
            development.market_context = {
                "disclaimer": "Structured market change in the same berry/geography. Not a claim that this development caused it.",
                "rows": rows[:4],
            }


def attach_trusted_context(
    developments: list[Development],
    *,
    evidence: Iterable[dict[str, Any]] = (),
    assessments: Iterable[dict[str, Any]] = (),
) -> None:
    evidence_rows = [row for row in evidence if row.get("id")]
    assessment_rows = [row for row in assessments if row.get("id")]
    for development in developments:
        owned = set(development.company_ids) | set(development.variety_ids)
        trusted: list[dict[str, Any]] = []
        evidence_ids: list[str] = []
        if not owned:
            development.trusted_context = []
            continue
        for row in evidence_rows:
            ids = set(row.get("entity_ids") or []) | set(row.get("geography_ids") or [])
            if not owned or not (owned & ids):
                continue
            title = str(row.get("title") or "")
            relation = "related"
            folded = f"{title} {row.get('summary') or ''}".casefold()
            if any(token in folded for token in ("denied", "cancelled", "false", "not proceeding")):
                relation = "contradicts"
            elif development.event_type.lower().replace("_", " ") in folded or any(
                name.casefold() in folded for name in development.company_names
            ):
                relation = "supports"
            trusted.append(
                {
                    "kind": TRUST_EVIDENCE,
                    "id": row["id"],
                    "title": title,
                    "relation": relation,
                    "href": f"/evidence/{row['id']}",
                }
            )
            evidence_ids.append(str(row["id"]))
            if len(trusted) >= 4:
                break
        assessment_ids: list[str] = []
        for row in assessment_rows:
            ids = set(row.get("entity_ids") or []) | set(row.get("geography_ids") or [])
            if owned and owned & ids:
                trusted.append(
                    {
                        "kind": TRUST_ASSESSMENT,
                        "id": row["id"],
                        "title": row.get("title") or row["id"],
                        "relation": "related",
                        "href": f"/assessments/{row['id']}",
                    }
                )
                assessment_ids.append(str(row["id"]))
            if len(trusted) >= 6:
                break
        development.trusted_context = trusted
        development.evidence_ids = tuple(evidence_ids)
        development.assessment_ids = tuple(assessment_ids)


def _rank_tuple(development: Development, *, today: date) -> tuple:
    event_day = _parse_day(development.event_date or development.latest_update) or date.min
    recency = (event_day - date.min).days
    named = 1 if development.company_ids or development.variety_ids else 0
    typed = 1 if development.event_type != "OTHER" else 0
    exa = 1 if "exa" in development.provenance else 0
    return (
        1 if development.watchlist_matches else 0,
        named,
        typed,
        1 if development.independent_source_count >= 2 else 0,
        exa,
        1 if development.event_type in GENETICS_TYPES else 0,
        1 if development.corroboration in {"OFFICIAL + PRESS", "REGISTRY + PRESS", "COMPANY CLAIM + INDEPENDENT REPORT"} else 0,
        recency,
        development.publisher_diversity,
        development.title,
    )


def assign_sections(developments: list[Development], *, today: date | None = None) -> list[Development]:
    today = today or datetime.now(timezone.utc).date()
    ranked = sorted(developments, key=lambda row: _rank_tuple(row, today=today), reverse=True)
    claimed: set[str] = set()

    def take(predicate, limit: int | None = None) -> list[Development]:
        chosen: list[Development] = []
        for row in ranked:
            if row.id in claimed:
                continue
            if predicate(row):
                chosen.append(row)
                claimed.add(row.id)
                if limit is not None and len(chosen) >= limit:
                    break
        return chosen

    emerging = take(
        lambda row: (
            row.status != "weak_signal"
            and (_parse_day(row.event_date or row.latest_update) or date.min) >= today - timedelta(days=7)
        ),
        limit=6,
    )
    for row in emerging:
        row.section = "emerging_now"
    for row in take(lambda row: bool(row.weak_signal_label) or row.status == "weak_signal"):
        row.section = "weak_signals"
    for row in take(
        lambda row: any(event.kind == "NEW_SOURCE" for event in row.evolution[-3:]) and row.independent_source_count >= 2
    ):
        row.section = "recently_corroborated"
    for row in take(lambda row: row.event_type in GENETICS_TYPES):
        row.section = "genetics_varieties"
    for row in take(lambda row: row.event_type in COMPETITOR_TYPES):
        row.section = "competitor_moves"
    for row in take(lambda row: row.event_type in MARKET_TYPES):
        row.section = "market_supply"
    for row in take(lambda row: row.event_type in REGULATORY_TYPES):
        row.section = "regulatory_ip"
    for row in ranked:
        if row.id not in claimed:
            row.section = "worth_watching"
            claimed.add(row.id)
    return ranked


def build_sections(developments: list[Development]) -> list[dict[str, Any]]:
    by_key: dict[str, list[Development]] = {key: [] for key, _, _ in SECTION_DEFS}
    for row in developments:
        by_key.setdefault(row.section, []).append(row)
    sections = []
    for key, title, kicker in SECTION_DEFS:
        items = by_key.get(key) or []
        if not items:
            continue
        sections.append(
            {
                "key": key,
                "title": title,
                "kicker": kicker,
                "developments": [item.as_dict() for item in items],
            }
        )
    return sections


def compose_edition(
    developments: list[Development],
    *,
    generated_at: str,
    window: str,
    latency_seconds: float,
    cache_status: str,
    expires_at: str | None,
    stats: dict[str, Any],
    query_failures: list[dict[str, str]] | None = None,
    provider_telemetry: dict[str, dict[str, int]] | None = None,
    today: date | None = None,
) -> RadarEdition:
    today = today or datetime.now(timezone.utc).date()
    for development in developments:
        development.radar_reasons = radar_reasons(development, watches=development.watchlist_matches, today=today)
        development.google_stack_would_find = any(
            source.provider in GOOGLE_STACK_PROVIDERS for source in development.sources
        )
        if any(is_social_host(source.domain) for source in development.sources) and not any(
            (not source.social and not source.syndicated) for source in development.sources
        ):
            development.weak_signal_label = development.weak_signal_label or "COMMUNITY / CHATTER — UNVERIFIED"
        elif any((not source.social and not source.syndicated) for source in development.sources):
            development.weak_signal_label = None
        development.trust_state = TRUST_LIVE
    ranked = sorted(developments, key=lambda row: _rank_tuple(row, today=today), reverse=True)
    board = ranked[:BOARD_LIMIT]
    assign_sections(board, today=today)
    for row in ranked[BOARD_LIMIT:]:
        row.section = ""
    stats = {**stats, "board": len(board), "catalog": len(ranked)}
    freshness = generated_at.replace("T", " ")[:16] + " UTC"
    return RadarEdition(
        generated_at=generated_at,
        window=window,
        latency_seconds=latency_seconds,
        freshness_label=f"Refreshed {freshness}",
        cache_status=cache_status,
        expires_at=expires_at,
        trust_label=TRUST_LIVE,
        developments=ranked,
        sections=build_sections(board),
        stats=stats,
        query_failures=query_failures or [],
        provider_telemetry=provider_telemetry or {},
    )


def load_watchlist(inbox_dir) -> list[dict[str, Any]]:
    return load_watches(inbox_dir)
