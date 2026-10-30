"""Private, versioned collection controls shared by the UI and collectors.

Defaults remain code-owned. Overrides live in the persistent inbox, never in
the public static snapshot. Removing a default leaves a reversible tombstone.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import replace
from datetime import datetime, timezone
from functools import wraps
import hashlib
import csv
import ipaddress
import json
import os
import re
from pathlib import Path
import uuid
from urllib.parse import urlsplit, parse_qs, urlencode

from app.runtime_config import resolve_inbox_dir

_defaults = ContextVar("collection_defaults", default=False)
GROUPS = {
    "today_google": "News · Google News (30-day collection window)",
    "today_perplexity": "News · Perplexity catch-net; first two also serve enabled Exa / APITube",
    "today_official": "News · official publisher searches",
    "pulse": "Industry discovery · Google News and enabled catch-net providers",
    "week": "Weekly discovery · Google News and enabled providers",
    "exa": "Weekly semantic discovery · Exa",
    "radar_google": "Radar · Google News",
    "radar_semantic": "Radar · Exa",
    "radar_catchnet": "Radar · optional Perplexity",
    "catchall": "Background recall · NewsCatcher CatchAll",
}

REGIONS = {"global": "Global", "apac": "Asia-Pacific", "asia_pacific": "Asia-Pacific",
           "americas": "Americas", "europe": "Europe", "africa": "Africa",
           "north_america": "North America", "south_america": "South America"}
WORKFLOWS = {"pulse": "Industry discovery", "week": "Weekly edition", "exa": "Weekly edition",
             "today_google": "News", "today_perplexity": "News", "today_official": "News",
             "radar_google": "Emerging developments", "radar_semantic": "Emerging developments",
             "radar_catchnet": "Emerging developments", "catchall": "Background recall"}
PROVIDERS = {"today_google": "Google News", "today_official": "Google News",
             "today_perplexity": "Perplexity", "pulse": "Google News + optional providers",
             "week": "Google News + optional providers", "exa": "Exa", "radar_google": "Google News",
             "radar_semantic": "Exa", "radar_catchnet": "Perplexity (optional)",
             "catchall": "NewsCatcher CatchAll"}
TOPIC_NAMES = {
    "new_variety": "New varieties", "breeder_genetics": "Breeding and genetics",
    "commercial_launch": "Commercial launches", "licensing_partnership": "Licensing and partnerships",
    "pbr_patent": "Plant variety rights and patents", "acreage_production": "Acreage and production",
    "trade": "Trade", "weather_crop": "Weather and crop conditions", "pricing_market": "Pricing and markets",
    "ma_investment": "Investment and acquisitions", "trials_academic": "Trials and research",
    "disease_regulation": "Disease and regulation", "retail": "Retail and supermarkets",
    "partnership": "Breeding partnerships", "variety": "Variety launches", "expansion": "Production expansion",
    "access": "Market access", "ip": "Plant variety protection", "cea": "Controlled environment production",
    "supply": "Supply and harvest volumes", "breeding-partnerships": "Breeding partnerships",
    "cultivar-commercialization": "Cultivar commercialization", "licensing": "Variety licensing",
    "cea-production": "Controlled environment production", "disease-resistance": "Disease resistance",
    "shelf-life": "Shelf life", "production-expansion": "Production expansion", "new-markets": "Export markets",
    "supply-pressure": "Supply pressures", "retailer-programs": "Retailer programs",
    "unusual-rd": "Breeding innovations", "emerging-systems": "Emerging growing systems",
    "genetics": "Genetics and commercialization", "genetics-licensing": "Genetics and licensing",
    "apac-supply": "Supply and market access", "vaccinium-traits": "Cultivar traits",
    "fragaria-traits": "Cultivar traits", "rubus-traits": "Caneberry genetics and rights",
    "supply-chain": "Supply chain agreements",
}

BERRY_CHOICES = {"all": "All berries", "blackberry": "Blackberry", "blueberry": "Blueberry",
                 "raspberry": "Raspberry", "strawberry": "Strawberry"}
REGION_CHOICES = {key: REGIONS[key] for key in ("global", "americas", "europe", "africa", "apac")}
BUILDER_DESTINATIONS = {
    "today_google": {"label": "News feed · Google News (recommended)",
        "help": "Use for topics you want in News. The next News refresh searches Google News within its 30-day collection window; reading filters still apply."},
    "pulse": {"label": "Industry discovery · Google News and enabled providers",
        "help": "Use for broader industry monitoring. Runs with the Industry discovery workflow when requested or enabled; it does not start a new scheduled job."},
    "week": {"label": "Weekly edition · Google News and enabled providers",
        "help": "Use for searches needed when assembling the weekly discovery edition. Saving does not fetch or refresh that edition."},
    "radar_google": {"label": "Emerging developments · Google News",
        "help": "Use for developing themes or early announcements collected by the existing Radar workflow when it runs."},
    "exa": {"label": "Weekly edition · Exa",
        "help": "Use for broader web or concept searches in the weekly edition. Requires configured Exa access; provider charges may apply when collection runs."},
    "radar_semantic": {"label": "Emerging developments · Exa",
        "help": "Use Exa web search for emerging themes. Requires configured Exa access; provider charges may apply when collection runs."},
    "today_perplexity": {"label": "News feed · Perplexity",
        "help": "Use the optional Perplexity News search path. Requires configured access. The first two enabled catch-net queries also serve configured Exa/APITube fallbacks; adding here does not enable those services."},
    "radar_catchnet": {"label": "Emerging developments · Perplexity",
        "help": "Use the optional Perplexity catch-net for developing themes. Requires configured access and the existing provider opt-in."},
    "catchall": {"label": "Background recall · NewsCatcher CatchAll",
        "help": "Use for broader background news discovery. Runs with the existing background recall pipeline and requires configured NewsCatcher access; results enter its discovery cache."},
}


LANGUAGE_EDITIONS = {"automatic": None, "en-US": ("en-US", "US", "US:en"),
                     "pl-PL": ("pl-PL", "PL", "PL:pl"), "pt-BR": ("pt-BR", "BR", "BR:pt")}


def compile_custom_query(*, query_input, input_mode="simple", scope_berry="all", scope_region="global", term_match="any", search_language="automatic"):
    """Compile explicit crop/place constraints once, for both preview and dispatch."""
    from app.services.industry_pulse.matrix import BERRY_TERMS, ALL_BERRIES_TERMS, GEO_EDITIONS
    if scope_berry not in BERRY_CHOICES or scope_region not in REGION_CHOICES:
        raise ValueError("Choose a berry and a supported region.")
    if input_mode not in {"simple", "advanced"} or term_match not in {"any", "all"}:
        raise ValueError("Choose a supported search format and term matching option.")
    raw = query_input.strip()
    if not raw or len(raw) > 1200 or any(ord(c) < 32 and c not in "\r\n\t" for c in raw):
        raise ValueError("Enter search terms or an expression of up to 1,200 characters.")
    terms = []
    if input_mode == "simple":
        try:
            terms = list(dict.fromkeys(term.strip() for line in csv.reader(raw.splitlines(), skipinitialspace=True, strict=True)
                                      for term in line if term.strip()))
        except csv.Error:
            raise ValueError("Check the quotation marks, or put each term on its own line.") from None
        if not terms or len(terms) > 20:
            raise ValueError("Enter between one and 20 terms or phrases, separated by lines or commas.")
        if any(re.search(r"\b(?:OR|AND|NOT)\b|[()\"]|^[-+]", term) for term in terms):
            raise ValueError("For alternatives, put each term on a separate line. Choose Advanced expression to use operators or exclusions.")
        parts = [term if re.fullmatch(r"[\w-]+", term) else '"' + term + '"' for term in terms]
        subject = (" OR " if term_match == "any" else " AND ").join(parts)
    else:
        subject = " ".join(raw.splitlines()).strip()
    berry_clause = BERRY_TERMS[scope_berry] if scope_berry != "all" else '(' + ' OR '.join(value.strip('()') for value in BERRY_TERMS.values()) + ')'
    # Keep each provider query compact. Native vocabulary belongs to the
    # selected edition, rather than inflating every English matrix row.
    native = {
        'pl-PL': {'blueberry': 'borówka OR borówki OR borówek', 'strawberry': 'truskawka OR truskawki OR truskawek',
                  'raspberry': 'malina OR maliny OR malin', 'blackberry': 'jeżyna OR jeżyny OR jeżyn'},
        'pt-BR': {'blueberry': 'mirtilo OR mirtilos', 'strawberry': 'morango OR morangos',
                  'raspberry': 'framboesa OR framboesas', 'blackberry': 'amora-preta OR amoras-pretas'},
    }.get(search_language)
    if native:
        berry_clause = '(' + (native[scope_berry] if scope_berry != 'all' else ' OR '.join(native.values())) + ')'
    if scope_berry == "blackberry":
        # Caneberry also describes raspberry; an explicit crop choice should stay narrower.
        berry_clause = berry_clause.replace(" OR caneberry", "")
    edition = GEO_EDITIONS[scope_region]
    if search_language not in LANGUAGE_EDITIONS:
        raise ValueError("Choose a supported search language.")
    if LANGUAGE_EDITIONS[search_language]:
        edition = {**edition, **dict(zip(("hl", "gl", "ceid"), LANGUAGE_EDITIONS[search_language]))}
    if input_mode == "advanced":
        from app.services.monitor_expression import grouped_expression
        try:
            subject = grouped_expression(subject)
        except ValueError:
            subject = f'({subject})'  # Provider-specific syntax remains available for prospective discovery.
    else:
        subject = f'({subject})'
    expression = f"{subject} AND {berry_clause}"
    if edition["terms"]:
        expression += " AND " + edition["terms"]
    if len(expression) > 2000:
        raise ValueError("This search is too long after adding berry and region terms. Shorten the topic terms.")
    return {"query_builder": True, "input_mode": input_mode, "query_input": raw, "term_match": term_match,
            "scope_berry": scope_berry, "scope_region": scope_region, "search_language": search_language, "query_terms": terms, "text": expression,
            "berry": None if scope_berry == "all" else scope_berry, "geography": scope_region,
            "hl": edition["hl"], "gl": edition["gl"], "ceid": edition["ceid"]}


def query_name(query):
    """Name the search subject; routing dimensions belong in their own columns."""
    key = query.id
    if key.startswith("lang:"):
        return "Regional industry developments"
    if key.startswith("apac:"):
        return "Harvest, markets and varieties"
    if key.startswith("today:official:") or key.startswith("site:"):
        host = re.search(r"\bsite:([^\s)]+)", query.text)
        return (host[1] if host else key.split(":")[-1]) + " coverage"
    if key.startswith("pulse:") or key.startswith("today:"):
        return "Industry developments"
    subject = query.topic if key.startswith("topic:") else key.split(":")[-1]
    return TOPIC_NAMES.get(subject, subject.replace("_", " ").replace("-", " ").capitalize())


def query_dimensions(row):
    """Display configured scope and literal crop terms without changing retrieval."""
    declared = row.get("berry")
    if declared:
        berries = [declared.removeprefix("berry-").capitalize()]
    else:
        berries = [label for label, pattern in (
            ("Blackberry", r"\b(?:blackberr(?:y|ies)|zarzamora|mûre)\b|ブラックベリー|黑莓"),
            ("Blueberry", r"\b(?:blueberr(?:y|ies)|arándano|arandano|myrtille)\b|ブルーベリー|蓝莓"),
            ("Raspberry", r"\b(?:raspberr(?:y|ies)|frambuesa|framboise)\b|ラズベリー|覆盆子"),
            ("Strawberry", r"\b(?:strawberr(?:y|ies)|fresa|fraise)\b|イチゴ|草莓"))
            if re.search(pattern, row.get("text", ""), re.I)]
    groups = row.get("member_groups") or [row.get("group", "")]
    workflows = list(dict.fromkeys(WORKFLOWS.get(group, group) for group in groups))
    language = (row.get("hl") or "en-US").split("-")[0]
    return {"berry_labels": berries or ["Not specified"],
            "region_labels": [REGIONS.get(row.get("geography", "global"), row.get("geography", "Global"))],
            "workflow_labels": workflows,
            "provider_labels": list(dict.fromkeys(PROVIDERS.get(group, group) for group in groups)),
            "language_label": {"en": "English", "es": "Spanish", "fr": "French", "zh": "Chinese", "ja": "Japanese", "pl": "Polish", "pt": "Portuguese"}.get(language, language),
            "search_kind": "Regional-language search" if row.get("query_kind") == "regional_language" else "Discovery search"}


def settings_path(inbox_dir=None):
    return Path(inbox_dir or resolve_inbox_dir()) / "operations" / "collection_settings.json"


def load(inbox_dir=None):
    path = settings_path(inbox_dir)
    if not path.exists():
        return {"version": 1, "entries": {}, "history": []}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("version") != 1 or not isinstance(value.get("entries"), dict):
            raise ValueError()
        return value
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Collection settings could not be read; no settings were overwritten.") from exc


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _write(value, inbox_dir):
    path = settings_path(inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def configured(group):
    """Apply overrides on every generator call, not only at process startup."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            rows = function(*args, **kwargs)
            return rows if _defaults.get() else apply_queries(rows, group)
        return wrapped
    return decorate


