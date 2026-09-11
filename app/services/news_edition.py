"""Selection and pagination for the shared front-page projection. No writes."""
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.chronology import parse_stamp
from app.services.geography_hierarchy import resolve_geography_scope
from app.services.berries.landscape import SEED_FIXTURE_ENTITY_IDS, SEED_FIXTURE_EVIDENCE_IDS
from app.services.entity_alias_recall import match_evidence_to_entity
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import QualificationIndex, qualify_hit

WINDOWS = {"latest": "Latest · 14 days", "today": "Today", "week": "Last 7 days", "quarter": "Last 90 days",
           "archive": "Archive · all dated reporting", "undated": "Date not established"}
PAGE_SIZE = 24


def select_edition(items, *, entities, relationships, params, now=None):
    instant = now or datetime.now(UTC)
    timezone = params.get("tz") or "UTC"
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        timezone, zone = "UTC", UTC
    day = instant.astimezone(zone).date()
    window = params.get("date") or "latest"
    if window not in WINDOWS:
        window = "latest"
    berry = params.get("berry", "")
    berry = berry if not berry or berry.startswith("berry-") else "berry-" + berry
    company = params.get("company", "")
    company_entity = next((e for e in entities if e.get("id") == company and e.get("entity_type") == "company"), None)
    geography = params.get("geography", "")
    query = params.get("q", "").strip()
    scope = resolve_geography_scope(geography, relationships=relationships).all_ids if geography else set()
    filters = {"berry": berry, "company": company, "geography": geography,
               "q": query, "date": window, "tz": timezone}
    rows = []
    qualification = QualificationIndex.compile(
        company_names=[name for e in entities if e.get("entity_type") == "company" and e.get("id") not in SEED_FIXTURE_ENTITY_IDS for name in [e["name"], *(e.get("aliases") or [])]],
        variety_names=[e["name"] for e in entities if e.get("entity_type") == "variety" and e.get("id") not in SEED_FIXTURE_ENTITY_IDS],
    )
    for raw in items:
        if raw.get("id") in SEED_FIXTURE_EVIDENCE_IDS:
            continue
        if not raw.get("open_reader"):
            continue
        if berry and berry not in raw["berry_ids"]:
            continue
        company_mention = False
        if company and company not in raw["entity_ids"]:
            company_mention = bool(company_entity and match_evidence_to_entity(company_entity, raw))
            if not company_mention:
                continue
        if geography and not (scope & set(raw["geography_ids"])):
            continue
        if query and query.casefold() not in (raw["title"] + " " + raw["summary"] + " " + raw["source_name"]).casefold():
            continue
        hit = DiscoveryHit(title=raw["title"], snippet=raw["summary"], url=raw.get("source_url") or "",
                           source_domain="", published_date=raw.get("published_date"), query_id="news-edition",
                           query_text="", geography="", berry=None, topic=None, provider="stored-source")
        qualified = qualify_hit(hit, index=qualification)
        if not qualified.qualifying:
            continue
        stamp = parse_stamp(raw.get("published_date"))
        # A date-only publication has no time or timezone to convert.
        published_day = (stamp.date() if len(str(raw.get("published_date"))) == 10
                         else stamp.astimezone(zone).date()) if stamp else None
        if window == "undated":
            if stamp:
                continue
        elif not published_day or published_day > day or (len(str(raw.get("published_date"))) > 10 and stamp > instant):
            continue
        elif window == "today" and published_day != day:
            continue
        elif window in {"week", "latest", "quarter"} and published_day < day - timedelta(days={"week": 6, "latest": 13, "quarter": 89}[window]):
            continue
        item = dict(raw)
        item["relevance_reason"] = qualified.qualify_reason
        item["company_match_label"] = "Named source mention" if company_mention else ""
        item["exact_date"] = published_day.strftime("%b %d, %Y") if published_day else "Date not established"
        item["date_basis_label"] = "Published" if published_day else ""
        item["href"] = "/intelligence/" + str(item["id"])
        image_url = item.get("image_url") or ""
        try:
            parsed = urlsplit(image_url)
            item["image_url"] = image_url if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password else ""
        except ValueError:
            item["image_url"] = ""
        rows.append(item)
    rows.sort(key=lambda i: (parse_stamp(i.get("published_date")) or datetime.min.replace(tzinfo=UTC), i["id"]), reverse=True)
    try:
        page = max(1, int(params.get("page") or 1))
    except ValueError:
        page = 1
    total = len(rows)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    visible = rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
    def href(**changes):
        return "/today?" + urlencode({**filters, **changes})
    return {"filters": filters, "window_label": WINDOWS[window], "windows": WINDOWS,
            "day_label": day.strftime("%A, %B %d, %Y"), "items": visible,
            "lead": visible[0] if visible else None, "supporting": visible[1:4],
            "stream": visible[4:], "total": total, "page": page, "pages": pages,
            "previous": href(page=page-1) if page > 1 else None,
            "next": href(page=page+1) if page < pages else None,
            "archive_href": href(date="archive", page=1),
            "companies": sorted([e for e in entities if e.get("entity_type") == "company" and e.get("id") not in SEED_FIXTURE_ENTITY_IDS], key=lambda e: e["name"]),
            "geographies": sorted([e for e in entities if e.get("entity_type") == "geography"], key=lambda e: e["name"])}
