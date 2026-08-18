"""USPTO Open Data Portal Patent Search client.

Official primary path when BIOS_USPTO_ODP_API_KEY is set. The ODP search
API requires a USPTO.gov-issued key (PatentsView migrated to ODP in 2026).
This client never logs the key.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.request import Request, urlopen

from app.services.patent_monitor.normalize import normalize_discovery_hit

ODP_SEARCH_URL = "https://api.uspto.gov/api/v1/patent/applications/search"
API_KEY_ENV = "BIOS_USPTO_ODP_API_KEY"
USER_AGENT = "berry-intelligence-os-patent-monitor/0.1"


class UsptoOdpError(RuntimeError):
    pass


def odp_api_key() -> str | None:
    raw = os.environ.get(API_KEY_ENV, "").strip()
    return raw or None


def odp_available() -> bool:
    return odp_api_key() is not None


def _post(url: str, body: dict[str, Any], key: str, timeout: float = 30.0) -> bytes:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-API-KEY": key,
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def parse_odp_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("patentFileWrapperDataBag") or payload.get("results") or payload.get("items") or []
    hits: list[dict[str, Any]] = []
    if isinstance(records, dict):
        records = records.get("items") or []
    for item in records:
        if not isinstance(item, dict):
            continue
        application = item.get("applicationMetaData") or item.get("patent") or item
        publication_number = (
            application.get("patentNumber")
            or application.get("publicationNumber")
            or item.get("publicationNumber")
            or ""
        )
        if not publication_number:
            continue
        inventors = []
        for inventor in application.get("inventorBag") or []:
            if isinstance(inventor, dict):
                name = " ".join(
                    part for part in [inventor.get("firstName"), inventor.get("lastName")] if part
                ).strip()
                if name:
                    inventors.append(name)
            elif inventor:
                inventors.append(str(inventor))
        assignees = []
        for assignee in application.get("assigneeBag") or application.get("applicantBag") or []:
            if isinstance(assignee, dict):
                name = assignee.get("nameLineOneText") or assignee.get("name") or ""
                if name:
                    assignees.append(str(name))
            elif assignee:
                assignees.append(str(assignee))
        hits.append(
            normalize_discovery_hit(
                {
                    "publication_number": publication_number,
                    "application_number": application.get("applicationNumberText") or item.get("applicationNumberText"),
                    "title": application.get("inventionTitle") or application.get("title") or "",
                    "abstract": application.get("abstractText") or item.get("abstract") or "",
                    "filing_date": application.get("filingDate") or application.get("applicationFilingDate"),
                    "publication_date": application.get("grantDate") or application.get("publicationDate"),
                    "grant_date": application.get("grantDate"),
                    "inventors": inventors,
                    "assignees": assignees,
                    "applicants": [],
                    "acquisition_method": "uspto_odp",
                    "source_url": f"https://patentcenter.uspto.gov/applications/{application.get('applicationNumberText') or publication_number}",
                    "jurisdiction": "US",
                }
            )
        )
    return hits


def search_uspto_odp(
    query: str,
    *,
    fetch: Callable[[str, dict[str, Any], str], bytes] | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    key = odp_api_key()
    if not key:
        raise UsptoOdpError(f"{API_KEY_ENV} is not set")
    body = {"q": query, "rows": limit}
    fetcher = fetch or _post
    try:
        raw = fetcher(ODP_SEARCH_URL, body, key)
        payload = json.loads(raw.decode("utf-8"))
    except UsptoOdpError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise UsptoOdpError("USPTO ODP search failed") from exc
    hits = parse_odp_results(payload)
    return {"query": query, "total": len(hits), "hits": hits}