def apply_queries(rows, group, inbox_dir=None):
    from app.services.industry_pulse.matrix import PulseQuery
    entries = load(inbox_dir)["entries"]
    result = []
    for row in rows:
        entry = entries.get(row.id, {})
        if entry.get("removed") or entry.get("enabled") is False:
            continue
        text = entry.get("text", row.text)
        if entry.get("text") and row.date_window:
            from app.services.industry_pulse.matrix import WINDOW_WHEN
            import re
            text = re.sub(r"\s+when:\d+d\s*$", "", text) + " when:" + WINDOW_WHEN[row.date_window]
        dimensions = {k: entry[k] for k in ("berry", "geography", "hl", "gl", "ceid") if entry.get("query_builder") and k in entry}
        result.append(replace(row, text=text, **dimensions))
    seen = {row.id for row in result}
    for key, entry in entries.items():
        if (entry.get("custom") and entry.get("kind") == "query" and entry.get("group") == group
                and entry.get("enabled", True) and not entry.get("removed") and key not in seen):
            scoped = entry.get("query_builder") is True
            query = PulseQuery(id=key, text=entry["text"], berry=entry.get("berry") if scoped else None,
                geography=entry.get("geography", "global") if scoped else "global",
                topic="industry_pulse" if group == "pulse" else "custom", kind="topic_global",
                hl=entry.get("hl", "en-US") if scoped else "en-US",
                gl=entry.get("gl", "US") if scoped else "US", ceid=entry.get("ceid", "US:en") if scoped else "US:en")
            if group.startswith("today_"):
                query = query.with_window("30d" if group == "today_google" else "24h")
            result.append(query)
    return result


