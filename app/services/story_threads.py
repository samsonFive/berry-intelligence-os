"""Presentation-only story threads (developing stories).

A thread groups related Evidence / publication drafts so the analyst reviews
one developing story instead of redundant documents. It is organizational
state only: not a Fact, Assessment, Position, Signal, or trusted conclusion.

Membership is conservative and deterministic. False separation is preferred
to merging unrelated stories. Same-company mention is never enough.
"""

from __future__ import annotations

from datetime import date
import re
import unicodedata
from typing import Any, Iterable

from app.services.article_dedup import normalize_canonical_url, normalize_title
from app.services.intelligence_feed import trust_state

DATE_PROXIMITY_EXACT_TITLE_DAYS = 14
DATE_PROXIMITY_EVENT_DAYS = 7
DATE_PROXIMITY_TRANSLATION_DAYS = 1
MIN_EVENT_JACCARD = 0.45
THREAD_LINK_PREDICATES = {"corroborates", "contradicts", "follows_up", "same_signal"}
STRONG_LINK_PREDICATES = {"follows_up", "same_signal"}
PRIMARY_SOURCE_HINTS = (
    "newsroom",
    "association",
    "government",
    "patent",
    "uspto",
    "filing",
    "gazette",
    "official",
    "organization",
)
TRADE_SOURCE_HINTS = (
    "plaza",
    "portal",
    "hortidaily",
    "packer",
    "produce report",
    "freshfruit",
    "fresh fruit",
    "trade",
)
WEAK_EXTRA = {
    "berry",
    "berries",
    "blueberry",
    "blueberries",
    "strawberry",
    "strawberries",
    "raspberry",
    "fruit",
    "plant",
    "named",
    "season",
    "industry",
}
STOPWORDS = {
    "about", "after", "amplian", "and", "con", "completa", "completas",
    "comprehensive", "de", "del", "expand", "for", "from", "host", "into",
    "las", "los", "mas", "more", "most", "new", "one", "para", "por", "role",
    "that", "the", "this", "una", "unas", "unos", "will", "with", "world",
    "worlds", "y", "the", "its", "now", "how", "why", "what", "when",
}
_TOKEN_RE = re.compile(r"[a-z0-9]{4,}")


def _folded(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def item_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or "")


def item_title(item: dict[str, Any]) -> str:
    return str(item.get("title") or item.get("headline") or "")


def item_url(item: dict[str, Any]) -> str:
    return normalize_canonical_url(
        item.get("canonical_url")
        or item.get("source_url")
        or (item.get("article") or {}).get("final_url")
        or (item.get("patent_filing") or {}).get("source_url")
    )


def item_date(item: dict[str, Any]) -> date | None:
    raw = str(item.get("published_date") or item.get("date") or item.get("captured_date") or "")[:10]
    if len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def item_date_text(item: dict[str, Any]) -> str:
    day = item_date(item)
    return day.isoformat() if day else str(item.get("published_date") or item.get("date") or item.get("captured_date") or "")[:10]


