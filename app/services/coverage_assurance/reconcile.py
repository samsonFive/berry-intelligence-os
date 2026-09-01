"""Collection-status reconciliation for Coverage Assurance.

Trusted Evidence / Publication hosts are compared against the active Source
inventory and the Source Universe registry. GET never writes Sources,
Evidence, or universe rows.
"""

from __future__ import annotations

from typing import Any

from app.services.coverage_assurance.classes import source_class_of
from app.services.coverage_assurance.statuses import (
    COLLECTED,
    COLLECTION_STATUS_LABELS,
    INTENTIONALLY_EXCLUDED,
    KNOWN_NOT_COLLECTED,
    UNKNOWN_SOURCE_IDENTITY,
)
from app.services.coverage_assurance.universe import berry_tokens, geography_tokens, overlay_source
from app.services.recall_audit.classify import WRAPPER_HOSTS, hostname, publisher_hosts
from app.services.source_lifecycle import is_collection_eligible, lifecycle_state

# Hosts genuinely, actively collected through a dedicated structured
# pipeline that never registers itself as a Source in sources.json and
# never runs through CollectionRunner -- so the generic Source-based
# reconciliation below would otherwise, incorrectly, call them
# UNKNOWN_SOURCE_IDENTITY. Verified against each pipeline's own
# source_url construction (Source Coverage Gap Closure V1):
# app.services.patent_monitor.google_patents (patents.google.com/xhr/query),
# app.services.patent_monitor.uspto_odp (patentcenter.uspto.gov), and
# app.services.cpvo_registry (online.plantvarieties.eu). This is a
# reconciliation-modeling fix only -- it does not change what those
# pipelines collect or how, and adds no new collection mechanism.
STRUCTURAL_COLLECTORS: dict[str, str] = {
    "patents.google.com": "app.services.patent_monitor.google_patents (structured patent registry pipeline)",
    "patentcenter.uspto.gov": "app.services.patent_monitor.uspto_odp (structured patent registry pipeline)",
    "online.plantvarieties.eu": "app.services.cpvo_registry (structured plant-variety-rights registry pipeline)",
}


