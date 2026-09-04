"""Executive Decision Memo -- a report_type "mode" on the existing Reports
architecture, not a second document engine.

Unlike the generic report types (which source from `build_report_packet()`
and dispatch through `synthesis.py`'s `SECTION_DEFS`/`_structured_prose()`
table, both keyed to a Company/Variety/Evidence-shaped packet), a Decision
Memo's packet sources from `app.services.war_room.compose.compose_war_room()`
-- richer, differently shaped (Moves/Market Reality/Whitespace/Watchtower
alerts), and self-contained: `build_decision_memo_packet()` takes only a
`ResolvedScope`, exactly the same contract `build_report_packet()` offers,
so `/reports/{id}/section/{id}/regenerate` and `/reports/{id}/export.pdf`
can rebuild it from the persisted `report["scope"]` alone, with no
dependency on the original War Room session that created it.

PROVIDER SECURITY BOUNDARY -- same discipline as synthesis.py, not weakened:
only item id/title/date/kind-label ever reaches a grounding digest sent to
the model (never a Move's full `what_happened`, an Alert's `why_triggered`
rationale, or Evidence beyond title/source/date). Every section's
citation_ids are validated against the packet's own `known_ids` before
being shown; an ungrounded claim degrades to INSUFFICIENT, never rendered.

PLAUSIBLE SCENARIOS / WHAT WOULD CONFIRM-REFUTE are a pluggable seam
(`scenario_provider`), disconnected until Grok's separate Change & Scenario
Engine PR lands -- see `_section_plausible_scenarios()`. Both sections are
omitted entirely (not a placeholder) while disconnected, matching "do not
show empty sections."
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from app.services.report_builder.scope import ResolvedScope
from app.services.report_builder.synthesis import SectionDraft
from app.services.war_room.compose import compose_war_room
from app.services.war_room.models import WarRoomScope

MODEL_DEFAULT = "anthropic/claude-haiku-4-5"

SECTION_TITLES: dict[str, str] = {
    "executive_takeaway": "Executive Takeaway",
    "what_changed": "What Changed",
    "competitive_moves": "Competitive Moves",
    "market_reality": "Market Reality",
    "genetics_ip": "Genetics / IP",
    "competitive_positioning": "Competitive Positioning",
    "what_we_know": "What We Know",
    "what_we_do_not_know": "What We Do Not Know",
    "plausible_scenarios": "Plausible Scenarios",
    "confirm_refute": "What Would Confirm / Refute",
    "watch_next": "What To Watch Next",
    "questions_for_team": "Questions For The Team",
    "sources_provenance": "Sources / Provenance",
    "internal_data_needed": "Internal Data Needed",
}


# ---------------------------------------------------------------------------
# Packet building -- self-contained from ResolvedScope alone.
# ---------------------------------------------------------------------------


def build_decision_memo_packet(
    scope: ResolvedScope,
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
    war_room_scope = WarRoomScope(
        berry_id=scope.berry_id,
        geography_ids=tuple(scope.geography_ids),
        company_ids=tuple(scope.company_ids),
        window_days=scope.date_window_days or 30,
    )
    session = compose_war_room(
        war_room_scope,
        inbox_dir=inbox_dir,
        entities=entities,
        relationships=relationships,
        published_evidence=published_evidence,
        facts=facts,
        signals=signals,
        assessments=assessments,
        strategic_questions=strategic_questions,
        berry_labels=berry_labels,
        identity_redirects=identity_redirects,
        market_repo=market_repo,
        completer=completer,
        now=now,
    )

    # One index, keyed by id, covering every citable thing this packet's
    # sections might reference -- what_changed, competitive_moves, market
    # reality series, and whitespace company x geography cells. known_ids
    # (citation validation) and source_trace (the report_workspace.html
    # "Sources" appendix every citation_id anchors to via #src-{id}) are
    # both derived from this one index, so a citation can never point at
    # an id with no corresponding source row.
    source_index: dict[str, dict[str, Any]] = {}
    for row in session["what_changed"]:
        if row.get("id"):
            source_index[str(row["id"])] = {
                "id": row["id"], "title": row["title"], "href": row["href"],
                "source_name": row["kind"], "date": row.get("when") or "",
            }
    for m in session["who_is_moving"]:
        if m.get("id") and m["id"] not in source_index:
            source_index[str(m["id"])] = {
                "id": m["id"], "title": f"{m['company_name']} — {m.get('move_label') or m.get('move_type')}",
                "href": f"/moves/{m['company_id']}", "source_name": "Competitive Move", "date": m.get("latest_update") or "",
            }
    for c in session["market_reality"]:
        if c.get("id") and c["id"] not in source_index:
            source_index[str(c["id"])] = {
                "id": c["id"], "title": f"{c['geography_label']} {c['commodity_label']} — {c['metric'].replace('_', ' ').title()}",
                "href": "/today", "source_name": c.get("source") or "Market Reality", "date": c.get("latest_period") or "",
            }
    for row in session["needs_attention"]:
        if row.get("id") and row["id"] not in source_index:
            source_index[str(row["id"])] = {
                "id": row["id"], "title": row["title"], "href": row.get("open_href") or "/watchtower",
                "source_name": row.get("trigger_label") or "Watchtower alert", "date": row.get("event_at") or "",
            }
    if session.get("whitespace"):
        for cell in session["whitespace"].get("company_geo") or []:
            cell_id = f"ws-{cell['company_id']}-{cell['geography_id']}"
            source_index[cell_id] = {
                "id": cell_id, "title": f"{cell['company_name']} x {cell['geography_name']}: {cell['state']}",
                "href": cell.get("ask_href") or "/whitespace", "source_name": "Strategic Whitespace", "date": "",
            }

    return {
        "report_type": "decision_memo",
        "scope_label": session["scope_label"],
        "focus_notes": scope.focus_notes,
        "berry_id": scope.berry_id,
        "geography_ids": list(scope.geography_ids),
        "company_ids": list(scope.company_ids),
        "window_days": war_room_scope.window_days,
        "radar_freshness_label": session["radar_freshness_label"],
        "what_changed": session["what_changed"],
        "competitive_moves": session["who_is_moving"],
        "market_reality": session["market_reality"],
        "genetics_ip": session["genetics_ip"],
        "competitive_positioning": session["competitive_positioning"],
        "whitespace": session.get("whitespace"),
        "coverage_unknown": session["coverage_unknown"],
        "key_uncertainties": session["key_uncertainties"],
        "watch_next": session["watch_next"],
        "whitespace_watch_next": session["whitespace_watch_next"],
        "questions_for_team": session["questions_for_team"],
        "strategic_questions": session["strategic_questions"],
        "needs_attention": session["needs_attention"],
        "known_ids": set(source_index),
        "source_trace": list(source_index.values()),
    }


# ---------------------------------------------------------------------------
# Section generation
# ---------------------------------------------------------------------------

_TAKEAWAY_SCHEMA = {
    "type": "object",
    "properties": {
        "bullets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "citation_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "citation_ids"],
                "additionalProperties": False,
            },
            "maxItems": 6,
        }
    },
    "required": ["bullets"],
    "additionalProperties": False,
}

_TAKEAWAY_INSTRUCTIONS = (
    "You are writing the executive takeaway for an internal competitive-intelligence decision memo. "
    "Write 3-6 concise bullet points a director could read in 30 seconds. State ONLY what is directly "
    "supported by the numbered items below -- never add outside knowledge, never speculate beyond them, "
    "never invent a company, variety, date, or figure not present in them. Every bullet's citation_ids "
    "must be drawn only from the ids listed. No generic consultant filler ('the market is dynamic', "
    "'companies should monitor closely'). If the items below do not support a substantive takeaway, "
    "return an empty bullets array."
)


def _digest_line(row: dict[str, Any]) -> str | None:
    row_id = row.get("id")
    if not row_id:
        return None
    parts = [str(row_id)]
    for key in ("kind", "title", "when"):
        value = row.get(key)
        if value:
            parts.append(str(value)[:160])
    return " | ".join(parts)


def _section_executive_takeaway(packet: dict[str, Any], *, completer: Callable[..., Any] | None, model: str) -> SectionDraft | None:
    # what_changed already includes the top Market Reality items in this
    # same {id, kind, title, when} shape (see compose_war_room()) -- a
    # separate pass over packet["market_reality"] would feed rows with a
    # different shape (metric/geography_label/pct_change, no "kind") into
    # a formatter that assumes the what_changed shape uniformly.
    digest_rows = packet["what_changed"][:10]
    digest = [line for line in (_digest_line(r) for r in digest_rows) if line]
    if not digest:
        return None
    known_ids = packet["known_ids"]

    if completer is not None:
        prompt = _TAKEAWAY_INSTRUCTIONS + "\n\nItems (id | kind | title | date):\n- " + "\n- ".join(digest[:24])
        try:
            result = completer(prompt, schema=_TAKEAWAY_SCHEMA, model=model, max_output_tokens=700)
            bullets = [
                (str(b.get("text") or "").strip(), [str(c) for c in (b.get("citation_ids") or []) if str(c) in known_ids])
                for b in (result.parsed.get("bullets") or [])
            ]
            bullets = [(text, cites) for text, cites in bullets if text and cites]
            if bullets:
                prose = "\n".join(f"- {text} [{', '.join(cites)}]" for text, cites in bullets[:6])
                all_cites = tuple(dict.fromkeys(c for _t, cites in bullets for c in cites))
                return SectionDraft(
                    section_id="executive_takeaway", title=SECTION_TITLES["executive_takeaway"], prose=prose,
                    citation_ids=all_cites, status="ai_draft", provider="perplexity-agent", model=model,
                )
        except Exception:
            pass

    # Deterministic fallback: top real items, one bullet each, always grounded.
    top = digest_rows[:5]
    if not top:
        return None
    prose = "\n".join(f"- {r['kind']}: {r['title']} ({r.get('when') or ''}) [{r['id']}]" for r in top)
    return SectionDraft(
        section_id="executive_takeaway", title=SECTION_TITLES["executive_takeaway"], prose=prose,
        citation_ids=tuple(r["id"] for r in top), status="structured", provider=None, model=None,
    )


def _section_what_changed(packet: dict[str, Any]) -> SectionDraft | None:
    rows = packet["what_changed"]
    if not rows:
        return None
    prose = "\n".join(f"[{r['id']}] {r['kind']}: {r['title']} ({r.get('when') or 'date unknown'})" for r in rows if r.get("id"))
    return SectionDraft(
        section_id="what_changed", title=SECTION_TITLES["what_changed"], prose=prose,
        citation_ids=tuple(r["id"] for r in rows if r.get("id")), status="structured", provider=None, model=None,
    )


def _section_competitive_moves(packet: dict[str, Any]) -> SectionDraft | None:
    rows = packet["competitive_moves"]
    if not rows:
        return None
    lines = []
    for m in rows:
        why = " | ".join(m.get("why_move") or [])
        lines.append(f"[{m['id']}] {m['company_name']} — {m.get('move_label') or m.get('move_type')}: {m.get('what_happened') or ''} ({why})")
    return SectionDraft(
        section_id="competitive_moves", title=SECTION_TITLES["competitive_moves"], prose="\n".join(lines),
        citation_ids=tuple(m["id"] for m in rows if m.get("id")), status="structured", provider=None, model=None,
    )


def _section_market_reality(packet: dict[str, Any]) -> SectionDraft | None:
    rows = packet["market_reality"]
    if not rows:
        return None
    blocks = []
    for c in rows:
        arrow = "+" if c["direction"] == "up" else ("-" if c["direction"] == "down" else "")
        blocks.append(
            f"[{c['id']}] {c['geography_label'].upper()} {c['commodity_label'].upper()}\n"
            f"{c['metric'].replace('_', ' ').title()}: {c['previous_value']:,.0f} -> {c['latest_value']:,.0f} {c['unit']} "
            f"({c['previous_period']} -> {c['latest_period']}, {arrow}{abs(c['pct_change']):.1f}%)\n"
            f"Source: {c.get('source') or 'unknown'} / {c.get('source_dataset') or 'unknown'}"
        )
    prose = "\n\n".join(blocks) + "\n\nStructured, sourced measurement. Not a claim of cause."
    return SectionDraft(
        section_id="market_reality", title=SECTION_TITLES["market_reality"], prose=prose,
        citation_ids=tuple(c["id"] for c in rows if c.get("id")), status="structured", provider=None, model=None,
    )


def _section_genetics_ip(packet: dict[str, Any]) -> SectionDraft | None:
    genetics = packet["genetics_ip"]
    moves = genetics.get("moves") or []
    developments = genetics.get("developments") or []
    if not moves and not developments:
        return None
    lines = [f"[{m['id']}] {m['company_name']} — {m.get('move_label') or m.get('move_type')}" for m in moves if m.get("id")]
    lines += [f"[{d['id']}] {d.get('event_type')}: {d['title']} ({d.get('trust_state')})" for d in developments if d.get("id")]
    cites = tuple(row["id"] for row in (moves + developments) if row.get("id"))
    return SectionDraft(
        section_id="genetics_ip", title=SECTION_TITLES["genetics_ip"], prose="\n".join(lines),
        citation_ids=cites, status="structured", provider=None, model=None,
    )


def _section_competitive_positioning(packet: dict[str, Any]) -> SectionDraft | None:
    """Never turns LOW COVERAGE / UNKNOWN into a strategic conclusion --
    the three whitespace state labels are reproduced verbatim, and every
    cell's state comes with its own real basis (move/rights/coverage
    counts), not a synthesized judgment."""
    whitespace = packet.get("whitespace")
    lines: list[str] = []
    cites: list[str] = []
    if whitespace:
        for cell in whitespace.get("company_geo") or []:
            cell_id = f"ws-{cell['company_id']}-{cell['geography_id']}"
            lines.append(
                f"[{cell_id}] {cell['company_name']} x {cell['geography_name']}: {cell['state']} "
                f"({cell['move_count']} moves, {cell['rights_count']} rights records)"
            )
            cites.append(cell_id)
        if lines:
            lines.append("")
            lines.append(whitespace.get("method_note") or "")
    compare = packet.get("competitive_positioning")
    if compare:
        for card in compare.get("companies") or []:
            cov = card.get("coverage") or {}
            lines.append(
                f"{card['name']}: {cov.get('evidence_count', 0)} evidence, {cov.get('geography_count', 0)} geographies, "
                f"{cov.get('variety_count', 0)} varieties, {cov.get('signal_count', 0)} signals -- captured coverage, not performance."
            )
    if not lines:
        return None
    return SectionDraft(
        section_id="competitive_positioning", title=SECTION_TITLES["competitive_positioning"], prose="\n".join(lines),
        citation_ids=tuple(cites), status="structured", provider=None, model=None,
    )


def _section_what_we_know(packet: dict[str, Any]) -> SectionDraft | None:
    """Deliberately the highest-confidence subset of What Changed, not a
    duplicate of it: Trusted Evidence, plus moves with corroboration
    beyond a single source."""
    rows = [r for r in packet["what_changed"] if r.get("kind") == "Trusted Evidence"]
    rows += [
        m for m in packet["competitive_moves"]
        if str(m.get("corroboration") or "") not in {"", "ONE SOURCE"}
    ]
    if not rows:
        return None
    lines = []
    for r in rows[:10]:
        if "company_name" in r:
            lines.append(f"[{r['id']}] {r['company_name']} — {r.get('move_label')}: corroboration {r.get('corroboration')}")
        else:
            lines.append(f"[{r['id']}] {r['title']} ({r.get('when') or ''})")
    cites = tuple(r["id"] for r in rows[:10] if r.get("id"))
    return SectionDraft(
        section_id="what_we_know", title=SECTION_TITLES["what_we_know"], prose="\n".join(lines),
        citation_ids=cites, status="structured", provider=None, model=None,
    )


def _section_what_we_do_not_know(packet: dict[str, Any]) -> SectionDraft | None:
    lines = [f"COVERAGE GAP: {row['text']}" for row in (packet.get("coverage_unknown") or [])]
    lines += [f"UNVALIDATED: {row['title']} — {row['why']}" for row in (packet.get("key_uncertainties") or [])]
    if not lines:
        return None
    return SectionDraft(
        section_id="what_we_do_not_know", title=SECTION_TITLES["what_we_do_not_know"], prose="\n".join(lines),
        citation_ids=(), status="structured", provider=None, model=None,
    )


def _section_plausible_scenarios(packet: dict[str, Any], *, scenario_provider: Callable[..., Any] | None) -> SectionDraft | None:
    """Pluggable seam for Grok's Change & Scenario Engine (separate PR,
    not yet merged as of this module's authoring). Omitted entirely, not
    shown as a placeholder, while disconnected -- see module docstring."""
    if scenario_provider is None:
        return None
    try:
        scenarios = scenario_provider(packet)
    except Exception:
        return None
    if not scenarios:
        return None
    lines = []
    cites: list[str] = []
    for s in scenarios:
        lines.append(
            f"PLAUSIBLE SCENARIO -- NOT FORECAST: {s.get('title')}\n"
            f"Why plausible: {s.get('why_plausible')}\n"
            f"What to watch: {s.get('what_to_watch')}"
        )
        cites.extend(s.get("citation_ids") or [])
    return SectionDraft(
        section_id="plausible_scenarios", title=SECTION_TITLES["plausible_scenarios"], prose="\n\n".join(lines),
        citation_ids=tuple(dict.fromkeys(cites)), status="structured", provider=None, model=None,
    )


def _section_confirm_refute(packet: dict[str, Any], *, scenario_provider: Callable[..., Any] | None) -> SectionDraft | None:
    if scenario_provider is None:
        return None
    try:
        scenarios = scenario_provider(packet)
    except Exception:
        return None
    if not scenarios:
        return None
    lines = [
        f"{s.get('title')} -- CONFIRMS: {s.get('what_confirms')} | REFUTES: {s.get('what_refutes')}"
        for s in scenarios
    ]
    return SectionDraft(
        section_id="confirm_refute", title=SECTION_TITLES["confirm_refute"], prose="\n".join(lines),
        citation_ids=(), status="structured", provider=None, model=None,
    )


def _section_watch_next(packet: dict[str, Any]) -> SectionDraft | None:
    lines = [f"Watch {w['label']} ({w['watch_type']}){' -- already watched' if w.get('already_watched') else ''}" for w in (packet.get("watch_next") or [])]
    lines += list(packet.get("whitespace_watch_next") or [])
    if not lines:
        return None
    return SectionDraft(
        section_id="watch_next", title=SECTION_TITLES["watch_next"], prose="\n".join(lines),
        citation_ids=(), status="structured", provider=None, model=None,
    )


def _section_questions_for_team(packet: dict[str, Any]) -> SectionDraft | None:
    """Reuses War Room's own already-generated questions verbatim rather
    than calling the model a second time. These remain proposals: nothing
    here creates a Strategic Question -- there is no route in this app
    that creates one today (see app/repositories/json/strategic_questions.py's
    own docstring), so a memo reader who wants to act on one must do so
    through whatever workflow this system supports, same as War Room."""
    q = packet.get("questions_for_team") or {}
    questions = q.get("questions") or []
    if not questions:
        return None
    label = "AI-GENERATED DISCUSSION QUESTIONS (PROPOSALS -- not saved as Strategic Questions)" if q.get("source") == "ai" else "SUGGESTED DISCUSSION QUESTIONS (PROPOSALS)"
    lines = [label, ""] + [f"- {question}" for question in questions]
    sq_rows = packet.get("strategic_questions") or []
    if sq_rows:
        lines.append("")
        lines.append("Related existing Strategic Questions:")
        lines += [f"[{sq['id']}] {sq['title']}" for sq in sq_rows[:6]]
    return SectionDraft(
        section_id="questions_for_team", title=SECTION_TITLES["questions_for_team"], prose="\n".join(lines),
        citation_ids=tuple(sq["id"] for sq in sq_rows[:6] if sq.get("id")), status="structured", provider=None, model=None,
    )


def _section_sources_provenance(packet: dict[str, Any]) -> SectionDraft | None:
    rows = packet.get("source_trace") or []
    if not rows:
        return None
    lines = [f"[{r['id']}] {r['source_name']}: {r['title']} — {r['href']}" for r in rows]
    return SectionDraft(
        section_id="sources_provenance", title=SECTION_TITLES["sources_provenance"], prose="\n".join(lines),
        citation_ids=tuple(r["id"] for r in rows), status="structured", provider=None, model=None,
    )


def _section_internal_data_needed(packet: dict[str, Any]) -> SectionDraft:
    """Always present -- communicates the eventual public+private
    architecture without pretending it exists. No invented data, no
    private content sent anywhere; this is a fixed, honest placeholder."""
    lines = [
        "This memo is built entirely from public, structured, and trusted-Evidence intelligence.",
        "The following internal inputs are not yet connected and are never sent to any external provider:",
        "",
        "OUR TESTING / PERFORMANCE: Internal evidence not connected.",
        "OUR CUSTOMER SIGNALS: Internal evidence not connected.",
        "OUR COMMERCIAL POSITION: Internal evidence not connected.",
        "OUR FIELD INTELLIGENCE: Internal evidence not connected.",
    ]
    return SectionDraft(
        section_id="internal_data_needed", title=SECTION_TITLES["internal_data_needed"], prose="\n".join(lines),
        citation_ids=(), status="structured", provider=None, model=None,
    )


def generate_decision_memo_sections(
    packet: dict[str, Any],
    *,
    completer: Callable[..., Any] | None = None,
    model: str = MODEL_DEFAULT,
    scenario_provider: Callable[..., Any] | None = None,
) -> list[SectionDraft]:
    """Never shows an empty section (mission section 3) -- each builder
    returns None when it has nothing real to say, and this assembly step
    simply omits it rather than padding with placeholder prose. The one
    exception is `internal_data_needed`, which is always present by
    design (mission section 9: communicate the boundary even when there
    is nothing on the other side of it yet)."""
    drafts: list[SectionDraft | None] = [
        _section_executive_takeaway(packet, completer=completer, model=model),
        _section_what_changed(packet),
        _section_competitive_moves(packet),
        _section_market_reality(packet),
        _section_genetics_ip(packet),
        _section_competitive_positioning(packet),
        _section_what_we_know(packet),
        _section_what_we_do_not_know(packet),
        _section_plausible_scenarios(packet, scenario_provider=scenario_provider),
        _section_confirm_refute(packet, scenario_provider=scenario_provider),
        _section_watch_next(packet),
        _section_questions_for_team(packet),
        _section_sources_provenance(packet),
        _section_internal_data_needed(packet),
    ]
    return [d for d in drafts if d is not None]
