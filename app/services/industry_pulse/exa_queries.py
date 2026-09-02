"""Exa-only unknown-unknown queries.

These are issued only to the Exa provider when EXA_API_KEY is set.
They are not part of the Pulse 32 and are not sent to Google.
Semantic wording is intentional: crop name may be absent from the title.
"""

from __future__ import annotations

from app.services.industry_pulse.matrix import GEO_EDITIONS, PulseQuery

_EDITION = GEO_EDITIONS["global"]

UNKNOWN_UNKNOWN_TEXTS: tuple[tuple[str, str, str | None], ...] = (
    (
        "exa:uu:licensing",
        "soft-fruit breeding program exclusive license or variety commercialization agreement",
        None,
    ),
    (
        "exa:uu:partnership",
        "berry genetics joint venture or breeder nursery partnership announced this year",
        None,
    ),
    (
        "exa:uu:vaccinium-traits",
        "Vaccinium cultivar with improved shelf life or disease resistance released by a breeding program",
        "blueberry",
    ),
    (
        "exa:uu:fragaria-traits",
        "Fragaria breeding program harvest trait or day-neutral cultivar release",
        "strawberry",
    ),
    (
        "exa:uu:rubus-traits",
        "Rubus caneberry cultivar breeding genetics or plant variety protection filing",
        None,
    ),
    (
        "exa:uu:supply-chain",
        "berry supply-chain offtake agreement or grower program expansion without a retail recap",
        None,
    ),
)


def week_unknown_unknown_queries() -> list[PulseQuery]:
    rows: list[PulseQuery] = []
    for query_id, text, berry in UNKNOWN_UNKNOWN_TEXTS:
        rows.append(
            PulseQuery(
                id=query_id,
                text=text,
                berry=berry,
                geography="global",
                topic="unknown_unknown",
                kind="unknown_unknown",
                hl=_EDITION["hl"],
                gl=_EDITION["gl"],
                ceid=_EDITION["ceid"],
            )
        )
    return rows
