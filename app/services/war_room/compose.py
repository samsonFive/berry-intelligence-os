"""Compose a War Room session -- prioritized, not a dashboard dump.

Every section below reads an existing subsystem's own output and filters/
ranks it to the session scope. Nothing here fetches a live provider or
persists anything; "live refresh" is the caller's job (refresh /radar/live
first, same as /moves and /watchtower already require).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from app.services.company_workspace import present_company_compare
from app.services.competitive_moves.board import compose_moves_board
from app.services.competitive_moves.research_desk import competitive_moves_for
from app.services.emerging_radar.cache import edition_from_cache
from app.services.emerging_radar.research_desk import developments_for
from app.services.geography_hierarchy import resolve_geography_scope
from app.services.market_reality.research_desk import market_reality_for
from app.services.war_room.discussion_questions import generate_discussion_questions
from app.services.war_room.models import WarRoomScope
from app.services.war_room.notes import list_notes_for_scope
from app.services.watchlist import is_watched
from app.services.watchtower.generate import generate_alerts
from app.services.whitespace_radar import compose_whitespace_landscape

_GENETICS_IP_MOVE_TYPES = {"GENETICS_LAUNCH", "VARIETY_COMMERCIALIZATION", "LICENSING", "PBR / IP", "R&D / TECHNOLOGY"}
_GENETICS_IP_EVENT_TYPES = {"GENETICS_INNOVATION", "VARIETY_LAUNCH", "PBR", "PATENT"}
_TIMEFRAME_BY_DAYS = ((1, "24h"), (7, "7d"), (30, "30d"), (90, "90d"))


def _timeframe_for(window_days: int) -> str:
    for days, label in _TIMEFRAME_BY_DAYS:
        if window_days <= days:
            return label
    return "90d"


def _within(date_str: str | None, *, cutoff_days: int, now: datetime) -> bool:
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
        return (now - parsed).days <= cutoff_days
    return False


def _all_geography_ids(geography_ids: tuple[str, ...], *, relationships: list[dict[str, Any]]) -> set[str]:
    """A region (e.g. geography-europe) expands to its member countries;
    a plain country contributes only itself -- see
    geography_hierarchy.resolve_geography_scope()."""
    out: set[str] = set()
    for gid in geography_ids:
        out |= resolve_geography_scope(gid, relationships=relationships).all_ids
    return out


def _move_matches_scope(move: Any, *, company_ids: set[str], geo_ids: set[str], berry_id: str | None) -> bool:
    if company_ids and move.company_id not in company_ids:
        return False
    if geo_ids and not geo_ids.intersection(move.geography_ids):
        return False
    if berry_id and berry_id not in move.berry_ids:
        return False
    return True


def compose_war_room(
    scope: WarRoomScope,
    *,
    inbox_dir: Path,
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    strategic_questions: list[dict[str, Any]],
    berry_labels: dict[str, str],
    identity_redirects: list[dict[str, Any]] | None = None,
    market_repo: Any | None = None,
    completer: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    instant = now or datetime.now(UTC)
    company_ids = set(scope.company_ids)
    geo_ids = _all_geography_ids(scope.geography_ids, relationships=relationships)
    berry_label = berry_labels.get(scope.berry_id or "", "") if scope.berry_id else ""
    geography_labels = [entities.get(g, {}).get("name") or g for g in scope.geography_ids]
    company_labels = [entities.get(c, {}).get("name") or c for c in company_ids]

    edition = edition_from_cache(inbox_dir=inbox_dir)
    all_developments = list(edition.developments) if edition else []
    board = compose_moves_board(all_developments, inbox_dir=inbox_dir)

    scoped_moves = [
        m for m in board.moves
        if _move_matches_scope(m, company_ids=company_ids, geo_ids=geo_ids, berry_id=scope.berry_id)
    ]
    scoped_moves.sort(key=lambda m: m.latest_update, reverse=True)

    # Strategic Whitespace Radar needs a company x geography grid -- only
    # call it when the scope actually has both dimensions (a company-only
    # or geography-less scope, e.g. "Hortifrut, global, 90 days", has no
    # grid to build). Reused verbatim, never re-derived: coverage_gaps
    # becomes this session's honest "what we don't know" section, overlap
    # becomes "where competitors overlap."
    whitespace = None
    if company_ids and scope.geography_ids and scope.berry_id:
        whitespace_moves = competitive_moves_for(
            berries=[scope.berry_id],
            geography=list(geo_ids) or None,
            timeframe=_timeframe_for(scope.window_days),
            moves=board.moves,
        )
        whitespace = compose_whitespace_landscape(
            berry_id=scope.berry_id,
            company_ids=list(company_ids),
            geography_ids=list(scope.geography_ids),
            window_days=30 if scope.window_days > 7 else 7,
            entities=entities,
            relationships=relationships,
            published_evidence=published_evidence,
            moves=whitespace_moves,
            market_repo=market_repo,
        )

    scoped_developments = developments_for(
        company_ids=company_ids or None,
        berry_ids={scope.berry_id} if scope.berry_id else None,
        geography_ids=geo_ids or None,
        timeframe=_timeframe_for(scope.window_days),
        developments=all_developments,
        today=instant.date(),
    )
    moved_development_ids = {dev_id for m in scoped_moves for dev_id in m.supporting_development_ids}
    emerging_only = [d for d in scoped_developments if d["id"] not in moved_development_ids]
    emerging_only.sort(key=lambda d: d.get("latest_update") or "", reverse=True)

    market_changes: list[dict[str, Any]] = []
    if market_repo is not None:
        geo_filter_ids = scope.geography_ids or (None,)
        seen_series: set[str] = set()
        for gid in geo_filter_ids:
            result = market_reality_for(
                market_repo,
                berry_id=scope.berry_id or None,
                geography_id=gid,
            )
            for label, changes in result["change_by_series"].items():
                change = changes.get("latest_vs_previous")
                if not change or change.get("pct_change") is None or label in seen_series:
                    continue
                seen_series.add(label)
                metric, code, _form, geography = label.split("|", 3)
                series_rows = [o for o in result["observations"] if o.get("metric") == metric and o.get("geography") == geography]
                source_row = series_rows[-1] if series_rows else {}
                market_changes.append(
                    {
                        "metric": metric,
                        "commodity_label": source_row.get("source_commodity_label") or code,
                        "geography_label": geography,
                        "pct_change": change["pct_change"],
                        "direction": change["direction"],
                        "previous_period": change["previous_period"],
                        "latest_period": change["latest_period"],
                        "previous_value": change["previous_value"],
                        "latest_value": change["latest_value"],
                        "unit": change["unit"],
                        "source": source_row.get("source"),
                        "source_dataset": source_row.get("source_dataset"),
                        "source_url": source_row.get("source_url"),
                    }
                )
        market_changes.sort(key=lambda c: abs(c["pct_change"]), reverse=True)

    # NEEDS ATTENTION: the session's own scope stands in for a Watchlist --
    # ephemeral, never persisted, so opening a War Room never writes a real
    # Watch or a real Alert on the operator's behalf (mission section 19:
    # GET/render must not mutate).
    synthetic_watches = [{"watch_type": "company", "object_id": cid} for cid in company_ids]
    synthetic_watches += [{"watch_type": "geography", "object_id": gid} for gid in scope.geography_ids]
    if scope.berry_id:
        synthetic_watches.append({"watch_type": "berry", "object_id": scope.berry_id})
    session_alerts = []
    if synthetic_watches:
        alerts = generate_alerts(
            watches=synthetic_watches, developments=all_developments, board=board,
            market_repo=market_repo, published_evidence=published_evidence,
            strategic_questions=strategic_questions, entities=entities, berry_labels=berry_labels,
            now=instant,
        )
        session_alerts = sorted(alerts, key=lambda a: (a.priority == "HIGH ATTENTION", a.event_at), reverse=True)

    genetics_ip_moves = [m for m in scoped_moves if m.move_type in _GENETICS_IP_MOVE_TYPES]
    genetics_ip_developments = [d for d in scoped_developments if d.get("event_type") in _GENETICS_IP_EVENT_TYPES]

    what_changed: list[dict[str, Any]] = []
    for m in scoped_moves[:6]:
        what_changed.append({"kind": "Competitive Move", "title": f"{m.company_name} — {m.move_label}", "when": m.latest_update, "href": f"/moves/{m.company_id}"})
    for c in market_changes[:4]:
        arrow = "up" if c["direction"] == "up" else ("down" if c["direction"] == "down" else "flat")
        what_changed.append({"kind": "Market Reality", "title": f"{c['geography_label']} {c['commodity_label']} {c['metric'].replace('_',' ').title()} {'+' if arrow=='up' else '-'}{abs(c['pct_change']):.1f}%", "when": c["latest_period"], "href": "/today"})
    for record in published_evidence:
        rec_entities = set(record.get("entity_ids") or [])
        rec_geo = set(record.get("geography_ids") or [])
        rec_berry = set(record.get("berry_ids") or [])
        if company_ids and not company_ids & rec_entities:
            continue
        if geo_ids and not geo_ids & rec_geo:
            continue
        if scope.berry_id and scope.berry_id not in rec_berry:
            continue
        if not _within(record.get("published_date"), cutoff_days=scope.window_days, now=instant):
            continue
        what_changed.append({"kind": "Trusted Evidence", "title": str(record.get("title") or record.get("id")), "when": str(record.get("published_date") or ""), "href": f"/evidence/{record.get('id')}"})
    what_changed.sort(key=lambda i: str(i.get("when") or ""), reverse=True)
    what_changed = what_changed[:10]

    key_uncertainties = [
        {
            "title": d.get("title"),
            "why": "Single, unreviewed source" if d.get("corroboration") == "ONE SOURCE" else (d.get("weak_signal_label") or "Unverified community mention"),
            "href": f"/radar/{d.get('id')}",
        }
        for d in scoped_developments
        if d.get("corroboration") == "ONE SOURCE" or d.get("weak_signal_label")
    ][:6]

    scoped_sq = [
        sq for sq in strategic_questions
        if not scope.berry_id or scope.berry_id in (sq.get("berry_ids") or [])
    ][:6]

    company_compare = None
    if len(company_ids) >= 2:
        company_compare = present_company_compare(
            list(company_ids)[:4], entities=entities, relationships=relationships,
            published_evidence=published_evidence, facts=facts,
            evidence_by_id={str(r.get("id")): r for r in published_evidence},
            signals=signals, assessments=assessments, berry_labels=berry_labels,
            redirects=identity_redirects or [],
        )

    watch_next = []
    for cid in company_ids:
        watch_next.append({"label": entities.get(cid, {}).get("name") or cid, "watch_type": "company", "object_id": cid, "already_watched": is_watched(inbox_dir, "company", cid)})
    for gid in scope.geography_ids:
        watch_next.append({"label": entities.get(gid, {}).get("name") or gid, "watch_type": "geography", "object_id": gid, "already_watched": is_watched(inbox_dir, "geography", gid)})
    if scope.berry_id:
        watch_next.append({"label": berry_label, "watch_type": "berry", "object_id": scope.berry_id, "already_watched": is_watched(inbox_dir, "berry", scope.berry_id)})

    questions = generate_discussion_questions(
        moves=[m.as_dict() for m in scoped_moves[:10]], market_changes=market_changes[:6],
        company_labels=company_labels, geography_labels=geography_labels, berry_label=berry_label,
        completer=completer,
    )

    notes = list_notes_for_scope(inbox_dir, berry_id=scope.berry_id, geography_ids=scope.geography_ids, company_ids=scope.company_ids)

    scope_label_parts = [p for p in ([berry_label] + geography_labels + company_labels) if p]
    scope_label = " · ".join(scope_label_parts) or "All berries, all markets"

    brief_query = urlencode(
        {
            k: v for k, v in {
                "berry": scope.berry_id or "",
                "geography_ids": ",".join(scope.geography_ids),
                "company_ids": ",".join(scope.company_ids),
            }.items() if v
        }
    )
    ask_question = f"What should I know about: {scope_label} — last {scope.window_days} days"

    return {
        "scope": scope.as_dict(),
        "scope_label": scope_label,
        "window_days": scope.window_days,
        "radar_freshness_label": edition.freshness_label if edition else "No Radar cache yet — open /radar to load emerging developments, then return here.",
        "executive_snapshot": {
            "moves": len(scoped_moves),
            "developments": len(scoped_developments),
            "market_changes": len(market_changes),
            "needs_attention": len([a for a in session_alerts if a.priority in {"HIGH ATTENTION", "ATTENTION"}]),
            "genetics_ip": len(genetics_ip_moves) + len(genetics_ip_developments),
            "strategic_questions": len(scoped_sq),
            # 3-7 source-grounded findings, each already tagged with its
            # real kind (Competitive Move / Market Reality / Trusted
            # Evidence) -- not a fourth synthesis layer; reuses what_changed
            # verbatim so there is exactly one place this ranking happens.
            "findings": what_changed[:6],
        },
        "what_changed": what_changed,
        "who_is_moving": [m.as_dict() for m in scoped_moves[:10]],
        "needs_attention": [a.as_dict() for a in session_alerts[:10]],
        "coverage_unknown": whitespace["coverage_gaps"] if whitespace else [],
        "competitive_overlap": whitespace["overlap"] if whitespace else [],
        "landscape_questions": whitespace["questions"] if whitespace else [],
        "whitespace_watch_next": whitespace["watch_next"] if whitespace else [],
        "whitespace_href": (
            f"/whitespace?berry={scope.berry_id}&companies={','.join(company_ids)}&geographies={','.join(scope.geography_ids)}&window={scope.window_days}"
            if whitespace else None
        ),
        "competitive_positioning": company_compare,
        "market_reality": market_changes[:8],
        "genetics_ip": {
            "moves": [m.as_dict() for m in genetics_ip_moves[:6]],
            "developments": genetics_ip_developments[:6],
        },
        "emerging_developments": emerging_only[:8],
        "key_uncertainties": key_uncertainties,
        "questions_for_team": questions,
        "strategic_questions": scoped_sq,
        "watch_next": watch_next,
        "notes": notes,
        "ask_berry_os_href": f"/research?{urlencode({'q': ask_question})}",
        "compare_href": f"/entities/company/compare?ids={','.join(list(company_ids)[:4])}" if len(company_ids) >= 2 else None,
        "create_meeting_brief_href": f"/reports/new?{brief_query}" if brief_query else "/reports/new",
        "watchtower_href": "/watchtower",
    }
