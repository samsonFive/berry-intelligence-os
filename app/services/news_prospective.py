"""Private first-observation receipts for an explicitly timed News pilot."""

from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3

from app.services.article_dedup import normalize_canonical_url
from app.services.feed_first_reader import is_public_http_url
from app.services.industry_pulse.canonical_urls import is_article_url, preferred_url

START_ENV = "BIOS_NEWS_PROSPECTIVE_START_UTC"
PILOT_DURATION = timedelta(days=14)
_SCHEMA = """
    CREATE TABLE IF NOT EXISTS runs (
        started_at TEXT PRIMARY KEY, completed_at TEXT NOT NULL,
        window_start TEXT NOT NULL, window_end TEXT NOT NULL,
        status TEXT NOT NULL, projection_status TEXT NOT NULL,
        route_attempts TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS observations (
        normalized_url TEXT NOT NULL, provider TEXT NOT NULL, route_id TEXT NOT NULL,
        stage TEXT NOT NULL CHECK(stage IN ('raw', 'qualified', 'news_eligible')),
        first_observed_at TEXT NOT NULL, run_started_at TEXT NOT NULL,
        publication_date TEXT, exact_url_candidate INTEGER NOT NULL,
        independent_reference INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(normalized_url, provider, route_id, stage)
    );
"""


@dataclass
class ProspectiveRun:
    window_start: datetime
    started_at: datetime
    observations: dict[tuple[str, str, str, str], tuple[str, str | None, int]] = field(default_factory=dict)
    projection_status: str = "not_run"

    @property
    def window_end(self) -> datetime:
        return self.window_start + PILOT_DURATION

    @classmethod
    def from_environment(cls, started_at: datetime) -> "ProspectiveRun | None":
        raw = os.environ.get(START_ENV, "").strip()
        if not raw:
            return None
        try:
            start = datetime.fromisoformat(raw)
            if start.utcoffset() != timedelta(0):
                raise ValueError
            start = start.astimezone(UTC)
            end = start + PILOT_DURATION
        except (ValueError, OverflowError):
            raise ValueError(f"{START_ENV} requires an ISO timestamp with an explicit UTC offset") from None
        return cls(start, started_at) if start <= started_at < end else None

    def _observe(self, stage, url, provider, route_id, published, observed_at):
        if not self.window_start <= observed_at < self.window_end or not is_public_http_url(url):
            return
        normalized = normalize_canonical_url(url)
        if not normalized or not provider or not route_id:
            return
        try:
            publication_date = date.fromisoformat(str(published)[:10]).isoformat()
        except ValueError:
            publication_date = None
        key = (normalized, provider, route_id, stage)
        seen_at = observed_at.isoformat(timespec="microseconds")
        prior = self.observations.get(key)
        if prior is None or seen_at < prior[0]:
            self.observations[key] = (seen_at, publication_date, int(is_article_url(url)))

    def observe_hits(self, stage, hits):
        observed_at = datetime.now(UTC)
        for hit in hits:
            try:
                url = preferred_url(hit)
                if url and "://" not in url:
                    url = f"https://{url.lstrip('/')}"
                self._observe(stage, url, hit.provider, hit.query_id, hit.published_date, observed_at)
            except (TypeError, ValueError):
                continue

    def observe_news(self, records):
        observed_at = datetime.now(UTC)
        for row in records:
            provenance = row.get("discovery_provenance") or {}
            self._observe("news_eligible", row.get("source_url"), provenance.get("provider"),
                          provenance.get("query_id"), row.get("published_date"), observed_at)
        self.projection_status = "complete"

    def save(self, inbox_dir: Path, *, completed_at: str, status: str, route_attempts: list) -> None:
        window_id = self.window_start.strftime("%Y%m%dT%H%M%S%fZ")
        path = Path(inbox_dir) / "operations" / "news_prospective" / window_id / "observations.sqlite3"
        path.parent.mkdir(parents=True, exist_ok=True)
        run_id = self.started_at.isoformat(timespec="microseconds")
        attempts = [{key: row.get(key) for key in ("query_id", "provider", "status", "hits", "edition")}
                    for row in route_attempts]
        with closing(sqlite3.connect(path)) as db:
            db.executescript(_SCHEMA)
            with db:
                db.execute("INSERT OR IGNORE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (run_id, completed_at, self.window_start.isoformat(), self.window_end.isoformat(),
                            status, self.projection_status, json.dumps(attempts)))
                db.executemany("""
                    INSERT INTO observations
                        (normalized_url, provider, route_id, stage, first_observed_at,
                         run_started_at, publication_date, exact_url_candidate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(normalized_url, provider, route_id, stage) DO UPDATE SET
                        first_observed_at=excluded.first_observed_at, run_started_at=excluded.run_started_at,
                        publication_date=excluded.publication_date, exact_url_candidate=excluded.exact_url_candidate
                    WHERE excluded.first_observed_at < observations.first_observed_at
                    """, ((*key, seen_at, run_id, published, exact)
                          for key, (seen_at, published, exact) in self.observations.items()))
