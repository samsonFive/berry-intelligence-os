"""Bounded Google Patents Public Datasets queries.

Tables (documented public dataset, not a scrape):
- patents-public-data.patents.publications
- patents-public-data.google_patents_research.publications
  (title/abstract translations, embedding_v1)

Live execution requires GOOGLE_CLOUD_PROJECT plus application default
credentials. This module never runs a full-table scan. Dry-run bytes are
recorded when the client is injected. Absence of credentials is not a
crash.
"""

from __future__ import annotations

import os
from typing import Any, Callable

PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"
PUBLICATIONS = "`patents-public-data.patents.publications`"
RESEARCH = "`patents-public-data.google_patents_research.publications`"
ON_DEMAND_USD_PER_TIB = 6.25
FREE_TIB_PER_MONTH = 1.0

BERRY_TERMS = (
    "blueberry",
    "strawberry",
    "raspberry",
    "blackberry",
    "vaccinium",
    "fragaria",
    "rubus",
)
KNOWN_ASSIGNEES = (
    "Fall Creek",
    "Driscoll",
    "Planasa",
    "BerryWorld",
    "Florida Foundation",
)


class BigQueryPatentsError(RuntimeError):
    pass


def project_id() -> str | None:
    raw = (os.environ.get(PROJECT_ENV) or "").strip()
    return raw or None


def available() -> bool:
    return project_id() is not None


def keyword_sql(*, limit: int = 25) -> str:
    """Known berry keyword retrieval. Research table, bounded."""
    if limit < 1 or limit > 50:
        raise BigQueryPatentsError("keyword limit must be 1..50")
    likes = " OR ".join(f"LOWER(title) LIKE '%{term}%'" for term in BERRY_TERMS)
    return f"""
SELECT
  publication_number,
  title,
  assignee,
  filing_date,
  publication_date,
  country
FROM {RESEARCH}
WHERE country IN ('US', 'EP', 'WO')
  AND ({likes})
LIMIT {int(limit)}
""".strip()


def assignee_sql(*, limit: int = 25) -> str:
    if limit < 1 or limit > 50:
        raise BigQueryPatentsError("assignee limit must be 1..50")
    assignees = " OR ".join(f"LOWER(assignee) LIKE '%{name.lower()}%'" for name in KNOWN_ASSIGNEES)
    return f"""
SELECT
  publication_number,
  title,
  assignee,
  filing_date,
  publication_date,
  country
FROM {RESEARCH}
WHERE country IN ('US', 'EP', 'WO')
  AND ({assignees})
LIMIT {int(limit)}
""".strip()


def cpc_sql(*, limit: int = 25) -> str:
    """CPC/IPC-assisted retrieval. No full-table scan."""
    if limit < 1 or limit > 50:
        raise BigQueryPatentsError("cpc limit must be 1..50")
    return f"""
SELECT
  publication_number,
  title_localized,
  filing_date,
  publication_date,
  country_code
FROM {PUBLICATIONS}
WHERE country_code IN ('US', 'EP', 'WO')
  AND (
    EXISTS (SELECT 1 FROM UNNEST(cpc) AS c
            WHERE c.code LIKE 'A01H6/74%'
               OR c.code LIKE 'A01H6/36%'
               OR c.code LIKE 'A01H5/08%')
    OR EXISTS (SELECT 1 FROM UNNEST(ipc) AS i
               WHERE i.code LIKE 'A01H6/74%'
                  OR i.code LIKE 'A01H6/36%'
                  OR i.code LIKE 'A01H5/08%')
  )
LIMIT {int(limit)}
""".strip()


def bibliographic_sql(*, limit: int = 25) -> str:
    if limit < 1 or limit > 50:
        raise BigQueryPatentsError("bibliographic limit must be 1..50")
    likes = " OR ".join(f"LOWER(title) LIKE '%{term}%'" for term in BERRY_TERMS)
    assignees = " OR ".join(f"LOWER(assignee) LIKE '%{name.lower()}%'" for name in KNOWN_ASSIGNEES)
    return f"""
SELECT
  publication_number,
  title,
  abstract,
  assignee,
  filing_date,
  publication_date,
  country
FROM {RESEARCH}
WHERE country IN ('US', 'EP', 'WO')
  AND ARRAY_LENGTH(embedding_v1) > 0
  AND (
    {likes}
    OR {assignees}
  )
LIMIT {int(limit)}
""".strip()


