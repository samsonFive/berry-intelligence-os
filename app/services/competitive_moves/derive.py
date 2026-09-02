"""Derive Competitive Moves from Radar Developments.

One company + one move type (+ named variety when present) becomes one
Move, even when several Developments describe the same real-world action.
Syndicated copies never count as extra support.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Iterable
from urllib.parse import urlparse

from app.services.emerging_radar.models import TRUST_LIVE, Development, SourceRef
from app.services.competitive_moves.models import (
    MOVE_LABELS,
    TRUST_LIVE_MOVE,
    CompetitiveMove,
    TimelineRow,
)
from app.services.competitive_moves.strategic import strategic_questions_for_move

ACQUISITION_RE = re.compile(
    r"\b(acqui(?:re[ds]?|sition)|merger|takeover|buyout|invest(?:s|ed) in|investment in|stake in|majority stake)\b",
    re.I,
)
MARKETING_RE = re.compile(r"\b(marketing campaign|brand awareness campaign)\b", re.I)
COMMERCIAL_RE = re.compile(
    r"\b(commerciali[sz]|royalt(?:y|ies)|managed variet|nursery (?:release|distribution)|licensees?)\b",
    re.I,
)
ENTRY_RE = re.compile(
    r"\b(bringing .{0,40} to|enters?|entering|entry into|new market|market access|into the (?:us|u\.s|united states|canada|europe|uk|eu))\b",
    re.I,
)
RD_RE = re.compile(r"\b(crispr|gene-?edit|trial|r&d|research station|controlled[- ]environment|shelf[- ]life genetics)\b", re.I)

BERRY_WORDS = {
    "blueberry": ("berry-blueberry", "Blueberry"),
    "blueberries": ("berry-blueberry", "Blueberry"),
    "strawberry": ("berry-strawberry", "Strawberry"),
    "strawberries": ("berry-strawberry", "Strawberry"),
    "raspberry": ("berry-raspberry", "Raspberry"),
    "raspberries": ("berry-raspberry", "Raspberry"),
    "blackberry": ("berry-blackberry", "Blackberry"),
    "blackberries": ("berry-blackberry", "Blackberry"),
}

EVENT_TO_MOVE = {
    "PRODUCTION_EXPANSION": "EXPANSION",
    "MARKET_ACCESS": "MARKET_ENTRY",
    "VARIETY_LAUNCH": "GENETICS_LAUNCH",
    "GENETICS_INNOVATION": "GENETICS_LAUNCH",
    "LICENSING": "LICENSING",
    "PARTNERSHIP": "PARTNERSHIP",
    "LEADERSHIP": "LEADERSHIP",
    "RESEARCH": "R&D / TECHNOLOGY",
    "PBR": "PBR / IP",
    "PATENT": "PBR / IP",
    "RETAIL_PROGRAM": "RETAIL_PROGRAM",
    "SUPPLY_CHANGE": "SUPPLY / PRODUCTION_SHIFT",
    "LEGAL": "LEGAL / COMPETITIVE_CONSTRAINT",
    "REGULATORY": "LEGAL / COMPETITIVE_CONSTRAINT",
    "OTHER": "OTHER",
}


def _text(development: Development) -> str:
    snippets = " ".join(source.snippet for source in development.sources[:4])
    return f"{development.title} {development.what_happened} {snippets}"


def classify_move_type(development: Development) -> str:
    """Map a Development onto the restrained competitive-move taxonomy."""
    text = _text(development)
    event = development.event_type
    if MARKETING_RE.search(text):
        return "OTHER"
    if ACQUISITION_RE.search(development.title or "") and event in {"PARTNERSHIP", "OTHER", "LICENSING"}:
        return "ACQUISITION / INVESTMENT"
    if event == "LEGAL" or event == "REGULATORY":
        return "LEGAL / COMPETITIVE_CONSTRAINT"
    if event in {"PBR", "PATENT"}:
        return "PBR / IP"
    if event == "LEADERSHIP":
        return "LEADERSHIP"
    if event == "RETAIL_PROGRAM":
        return "RETAIL_PROGRAM"
    if event == "MARKET_ACCESS":
        return "MARKET_ENTRY"
    if event == "PRODUCTION_EXPANSION":
        return "EXPANSION"
    if event == "SUPPLY_CHANGE":
        return "SUPPLY / PRODUCTION_SHIFT"
    if event == "LICENSING":
        if development.variety_ids or COMMERCIAL_RE.search(text):
            return "VARIETY_COMMERCIALIZATION"
        return "LICENSING"
    if event in {"VARIETY_LAUNCH", "GENETICS_INNOVATION"}:
        if (ENTRY_RE.search(text) and development.geography_ids) or COMMERCIAL_RE.search(text):
            return "VARIETY_COMMERCIALIZATION"
        if RD_RE.search(text) and event == "GENETICS_INNOVATION" and not re.search(
            r"\b(launch|introduc|unveil|debut)\b", text, re.I
        ):
            return "R&D / TECHNOLOGY"
        return "GENETICS_LAUNCH"
    if event == "RESEARCH":
        return "R&D / TECHNOLOGY"
    if event == "PARTNERSHIP":
        return "PARTNERSHIP"
    if event == "OTHER" and development.variety_ids:
        return "GENETICS_LAUNCH"
    return EVENT_TO_MOVE.get(event, "OTHER")


def _registrable(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _independent_sources(sources: Iterable[SourceRef]) -> list[SourceRef]:
    seen: set[str] = set()
    out: list[SourceRef] = []
    for source in sources:
        if source.syndicated:
            continue
        key = _registrable(source.url) or source.domain
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(source)
    return out


def _development_eligible(development: Development) -> bool:
    if not development.company_ids:
        return False
    if development.weak_signal_label and development.independent_source_count < 1:
        return False
    if development.status == "weak_signal":
        return False
    return True


def _group_key(company_id: str, move_type: str, development: Development) -> tuple[str, ...]:
    varieties = tuple(sorted(development.variety_ids))
    if varieties:
        return (company_id, move_type, "variety", ",".join(varieties))
    return (company_id, move_type, "company", "")


def _move_id(key: tuple[str, ...]) -> str:
    return "move-" + hashlib.sha1("|".join(key).encode("utf-8")).hexdigest()[:12]


def _why_move(move_type: str, members: list[Development], company_name: str) -> tuple[str, ...]:
    reasons: list[str] = []
    reasons.append(f"{company_name} is a canonical competitor")
    reasons.append(f"Classified as {MOVE_LABELS.get(move_type, move_type)} from {members[0].event_type.replace('_', ' ').title()}")
    if len(members) > 1:
        reasons.append(f"{len(members)} supporting developments describe the same move")
    geos = [label for row in members for label in row.geography_labels]
    if geos:
        reasons.append("Geography named: " + ", ".join(list(dict.fromkeys(geos))[:4]))
    varieties = [name for row in members for name in row.variety_names]
    if varieties:
        reasons.append("Named variety: " + ", ".join(list(dict.fromkeys(varieties))[:4]))
    if any(row.independent_source_count >= 2 for row in members):
        reasons.append("Multiple independent sources among supporting developments")
    if any(
        row.provenance == ("exa",)
        or ("exa" in row.provenance and not any(name in {"google_news_rss", "specialist_rss"} for name in row.provenance))
        for row in members
    ):
        reasons.append("Exa semantic discovery contributed")
    if any(row.trusted_context for row in members):
        reasons.append("Trusted Evidence exists alongside this live move")
    return tuple(dict.fromkeys(reasons))


def _timeline(members: list[Development], move_type: str) -> list[TimelineRow]:
    rows: list[TimelineRow] = []
    seen_dev: set[str] = set()
    for development in sorted(members, key=lambda row: row.event_date or row.first_seen or ""):
        if development.id in seen_dev:
            continue
        seen_dev.add(development.id)
        lead = next((source for source in development.sources if not source.syndicated), None)
        publisher = lead.publisher if lead else (development.sources[0].publisher if development.sources else "Unknown")
        geo = ", ".join(development.geography_labels[:3])
        crop = ", ".join(tuple(development.variety_names)[:2] or development.berry_labels[:2])
        rows.append(
            TimelineRow(
                date=(development.event_date or development.first_seen or "")[:10],
                move_type=move_type,
                what_happened=development.what_happened or development.title,
                source=publisher,
                geography=geo,
                variety_or_berry=crop,
                trust_state=TRUST_LIVE,
                development_id=development.id,
                href=f"/radar/{development.id}",
            )
        )
    return rows


def _dedupe_members(members: list[Development]) -> list[Development]:
    """Drop Developments whose independent URLs are already represented."""
    kept: list[Development] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for row in members:
        urls = {source.url for source in row.sources if source.url and not source.syndicated}
        title_key = re.sub(r"\W+", " ", (row.title or "").casefold()).strip()[:80]
        if urls and urls <= seen_urls:
            continue
        if title_key and title_key in seen_titles and not urls - seen_urls:
            continue
        kept.append(row)
        seen_urls.update(urls)
        if title_key:
            seen_titles.add(title_key)
    return kept


def _merge_market(members: list[Development]) -> dict | None:
    for row in members:
        ctx = row.market_context
        if isinstance(ctx, dict) and ctx.get("rows"):
            return ctx
    return None


def _merge_trusted(members: list[Development]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for row in members:
        for item in row.trusted_context or []:
            key = str(item.get("id") or item.get("href") or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            out.append(item)
            if len(out) >= 6:
                return out
    return out


def derive_moves(
    developments: Iterable[Development],
    *,
    today: date | None = None,
) -> list[CompetitiveMove]:
    """Build Competitive Moves from Developments. Does not fetch providers."""
    del today
    buckets: dict[tuple[str, ...], list[tuple[str, Development]]] = {}
    names: dict[str, str] = {}
    for development in developments:
        if not _development_eligible(development):
            continue
        move_type = classify_move_type(development)
        if move_type == "OTHER" and not development.variety_ids:
            continue
        for index, company_id in enumerate(development.company_ids):
            name = development.company_names[index] if index < len(development.company_names) else company_id
            names[company_id] = name
            key = _group_key(company_id, move_type, development)
            buckets.setdefault(key, []).append((company_id, development))

    moves: list[CompetitiveMove] = []
    for key, pairs in buckets.items():
        company_id = key[0]
        move_type = key[1]
        members = _dedupe_members([row for _, row in pairs])
        if not members:
            continue
        company_name = names.get(company_id, company_id)
        lead = max(members, key=lambda row: (row.independent_source_count, len(row.title or ""), row.latest_update or ""))
        sources = []
        seen_src: set[str] = set()
        provenance: list[str] = []
        for row in members:
            for source in _independent_sources(row.sources):
                if source.url in seen_src:
                    continue
                seen_src.add(source.url)
                sources.append(
                    {
                        "url": source.url,
                        "title": source.title,
                        "publisher": source.publisher,
                        "provider": source.provider,
                        "published_date": source.published_date,
                    }
                )
            for provider in row.provenance:
                if provider not in provenance:
                    provenance.append(provider)
        geos = tuple(dict.fromkeys(gid for row in members for gid in row.geography_ids))
        geo_labels = tuple(dict.fromkeys(label for row in members for label in row.geography_labels))
        berries = tuple(dict.fromkeys(bid for row in members for bid in row.berry_ids))
        berry_labels = tuple(dict.fromkeys(label for row in members for label in row.berry_labels))
        if not berries:
            blob = " ".join(_text(row) for row in members).casefold()
            extra_ids: list[str] = []
            extra_labels: list[str] = []
            for word, (berry_id, label) in BERRY_WORDS.items():
                if word in blob and berry_id not in extra_ids:
                    extra_ids.append(berry_id)
                    extra_labels.append(label)
            berries = tuple(extra_ids)
            berry_labels = tuple(extra_labels)
        varieties = tuple(dict.fromkeys(vid for row in members for vid in row.variety_ids))
        variety_names = tuple(dict.fromkeys(name for row in members for name in row.variety_names))
        first_seen = min((row.first_seen for row in members if row.first_seen), default=lead.first_seen)
        latest = max((row.latest_update for row in members if row.latest_update), default=lead.latest_update)
        corroboration = lead.corroboration
        if any(row.independent_source_count >= 2 for row in members):
            if corroboration == "ONE SOURCE":
                corroboration = "MULTIPLE INDEPENDENT SOURCES"
        what = f"{company_name} — {MOVE_LABELS.get(move_type, move_type).lower()}: {lead.title}"
        where = ", ".join(geo_labels[:3])
        if where:
            what = f"{what} ({where})"
        exa_only = provenance == ["exa"] or ("exa" in provenance and not any(name in {"google_news_rss", "specialist_rss"} for name in provenance))
        move = CompetitiveMove(
            id=_move_id(key),
            company_id=company_id,
            company_name=company_name,
            move_type=move_type,
            title=lead.title,
            what_happened=what,
            why_move=_why_move(move_type, members, company_name),
            first_seen=first_seen,
            latest_update=latest,
            geography_ids=geos,
            geography_labels=geo_labels,
            berry_ids=berries,
            berry_labels=berry_labels,
            variety_ids=varieties,
            variety_names=variety_names,
            supporting_development_ids=tuple(row.id for row in members),
            supporting_sources=sources[:8],
            trusted_context=_merge_trusted(members),
            market_context=_merge_market(members),
            strategic_questions=strategic_questions_for_move(
                move_type=move_type,
                berry_ids=berries,
                geography_ids=geos,
                variety_ids=varieties,
            ),
            provenance=tuple(provenance),
            exa_mattered="exa" in provenance,
            corroboration=corroboration,
            trust_state=TRUST_LIVE_MOVE,
            development_trust_state=TRUST_LIVE,
            timeline=_timeline(members, move_type),
        )
        if exa_only and "Exa semantic discovery contributed" not in move.why_move:
            move.why_move = move.why_move + ("Exa semantic discovery contributed",)
        moves.append(move)
    moves.sort(key=lambda row: (row.latest_update, row.first_seen, row.company_name), reverse=True)
    return moves
