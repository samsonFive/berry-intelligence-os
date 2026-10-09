"""Pure News selection over retained source metadata, not a new trust store."""
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services import feed_first, personal_digest
from app.services.chronology import parse_stamp
from app.services.geography_hierarchy import record_geography_ids, resolve_geography_scope
from app.services.global_explorer import IntelligenceQuery
from app.services.berries.landscape import SEED_FIXTURE_EVIDENCE_IDS
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import QualificationIndex, qualify_hit
from app.services import company_source_scope
from app.services.company_source_scope import source_reviewed

NEWS_TYPES = {
    "news_search", "trade_press", "web_article", "company_press_release", "company_website",
    "brand_website", "industry_association_report", "industry_association_profile",
    "research_program_publication", "private_equity_press_release", "press_release",
    "news_article", "newsletter", "industry_report",
}
PAGE_SIZE = 36


def escalations(facts):
    result = {}
    for fact in facts:
        if fact.get("status") != "active":
            continue
        for source_id in fact.get("evidence_ids") or []:
            result.setdefault(str(source_id), []).append(fact)
    return result


def parameters(params):
    """Retain bookmarked feed/map scope, while normalizing to one News vocabulary."""
    values = {key: str(params.get(key) or "").strip() for key in
              ("q", "view", "berry", "countries", "company", "list", "tier", "favorites", "window", "start", "end", "tz")}
    values["view"] = values["view"] or "unreviewed"
    if values["view"] not in {"trusted", "unreviewed"}:
        raise ValueError("Choose Trusted or Unreviewed")
    if not values["berry"]:
        values["berry"] = str(params.get("crop") or "")
    values["berry"] = ",".join(dict.fromkeys(
        key if key.startswith("berry-") else "berry-" + key
        for key in values["berry"].split(",") if key))
    values["countries"] = values["countries"] or str(params.get("country") or params.get("geography") or "")
    values["company"] = values["company"] or str(params.get("entity") or "")
    if values["window"] not in {"", "today", "7d", "30d", "ytd", "custom", "undated"}:
        raise ValueError("Choose a supported date range")
    if values["tier"] not in {"", "tier1", "tier2", "tier3", "untiered", "watch", "muted"}:
        raise ValueError("Choose a supported company tier")
    if values["favorites"] not in {"", "1"}:
        raise ValueError("Choose a supported favorites filter")
    return values