def _source_by_publisher_host(sources: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        for host in publisher_hosts(source):
            index.setdefault(host, []).append(source)
    return index


def _collected_hosts(sources: list[dict[str, Any]]) -> set[str]:
    return {
        host
        for source in sources
        if is_collection_eligible(source)
        for host in publisher_hosts(source)
    }


def collection_status_for_host(
    host: str,
    *,
    universe_by_host: dict[str, dict[str, Any]],
    sources_by_host: dict[str, list[dict[str, Any]]],
    collected_hosts: set[str],
    blocked_domains: set[str],
) -> tuple[str, str | None, dict[str, Any] | None]:
    """Return (status, exclusion_or_gap_reason, matching_source_or_none)."""
    host = hostname(host)
    if not host:
        return UNKNOWN_SOURCE_IDENTITY, "No parseable hostname.", None

    universe_row = universe_by_host.get(host)
    blocked = host in blocked_domains or host in WRAPPER_HOSTS
    if universe_row and universe_row.get("intentionally_excluded"):
        return (
            INTENTIONALLY_EXCLUDED,
            str(universe_row.get("exclusion_reason") or "Intentionally excluded from collection."),
            None,
        )
    if blocked and not (universe_row and universe_row.get("intentionally_excluded") is False):
        reason = None
        if universe_row:
            reason = universe_row.get("exclusion_reason")
        if host in WRAPPER_HOSTS:
            reason = reason or "Redirect/wrapper host, not a publisher."
        elif host in blocked_domains:
            reason = reason or "Host is on the operator blocklist."
        return INTENTIONALLY_EXCLUDED, reason, None

    if host in STRUCTURAL_COLLECTORS:
        return COLLECTED, f"Collected via {STRUCTURAL_COLLECTORS[host]}, not a generic Source.", None

    matching = sources_by_host.get(host) or []
    collected = [row for row in matching if is_collection_eligible(row)]
    if host in collected_hosts or collected:
        return COLLECTED, None, collected[0] if collected else matching[0]

    if universe_row or matching:
        if matching:
            source = matching[0]
            state = lifecycle_state(source)
            return (
                KNOWN_NOT_COLLECTED,
                f"Onboarded Source {source.get('id')} is not collection-eligible (lifecycle {state}).",
                source,
            )
        return (
            KNOWN_NOT_COLLECTED,
            str(universe_row.get("notes") or "Known publisher; not an actively collected Source."),
            None,
        )
    return UNKNOWN_SOURCE_IDENTITY, "Host is cited or observed but has no Source Universe identity.", None


def cited_hosts_from_records(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """hostname -> {evidence_ids, publication_ids, berry_ids, geography_ids, source_ids}."""
    cited: dict[str, dict[str, Any]] = {}
    for record in records:
        host = hostname(record.get("source_url") or record.get("canonical_url") or record.get("url"))
        if not host:
            continue
        bucket = cited.setdefault(
            host,
            {
                "hostname": host,
                "evidence_ids": [],
                "publication_ids": [],
                "berry_ids": set(),
                "geography_ids": set(),
                "source_ids": set(),
                "titles": [],
            },
        )
        record_id = str(record.get("id") or "")
        role = str(record.get("evidence_role") or record.get("record_type") or "")
        if record.get("status") == "published" or role in {"", "evidence"}:
            if record_id and record_id not in bucket["evidence_ids"]:
                if record.get("status") in {None, "published"}:
                    bucket["evidence_ids"].append(record_id)
        if role == "publication_artifact" or record.get("record_type") == "publication":
            if record_id and record_id not in bucket["publication_ids"]:
                bucket["publication_ids"].append(record_id)
        bucket["berry_ids"].update(str(item) for item in (record.get("berry_ids") or []) if item)
        bucket["geography_ids"].update(str(item) for item in (record.get("geography_ids") or []) if item)
        source_id = str(record.get("source_id") or "").strip()
        if source_id:
            bucket["source_ids"].add(source_id)
        title = str(record.get("title") or "").strip()
        if title and title not in bucket["titles"]:
            bucket["titles"].append(title)
    return cited


def reconcile(
    *,
    universe_entries: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    publications: list[dict[str, Any]] | None = None,
    blocked_domains: list[str] | None = None,
) -> dict[str, Any]:
    blocked = {hostname(item) for item in (blocked_domains or []) if item}
    blocked |= set(WRAPPER_HOSTS)
    sources_by_host = _source_by_publisher_host(sources)
    collected_hosts = _collected_hosts(sources)
    universe_by_host = {
        str(row.get("hostname") or ""): row
        for row in universe_entries
        if row.get("hostname")
    }

    rows_by_host: dict[str, dict[str, Any]] = {}

    def ensure_row(host: str, *, origin: str) -> dict[str, Any]:
        existing = rows_by_host.get(host)
        if existing:
            if origin not in existing["origins"]:
                existing["origins"].append(origin)
            return existing
        universe_row = universe_by_host.get(host)
        matching = sources_by_host.get(host) or []
        overlay = overlay_source(matching[0], universe_row) if matching else dict(universe_row or {})
        if not overlay:
            overlay = {
                "id": f"observed-{host.replace('.', '-')}",
                "hostname": host,
                "display_name": host,
                "discovery_basis": "cited_in_trusted_evidence",
            }
        status, reason, matched_source = collection_status_for_host(
            host,
            universe_by_host=universe_by_host,
            sources_by_host=sources_by_host,
            collected_hosts=collected_hosts,
            blocked_domains=blocked,
        )
        berries = berry_tokens(overlay.get("berry_scope") or overlay.get("berry_ids"))
        geos = geography_tokens(overlay.get("geography") or overlay.get("geography_ids"))
        if matching:
            berries |= berry_tokens(matching[0].get("berry_ids"))
            geos |= geography_tokens(matching[0].get("region_coverage"))
        source_class = overlay.get("source_class") or (
            source_class_of(matching[0]) if matching else None
        ) or "trade_press"
        row = {
            "id": overlay.get("id") or (matched_source or {}).get("id") or f"observed-{host.replace('.', '-')}",
            "hostname": host,
            "display_name": overlay.get("display_name") or (matched_source or {}).get("label") or host,
            "source_class": source_class,
            "berry_scope": sorted(berries),
            "geography": sorted(geos) if geos else ["other"],
            "known_source_id": overlay.get("known_source_id") or (matched_source or {}).get("id"),
            "collection_status": status,
            "collection_status_label": COLLECTION_STATUS_LABELS[status],
            "reason": reason,
            "intentionally_excluded": status == INTENTIONALLY_EXCLUDED,
            "exclusion_reason": reason if status == INTENTIONALLY_EXCLUDED else overlay.get("exclusion_reason"),
            "discovery_basis": overlay.get("discovery_basis") or origin,
            "variety_dense": bool(overlay.get("variety_dense")),
            "coverage_category": overlay.get("coverage_category"),
            "expected_content_type": overlay.get("expected_content_type"),
            "yield_expectation_days": overlay.get("yield_expectation_days"),
            "notes": overlay.get("notes"),
            "provenance": overlay.get("provenance"),
            "first_observed": overlay.get("first_observed"),
            "last_externally_observed": overlay.get("last_externally_observed"),
            "origins": [origin],
            "cited_evidence_ids": [],
            "cited_publication_ids": [],
            "onboard_href": "/sources",
        }
        rows_by_host[host] = row
        return row

    for entry in universe_entries:
        host = str(entry.get("hostname") or "")
        if host:
            ensure_row(host, origin="universe")

    for source in sources:
        for host in publisher_hosts(source):
            row = ensure_row(host, origin="source_inventory")
            if is_collection_eligible(source):
                row["known_source_id"] = row.get("known_source_id") or source.get("id")

    cited = cited_hosts_from_records(list(published_evidence) + list(publications or []))
    for host, payload in cited.items():
        row = ensure_row(host, origin="trusted_evidence")
        row["cited_evidence_ids"] = list(payload["evidence_ids"])
        row["cited_publication_ids"] = list(payload["publication_ids"])
        if payload["berry_ids"]:
            row["berry_scope"] = sorted(set(row.get("berry_scope") or []) | berry_tokens(payload["berry_ids"]))
        extra_geo = geography_tokens(payload["geography_ids"])
        if extra_geo:
            row["geography"] = sorted(set(row.get("geography") or []) | extra_geo)
        if payload["evidence_ids"] and not row.get("variety_dense"):
            # Variety-related citation is recorded later by the report using entity ids.
            pass

    cited_not_collected = []
    unknown = []
    collected = []
    known_not_collected = []
    excluded = []
    for row in rows_by_host.values():
        status = row["collection_status"]
        cited_here = bool(row.get("cited_evidence_ids") or row.get("cited_publication_ids"))
        if status == COLLECTED:
            collected.append(row)
        elif status == INTENTIONALLY_EXCLUDED:
            excluded.append(row)
        elif status == UNKNOWN_SOURCE_IDENTITY:
            unknown.append(row)
            if cited_here:
                cited_not_collected.append(row)
        else:
            known_not_collected.append(row)
            if cited_here:
                cited_not_collected.append(row)

    return {
        "rows": sorted(rows_by_host.values(), key=lambda row: row["hostname"]),
        "by_host": rows_by_host,
        "collected": collected,
        "known_not_collected": known_not_collected,
        "unknown_identity": unknown,
        "intentionally_excluded": excluded,
        "cited_not_collected": sorted(cited_not_collected, key=lambda row: row["hostname"]),
        "collected_hosts": sorted(collected_hosts),
        "universe_by_host": universe_by_host,
        "sources_by_host": sources_by_host,
    }