def effective_feeds(defaults, inbox_dir=None):
    if _defaults.get():
        return list(defaults)
    entries = load(inbox_dir)["entries"]
    result = []
    for feed in defaults:
        entry = entries.get(feed["id"], {})
        if not entry.get("removed") and entry.get("enabled", True):
            editable = ("label",) if feed.get("registry_managed") else ("label", "feed_url", "host")
            result.append({**feed, **{k: entry[k] for k in editable if k in entry}})
    result.extend({**entry, "id": key} for key, entry in entries.items()
                  if entry.get("custom") and entry.get("kind") == "feed"
                  and entry.get("enabled", True) and not entry.get("removed"))
    return result


def catalog(official_hosts=None):
    from app.services.industry_pulse.matrix import generate_pulse_queries
    from app.services.global_week import week_queries
    from app.services.industry_pulse.exa_queries import week_unknown_unknown_queries
    from app.services.emerging_radar.queries import radar_google_queries, radar_semantic_queries, radar_catchnet_queries
    from app.services.industry_pulse.catchall_recall import CATCHALL_RECALL_QUERIES
    from app.services.industry_pulse.specialist_feeds import configured_feeds
    from app.services.feed_first_live import today_google_queries, today_perplexity_queries, today_official_site_queries
    marker = _defaults.set(True)
    try:
        queries = {}
        for group, rows in (("today_google", today_google_queries()), ("today_perplexity", today_perplexity_queries()),
                            ("today_official", today_official_site_queries(official_hosts, include_all=True)),
                            ("pulse", generate_pulse_queries()), ("week", week_queries()),
                            ("exa", week_unknown_unknown_queries()), ("radar_google", radar_google_queries()),
                            ("radar_semantic", radar_semantic_queries()), ("radar_catchnet", radar_catchnet_queries()),
                            ("catchall", CATCHALL_RECALL_QUERIES)):
            for row in rows:
                if row.id in queries:
                    queries[row.id]["member_groups"].append(group)
                    continue
                queries[row.id] = {"id": row.id, "kind": "query", "group": group, "member_groups": [group],
                    "text": row.text, "label": query_name(row), "berry": row.berry, "geography": row.geography,
                    "hl": row.hl, "query_kind": row.kind, "enabled": True}
        from app.services.default_keyword_monitors import metadata
        for key, row in queries.items():
            scoped = metadata(key)
            if scoped:
                row.update(scoped)
        for feed in configured_feeds():
            queries[feed["id"]] = {**feed, "kind": "feed", "group": "specialist", "enabled": True}
        return queries
    finally:
        _defaults.reset(marker)