def model(*, records, entities, relationships, facts, state, params, now=None):
    filters = parameters(params)
    try:
        zone = ZoneInfo(filters["tz"] or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Choose a valid timezone") from None
    filters["tz"] = zone.key
    instant = now or datetime.now(UTC)
    day = instant.astimezone(zone).date()
    starts = {"today": day, "7d": day - timedelta(days=6), "30d": day - timedelta(days=29), "ytd": day.replace(month=1, day=1)}
    start, end = starts.get(filters["window"]), day
    if filters["window"] == "custom":
        from datetime import date
        try:
            start = date.fromisoformat(filters["start"]) if filters["start"] else None
            end = date.fromisoformat(filters["end"]) if filters["end"] else day
        except ValueError:
            raise ValueError("Choose valid start and end dates") from None
        if start and start > end:
            raise ValueError("Start date must come before end date")
    query = IntelligenceQuery.parse(filters["countries"], filters["berry"], entities,
                                    {"berry-" + key: label for key, label in feed_first.CROP_LABELS.items()})
    from dataclasses import replace
    query = replace(query, view=filters["view"])
    filters["countries"], filters["berry"] = query.params()["countries"], query.params()["berry"]
    scope = set()
    for key in query.geography_ids:
        scope.update(resolve_geography_scope(key, relationships=relationships).all_ids)
    lists = personal_digest.company_lists(state)
    selected_list = next((row for row in lists if row["id"] == filters["list"]), None)
    if filters["list"] and selected_list is None:
        raise ValueError("Company list is unavailable")
    if filters["company"] and filters["company"] not in entities:
        raise ValueError("Company is unavailable")
    subjects = company_source_scope.candidates(entities, state, filters)
    support = escalations(facts)
    qualification = QualificationIndex.compile(
        company_names=[name for row in entities.values() if row.get("entity_type") == "company"
                       for name in [row.get("name", ""), *(row.get("aliases") or [])]],
        variety_names=[row.get("name", "") for row in entities.values() if row.get("entity_type") == "variety"],
    )
    counts = {"trusted": 0, "unreviewed": 0}
    matched = []
    for record in records.values():
        key = str(record.get("id") or "")
        if key in SEED_FIXTURE_EVIDENCE_IDS or not feed_first.SAFE_ID_RE.fullmatch(key):
            continue
        article_capture = (record.get("source_type") == "discovered_media"
                           and record.get("media_format") == "web_article")
        if (record.get("source_type") not in NEWS_TYPES and not article_capture) or "structural" in (record.get("tags") or []):
            continue
        hit = DiscoveryHit(title=str(record.get("title") or ""), snippet=str(record.get("summary") or ""),
                           url=str(record.get("source_url") or ""), source_domain="", published_date=record.get("published_date"),
                           query_id="news-workspace", query_text="", geography="", berry=None, topic=None, provider="stored-source")
        if not qualify_hit(hit, index=qualification).qualifying:
            continue
        stamp = parse_stamp(record.get("published_date"))
        # Publication dates, never capture dates. Undated items have their own view.
        published_day = (stamp.date() if len(str(record.get("published_date"))) == 10
                         else stamp.astimezone(zone).date()) if stamp else None
        if filters["window"] == "undated":
            if stamp:
                continue
        elif (not stamp or published_day > day or (len(str(record.get("published_date"))) > 10 and stamp > instant)
              or (start and published_day < start) or (end and published_day > end)):
            continue
        if query.commodities() and not set(query.commodities()).intersection(record.get("berry_ids") or []):
            continue
        if (query.country_codes and not scope) or (scope and not scope.intersection(record_geography_ids(record))):
            continue
        linked, mentions = company_source_scope.links(record, subjects)
        if filters["favorites"] == "1" and not any((state.get("entity_favorites") or {}).get(key) for key in linked):
            continue
        if filters["company"] and filters["company"] not in linked:
            continue
        if selected_list and not linked.intersection(selected_list.get("company_ids") or []):
            continue
        company_ids = {key for key in linked if (entities.get(key) or {}).get("entity_type") == "company"}
        tiers = {str((state.get("entity_tiers") or {}).get(key) or "untiered") for key in company_ids}
        if filters["tier"] and filters["tier"] not in tiers:
            continue
        if filters["tier"] != "muted" and company_ids and all(tier == "muted" for tier in tiers):
            continue
        haystack = " ".join(str(record.get(field) or "") for field in ("title", "summary", "source_name"))
        if filters["q"].casefold() not in haystack.casefold():
            continue
        trusted = source_reviewed(record) and key in support
        counts["unreviewed"] += 1  # Raw source lane includes reviewed sources, labeled separately.
        counts["trusted"] += int(trusted)
        if filters["view"] == "trusted" and not trusted:
            continue
        matched.append((record, stamp, trusted, mentions))
    matched.sort(key=lambda row: (row[1] or datetime.min.replace(tzinfo=UTC), row[0]["id"]), reverse=True)
    pages = max(1, (len(matched) + PAGE_SIZE - 1) // PAGE_SIZE)
    try:
        page = min(pages, max(1, int(params.get("page") or 1)))
    except ValueError:
        page = 1
    cards = []
    # Only metadata is presented; the selected Reader alone hydrates capture text.
    for record, _, trusted, mentions in matched[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]:
        preview = {key: value for key, value in record.items() if key not in
                   {"article", "transcript", "transcript_excerpt", "images", "reader_capture"}}
        preview["article"] = {"image_url": feed_first.safe_image_url(record)}
        card = feed_first.present_item(preview, entities_by_id=entities, state=state, filters=feed_first.parse_filters({}))
        from app.services.feed_first_reader import is_public_http_url
        card["source_url"] = card["source_url"] if is_public_http_url(card["source_url"]) else ""
        card.update(trusted=trusted, source_reviewed=source_reviewed(record), escalated_count=len(support.get(card["id"], [])))
        card["company_mentions"] = mentions
        card["entities"] = [row for row in card["entities"] if (entities.get(row["id"]) or {}).get("entity_type") in {"company", "brand", "research_program"}]
        cards.append(card)
    date_label = {'': 'All dated news', 'today': 'Today', '7d': 'Past 7 days', '30d': 'Past 30 days',
                  'ytd': 'Year to date', 'undated': 'Publication date unavailable'}.get(filters['window'])
    if filters['window'] == 'custom':
        date_label = (filters['start'] or 'Earliest recorded') + ' through ' + (filters['end'] or 'Today')
    filter_summary = [date_label + ' / ' + filters['tz']]
    if filters['company']:
        filter_summary.append(entities[filters['company']].get('name') or 'Selected company')
    if filters['berry']:
        filter_summary.append(', '.join(feed_first.CROP_LABELS[key.removeprefix('berry-')] for key in query.commodities()))
    if query.geography_ids:
        filter_summary.append(', '.join(entities[key].get('name') or 'Selected country' for key in query.geography_ids))
    if query.country_codes:
        from app.services.global_explorer import boundary_countries
        filter_summary.append(', '.join(boundary_countries()[code] for code in query.country_codes))
    if filters['list']:
        filter_summary.append(next(row.get('name') or 'Selected list' for row in lists if row['id'] == filters['list']))
    if filters['tier']:
        from app.services.company_directory import TIERS
        filter_summary.append(TIERS[filters['tier']])
    if filters['favorites']:
        filter_summary.append('Favorite companies')
    if filters['q']:
        filter_summary.append('Search: ' + filters['q'])
    return {"cards": cards, "matching": len(matched), "matching_ids": [r[0]["id"] for r in matched], "counts": counts, "filters": filters,
            "filter_summary": filter_summary,
            "page": page, "pages": pages, "lists": lists, "query": query}
