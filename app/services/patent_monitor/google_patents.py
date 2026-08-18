"""Google Patents public JSON search client (secondary discovery).

This is not HTML scraping. Google Patents exposes a public JSON XHR used by
its own search UI. USPTO Open Data Portal remains the preferred official
API when BIOS_USPTO_ODP_API_KEY is configured.

Do not use this client to log in, bypass paywalls, or automate LinkedIn.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import json
import time

from app.services.patent_monitor.normalize import normalize_discovery_hit, strip_markup

DEFAULT_ENDPOINT = "https://patents.google.com/xhr/query"
# Public JSON XHR used by the Google Patents search UI. A browser-like UA
# reduces 503s from Google's edge; this is not a login or access-control bypass.
USER_AGENT = (
    "Mozilla/5.0 (compatible; BerryIntelligenceOS/0.1; "
    "+https://github.com/samsonFive/berry-intelligence-os) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class GooglePatentsError(RuntimeError):
    pass


def _default_fetch(url: str, timeout: float = 30.0) -> bytes:
    retries = (0.0, 8.0, 20.0)
    last_exc: Exception | None = None
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://patents.google.com/",
    }
    for delay in retries:
        if delay:
            time.sleep(delay)
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - public HTTPS search
                return response.read()
        except HTTPError as extra:
            last_exc = extra
            if extra.code not in {429, 500, 502, 503, 504}:
                break
        except URLError as extra:
            last_exc = extra
    raise GooglePatentsError(f"Google Patents request failed: {last_exc}") from last_exc


def parse_search_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("results") or payload
    hits: list[dict[str, Any]] = []
    for cluster in results.get("cluster") or []:
        for item in cluster.get("result") or []:
            patent = item.get("patent") or {}
            publication_number = patent.get("publication_number") or ""
            if not publication_number:
                identity = str(item.get("id") or "")
                if identity.startswith("patent/"):
                    publication_number = identity.split("/")[1]
            if not publication_number:
                continue
            hits.append(
                normalize_discovery_hit(
                    {
                        "publication_number": publication_number,
                        "title": strip_markup(patent.get("title") or ""),
                        "snippet": patent.get("snippet") or "",
                        "filing_date": patent.get("filing_date"),
                        "publication_date": patent.get("publication_date"),
                        "grant_date": patent.get("grant_date"),
                        "inventor": patent.get("inventor"),
                        "assignee": patent.get("assignee"),
                        "acquisition_method": "google_patents_json",
                    }
                )
            )
    return hits


def search_google_patents(
    query: str,
    *,
    after_publication: str | None = None,
    page: int = 0,
    num: int = 25,
    fetch: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    """Run one Google Patents JSON search.

    `query` is the `q=` expression only, e.g. '("blueberry plant named")'.
    """

    fetcher = fetch or _default_fetch
    parts = [f"q={query}"]
    if after_publication:
        parts.append(f"after=publication:{after_publication.replace('-', '')}")
    if page:
        parts.append(f"page={page}")
    if num:
        parts.append(f"num={num}")
    inner = "&".join(parts)
    url = f"{DEFAULT_ENDPOINT}?{urlencode({'url': inner, 'exp': ''})}"
    try:
        raw = fetcher(url)
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise GooglePatentsError(f"Google Patents search failed for {query!r}") from exc
    hits = parse_search_results(payload)
    total = int((payload.get("results") or {}).get("total_num_results") or len(hits))
    return {"query": query, "total": total, "hits": hits, "raw_url": url}