def view_model(sources, inbox_dir, data_dir, official_hosts=None):
    state = load(inbox_dir)
    rows = catalog(official_hosts)
    for key, entry in state["entries"].items():
        baseline = rows.get(key, {"id": key})
        merged = {**baseline, **entry}
        if baseline.get('registry_managed'):
            for field in ('feed_url', 'host', 'source_id', 'adapter'):
                merged[field] = baseline[field]
        elif entry.get('registry_managed') and key not in rows:
            merged['enabled'] = False  # The owning Source is no longer eligible.
        if key in rows and baseline["kind"] == "query":
            # Earlier editor versions persisted the generated technical label.
            # Upgrade only that exact label, never an analyst's custom name.
            legacy = key.replace(":", " · ").replace("_", " ").title()
            if entry.get("label") == legacy:
                merged["label"] = baseline["label"]
            for field in (("query_kind", "member_groups") if baseline.get("query_builder") else ("berry", "geography", "hl", "query_kind", "member_groups")):
                merged[field] = baseline[field]
        rows[key] = merged
    for row in rows.values():
        row["revision"] = fingerprint(state["entries"].get(row["id"], {}))
        if row["kind"] == "query":
            row.update(query_dimensions(row))
        else:
            row.update(berry_labels=["Not specified"], region_labels=[REGIONS.get(row.get("geography", "global"), "Global")])
    source_rows = []
    for source in sources:
        discovery = source.get("discovery") or {}
        adapter = discovery.get("adapter", "")
        urls = discovery.get("feed_urls") or [discovery.get("feed_url") or source.get("value", "")]
        source_input = "\n".join(urls)
        if adapter == "news_search_rss":
            source_input = parse_qs(urlsplit(urls[0]).query).get("q", [source_input])[0]
        source_rows.append({**source, "revision": fingerprint(source), "input": source_input,
                            "adapter": adapter, "removed": source.get("collection_removed", False),
                            "berry_labels": [value.removeprefix("berry-").capitalize() for value in (source.get("berry_ids") or [])] or ["Not specified"],
                            "region_labels": [REGIONS.get(value, value.replace("_", " ").title()) for value in (source.get("region_coverage") or [])] or ["Not specified"],
                            "term_source": source.get("type") == "keyword" or adapter == "news_search_rss"})
    pipeline_path = Path(data_dir) / "configuration" / "collection_pipelines.json"
    pipelines = json.loads(pipeline_path.read_text(encoding="utf-8")).get("pipelines", []) if pipeline_path.exists() else []
    return {"queries": [r for r in rows.values() if r["kind"] == "query"],
            "feeds": [r for r in rows.values() if r["kind"] == "feed"], "sources": source_rows,
            "groups": GROUPS, "pipelines": pipelines, "history": list(reversed(state.get("history", [])[-20:])),
            "builder_destinations": BUILDER_DESTINATIONS, "berry_choices": BERRY_CHOICES, "region_choices": REGION_CHOICES}


