"""Shared freeze helper for the injectable UTC clock."""

from __future__ import annotations

from datetime import date, datetime

from app.services.clock import as_utc


def freeze_utc_now(monkeypatch, value: datetime | date | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    instant = as_utc(value)
    monkeypatch.setattr("app.services.clock.utc_now", lambda: instant)
    return instant
