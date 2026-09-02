"""Deterministic alert generation.

Pure over already-cached state: the current Radar cache, the Moves board
derived from it, the Market Observation store, and canonical published
Evidence -- never fetches a provider itself (that is Radar's `/radar/live`
job, section 9 of the mission: "Radar discovers. Competitive Moves
classify. Watchtower decides whether a watch should be notified.").

Every alert requires an explicit watch match. No opaque importance score
anywhere -- `why_triggered` and `priority_reasons` are always human-
readable strings a stakeholder can read and agree or disagree with.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from app.services.competitive_moves.models import MOVE_LABELS, CompanyPattern, CompetitiveMove, MovesBoard
from app.services.emerging_radar.models import Development
from app.services.market_reality.research_desk import market_reality_for
from app.services.watchtower.models import PRIORITY_ATTENTION, PRIORITY_FYI, PRIORITY_HIGH, Alert

# How far back an underlying thing's own date must fall for a "new" alert
# to fire on it -- a first Watchtower run against a mature corpus must not
# replay years of history as if it all just happened (mission section 16:
# "A Watchtower that cries wolf is a failed product").
RECENCY_WINDOW_DAYS = 30

# Same materiality bar Radar's own `attach_market_context` already applies
# when cross-referencing Market Reality into a Development (3x that bar,
# tuned against real production data during this mission's own acceptance
# pass -- see docs/v2/WATCHTOWER-ALERTS-V1.md section "Signal-to-noise").
MARKET_CHANGE_THRESHOLD_PCT = 15.0

_FORECAST_SUFFIX = "f"

# Weak-signal Developments need at least one independent source before they
# are alert-worthy -- a lone unreviewed mention should not page an analyst
# (mirrors Competitive Moves' own `_development_eligible` eligibility gate).
_ALERTABLE_EVENT_STATUSES = {"emerging"}


def _alert_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"wta-{digest}"


def _within_window(date_str: str | None, *, now: datetime, days: int = RECENCY_WINDOW_DAYS) -> bool:
    if not date_str:
        return False
    raw = str(date_str)[:19].replace("Z", "")
    for candidate in (raw, raw[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return (now - parsed).days <= days
    return False


def _ask_berry_os_href(title: str, *, company_names: tuple[str, ...] = (), geography_labels: tuple[str, ...] = ()) -> str:
    parts = [title]
    parts.extend(str(n) for n in company_names[:2])
    parts.extend(str(g) for g in geography_labels[:2])
    question = "What should I know about: " + " -- ".join(p for p in parts if p)
    return f"/research?{urlencode({'q': question})}"


def _create_brief_href(*, company_ids: tuple[str, ...] = (), geography_ids: tuple[str, ...] = (), berry_ids: tuple[str, ...] = ()) -> str:
    query: dict[str, str] = {}
    if company_ids:
        query["company_ids"] = ",".join(company_ids[:6])
    if geography_ids:
        query["geography_ids"] = ",".join(geography_ids[:6])
    if berry_ids:
        query["berry"] = berry_ids[0]
    return f"/reports/new?{urlencode(query)}" if query else "/reports/new"


def _priority(reasons: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    if len(reasons) >= 3:
        return PRIORITY_HIGH, reasons
    if len(reasons) >= 2:
        return PRIORITY_ATTENTION, reasons
    return PRIORITY_FYI, reasons


def _subject_label(watch_type: str, object_id: str, *, entities: dict[str, dict[str, Any]], berry_labels: dict[str, str], sq_by_id: dict[str, dict[str, Any]]) -> str:
    if watch_type == "berry":
        return berry_labels.get(object_id, object_id)
    if watch_type == "move_type":
        return MOVE_LABELS.get(object_id, object_id)
    if watch_type == "strategic_question":
        sq = sq_by_id.get(object_id)
        return str(sq.get("title")) if sq and sq.get("title") else object_id
    entity = entities.get(object_id) or {}
    return str(entity.get("name")) if entity.get("name") else object_id


def _development_matches(dev: Development, watch_type: str, object_id: str) -> bool:
    if watch_type == "company":
        return object_id in dev.company_ids
    if watch_type == "variety":
        return object_id in dev.variety_ids
    if watch_type == "geography":
        return object_id in dev.geography_ids
    if watch_type == "berry":
        return object_id in dev.berry_ids
    return False


def _move_matches(move: CompetitiveMove, watch_type: str, object_id: str) -> bool:
    if watch_type == "company":
        return move.company_id == object_id
    if watch_type == "variety":
        return object_id in move.variety_ids
    if watch_type == "geography":
        return object_id in move.geography_ids
    if watch_type == "berry":
        return object_id in move.berry_ids
    if watch_type == "move_type":
        return move.move_type == object_id
    return False


def _market_reality_changes(repo: Any) -> list[dict[str, Any]]:
    """Adapter mirroring `market_reality.research_desk.market_reality_for`'s
    own highlight-building logic, but keeping geography_id/berry_id per row
    -- `market_reality_highlights()` intentionally only carries display
    labels (three other consumers already depend on that shape), so this
    stays a local, separate adapter rather than widening that contract."""
    result = market_reality_for(repo)
    rows: list[dict[str, Any]] = []
    for label, changes in result["change_by_series"].items():
        change = changes.get("latest_vs_previous")
        if not change or change.get("pct_change") is None:
            continue
        if str(change["latest_period"]).endswith(_FORECAST_SUFFIX) and str(change["previous_period"]).endswith(_FORECAST_SUFFIX):
            continue
        metric, commodity_code, _form, geography = label.split("|", 3)
        series_rows = [
            o for o in result["observations"]
            if o.get("metric") == metric and o.get("source_commodity_code") == commodity_code and o.get("geography") == geography
        ]
        source_row = series_rows[-1] if series_rows else {}
        # Real records populate both the singular id and the plural graph-
        # connection array identically (see market-observation.schema.json);
        # falling back to the singular field keeps this robust for any
        # caller/fixture that only sets one.
        geography_ids = source_row.get("geography_ids") or ([source_row["geography_id"]] if source_row.get("geography_id") else [])
        berry_ids = source_row.get("berry_ids") or ([source_row["berry_id"]] if source_row.get("berry_id") else [])
        rows.append(
            {
                "series_key": label,
                "metric": metric,
                "commodity_label": source_row.get("source_commodity_label") or commodity_code,
                "geography": geography,
                "geography_id": geography_ids[0] if geography_ids else None,
                "berry_id": berry_ids[0] if berry_ids else None,
                "unit": change["unit"],
                "previous_period": change["previous_period"],
                "previous_value": change["previous_value"],
                "latest_period": change["latest_period"],
                "latest_value": change["latest_value"],
                "direction": change["direction"],
                "pct_change": change["pct_change"],
                "source": source_row.get("source"),
                "source_dataset": source_row.get("source_dataset"),
                "source_url": source_row.get("source_url"),
                "captured_at": source_row.get("captured_at"),
            }
        )
    return rows


def generate_alerts(
    *,
    watches: list[dict[str, Any]],
    developments: list[Development],
    board: MovesBoard,
    market_repo: Any | None,
    published_evidence: list[dict[str, Any]],
    strategic_questions: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    now: datetime | None = None,
    market_threshold_pct: float = MARKET_CHANGE_THRESHOLD_PCT,
) -> list[Alert]:
    instant = now or datetime.now(UTC)
    generated_at = instant.isoformat(timespec="seconds")
    sq_by_id = {str(q.get("id")): q for q in strategic_questions if q.get("id")}
    alerts: dict[str, Alert] = {}
    watch_rows = [w for w in watches if w.get("watch_type") and w.get("object_id")]

    def subject_label(watch_type: str, object_id: str) -> str:
        return _subject_label(watch_type, object_id, entities=entities, berry_labels=berry_labels, sq_by_id=sq_by_id)

    def upsert(alert: Alert) -> None:
        existing = alerts.get(alert.id)
        if existing is not None:
            alert.first_generated_at = existing.first_generated_at
        alerts[alert.id] = alert

    # -- Developments: NEW_DEVELOPMENT / DEVELOPMENT_UPDATED / PBR / patent --
    for dev in developments:
        if dev.status not in _ALERTABLE_EVENT_STATUSES and not dev.independent_source_count:
            continue  # signal-to-noise: a lone weak signal doesn't page anyone
        anchor_date = dev.event_date or dev.latest_update or dev.first_seen
        if not _within_window(anchor_date, now=instant):
            continue
        for watch in watch_rows:
            wt, oid = str(watch["watch_type"]), str(watch["object_id"])
            if not _development_matches(dev, wt, oid):
                continue
            label = subject_label(wt, oid)
            reasons = [f"Watched {wt.replace('_', ' ')}: {label}"]
            if dev.corroboration and dev.corroboration != "ONE SOURCE":
                reasons.append(f"Corroboration: {dev.corroboration.lower()}")
            if any(s.official for s in dev.sources):
                reasons.append("Primary-source corroboration")
            if len(dev.company_ids) + len(dev.geography_ids) > 1:
                reasons.append("Names a watched competitor and geography together")
            priority, reasons_t = _priority(tuple(reasons))
            ask_href = _ask_berry_os_href(dev.title, company_names=dev.company_names, geography_labels=dev.geography_labels)
            brief_href = _create_brief_href(company_ids=dev.company_ids, geography_ids=dev.geography_ids, berry_ids=dev.berry_ids)
            upsert(
                Alert(
                    id=_alert_id("NEW_DEVELOPMENT", wt, oid, dev.id),
                    trigger_type="NEW_DEVELOPMENT",
                    subject_type=wt,
                    subject_id=oid,
                    subject_label=label,
                    title=dev.title,
                    what_happened=dev.what_happened,
                    why_triggered=reasons_t,
                    priority=priority,
                    priority_reasons=reasons_t,
                    generated_at=generated_at,
                    first_generated_at=generated_at,
                    event_at=anchor_date,
                    sources=[{"url": s.url, "title": s.title, "publisher": s.publisher} for s in dev.sources[:3]],
                    trust_state=dev.trust_state,
                    related_development_id=dev.id,
                    market_context=dev.market_context,
                    trusted_context=list(dev.trusted_context or [])[:3],
                    open_href=f"/radar/{dev.id}",
                    ask_berry_os_href=ask_href,
                    create_brief_href=brief_href,
                )
            )

            if len(dev.evolution) > 1:
                latest_event = dev.evolution[-1]
                update_reasons = [f"Watched {wt.replace('_', ' ')}: {label}", f"{latest_event.kind.replace('_', ' ').title()}: {latest_event.detail[:120]}"]
                if dev.corroboration and dev.corroboration != "ONE SOURCE":
                    update_reasons.append(f"Corroboration: {dev.corroboration.lower()}")
                priority_u, reasons_u = _priority(tuple(update_reasons))
                upsert(
                    Alert(
                        id=_alert_id("DEVELOPMENT_UPDATED", wt, oid, dev.id),
                        trigger_type="DEVELOPMENT_UPDATED",
                        subject_type=wt,
                        subject_id=oid,
                        subject_label=label,
                        title=f"{dev.title} — updated",
                        what_happened=dev.what_happened,
                        why_triggered=reasons_u,
                        priority=priority_u,
                        priority_reasons=reasons_u,
                        generated_at=generated_at,
                        first_generated_at=generated_at,
                        event_at=dev.latest_update,
                        sources=[{"url": s.url, "title": s.title, "publisher": s.publisher} for s in dev.sources[:3]],
                        trust_state=dev.trust_state,
                        related_development_id=dev.id,
                        market_context=dev.market_context,
                        trusted_context=list(dev.trusted_context or [])[:3],
                        open_href=f"/radar/{dev.id}",
                        ask_berry_os_href=ask_href,
                        create_brief_href=brief_href,
                    )
                )

            if dev.event_type in {"PBR", "PATENT"}:
                trigger = "NEW_PBR_RIGHTS_EVENT" if dev.event_type == "PBR" else "NEW_PATENT_IP_EVENT"
                ip_reasons = [f"Watched {wt.replace('_', ' ')}: {label}", f"Event type: {dev.event_type}"]
                if any(s.registry for s in dev.sources):
                    ip_reasons.append("Registry / official filing source")
                priority_ip, reasons_ip = _priority(tuple(ip_reasons))
                upsert(
                    Alert(
                        id=_alert_id(trigger, wt, oid, dev.id),
                        trigger_type=trigger,
                        subject_type=wt,
                        subject_id=oid,
                        subject_label=label,
                        title=dev.title,
                        what_happened=dev.what_happened,
                        why_triggered=reasons_ip,
                        priority=priority_ip,
                        priority_reasons=reasons_ip,
                        generated_at=generated_at,
                        first_generated_at=generated_at,
                        event_at=anchor_date,
                        sources=[{"url": s.url, "title": s.title, "publisher": s.publisher} for s in dev.sources[:3]],
                        trust_state=dev.trust_state,
                        related_development_id=dev.id,
                        market_context=dev.market_context,
                        trusted_context=list(dev.trusted_context or [])[:3],
                        open_href=f"/radar/{dev.id}",
                        ask_berry_os_href=ask_href,
                        create_brief_href=brief_href,
                    )
                )

    # -- Competitive Moves: NEW_COMPETITIVE_MOVE --
    for move in board.moves:
        if not _within_window(move.latest_update, now=instant):
            continue
        for watch in watch_rows:
            wt, oid = str(watch["watch_type"]), str(watch["object_id"])
            if not _move_matches(move, wt, oid):
                continue
            label = subject_label(wt, oid)
            reasons = [f"Watched {wt.replace('_', ' ')}: {label}"]
            reasons.extend(move.why_move[:3])
            priority, reasons_t = _priority(tuple(dict.fromkeys(reasons)))
            ask_href = _ask_berry_os_href(move.title, company_names=(move.company_name,), geography_labels=move.geography_labels)
            brief_href = _create_brief_href(company_ids=(move.company_id,), geography_ids=move.geography_ids, berry_ids=move.berry_ids)
            upsert(
                Alert(
                    id=_alert_id("NEW_COMPETITIVE_MOVE", wt, oid, move.id),
                    trigger_type="NEW_COMPETITIVE_MOVE",
                    subject_type=wt,
                    subject_id=oid,
                    subject_label=label,
                    title=f"{move.company_name} — {move.move_label}",
                    what_happened=move.what_happened,
                    why_triggered=reasons_t,
                    priority=priority,
                    priority_reasons=reasons_t,
                    generated_at=generated_at,
                    first_generated_at=generated_at,
                    event_at=move.latest_update,
                    sources=list(move.supporting_sources[:3]),
                    trust_state=move.trust_state,
                    related_move_id=move.id,
                    market_context=move.market_context,
                    trusted_context=list(move.trusted_context or [])[:3],
                    open_href=f"/moves/{move.company_id}",
                    ask_berry_os_href=ask_href,
                    create_brief_href=brief_href,
                )
            )

            if move.strategic_questions:
                for sq in move.strategic_questions:
                    sq_id = str(sq.get("id") or "")
                    if not any(w.get("watch_type") == "strategic_question" and str(w.get("object_id")) == sq_id for w in watch_rows):
                        continue
                    sq_label = subject_label("strategic_question", sq_id)
                    sq_reasons = [f"Watched Strategic Question: {sq_label}", f"New Competitive Move: {move.company_name} — {move.move_label}"]
                    priority_sq, reasons_sq = _priority(tuple(sq_reasons))
                    upsert(
                        Alert(
                            id=_alert_id("WATCHED_STRATEGIC_QUESTION_MATCH", "strategic_question", sq_id, move.id),
                            trigger_type="WATCHED_STRATEGIC_QUESTION_MATCH",
                            subject_type="strategic_question",
                            subject_id=sq_id,
                            subject_label=sq_label,
                            title=f"{move.company_name} — {move.move_label} bears on: {sq_label}",
                            what_happened=move.what_happened,
                            why_triggered=reasons_sq,
                            priority=priority_sq,
                            priority_reasons=reasons_sq,
                            generated_at=generated_at,
                            first_generated_at=generated_at,
                            event_at=move.latest_update,
                            sources=list(move.supporting_sources[:3]),
                            trust_state=move.trust_state,
                            related_move_id=move.id,
                            market_context=move.market_context,
                            trusted_context=list(move.trusted_context or [])[:3],
                            open_href=f"/moves/{move.company_id}",
                            ask_berry_os_href=_ask_berry_os_href(sq_label, company_names=(move.company_name,)),
                            create_brief_href=_create_brief_href(company_ids=(move.company_id,), geography_ids=move.geography_ids, berry_ids=move.berry_ids),
                        )
                    )

    # -- Company patterns: REPEATED_MOVE_PATTERN --
    for pattern in board.patterns:
        if not _within_window(pattern.latest_update, now=instant):
            continue
        for watch in watch_rows:
            wt, oid = str(watch["watch_type"]), str(watch["object_id"])
            if wt != "company" or oid != pattern.company_id:
                continue
            label = subject_label(wt, oid)
            reasons = [f"Watched company: {label}", pattern.why, f"{pattern.move_count} related moves in this theme"]
            priority, reasons_t = _priority(tuple(reasons))
            upsert(
                Alert(
                    id=_alert_id("REPEATED_MOVE_PATTERN", wt, oid, pattern.theme),
                    trigger_type="REPEATED_MOVE_PATTERN",
                    subject_type=wt,
                    subject_id=oid,
                    subject_label=label,
                    title=f"{pattern.company_name} — {pattern.label}",
                    what_happened=pattern.why,
                    why_triggered=reasons_t,
                    priority=priority,
                    priority_reasons=reasons_t,
                    generated_at=generated_at,
                    first_generated_at=generated_at,
                    event_at=pattern.latest_update,
                    trust_state="LIVE / UNREVIEWED MOVE",
                    open_href=f"/moves/{pattern.company_id}",
                    ask_berry_os_href=_ask_berry_os_href(f"{pattern.company_name} {pattern.label}", company_names=(pattern.company_name,)),
                    create_brief_href=_create_brief_href(company_ids=(pattern.company_id,)),
                )
            )

    # -- Market Reality: MARKET_REALITY_CHANGE --
    if market_repo is not None:
        for change in _market_reality_changes(market_repo):
            if abs(change["pct_change"]) < market_threshold_pct:
                continue
            for watch in watch_rows:
                wt, oid = str(watch["watch_type"]), str(watch["object_id"])
                if wt == "geography" and change.get("geography_id") != oid:
                    continue
                if wt == "berry" and change.get("berry_id") != oid:
                    continue
                if wt not in {"geography", "berry"}:
                    continue
                label = subject_label(wt, oid)
                arrow = "up" if change["direction"] == "up" else ("down" if change["direction"] == "down" else "flat")
                headline = (
                    f"{change['geography']} {change['commodity_label']} — {change['metric'].replace('_', ' ').title()} "
                    f"{'+' if arrow == 'up' else ('-' if arrow == 'down' else '')}{abs(change['pct_change']):.1f}% "
                    f"({change['previous_period']} → {change['latest_period']})"
                )
                reasons = [
                    f"Watched {wt}: {label}",
                    f"Material {arrow} move of {abs(change['pct_change']):.1f}% (threshold {market_threshold_pct:.0f}%)",
                    f"Source: {change.get('source') or 'unknown'} / {change.get('source_dataset') or 'unknown'}",
                ]
                priority, reasons_t = _priority(tuple(reasons))
                upsert(
                    Alert(
                        id=_alert_id("MARKET_REALITY_CHANGE", wt, oid, str(change["series_key"])),
                        trigger_type="MARKET_REALITY_CHANGE",
                        subject_type=wt,
                        subject_id=oid,
                        subject_label=label,
                        title=headline,
                        what_happened=(
                            f"{change['previous_value']:,.0f} → {change['latest_value']:,.0f} {change['unit']} "
                            f"({change['previous_period']} to {change['latest_period']})"
                        ),
                        why_triggered=reasons_t,
                        priority=priority,
                        priority_reasons=reasons_t,
                        generated_at=generated_at,
                        first_generated_at=generated_at,
                        event_at=change.get("captured_at") or generated_at,
                        sources=[{"url": change.get("source_url") or "", "title": change.get("source_dataset") or "", "publisher": change.get("source") or ""}],
                        trust_state="MARKET REALITY",
                        market_context={"disclaimer": "Structured, sourced measurement. Not a claim of cause.", "rows": [{"label": headline}]},
                        open_href="/today",
                        ask_berry_os_href=_ask_berry_os_href(headline, geography_labels=(change["geography"],) if wt == "geography" else ()),
                        create_brief_href=_create_brief_href(geography_ids=(oid,) if wt == "geography" else (), berry_ids=(oid,) if wt == "berry" else ()),
                    )
                )

    # -- Trusted Evidence: NEW_TRUSTED_EVIDENCE + WATCHED_STRATEGIC_QUESTION_MATCH --
    for record in published_evidence:
        published_date = record.get("published_date")
        if not _within_window(published_date, now=instant):
            continue
        entity_ids = set(record.get("entity_ids") or [])
        geography_ids = set(record.get("geography_ids") or [])
        berry_ids = set(record.get("berry_ids") or [])
        sq_ids = set(record.get("strategic_question_ids") or [])
        record_id = str(record.get("id") or "")
        title = str(record.get("title") or record.get("claim_text") or record_id)
        href = f"/evidence/{record_id}" if record_id else "/today"
        for watch in watch_rows:
            wt, oid = str(watch["watch_type"]), str(watch["object_id"])
            matched = (
                (wt == "company" and oid in entity_ids)
                or (wt == "variety" and oid in entity_ids)
                or (wt == "geography" and oid in geography_ids)
                or (wt == "berry" and oid in berry_ids)
            )
            if matched:
                label = subject_label(wt, oid)
                reasons = [f"Watched {wt}: {label}", "Reviewed, trusted Evidence — not a live/unreviewed mention"]
                priority, reasons_t = _priority(tuple(reasons))
                upsert(
                    Alert(
                        id=_alert_id("NEW_TRUSTED_EVIDENCE", wt, oid, record_id),
                        trigger_type="NEW_TRUSTED_EVIDENCE",
                        subject_type=wt,
                        subject_id=oid,
                        subject_label=label,
                        title=title,
                        what_happened=str(record.get("summary") or "")[:400],
                        why_triggered=reasons_t,
                        priority=priority,
                        priority_reasons=reasons_t,
                        generated_at=generated_at,
                        first_generated_at=generated_at,
                        event_at=str(published_date or ""),
                        trust_state="REVIEWED EVIDENCE",
                        open_href=href,
                        ask_berry_os_href=_ask_berry_os_href(title),
                        create_brief_href=_create_brief_href(company_ids=tuple(entity_ids), geography_ids=tuple(geography_ids), berry_ids=tuple(berry_ids)),
                    )
                )
            if wt == "strategic_question" and oid in sq_ids:
                label = subject_label(wt, oid)
                reasons = [f"Watched Strategic Question: {label}", "New reviewed Evidence linked to this question"]
                priority, reasons_t = _priority(tuple(reasons))
                upsert(
                    Alert(
                        id=_alert_id("WATCHED_STRATEGIC_QUESTION_MATCH", wt, oid, record_id),
                        trigger_type="WATCHED_STRATEGIC_QUESTION_MATCH",
                        subject_type=wt,
                        subject_id=oid,
                        subject_label=label,
                        title=f"New Evidence bears on: {label}",
                        what_happened=title,
                        why_triggered=reasons_t,
                        priority=priority,
                        priority_reasons=reasons_t,
                        generated_at=generated_at,
                        first_generated_at=generated_at,
                        event_at=str(published_date or ""),
                        trust_state="REVIEWED EVIDENCE",
                        open_href=href,
                        ask_berry_os_href=_ask_berry_os_href(label),
                        create_brief_href=_create_brief_href(),
                    )
                )

    return list(alerts.values())
