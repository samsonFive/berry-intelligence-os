"""CPVO (Community Plant Variety Office) public register lookup.

Registry Backbone V1 (Variety Intelligence Backbone mission, 2026-08-21).
CPVO's public register search (https://online.plantvarieties.eu/publicSearch,
backed by the real, unauthenticated JSON API at
https://online.plantvarieties.eu/api/publicSearch/v3/publicSearch) is the one
registry integration this mission adds, chosen over UPOV PLUTO (requires a
WIPO account -- not anonymously public), the CPVO "Variety Finder" aggregator
(explicitly registration-gated per CPVO's own documentation, distinct from
this public-register endpoint), IP Australia's PBR search (a real public web
UI, but no API endpoint was discoverable in this mission's live testing), and
the UK PVRO (no unified public database at all -- Seeds Gazette PDF
publications only). See docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md Part 4 for
the full audit.

This module queries CPVO by denomination (the real, working query shape --
`specieId`/`species` params were tested live and do not filter; denomination
search does), for a caller-supplied set of candidate names (a Variety's
canonical name + aliases + commercial names), and only treats a hit as a real
match when the CPVO record's own species maps to one of the four tracked
berries. It never queries "everything CPVO has" -- only names this project
already tracks, per Section 5's "do not build a bulk crawl" instruction.

Like Patent Monitor v2, this never writes trusted data, Facts, or
Relationships -- only untrusted `inbox/evidence/` review drafts. A PVR grant
proves a filing/grant event, nothing about commercialization -- see
`CPVO_DOES_NOT_PROVE`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import httpx

from app.services.patent_monitor.entity_link import matched_entity_ids, suggest_entity_links
from app.services.transcript_evidence import PRIORITY_NONE

CPVO_SEARCH_URL = "https://online.plantvarieties.eu/api/publicSearch/v3/publicSearch"
CPVO_USER_AGENT = "berry-intelligence-os-cpvo-registry/1.0"
CPVO_FETCH_TIMEOUT_SECONDS = 15

# CPVO's own `speciesName` string (exact, as returned by its API -- verified
# live 2026-08-21) -> this project's berry id. Only species real CPVO hits
# were confirmed to use for these genera; not an exhaustive botanical list.
CPVO_SPECIES_TO_BERRY: dict[str, str] = {
    "Fragaria x ananassa Duchesne ex Rozier": "berry-strawberry",
    "Fragaria vesca L.": "berry-strawberry",
    "Vaccinium corymbosum L.": "berry-blueberry",
    "Vaccinium corymbosum L. x V. darrowii Camp": "berry-blueberry",
    "Vaccinium angustifolium Aiton": "berry-blueberry",
    "Vaccinium angustifolium Aiton x V. corymbosum L.": "berry-blueberry",
    "Vaccinium virgatum Aiton": "berry-blueberry",
    "Rubus idaeus L.": "berry-raspberry",
    "Rubus idaeus L. x R. parvifolius L.": "berry-raspberry",
    "Rubus subg. Rubus": "berry-blackberry",
    "Rubus occidentalis L.": "berry-blackberry",
}

CPVO_DOES_NOT_PROVE = (
    "commercialization or planted acreage",
    "market adoption or sales success",
    "commercial launch timing",
    "that the applicant is the breeder (applicant/breeder may differ)",
    "licensee identity or exclusive territory",
    "that this is the variety's only registered right in any jurisdiction",
)


class CpvoRegistryError(RuntimeError):
    pass


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def search_cpvo_register(
    denomination: str,
    *,
    search_type: str = "contains",
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Real, unauthenticated GET against CPVO's public register API. Raises
    CpvoRegistryError on transport/HTTP failure; never raises for zero
    results (an empty list is a legitimate, common answer)."""
    params = {"denomination": denomination, "denominationSearchType": search_type}
    try:
        if client is not None:
            response = client.get(CPVO_SEARCH_URL, params=params, timeout=CPVO_FETCH_TIMEOUT_SECONDS)
        else:
            response = httpx.get(
                CPVO_SEARCH_URL,
                params=params,
                timeout=CPVO_FETCH_TIMEOUT_SECONDS,
                headers={"User-Agent": CPVO_USER_AGENT},
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise CpvoRegistryError(f"CPVO search failed for {denomination!r}: {exc}") from exc
    payload = response.json()
    registers = ((payload or {}).get("data") or {}).get("registers") or []
    return [row for row in registers if isinstance(row, dict)]


def berry_id_for_species(species_name: str | None) -> str | None:
    return CPVO_SPECIES_TO_BERRY.get((species_name or "").strip())


def canonical_filing_id(application_number: Any, examination_office: str | None) -> str:
    raw = f"{application_number}-{(examination_office or '').strip().lower()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"cpvo-{digest}"


def draft_id_for_filing(filing_id: str) -> str:
    return f"ev-cpvo-{filing_id}"


def normalize_cpvo_register_row(row: dict[str, Any], *, acquired_at: datetime | None = None) -> dict[str, Any]:
    """A CPVO register row into a filing-shaped dict, deliberately parallel
    to patent_monitor.normalize.normalize_discovery_hit()'s field names
    (cultivar_name, applicants, publication_number, jurisdiction, source_url)
    so app.services.patent_monitor.entity_link.suggest_entity_links() --
    generic, not patent-specific in its matching logic -- can be reused
    as-is rather than reimplemented for CPVO."""
    acquired = (acquired_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    application_number = row.get("applicationNumber")
    filing_id = canonical_filing_id(application_number, row.get("examOfficeName"))
    applicants = [a for a in (row.get("applicants") or []) if isinstance(a, str) and a.strip()]
    denomination = (row.get("denomination") or "").strip()
    filing = {
        "filing_id": filing_id,
        "application_number": application_number,
        "grant_number": row.get("grantNumber"),
        "denomination": denomination,
        "cultivar_name": denomination,
        "species_name": row.get("speciesName"),
        "applicants": applicants,
        "application_date": row.get("applicationDate"),
        "granting_date": row.get("grantingDate"),
        "expiration_date": row.get("expirationDate"),
        "application_status": row.get("applicationStatus"),
        "title_status": row.get("titleStatus"),
        "exam_office_country": row.get("examOfficeCountry"),
        "exam_office_name": row.get("examOfficeName"),
        "breeders_reference": row.get("breedersReference"),
        # No stable per-record deep-link is confirmed working (the public
        # portal is a query-driven SPA; this mirrors the same query the API
        # itself used, which is the most honest "source_url" available
        # without a verified permalink -- documented as a real limitation,
        # not assumed to resolve).
        "source_url": (
            f"https://online.plantvarieties.eu/publicSearch?denomination={denomination}"
            "&denominationSearchType=equals"
        ),
        "jurisdiction": "EU (CPVO)",
        "acquired_at": acquired,
        "acquisition_method": "cpvo_public_register_api",
    }
    return filing


def build_cpvo_review_draft(
    filing: dict[str, Any],
    *,
    berry_id: str,
    suggestions: list[dict[str, Any]],
    captured_date: str,
) -> dict[str, Any]:
    entity_ids = matched_entity_ids(suggestions)
    applicants = filing.get("applicants") or []
    applicant_label = ", ".join(applicants) if applicants else "applicant not recorded on this register row"
    status = filing.get("title_status") or filing.get("application_status") or "status unknown"
    summary = (
        f"CPVO Community Plant Variety Right register entry for denomination {filing['denomination']!r} "
        f"(species: {filing.get('species_name') or 'not recorded'}), application {filing.get('application_number')}, "
        f"title status {status!r}. Applicant as listed: {applicant_label}. "
        f"Examination office: {filing.get('exam_office_name') or 'not recorded'}, "
        f"{filing.get('exam_office_country') or ''}."
    )
    why = (
        f"A CPVO Community Plant Variety Right filing/grant is an authoritative EU-wide IP event for "
        f"{filing['denomination']!r}. Treat it as evidence a rights claim exists (and, if title_status is "
        "'approved', was granted), not as proof of EU commercialization, acreage, or market success."
    )
    published = filing.get("granting_date") or filing.get("application_date")
    return {
        "id": draft_id_for_filing(filing["filing_id"]),
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "source_authority": "high",
        "source_tier": "tier_1_primary",
        "verification_state": "unverified",
        "does_not_prove": list(CPVO_DOES_NOT_PROVE),
        "relevance_tier": "direct",
        "intake_type": "pvr_filing",
        "source_type": "plant_breeders_rights_record",
        "title": f"CPVO Community Plant Variety Right -- {filing['denomination']} ({filing.get('species_name') or 'species not recorded'})",
        "source_name": "CPVO public register (online.plantvarieties.eu)",
        "source_url": filing.get("source_url") or "",
        "published_date": published,
        "event_date": filing.get("application_date") or published,
        "captured_date": captured_date,
        "summary": summary,
        "why_it_matters": why,
        "submitted_by": "cpvo-registry-monitor",
        "berry_ids": [berry_id],
        "geography_ids": ["geography-europe"] if berry_id else [],
        "entity_ids": entity_ids,
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": ["pvr", "cpvo", "plant-variety-rights", "alternative-data"],
        "auto_captured": False,
        "validated": False,
        "source_id": "source-cpvo-public-register",
        "evidence_role": "publication_artifact",
        "priority": {
            **PRIORITY_NONE,
            "monitoring": {
                "level": "high",
                "rationale": "New or existing PVR registry activity for a tracked variety's own denomination/alias.",
            },
        },
        "cpvo_filing": filing,
        "entity_link_suggestions": suggestions,
    }


@dataclass
class CpvoRegistryService:
    data_dir: Path
    inbox_dir: Path
    search: Callable[..., list[dict[str, Any]]] = search_cpvo_register
    failures: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.operations_dir = self.inbox_dir / "operations" / "cpvo_registry"
        self.state_path = self.operations_dir / "state.json"
        self.evidence_dir = self.inbox_dir / "evidence"

    def _entities(self) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        folder = self.data_dir / "entities"
        if not folder.is_dir():
            return entities
        for path in folder.rglob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                entities.append(payload)
        return entities

    def _candidate_names(self, entities: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
        """(candidate name to query CPVO with, owning Variety entity) pairs
        -- the variety's own canonical name plus every alias, deduplicated.
        Never queries a name shorter than 4 characters (matches this
        project's existing entity-matching floor -- a shorter query risks
        matching unrelated ornamentals/crops by coincidence)."""
        pairs: list[tuple[str, dict[str, Any]]] = []
        seen: set[str] = set()
        for entity in entities:
            if entity.get("entity_type") != "variety":
                continue
            names = [entity.get("name") or ""] + list(entity.get("aliases") or [])
            for name in names:
                cleaned = (name or "").strip()
                if len(cleaned) < 4 or cleaned.casefold() in seen:
                    continue
                seen.add(cleaned.casefold())
                pairs.append((cleaned, entity))
        return pairs

    def discover(self, *, max_queries: int | None = None) -> dict[str, Any]:
        entities = self._entities()
        candidates = self._candidate_names(entities)
        if max_queries is not None:
            candidates = candidates[:max_queries]
        filings: dict[str, dict[str, Any]] = {}
        query_reports: list[dict[str, Any]] = []
        for name, owning_variety in candidates:
            try:
                rows = self.search(name)
            except CpvoRegistryError as exc:
                self.failures.append(str(exc))
                query_reports.append({"query": name, "status": "error", "error": str(exc)})
                continue
            matched_rows = [row for row in rows if berry_id_for_species(row.get("speciesName"))]
            query_reports.append(
                {
                    "query": name,
                    "status": "ok",
                    "candidate_variety_id": owning_variety.get("id"),
                    "raw_hits": len(rows),
                    "berry_relevant_hits": len(matched_rows),
                }
            )
            for row in matched_rows:
                filing = normalize_cpvo_register_row(row)
                filing["matched_query"] = name
                filing["matched_variety_id"] = owning_variety.get("id")
                filings.setdefault(filing["filing_id"], filing)
        return {
            "filings": list(filings.values()),
            "queries": query_reports,
            "queried": len(candidates),
        }

    def persist_drafts(self, filings: list[dict[str, Any]], *, dry_run: bool = False) -> dict[str, Any]:
        state = load_registry_state(self.state_path)
        seen = set(state.get("seen_filing_ids") or [])
        entities = self._entities()
        captured = date.today().isoformat()
        created: list[str] = []
        duplicates: list[str] = []
        review_ready: list[str] = []
        for filing in filings:
            filing_id = filing["filing_id"]
            draft_id = draft_id_for_filing(filing_id)
            draft_path = self.evidence_dir / f"{draft_id}.json"
            if filing_id in seen or draft_path.is_file():
                duplicates.append(filing_id)
                continue
            berry_id = berry_id_for_species(filing.get("species_name"))
            if berry_id is None:
                continue
            filing_for_matching = {
                "applicants": filing.get("applicants") or [],
                "cultivar_name": filing.get("cultivar_name"),
                "publication_number": filing.get("application_number"),
            }
            suggestions = suggest_entity_links(filing_for_matching, entities)
            clean_filing = {key: value for key, value in filing.items() if not key.startswith("_")}
            draft = build_cpvo_review_draft(clean_filing, berry_id=berry_id, suggestions=suggestions, captured_date=captured)
            review_ready.append(draft_id)
            if not dry_run:
                _write_json(draft_path, draft)
                seen.add(filing_id)
                created.append(draft_id)
        if not dry_run:
            state["seen_filing_ids"] = sorted(seen)
            state["last_run_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            state["runs"] = (state.get("runs") or [])[-19:] + [
                {"at": state["last_run_at"], "created": created, "duplicates": duplicates, "failures": self.failures}
            ]
            _write_json(self.state_path, state)
        return {"created": created, "duplicates": duplicates, "review_ready": review_ready, "failures": self.failures}


def load_registry_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"seen_filing_ids": [], "runs": []}
    payload = _read_json(path)
    payload.setdefault("seen_filing_ids", [])
    payload.setdefault("runs", [])
    return payload


def run_cpvo_registry_monitor(
    *,
    data_dir: Path,
    inbox_dir: Path,
    max_queries: int | None = None,
    dry_run: bool = False,
    search: Callable[..., list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    service = CpvoRegistryService(data_dir=data_dir, inbox_dir=inbox_dir, search=search or search_cpvo_register)
    discovery = service.discover(max_queries=max_queries)
    persisted = service.persist_drafts(discovery["filings"], dry_run=dry_run)
    return {
        "queried": discovery["queried"],
        "berry_relevant_filings": len(discovery["filings"]),
        "duplicates": len(persisted["duplicates"]),
        "review_ready": len(persisted["review_ready"]),
        "created": persisted["created"],
        "failed": persisted["failures"],
        "queries": discovery["queries"],
        "dry_run": dry_run,
    }
