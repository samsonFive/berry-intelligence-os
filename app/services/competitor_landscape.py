"""Competitor Landscape V1 — filterable stakeholder landscape foundation.

Adapter-backed view model. Default source is the complete 33-entry test
fixture until Claude's canonical competitor roster is integrated. Does not
create a competing production registry or invent genetics relationships.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "competitor_landscape_registry_v1.json"

EXPECTED_REGISTRY_LABELS: tuple[str, ...] = (
    "Advanced Berry Breeding",
    "AgroBerries",
    "Australasian Plant Genetics",
    "BerryWorld",
    "Black Venture Farm",
    "California Giant",
    "Costa",
    "Denning Blueberries",
    "Expoberries",
    "Fall Creek",
    "Fresh Forward",
    "Fruitist",
    "Gem-Pack Berries",
    "Hortifrut Genetica",
    "IQ Berries",
    "Marionnet",
    "Mountain Blue",
    "Oishii",
    "Ozblu",
    "Pairwise",
    "Perfection Fresh",
    "Planasa",
    "Plant Sciences",
    "Royakkers",
    "Smart Berries",
    "Splendor Produce",
    "SunBelle",
    "The Berry Collective",
    "UC Davis",
    "University of Arkansas",
    "University of Florida",
    "Well-Pict",
    "Wish Farms",
)

BERRIES: tuple[tuple[str, str], ...] = (
    ("strawberry", "Strawberry"),
    ("blueberry", "Blueberry"),
    ("raspberry", "Raspberry"),
    ("blackberry", "Blackberry"),
)
BERRY_KEYS = {key for key, _ in BERRIES}

TIER_STATUS_VALUES: tuple[str, ...] = (
    "Tier 1",
    "Tier 2",
    "Tier 3",
    "Present",
    "Unknown/Unassigned",
    "Not Applicable",
)
TIER_BAND_ORDER = TIER_STATUS_VALUES

PRIORITY_VALUES: tuple[str, ...] = ("Top", "Watch", "unassigned")

COMPETITOR_TYPE_VALUES: tuple[str, ...] = (
    "Commercial",
    "Breeding",
    "Genetics",
    "Technology",
    "University/Public",
)

DEFAULT_REGION_CODE_LABELS = {
    "DOTA": "Americas (DOTA)",
    "DEMEA": "Europe, Middle East & Africa (DEMEA)",
    "DOA_DANZ": "Oceania / ANZ (DOA_DANZ)",
}


def normalize_tier_status(raw: Any) -> str:
    if raw is None:
        return "Unknown/Unassigned"
    text = str(raw).strip()
    if not text:
        return "Unknown/Unassigned"
    aliases = {
        "tier1": "Tier 1",
        "tier 1": "Tier 1",
        "tier2": "Tier 2",
        "tier 2": "Tier 2",
        "tier3": "Tier 3",
        "tier 3": "Tier 3",
        "present": "Present",
        "unknown": "Unknown/Unassigned",
        "unassigned": "Unknown/Unassigned",
        "unknown/unassigned": "Unknown/Unassigned",
        "n/a": "Not Applicable",
        "na": "Not Applicable",
        "not applicable": "Not Applicable",
    }
    return aliases.get(text.casefold(), text)


def normalize_priority(raw: Any) -> str:
    if raw is None:
        return "unassigned"
    text = str(raw).strip()
    if not text:
        return "unassigned"
    lowered = text.casefold()
    if lowered == "top":
        return "Top"
    if lowered == "watch":
        return "Watch"
    if lowered in {"unassigned", "unknown", "none"}:
        return "unassigned"
    return text


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-") or "competitor"


@dataclass(frozen=True)
class LandscapeFilters:
    berry: str = "blueberry"
    regions: tuple[str, ...] = ()
    tier: str = ""
    priority: str = ""
    competitor_type: str = ""
    q: str = ""
    company: str = ""

    def active_chips(self, region_labels: dict[str, str] | None = None) -> list[dict[str, str]]:
        labels = region_labels or DEFAULT_REGION_CODE_LABELS
        chips: list[dict[str, str]] = [
            {"key": "berry", "label": f"Berry: {dict(BERRIES).get(self.berry, self.berry.title())}"}
        ]
        for code in self.regions:
            chips.append({"key": "region", "value": code, "label": f"Region: {labels.get(code, code)}"})
        if self.tier:
            chips.append({"key": "tier", "label": f"Tier/status: {self.tier}"})
        if self.priority:
            chips.append({"key": "priority", "label": f"Priority: {self.priority}"})
        if self.competitor_type:
            chips.append({"key": "type", "label": f"Type: {self.competitor_type}"})
        if self.q:
            chips.append({"key": "q", "label": f"Search: {self.q}"})
        return chips


def parse_filters(params: dict[str, Any] | None) -> LandscapeFilters:
    raw = params or {}

    def values(key: str) -> list[str]:
        value = raw.get(key)
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            items = value
        else:
            items = str(value).split(",")
        out: list[str] = []
        for item in items:
            text = str(item).strip()
            if text and text not in out:
                out.append(text)
        return out

    def first(*keys: str, default: str = "") -> str:
        for key in keys:
            found = values(key)
            if found:
                return found[0]
        return default

    berry = first("berry", default="blueberry").casefold()
    if berry not in BERRY_KEYS:
        berry = "blueberry"

    region_values: list[str] = []
    for key in ("region", "regions"):
        for code in values(key):
            if code not in region_values:
                region_values.append(code)

    tier = first("tier", "status")
    if tier:
        tier = normalize_tier_status(tier)
        if tier not in TIER_STATUS_VALUES:
            tier = ""

    priority = first("priority")
    if priority:
        priority = normalize_priority(priority)

    return LandscapeFilters(
        berry=berry,
        regions=tuple(region_values),
        tier=tier,
        priority=priority,
        competitor_type=first("type", "competitor_type"),
        q=first("q", "search"),
        company=first("company", "selected"),
    )


def filters_to_query(filters: LandscapeFilters, *, include_company: bool = True) -> str:
    pairs: list[tuple[str, str]] = [("berry", filters.berry)]
    for code in filters.regions:
        pairs.append(("region", code))
    if filters.tier:
        pairs.append(("tier", filters.tier))
    if filters.priority:
        pairs.append(("priority", filters.priority))
    if filters.competitor_type:
        pairs.append(("type", filters.competitor_type))
    if filters.q:
        pairs.append(("q", filters.q))
    if include_company and filters.company:
        pairs.append(("company", filters.company))
    return urlencode(pairs, doseq=True)


class CompetitorLandscapeAdapter:
    def __init__(
        self,
        *,
        fixture_path: Path | None = None,
        entities_by_id: dict[str, dict[str, Any]] | None = None,
        evidence: Iterable[dict[str, Any]] | None = None,
        relationships: Iterable[dict[str, Any]] | None = None,
    ) -> None:
        self.fixture_path = fixture_path or DEFAULT_FIXTURE_PATH
        self.entities_by_id = entities_by_id or {}
        self.evidence = list(evidence or [])
        self.relationships = list(relationships or [])
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
            raise ValueError("competitor landscape fixture must provide entries[]")
        self._payload = payload

    @property
    def region_code_labels(self) -> dict[str, str]:
        labels = dict(DEFAULT_REGION_CODE_LABELS)
        codes = self._payload.get("region_codes") or {}
        if isinstance(codes, dict):
            for code, meta in codes.items():
                if isinstance(meta, dict) and meta.get("label"):
                    labels[str(code)] = str(meta["label"])
                elif isinstance(meta, str):
                    labels[str(code)] = meta
        return labels

    def roster_labels(self) -> list[str]:
        return [str(row.get("registry_label") or "") for row in self._payload["entries"]]

    def missing_expected_labels(self) -> list[str]:
        have = set(self.roster_labels())
        return [label for label in EXPECTED_REGISTRY_LABELS if label not in have]

    def unexpected_labels(self) -> list[str]:
        expected = set(EXPECTED_REGISTRY_LABELS)
        return [label for label in self.roster_labels() if label and label not in expected]

    def load_rows(self) -> list[dict[str, Any]]:
        rows = [self._row_from_entry(entry) for entry in self._payload["entries"] if isinstance(entry, dict)]
        rows.sort(key=lambda row: row["display_name"].casefold())
        return rows

    def _row_from_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        label = str(entry.get("registry_label") or "").strip()
        aliases = [str(a) for a in (entry.get("aliases") or []) if str(a).strip()]
        types = [str(t).strip() for t in (entry.get("competitor_types") or []) if str(t).strip()]
        regions = [str(r).strip() for r in (entry.get("regions") or []) if str(r).strip()]
        priority = normalize_priority(entry.get("strategic_priority"))
        positions_raw = entry.get("berry_positions") if isinstance(entry.get("berry_positions"), dict) else {}
        berry_positions = {berry: normalize_tier_status(positions_raw.get(berry)) for berry, _ in BERRIES}

        suggested = entry.get("suggested_entity_id")
        entity = self.entities_by_id.get(str(suggested)) if suggested else None
        if entity:
            entity_id = str(entity.get("id"))
            canonical_or_pending_state = "canonical"
            profile_url = f"/entities/company/{entity_id}"
            merged = list(dict.fromkeys([*(entity.get("aliases") or []), *aliases, entity.get("name") or ""]))
            aliases = [a for a in merged if a and a != label]
            recent_usable_coverage_count = sum(
                1
                for ev in self.evidence
                if entity_id in (ev.get("entity_ids") or []) and ev.get("status") == "published"
            )
            genetics_relationship_count = sum(
                1
                for rel in self.relationships
                if entity_id in {rel.get("subject_id"), rel.get("object_id")}
                and str(rel.get("predicate") or "") in {"develops", "owns", "licenses", "breeds"}
            )
            monitoring_state = "monitored" if recent_usable_coverage_count else "thin_coverage"
        else:
            entity_id = f"pending-competitor-{_slug(label)}"
            canonical_or_pending_state = "pending"
            profile_url = ""
            recent_usable_coverage_count = 0
            genetics_relationship_count = 0
            monitoring_state = "identity_pending"

        return {
            "entity_id": entity_id,
            "display_name": label,
            "registry_label": label,
            "aliases": aliases,
            "entity_type": "company",
            "competitor_types": types,
            "strategic_priority": priority,
            "regions": regions,
            "berry_positions": berry_positions,
            "monitoring_state": monitoring_state,
            "recent_usable_coverage_count": recent_usable_coverage_count,
            "genetics_relationship_count": genetics_relationship_count,
            "canonical_or_pending_state": canonical_or_pending_state,
            "profile_url": profile_url,
        }


def berry_status_for(row: dict[str, Any], berry: str) -> str:
    return normalize_tier_status((row.get("berry_positions") or {}).get(berry))


def matches_filters(row: dict[str, Any], filters: LandscapeFilters) -> bool:
    if filters.regions and not set(row.get("regions") or []).intersection(filters.regions):
        return False
    if filters.tier and berry_status_for(row, filters.berry) != filters.tier:
        return False
    if filters.priority and normalize_priority(row.get("strategic_priority")) != normalize_priority(filters.priority):
        return False
    if filters.competitor_type and filters.competitor_type not in set(row.get("competitor_types") or []):
        return False
    if filters.q:
        needle = filters.q.casefold().strip()
        haystacks = [
            str(row.get("display_name") or ""),
            str(row.get("registry_label") or ""),
            *list(row.get("aliases") or []),
            *list(row.get("competitor_types") or []),
        ]
        if not any(needle in text.casefold() for text in haystacks):
            return False
    return True


def filter_rows(rows: Iterable[dict[str, Any]], filters: LandscapeFilters) -> list[dict[str, Any]]:
    return [row for row in rows if matches_filters(row, filters)]


def tier_counts(rows: Iterable[dict[str, Any]], berry: str) -> dict[str, int]:
    counts = {status: 0 for status in TIER_BAND_ORDER}
    for row in rows:
        status = berry_status_for(row, berry)
        counts[status] = counts.get(status, 0) + 1
    return counts


def group_by_tier(rows: Iterable[dict[str, Any]], berry: str) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {status: [] for status in TIER_BAND_ORDER}
    for row in rows:
        enriched = deepcopy(row)
        status = berry_status_for(row, berry)
        enriched["selected_berry_status"] = status
        buckets.setdefault(status, []).append(enriched)
    bands = []
    for status in TIER_BAND_ORDER:
        members = sorted(buckets.get(status) or [], key=lambda r: r["display_name"].casefold())
        bands.append({"status": status, "label": status, "count": len(members), "competitors": members})
    return bands


def empty_state_message(filters: LandscapeFilters, *, matched: int, universe: int) -> str | None:
    if matched:
        return None
    reasons = []
    if filters.tier:
        reasons.append(f"no competitor has {filters.tier} status for the selected berry")
    if filters.regions:
        reasons.append("no competitor matches the selected region(s)")
    if filters.priority:
        reasons.append(f"no competitor has priority {filters.priority}")
    if filters.competitor_type:
        reasons.append(f"no competitor is typed as {filters.competitor_type}")
    if filters.q:
        reasons.append("search did not match any registry name or alias")
    if not reasons:
        reasons.append("no company matches the selected filters")
    return (
        f"No competitors in this landscape ({universe} in the full roster). "
        + "; ".join(reasons)
        + ". Unknown/Unassigned is deliberate — incomplete metadata never hides a roster entry from the default view."
    )


def selected_company_detail(rows: Iterable[dict[str, Any]], company_id: str, *, berry: str) -> dict[str, Any] | None:
    if not company_id:
        return None
    for row in rows:
        if row.get("entity_id") == company_id or row.get("registry_label") == company_id:
            detail = deepcopy(row)
            detail["selected_berry_status"] = berry_status_for(row, berry)
            detail["data_gaps"] = _data_gaps(row)
            return detail
    return None


def _data_gaps(row: dict[str, Any]) -> list[str]:
    gaps = []
    if row.get("canonical_or_pending_state") == "pending":
        gaps.append("Canonical company identity is pending — Claude owns the registry merge.")
    if not row.get("regions"):
        gaps.append("Region assignment is Unknown/Unassigned.")
    if not row.get("competitor_types"):
        gaps.append("Competitor type is Unknown/Unassigned.")
    if normalize_priority(row.get("strategic_priority")) == "unassigned":
        gaps.append("Strategic priority is unassigned.")
    for berry, label in BERRIES:
        if berry_status_for(row, berry) == "Unknown/Unassigned":
            gaps.append(f"{label} tier/status is Unknown/Unassigned.")
    if row.get("recent_usable_coverage_count", 0) == 0:
        gaps.append("No recent usable trusted coverage counted for this identity.")
    return gaps


def build_landscape_context(adapter: CompetitorLandscapeAdapter, filters: LandscapeFilters) -> dict[str, Any]:
    universe = adapter.load_rows()
    matched = filter_rows(universe, filters)
    bands = group_by_tier(matched, filters.berry)
    counts = tier_counts(matched, filters.berry)
    selected = selected_company_detail(universe, filters.company, berry=filters.berry)
    completeness = {
        "with_regions": sum(1 for row in universe if row.get("regions")),
        "with_types": sum(1 for row in universe if row.get("competitor_types")),
        "with_priority": sum(
            1 for row in universe if normalize_priority(row.get("strategic_priority")) != "unassigned"
        ),
        "canonical": sum(1 for row in universe if row.get("canonical_or_pending_state") == "canonical"),
        "pending": sum(1 for row in universe if row.get("canonical_or_pending_state") == "pending"),
    }
    return {
        "filters": filters,
        "selected_berry_label": dict(BERRIES).get(filters.berry, filters.berry.title()),
        "universe_count": len(universe),
        "result_count": len(matched),
        "tier_counts": counts,
        "bands": bands,
        "region_labels": adapter.region_code_labels,
        "berry_options": [{"id": key, "label": label} for key, label in BERRIES],
        "tier_options": list(TIER_STATUS_VALUES),
        "priority_options": list(PRIORITY_VALUES),
        "type_options": list(COMPETITOR_TYPE_VALUES),
        "region_options": [{"id": code, "label": label} for code, label in adapter.region_code_labels.items()],
        "active_chips": filters.active_chips(adapter.region_code_labels),
        "query_string": filters_to_query(filters, include_company=False),
        "selected_query_string": filters_to_query(filters, include_company=True),
        "clear_href": "/competitors",
        "selected_company": selected,
        "empty_message": empty_state_message(filters, matched=len(matched), universe=len(universe)),
        "completeness": completeness,
        "missing_expected_labels": adapter.missing_expected_labels(),
        "fixture_note": (
            "Showing the complete 33-entry competitor-universe fixture behind the "
            "adapter contract. Canonical roster integration is owned separately."
        ),
    }


def adapter_from_repositories(
    *,
    entities: Iterable[dict[str, Any]] | None = None,
    evidence: Iterable[dict[str, Any]] | None = None,
    relationships: Iterable[dict[str, Any]] | None = None,
    fixture_path: Path | None = None,
) -> CompetitorLandscapeAdapter:
    entities_by_id = {
        str(row.get("id")): row
        for row in (entities or [])
        if isinstance(row, dict) and row.get("id")
    }
    return CompetitorLandscapeAdapter(
        fixture_path=fixture_path,
        entities_by_id=entities_by_id,
        evidence=evidence,
        relationships=relationships,
    )
