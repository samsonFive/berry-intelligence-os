"""Conservative Strategic Question links for Competitive Moves.

Only attach when the move type and berry/geography facts match a seeded
question directly. No embedding or broad semantic guessing.
"""

from __future__ import annotations

SQ_COMPETITOR_EXPANSION = {
    "id": "sq-competitor-expansion",
    "title": "Which organizations appear to be expanding through partnerships, acquisitions, nurseries, licensing networks or commercial plantings?",
    "href": "/strategic-questions/sq-competitor-expansion",
}
SQ_GEO_SPREAD = {
    "id": "sq-genetics-geographic-spread",
    "title": "Which genetics are becoming available in new countries or production regions through licensing or nursery distribution?",
    "href": "/strategic-questions/sq-genetics-geographic-spread",
}
SQ_EMERGING = {
    "id": "sq-emerging-varieties",
    "title": "Which recently introduced or expanding blueberry varieties appear most commercially significant?",
    "href": "/strategic-questions/sq-emerging-varieties",
}
SQ_GLOBAL_REACH = {
    "id": "sq-global-genetics-reach",
    "title": "Which breeding programs and genetics owners have the strongest visible global blueberry reach?",
    "href": "/strategic-questions/sq-global-genetics-reach",
}

BLUEBERRY = "berry-blueberry"

EXPANSION_TYPES = frozenset(
    {"EXPANSION", "MARKET_ENTRY", "PARTNERSHIP", "ACQUISITION / INVESTMENT", "LICENSING", "VARIETY_COMMERCIALIZATION"}
)
GENETICS_TYPES = frozenset({"GENETICS_LAUNCH", "VARIETY_COMMERCIALIZATION", "LICENSING", "PBR / IP"})


def strategic_questions_for_move(
    *,
    move_type: str,
    berry_ids: tuple[str, ...] = (),
    geography_ids: tuple[str, ...] = (),
    variety_ids: tuple[str, ...] = (),
) -> tuple[dict[str, str], ...]:
    blueberry = not berry_ids or BLUEBERRY in berry_ids
    linked: list[dict[str, str]] = []
    if move_type in EXPANSION_TYPES:
        linked.append(SQ_COMPETITOR_EXPANSION)
    if blueberry and move_type in GENETICS_TYPES and geography_ids:
        linked.append(SQ_GEO_SPREAD)
    if blueberry and move_type in {"GENETICS_LAUNCH", "VARIETY_COMMERCIALIZATION"} and variety_ids:
        linked.append(SQ_EMERGING)
    if blueberry and move_type in GENETICS_TYPES and len(geography_ids) >= 2:
        linked.append(SQ_GLOBAL_REACH)
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in linked:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        out.append(row)
    return tuple(out)
