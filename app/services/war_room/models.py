"""War Room scope -- the only new "shape" this feature introduces.

Every other object a War Room session shows (a Development, a Move, a
Market Reality change, an Alert, a Strategic Question) is someone else's
existing object, read verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WarRoomScope:
    berry_id: str | None
    geography_ids: tuple[str, ...] = ()
    company_ids: tuple[str, ...] = ()
    window_days: int = 30

    def as_dict(self) -> dict[str, Any]:
        return {
            "berry_id": self.berry_id,
            "geography_ids": list(self.geography_ids),
            "company_ids": list(self.company_ids),
            "window_days": self.window_days,
        }

    @property
    def is_empty(self) -> bool:
        return not self.berry_id and not self.geography_ids and not self.company_ids