def public_url(value):
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Enter a public HTTP or HTTPS URL without credentials.")
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
        raise ValueError("Use a public publisher URL.")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError("Use a public publisher URL.")
    except ValueError as exc:
        if str(exc) == "Use a public publisher URL.":
            raise
    return value


def change(inbox_dir, *, key, kind, group, action, revision, label="", text="", enabled=True, actor="analyst", official_hosts=None,
           query_builder=False, query_input="", input_mode="simple", scope_berry="all", scope_region="global", term_match="any", search_language="automatic"):
    """Caller holds the shared collection lease. Stale forms never win silently."""
    state = load(inbox_dir)
    old = state["entries"].get(key, {})
    defaults = catalog(official_hosts)
    if key:
        if key not in defaults and key not in state["entries"]:
            raise ValueError("Collection entry no longer exists.")
        if fingerprint(old) != revision:
            raise ValueError("This entry changed since you opened it. Reload before saving.")
        baseline = {**defaults.get(key, {}), **old}
        if defaults.get(key, {}).get('registry_managed'):
            for field in ('feed_url', 'host', 'source_id', 'adapter'):
                baseline[field] = defaults[key][field]
        kind, group = baseline["kind"], baseline["group"]
    else:
        if action != "save" or kind not in {"query", "feed"}:
            raise ValueError("Invalid collection action.")
        if kind == "query" and group not in GROUPS:
            raise ValueError("Choose a collection destination.")
        if sum(bool(e.get("custom")) and not e.get("removed") for e in state["entries"].values()) >= 30:
            raise ValueError("The 30 custom-entry collection limit has been reached.")
        key = "custom:" + uuid.uuid4().hex
        baseline = {"kind": kind, "group": group if kind == "query" else "specialist", "custom": True}
    if action == "restore":
        if baseline.get("custom") and baseline.get("removed") and sum(
                bool(e.get("custom")) and not e.get("removed") for e in state["entries"].values()) >= 30:
            raise ValueError("The 30 custom-entry collection limit has been reached.")
        entry = {**baseline, "removed": False, "enabled": True}
    elif action == "remove":
        entry = {**baseline, "removed": True, "enabled": False}
    elif action == "save":
        compiled = None
        if kind == "query" and (query_builder or baseline.get("query_builder")):
            if not (baseline.get("custom") or baseline.get("query_builder")) or group not in BUILDER_DESTINATIONS:
                raise ValueError("Use the scoped builder for a custom discovery monitor. Publisher-specific sources stay in Sources.")
            compiled = compile_custom_query(query_input=query_input, input_mode=input_mode, scope_berry=scope_berry,
                                             scope_region=scope_region, term_match=term_match, search_language=search_language)
            text = compiled["text"]
        if not label.strip() or len(label) > 150 or not text.strip() or len(text) > 2000 or any(ord(c) < 32 for c in text):
            raise ValueError("Enter a name (up to 150 characters) and terms or URL (up to 2,000 characters).")
        entry = {**baseline, "label": label.strip(), "enabled": bool(enabled), "removed": False}
        if kind == "feed":
            if baseline.get("registry_managed") and text.strip() != baseline.get("feed_url"):
                raise ValueError("This feed uses the Source registry. Edit its URL under Sources so every collector uses the same path.")
            entry["feed_url"] = public_url(text.strip())
            if baseline.get("adapter") != "news_search_rss":
                entry["host"] = urlsplit(text.strip()).hostname.removeprefix("www.")
            if baseline.get("custom"):
                entry.update(adapter="article_rss", geography="global", source_id=key)
        else:
            entry["text"] = text.strip()
            if compiled is not None:
                entry.update(compiled)
    else:
        raise ValueError("Invalid collection action.")
    state["entries"][key] = entry
    state["history"] = [*state.get("history", []), {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "actor": actor, "action": action, "label": entry.get("label", key)}][-200:]
    _write(state, inbox_dir)
    return key


