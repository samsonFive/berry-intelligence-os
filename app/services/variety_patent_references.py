"""Read-only original filing links; never a current-rights assessment."""
from urllib.parse import urlsplit

from app.services.variety_portfolio_coverage import reconcile_portfolios


def _public_url(value):
    if not isinstance(value, str):
        return ""
    try:
        parts = urlsplit(value)
        return value if parts.scheme in {"http", "https"} and parts.hostname and not parts.username and not parts.password else ""
    except ValueError:
        return ""


def original_patent_references(*, variety, varieties, entities, candidates, sources):
    """Use existing identity decisions and source/code ambiguity handling.

    Only exact catalog associations reach a profile. A reference remains
    unreviewed; source text, grant metadata and linked figures approve nothing.
    No corpus-body hydration, footprints, acquisition or persistent writes.
    """
    rights = [s for s in sources if s.get("source_type") in {"plant_patent", "national_register"}]
    if not rights:
        return []
    # Keep cross-source code/label conflicts visible even if a conflicting
    # observation is not itself a patent or register record.
    rows, _ = reconcile_portfolios(sources=sources, varieties=varieties,
                                  entities=entities, candidates=candidates,
                                  source_ids={s["id"] for s in rights})
    source_ids = {s["id"] for s in rights}
    refs = {}
    for source in rows:
        if source["id"] not in source_ids:
            continue
        for name in source["names"]:
            if name.get("catalog_id") != variety["id"]:
                continue
            url = _public_url(source["url"])
            if not url:
                continue
            capture = source.get("capture_reference") or {}
            key = (url, name.get("grant_number") or name.get("application_number") or "")
            refs[key] = {
                "source_id": source["id"], "title": source["title"], "url": url,
                "number": name.get("grant_number") or name.get("application_number") or "",
                "published_date": source.get("published_date") or name.get("grant_date") or "",
                "checked_on": source["checked_on"],
                "document_url": _public_url(name.get("product_url")) or _public_url(capture.get("original_pdf_url")),
                "claim_url": _public_url(capture.get("claim_url")),
                "figures_url": _public_url(capture.get("figures_url")),
                "context": name.get("portfolio_context") or source["limitations"],
            }
    return sorted(refs.values(), key=lambda r: (r["published_date"], r["checked_on"], r["title"]), reverse=True)
