"""Berry genetics relevance for plant-patent records.

Generic 'berry' is not enough. Cranberry/lingonberry/huckleberry are
Vaccinium relatives but are out of the four-crop scope unless a title
explicitly names blueberry/strawberry/raspberry/blackberry.
"""

from __future__ import annotations

import re
from typing import Any

BERRY_POSITIVE: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "berry-blueberry",
        (
            "blueberry",
            "blueberries",
            "vaccinium corymbosum",
            "vaccinium darrowii",
            "vaccinium virgatum",
            "vaccinium ashei",
            "vaccinium angustifolium",
            "southern highbush",
            "northern highbush",
            "rabbiteye",
        ),
    ),
    (
        "berry-strawberry",
        (
            "strawberry",
            "strawberries",
            "fragaria",
            "fragaria x ananassa",
            "fragaria vesca",
            "day-neutral",
            "june-bearing",
            "frutilla",
            "fresa",
        ),
    ),
    (
        "berry-raspberry",
        (
            "raspberry",
            "raspberries",
            "rubus idaeus",
            "rubus occidentalis",
            "rubus idaeus subsp",
            "rubus strigosus",
            "primocane",
            "floricane",
            "frambuesa",
        ),
    ),
    (
        "berry-blackberry",
        (
            "blackberry",
            "blackberries",
            "rubus ursinus",
            "trailing blackberry",
            "rubus fruticosus",
            "rubus laciniatus",
            "primocane",
            "floricane",
            "mora",
        ),
    ),
)

EXCLUDE_DEFAULT = (
    "cranberry",
    "lingonberry",
    "huckleberry",
    "goji",
    "acai",
    "açaí",
    "elderberry",
    "mulberry",
    "serviceberry",
    "juniper berry",
)


def _haystack(filing: dict[str, Any]) -> str:
    parts = [
        filing.get("title") or "",
        filing.get("abstract") or "",
        filing.get("botanical_name") or "",
        filing.get("cultivar_name") or "",
        " ".join(filing.get("assignees") or []),
    ]
    return " ".join(parts).casefold()


def is_excluded(haystack: str, exclude_terms: tuple[str, ...] | list[str] = EXCLUDE_DEFAULT) -> bool:
    lowered = haystack.casefold()
    if any(term in lowered for term in exclude_terms):
        # Still allow if an in-scope crop is explicitly named.
        in_scope = ("blueberry", "strawberry", "raspberry", "blackberry")
        return not any(term in lowered for term in in_scope)
    return False


def berry_ids_for_filing(
    filing: dict[str, Any],
    *,
    exclude_terms: tuple[str, ...] | list[str] = EXCLUDE_DEFAULT,
) -> list[str]:
    haystack = _haystack(filing)
    if is_excluded(haystack, exclude_terms):
        return []
    found: list[str] = []
    for berry_id, terms in BERRY_POSITIVE:
        if any(re.search(r"\b" + re.escape(term) + r"\b", haystack) or term in haystack for term in terms):
            found.append(berry_id)
    return found


def relevance_decision(
    filing: dict[str, Any],
    *,
    berry_hint: str | None = None,
    exclude_terms: tuple[str, ...] | list[str] = EXCLUDE_DEFAULT,
) -> dict[str, Any]:
    berry_ids = berry_ids_for_filing(filing, exclude_terms=exclude_terms)
    if berry_hint and berry_hint not in berry_ids:
        # Hint is a query-level prior, not a substitute for matching.
        hinted = berry_ids_for_filing(
            {**filing, "title": f"{filing.get('title') or ''} {berry_hint}"},
            exclude_terms=exclude_terms,
        )
        if berry_hint in hinted and berry_ids:
            pass
    relevant = bool(berry_ids)
    return {
        "relevant": relevant,
        "berry_ids": berry_ids,
        "reason": "botanical_or_common_name_match" if relevant else "no_in_scope_berry_match",
    }
