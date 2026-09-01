"""Bounded berry-genetics USPTO ODP query strings.

Public search terms only. Plant-patent class + crop/genus tokens.
Does not automate Patent Public Search UI.
"""

from __future__ import annotations

BERRY_ODP_QUERIES: tuple[tuple[str, str], ...] = (
    ("blueberry", 'applicationMetaData.inventionTitle:(blueberry OR Vaccinium)'),
    ("strawberry", 'applicationMetaData.inventionTitle:(strawberry OR Fragaria)'),
    ("raspberry", 'applicationMetaData.inventionTitle:(raspberry OR "Rubus idaeus")'),
    ("blackberry", 'applicationMetaData.inventionTitle:(blackberry OR "Rubus")'),
    ("assignees", 'applicationMetaData.inventionTitle:(blueberry OR strawberry) AND ("Fall Creek" OR Driscoll OR Planasa)'),
)


def odp_query_for(berry: str) -> str:
    for name, query in BERRY_ODP_QUERIES:
        if name == berry:
            return query
    raise KeyError(berry)