def similarity_sql(*, publication_number: str, limit: int = 5) -> str:
    """Similarity from one known berry patent. No giant scan.

    VECTOR_SEARCH over the full research table would process terabytes.
    Restrict the base set with the same berry/assignee filter and the
    query row by publication_number.
    """
    number = (publication_number or "").strip()
    if not number:
        raise BigQueryPatentsError("publication_number is required")
    if limit < 1 or limit > 10:
        raise BigQueryPatentsError("similarity limit must be 1..10")
    return f"""
SELECT
  query.publication_number AS query_publication_number,
  base.publication_number,
  base.title,
  distance
FROM VECTOR_SEARCH(
  (
    SELECT publication_number, title, embedding_v1
    FROM {RESEARCH}
    WHERE ARRAY_LENGTH(embedding_v1) > 0
      AND (
        LOWER(title) LIKE '%blueberry%'
        OR LOWER(title) LIKE '%strawberry%'
        OR LOWER(title) LIKE '%raspberry%'
        OR LOWER(title) LIKE '%blackberry%'
        OR LOWER(title) LIKE '%vaccinium%'
        OR LOWER(title) LIKE '%fragaria%'
        OR LOWER(title) LIKE '%rubus%'
      )
    LIMIT 2000
  ),
  'embedding_v1',
  (
    SELECT publication_number, title, embedding_v1
    FROM {RESEARCH}
    WHERE publication_number = '{number.replace("'", "")}'
    LIMIT 1
  ),
  top_k => {int(limit)},
  distance_type => 'COSINE'
)
""".strip()


def estimate_usd(bytes_processed: int) -> float:
    tib = max(bytes_processed, 0) / (1024**4)
    billable = max(tib - 0.0, 0.0)
    return round(billable * ON_DEMAND_USD_PER_TIB, 6)


def run_bounded_query(
    sql: str,
    *,
    client: Any | None = None,
    dry_run: bool = True,
    query_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Execute or dry-run. Never writes Evidence."""
    if "LIMIT" not in sql.upper():
        raise BigQueryPatentsError("refusing unbounded BigQuery SQL")
    if project_id() is None and client is None and query_fn is None:
        return {
            "available": False,
            "reason": f"{PROJECT_ENV} absent",
            "sql": sql,
            "bytes_processed": None,
            "estimated_usd": None,
            "rows": [],
        }
    if query_fn is not None:
        result = query_fn(sql, dry_run=dry_run)
        bytes_processed = int(result.get("bytes_processed") or 0)
        return {
            "available": True,
            "reason": None,
            "sql": sql,
            "dry_run": dry_run,
            "bytes_processed": bytes_processed,
            "estimated_usd": estimate_usd(bytes_processed),
            "rows": list(result.get("rows") or []),
        }
    raise BigQueryPatentsError("live BigQuery client is not configured in this environment")


OPERATOR_SETUP = (
    "Operator setup: create a Google Cloud project, enable BigQuery, run "
    "`gcloud auth application-default login`, then SET GOOGLE_CLOUD_PROJECT. "
    "Queries stay LIMIT-bounded. On-demand pricing is $6.25/TiB with 1 TiB/month free."
)


def prototype_bundle(*, limit: int = 15) -> dict[str, Any]:
    """Four bounded templates. Executes only when a project/client exists."""
    templates = {
        "keyword": keyword_sql(limit=limit),
        "assignee": assignee_sql(limit=limit),
        "cpc_ipc": cpc_sql(limit=limit),
        "bibliographic": bibliographic_sql(limit=limit),
    }
    reports = {name: run_bounded_query(sql) for name, sql in templates.items()}
    return {
        "available": available(),
        "operator_setup": OPERATOR_SETUP,
        "templates": templates,
        "reports": reports,
    }