def record_source_change(inbox_dir, key, action, actor, label):
    state = load(inbox_dir)
    state["history"] = [*state.get("history", []), {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "actor": actor, "action": action, "label": label or key}][-200:]
    _write(state, inbox_dir)


def change_source(repository, *, key, action, revision, label, text, enabled, source_type, priority, cadence):
    """Edit the real registry consumed by article collectors; keep adapter options/history."""
    current = repository.get(key) if key else None
    if key and current is None:
        raise ValueError("Source no longer exists. Reload the page.")
    if current and fingerprint(current) != revision:
        raise ValueError("This source changed since you opened it. Reload before saving.")
    if action in {"remove", "restore"}:
        if not current:
            raise ValueError("Source not found.")
        record = {**current, "enabled": action == "restore", "collection_removed": action == "remove"}
    elif action == "save":
        if not label.strip() or len(label) > 150 or not text.strip() or len(text) > 4000:
            raise ValueError("Enter a source name and feed URLs or search terms.")
        if source_type not in {"rss", "keyword", "reference"}:
            raise ValueError("Choose an RSS feed, keyword search, or manual reference.")
        if priority not in {"", "low", "medium", "high"} or cadence not in {"", "realtime", "daily", "weekly", "biweekly", "monthly", "quarterly", "annual", "event_driven"}:
            raise ValueError("Invalid priority or cadence.")
        record = dict(current or {"id": "source-ui-" + uuid.uuid4().hex, "type": source_type,
            "created_at": datetime.now(timezone.utc).date().isoformat(), "last_checked_at": None, "last_status": None})
        source_type = record["type"]  # Retain adapter identity on edits.
        discovery = dict(record.get("discovery") or {})
        adapter = discovery.get("adapter", "")
        term_source = source_type == "keyword" or adapter == "news_search_rss"
        if term_source:
            if "\n" in text or "\r" in text or len(text) > 2000:
                raise ValueError("Enter one search expression of up to 2,000 characters.")
            old_url = discovery.get("feed_url", "")
            edition = parse_qs(urlsplit(old_url).query)
            feed = "https://news.google.com/rss/search?" + urlencode({"q": text.strip(),
                "hl": edition.get("hl", ["en-US"])[0], "gl": edition.get("gl", ["US"])[0],
                "ceid": edition.get("ceid", ["US:en"])[0]})
            discovery.update(adapter="news_search_rss", feed_url=feed)
            discovery.pop("feed_urls", None)
            record["value"] = text.strip() if source_type == "keyword" else feed
        elif source_type == "reference" and not adapter:
            record["value"] = text.strip()
        else:
            urls = [public_url(url.strip()) for url in text.splitlines() if url.strip()]
            if not urls or len(urls) > 10:
                raise ValueError("Enter between one and ten public feed URLs, one per line.")
            discovery["adapter"] = adapter or "article_rss"
            discovery.pop("feed_url", None)
            discovery.pop("feed_urls", None)
            discovery["feed_url" if len(urls) == 1 else "feed_urls"] = urls[0] if len(urls) == 1 else urls
            record["value"] = urls[0]
        if discovery:
            old_urls = (current or {}).get("discovery", {})
            if any(discovery.get(k) != old_urls.get(k) for k in ("feed_url", "feed_urls")):
                discovery.pop("feed_url_verified_at", None)
            record["discovery"] = discovery
        record.update(label=label.strip(), enabled=bool(enabled), collection_removed=False,
                      monitoring_priority=priority or None, update_cadence=cadence or None)
        if current is None and source_type in {"rss", "keyword"}:
            # Modern discovery is adapter-driven. Keep new entries out of the
            # legacy headline-only loop, which writes directly to data/evidence.
            record["type"] = "reference"
    else:
        raise ValueError("Invalid source action.")
    if current:
        repository.update(record["id"], record)
    else:
        repository.create(record)
    return record["id"]