def _primary(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("primary_subject") or {}
    return value if isinstance(value, dict) else {}


def primary_entity_id(item: dict[str, Any]) -> str:
    return str(_primary(item).get("id") or "")


def primary_entity_type(item: dict[str, Any]) -> str:
    return str(_primary(item).get("entity_type") or "")


def title_tokens(title: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(_folded(title)) if token not in STOPWORDS}


def _name_tokens(item: dict[str, Any]) -> set[str]:
    primary = _primary(item)
    tokens = title_tokens(str(primary.get("name") or ""))
    for company in item.get("title_companies") or []:
        tokens |= title_tokens(str(company.get("name") or ""))
    return tokens


def _date_diff(left: dict[str, Any], right: dict[str, Any]) -> int | None:
    a, b = item_date(left), item_date(right)
    if not a or not b:
        return None
    return abs((a - b).days)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _blob(item: dict[str, Any]) -> str:
    return _folded(
        " ".join(
            str(part or "")
            for part in (
                item.get("source_name"),
                item.get("source_type"),
                item.get("kind"),
                item.get("kind_label"),
                item.get("intake_type"),
            )
        )
    )


def primary_source_rank(item: dict[str, Any]) -> int:
    blob = _blob(item)
    score = 0
    if "newsroom" in blob:
        score += 50
    if any(hint in blob for hint in ("patent", "uspto")) or item.get("source_type") == "patent_record":
        score += 45
    if "government" in blob:
        score += 40
    if any(hint in blob for hint in ("association", "organization")):
        score += 25
    if any(hint in blob for hint in TRADE_SOURCE_HINTS):
        score -= 15
    monitoring = str(item.get("monitoring_priority") or "")
    if monitoring == "high":
        score += 8
    return score


def coverage_role(item: dict[str, Any], *, is_primary: bool) -> str:
    if is_primary:
        return "primary_source"
    blob = _blob(item)
    if any(hint in blob for hint in TRADE_SOURCE_HINTS) or "newsroom" not in blob:
        if any(hint in blob for hint in TRADE_SOURCE_HINTS):
            return "trade_reprint"
    return "related_coverage"


def _link_target(link: dict[str, Any]) -> str:
    return str(link.get("target_evidence_id") or link.get("target_id") or "")


def _generic_assignee_link(link: dict[str, Any]) -> bool:
    notes = str(link.get("notes") or "").casefold()
    proposed_by = str(link.get("proposed_by") or "").casefold()
    return proposed_by == "patent-monitor" and "already linked" in notes


def evidence_links_of(item: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for link in item.get("evidence_links") or []:
        if not isinstance(link, dict):
            continue
        predicate = str(link.get("predicate") or "")
        target = _link_target(link)
        if predicate in THREAD_LINK_PREDICATES and target:
            rows.append(link)
    return rows


def _titles_share_variety_token(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Quoted cultivar / 'plant named X' overlap — not a company name."""

    def _variety_bits(item: dict[str, Any]) -> set[str]:
        title = item_title(item)
        bits = {token.casefold() for token in re.findall(r"[‘'\"`]([^‘'\"`]{3,40})[’'\"`]", title)}
        named = re.search(r"plant named\s+[‘'\"`]?([^’'\"`.]+)", title, re.IGNORECASE)
        if named:
            bits.add(named.group(1).strip().casefold())
        for suggestion in item.get("entity_link_suggestions") or []:
            if suggestion.get("role") == "variety" and suggestion.get("name"):
                bits.add(str(suggestion["name"]).casefold())
        return {bit for bit in bits if len(bit) >= 3}

    return bool(_variety_bits(left) & _variety_bits(right))


def _evidence_edge(left: dict[str, Any], right: dict[str, Any]) -> str | None:
    left_id, right_id = item_id(left), item_id(right)
    if not left_id or not right_id:
        return None
    for source, target in ((left, right), (right, left)):
        for link in evidence_links_of(source):
            if _link_target(link) != item_id(target):
                continue
            predicate = str(link.get("predicate") or "")
            if predicate in STRONG_LINK_PREDICATES:
                return predicate
            if _generic_assignee_link(link) and not _titles_share_variety_token(left, right):
                continue
            if predicate == "corroborates":
                overlap = title_tokens(item_title(left)) & title_tokens(item_title(right))
                if overlap or _titles_share_variety_token(left, right):
                    return predicate
                continue
            if predicate == "contradicts":
                if title_tokens(item_title(left)) & title_tokens(item_title(right)):
                    return predicate
    return None


def _same_url(left: dict[str, Any], right: dict[str, Any]) -> bool:
    a, b = item_url(left), item_url(right)
    return bool(a and b and a == b)


def _exact_title_reprint(left: dict[str, Any], right: dict[str, Any]) -> bool:
    a, b = normalize_title(item_title(left)), normalize_title(item_title(right))
    if not a or a != b:
        return False
    gap = _date_diff(left, right)
    if gap is not None and gap <= DATE_PROXIMITY_EXACT_TITLE_DAYS:
        return True
    return bool(primary_entity_id(left) and primary_entity_id(left) == primary_entity_id(right))


def _strong_event_edge(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Same primary company/variety plus title/date evidence of one event.

    Geography-only primaries never merge here. Same-company mention is not enough.
    """

    left_type, right_type = primary_entity_type(left), primary_entity_type(right)
    if left_type == "geography" or right_type == "geography":
        return False
    if left_type not in {"company", "variety"} or right_type not in {"company", "variety"}:
        return False
    if primary_entity_id(left) != primary_entity_id(right) or not primary_entity_id(left):
        return False
    gap = _date_diff(left, right)
    if gap is None or gap > DATE_PROXIMITY_EVENT_DAYS:
        return False
    left_tokens = title_tokens(item_title(left))
    right_tokens = title_tokens(item_title(right))
    company_tokens = _name_tokens(left) | _name_tokens(right)
    residual_left = left_tokens - company_tokens
    residual_right = right_tokens - company_tokens
    shared_extra = (residual_left & residual_right) - WEAK_EXTRA
    if _jaccard(residual_left, residual_right) >= MIN_EVENT_JACCARD and shared_extra:
        return True
    if gap <= DATE_PROXIMITY_TRANSLATION_DAYS and len(shared_extra) >= 1 and len((left_tokens & right_tokens) - WEAK_EXTRA) >= 2:
        return True
    return False


def items_form_thread(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if item_id(left) == item_id(right):
        return False
    if _same_url(left, right):
        return True
    if _exact_title_reprint(left, right):
        return True
    if _evidence_edge(left, right):
        return True
    if _strong_event_edge(left, right):
        return True
    return False


class _UnionFind:
    def __init__(self, ids: Iterable[str]) -> None:
        self.parent = {item: item for item in ids}

    def find(self, key: str) -> str:
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def union(self, left: str, right: str) -> None:
        ra, rb = self.find(left), self.find(right)
        if ra != rb:
            self.parent[rb] = ra


def _choose_primary(members: list[dict[str, Any]]) -> dict[str, Any]:
    def key(item: dict[str, Any]) -> tuple:
        day = item_date(item) or date.min
        return (
            primary_source_rank(item),
            1 if item.get("status") == "published" else 0,
            int(item.get("score") or 0),
            day.isoformat(),
        )

    return max(members, key=key)


def _unique_named(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        entity_id = str(row.get("id") or row.get("name") or "")
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        out.append(row)
    return out


def _member_entities(members: list[dict[str, Any]], entity_type: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in members:
        primary = _primary(item)
        if primary.get("entity_type") == entity_type and (primary.get("id") or primary.get("name")):
            rows.append(primary)
        for chip in item.get("entities") or []:
            if chip.get("entity_type") == entity_type:
                rows.append(chip)
        if entity_type == "company":
            for chip in item.get("title_companies") or []:
                rows.append(chip)
    return _unique_named(rows)


def _what_happened(primary: dict[str, Any]) -> str:
    for key in ("summary", "why_it_matters", "publisher_description", "why"):
        value = str(primary.get(key) or "").strip()
        if value:
            return value
    enrichment = primary.get("ai_enrichment") or {}
    for key in ("concise_summary", "why_it_matters"):
        value = str(enrichment.get(key) or "").strip()
        if value:
            return value
    return str(primary.get("title") or "")


def _proposed_links(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = {item_id(item) for item in members}
    titles = {item_id(item): item_title(item) for item in members}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in members:
        source = item_id(item)
        for link in evidence_links_of(item):
            target = _link_target(link)
            if target not in ids or target == source:
                continue
            if _generic_assignee_link(link) and not _titles_share_variety_token(item, next(m for m in members if item_id(m) == target)):
                continue
            key = (str(link.get("predicate") or ""), source, target)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "predicate": link.get("predicate"),
                    "status": link.get("status") or "proposed",
                    "from_id": source,
                    "from_title": titles.get(source) or source,
                    "target_id": target,
                    "target_title": titles.get(target) or target,
                    "notes": link.get("notes") or "",
                }
            )
    return rows


def present_thread(members: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(members, key=lambda item: (item_date_text(item), item_id(item)))
    primary = _choose_primary(ordered)
    primary_id = item_id(primary)
    dates = [item_date_text(item) for item in ordered if item_date_text(item)]
    additional = []
    presented_members = []
    for item in ordered:
        is_primary = item_id(item) == primary_id
        role = coverage_role(item, is_primary=is_primary)
        row = {
            **item,
            "coverage_role": role,
            "is_primary_source": is_primary,
            "href": item.get("href") or f"/intelligence/{item_id(item)}",
            "date": item_date_text(item),
            "source_name": item.get("source_name") or item.get("source_id") or "",
            "trust": item.get("trust") or trust_state(item),
            "trust_label": item.get("trust_label")
            or ("Trusted" if (item.get("trust") or trust_state(item)) == "trusted" else "Pending"),
        }
        presented_members.append(row)
        if not is_primary:
            additional.append(
                {
                    "id": item_id(item),
                    "name": row["source_name"],
                    "title": item_title(item),
                    "role": role,
                    "href": row["href"],
                }
            )
    source_names = []
    for item in presented_members:
        name = str(item.get("source_name") or "").strip()
        if name and name not in source_names:
            source_names.append(name)
    return {
        "is_thread": True,
        "id": primary_id,
        "thread_id": f"thread-{primary_id}",
        "href": f"/threads/{primary_id}",
        "title": item_title(primary) or primary_id,
        "label": "Developing story",
        "kind_label": "Developing story",
        "trust": "pending",
        "trust_label": "Organizational grouping",
        "source_count": len(presented_members),
        "first_seen": dates[0] if dates else "",
        "latest": dates[-1] if dates else "",
        "date": dates[-1] if dates else item_date_text(primary),
        "primary": next(row for row in presented_members if row["is_primary_source"]),
        "primary_source_name": str(primary.get("source_name") or primary.get("source_id") or ""),
        "additional_coverage": additional,
        "members": presented_members,
        "member_ids": [item_id(item) for item in presented_members],
        "what_happened": _what_happened(primary),
        "companies": _member_entities(presented_members, "company"),
        "varieties": _member_entities(presented_members, "variety"),
        "geographies": _member_entities(presented_members, "geography"),
        "proposed_links": _proposed_links(presented_members),
        "score": max(int(item.get("score") or 0) for item in presented_members),
        "cluster": primary.get("cluster") or primary_entity_id(primary) or primary_id,
        "age_days": primary.get("age_days"),
        "calendar_age": primary.get("calendar_age"),
        "why_ranked": "Because: related coverage of one developing story",
        "source_name": str(primary.get("source_name") or ""),
        "source_names": source_names,
        "status": primary.get("status"),
        "why": "Presentation grouping of related sources. Not a trusted conclusion.",
        "change_label": "developing story",
        "new_since_last": any(item.get("new_since_last") for item in presented_members),
        "triage_bucket": _best_triage_bucket(presented_members),
        "show_pending_actions": False,
    }


def _best_triage_bucket(members: list[dict[str, Any]]) -> str:
    order = ["review_now", "review_soon", "adjacent", "likely_ignore", "older_backlog", "dismissed"]
    present = {str(item.get("triage_bucket") or "") for item in members}
    for key in order:
        if key in present:
            return key
    return str(members[0].get("triage_bucket") or "")


def group_story_threads(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Connected components over conservative edges. Singletons included."""

    usable = [item for item in items if item_id(item)]
    ids = [item_id(item) for item in usable]
    by_id = {item_id(item): item for item in usable}
    forest = _UnionFind(ids)
    for index, left in enumerate(usable):
        for right in usable[index + 1 :]:
            if items_form_thread(left, right):
                forest.union(item_id(left), item_id(right))
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for item in usable:
        root = forest.find(item_id(item))
        if root not in grouped:
            grouped[root] = []
            order.append(root)
        grouped[root].append(by_id[item_id(item)])
    threads = [present_thread(grouped[root]) for root in order]
    threads.sort(key=lambda row: int(row.get("score") or 0), reverse=True)
    return threads


def threads_by_item_id(threads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for thread in threads:
        for member_id in thread.get("member_ids") or []:
            index[str(member_id)] = thread
    return index


def compress_entries(
    entries: list[dict[str, Any]],
    threads_by_id: dict[str, dict[str, Any]],
    *,
    occupied_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Replace redundant rows with one developing-story card.

    Members already shown in a higher-priority bucket (occupied_ids) are omitted
    rather than repeated.
    """

    occupied = set(occupied_ids or ())
    used: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in entries:
        iid = item_id(item)
        if not iid or iid in occupied or iid in used:
            continue
        thread = threads_by_id.get(iid)
        member_ids = {str(member_id) for member_id in (thread.get("member_ids") if thread else [iid]) or [iid]}
        if thread and int(thread.get("source_count") or 0) > 1:
            if member_ids & occupied:
                used.add(iid)
                continue
            out.append(thread)
            used |= member_ids
        else:
            out.append(item)
            used.add(iid)
    return out, used


def compress_recent_intelligence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse near-identical recent-intelligence rows into developing stories."""

    records = []
    for item in items:
        record = dict(item.get("record") or {})
        if not record.get("id"):
            continue
        record["_recent_kind"] = item.get("kind")
        record["_recent_date"] = item.get("date")
        record["_date_is_published"] = item.get("date_is_published")
        records.append(record)
    if not records:
        return items
    threads = group_story_threads(records)
    index = threads_by_item_id(threads)
    compressed, _ = compress_entries(records, index)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    original_by_id = {str((item.get("record") or {}).get("id")): item for item in items}
    for row in compressed:
        if row.get("is_thread") and int(row.get("source_count") or 0) > 1:
            kinds = {str(member.get("_recent_kind") or "pending") for member in row.get("members") or []}
            kind = "pending" if "pending" in kinds else "trusted"
            out.append(
                {
                    "kind": kind,
                    "is_thread": True,
                    "record": row.get("primary") or {},
                    "date": row.get("latest") or row.get("date"),
                    "date_is_published": True,
                    "thread": row,
                    "sources_count": row.get("source_count"),
                    "developing_label": row.get("title"),
                }
            )
            seen.update(str(member_id) for member_id in row.get("member_ids") or [])
            continue
        iid = item_id(row)
        if iid in original_by_id and iid not in seen:
            out.append(original_by_id[iid])
            seen.add(iid)
    return out


def thread_for_item(item_id_value: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not item_id_value:
        return None
    threads = group_story_threads(items)
    return threads_by_item_id(threads).get(item_id_value)


def expand_with_related(items: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add published/other records that share a conservative edge with `items`."""

    known = {item_id(item) for item in items}
    out = list(items)
    for record in extra:
        rid = item_id(record)
        if not rid or rid in known:
            continue
        if any(items_form_thread(record, item) for item in items):
            out.append(record)
            known.add(rid)
    return out


def compression_report(items: list[dict[str, Any]]) -> dict[str, Any]:
    threads = group_story_threads(items)
    multi = [thread for thread in threads if int(thread.get("source_count") or 0) > 1]
    singles = [thread for thread in threads if int(thread.get("source_count") or 0) == 1]
    return {
        "raw_items": len(items),
        "distinct_stories": len(threads),
        "multi_source_threads": len(multi),
        "singletons": len(singles),
        "threads": threads,
        "multi": multi,
        "singleton_items": singles,
    }
