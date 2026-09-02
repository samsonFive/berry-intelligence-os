"""Bounded berry-genetics USPTO ODP query strings.

Public search terms only. Taxonomic names, commercial crop terms, trait
language, and known assignees. Does not automate Patent Public Search UI.
"""

from __future__ import annotations

TITLE = "applicationMetaData.inventionTitle"

BERRY_ODP_QUERIES: tuple[tuple[str, str], ...] = (
    ("blueberry", f"{TITLE}:(blueberry OR Vaccinium)"),
    ("strawberry", f"{TITLE}:(strawberry OR Fragaria)"),
    ("raspberry", f'{TITLE}:(raspberry OR "Rubus idaeus")'),
    ("blackberry", f"{TITLE}:(blackberry OR Rubus)"),
    ("taxonomic-vaccinium", f"{TITLE}:(Vaccinium)"),
    ("taxonomic-fragaria", f"{TITLE}:(Fragaria)"),
    ("taxonomic-rubus", f"{TITLE}:(Rubus)"),
    (
        "semantic-traits",
        f"{TITLE}:(blueberry OR strawberry OR raspberry OR blackberry OR Vaccinium OR Fragaria OR Rubus) "
        "AND (cultivar OR breeding OR genetics OR \"plant variety\" OR harvest OR \"disease resistance\" OR \"shelf life\")",
    ),
    (
        "assignees",
        f'{TITLE}:(blueberry OR strawberry OR raspberry OR blackberry OR Vaccinium OR Fragaria) '
        'AND ("Fall Creek" OR Driscoll OR Planasa OR Hortifrut OR BerryWorld OR "Florida Foundation" OR Nourse OR Sekoya)',
    ),
)

GOOGLE_PATENTS_QUERIES: tuple[tuple[str, str], ...] = (
    ("blueberry-plant-named", '("blueberry plant named" OR "Vaccinium plant named")'),
    ("strawberry-plant-named", '("strawberry plant named" OR "strawberry plant variety named")'),
    ("raspberry-plant-named", '("raspberry plant named")'),
    ("blackberry-plant-named", '("blackberry plant named")'),
    ("assignee-fall-creek", '(assignee:"Fall Creek" blueberry OR Vaccinium)'),
    ("assignee-driscoll", '(assignee:Driscoll strawberry OR blueberry)'),
    ("assignee-planasa", '(assignee:Planasa blueberry OR strawberry)'),
)


def odp_query_for(berry: str) -> str:
    for name, query in BERRY_ODP_QUERIES:
        if name == berry:
            return query
    raise KeyError(berry)


def all_odp_queries() -> tuple[tuple[str, str], ...]:
    return BERRY_ODP_QUERIES
