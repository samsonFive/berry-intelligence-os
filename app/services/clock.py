"""Injectable UTC clock for recency windows.

Production default is the current UTC instant. Tests freeze ``utc_now``.
``now=None`` means that default — never a hidden local-timezone clock.
Naive datetimes are treated as UTC, matching ``chronology.parse_stamp``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime


def utc_now() -> datetime:
    """Current UTC instant. Monkeypatch this in tests; do not patch datetime.now."""

    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC.

    Naive values are assumed UTC. Aware values convert to UTC. Local-zone
    ``astimezone`` on a naive stamp is never used.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def resolve_now(now: datetime | None = None) -> datetime:
    """Resolve an optional caller instant to timezone-aware UTC.

    None uses ``utc_now()`` so accidental ``now=None`` still goes through
    the injectable seam instead of a second wall-clock call site.
    """

    if now is None:
        return as_utc(utc_now())
    return as_utc(now)


def utc_today(now: datetime | None = None) -> date:
    return resolve_now(now).date()
