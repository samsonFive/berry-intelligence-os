"""Run one bounded plant-patent monitor cycle.

Writes untrusted publication_artifact drafts to inbox/evidence/. Never
writes trusted data/, Facts, or Relationships. Per-query failures are
isolated so one bad search does not abort the run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Callable

from app.services.patent_monitor.corroboration import propose_corroboration_links
from app.services.patent_monitor.entity_link import matched_entity_ids, suggest_entity_links
from app.services.patent_monitor.google_patents import GooglePatentsError, search_google_patents
from app.services.patent_monitor.normalize import (
    PATENT_DOES_NOT_PROVE,
    canonical_publication_number,
    draft_id_for_publication,
)
from app.services.patent_monitor.relevance import relevance_decision
from app.services.patent_monitor.uspto_odp import UsptoOdpError, odp_available, search_uspto_odp
from app.services.transcript_evidence import PRIORITY_NONE

WATCHLIST_PATH = Path("data/configuration/patent_watchlist.json")


class PatentMonitorError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_watchlist(path: Path | None = None) -> dict[str, Any]:
    target = path or WATCHLIST_PATH
    payload = _read_json(target)
    if payload.get("kind") != "berry-intelligence-os-patent-watchlist":
        raise PatentMonitorError(f"not a patent watchlist: {target}")
    return payload


def load_monitor_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"seen_publication_numbers": [], "runs": []}
    payload = _read_json(path)
    payload.setdefault("seen_publication_numbers", [])
    payload.setdefault("runs", [])
    return payload


def choose_provider(preferred: list[str] | None = None) -> str:
    order = preferred or ["uspto_odp", "google_patents_json"]
    if "uspto_odp" in order and odp_available():
        return "uspto_odp"
    if "google_patents_json" in order:
        return "google_patents_json"
    raise PatentMonitorError("no patent discovery provider available")


def search_with_provider(
    provider: str,
    query: str,
    *,
    after_publication: str | None,
    num: int,
    google_search: Callable[..., dict[str, Any]] = search_google_patents,
    odp_search: Callable[..., dict[str, Any]] = search_uspto_odp,
) -> dict[str, Any]:
    if provider == "uspto_odp":
        return odp_search(query, limit=num)
    return google_search(query, after_publication=after_publication, num=num)


def build_review_draft(
    filing: dict[str, Any],
    *,
    berry_ids: list[str],
    suggestions: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
    source_id: str,
    captured_date: str,
) -> dict[str, Any]:
    entity_ids = matched_entity_ids(suggestions)
    assignees = filing.get("assignees") or []
    inventors = filing.get("inventors") or []
    cultivar = filing.get("cultivar_name") or "unnamed cultivar"
    assignee_label = ", ".join(assignees) if assignees else "assignee not recorded on this discovery record"
    inventor_label = ", ".join(inventors) if inventors else "inventor list incomplete on this discovery record"
    summary = (
        f"USPTO plant patent {filing['publication_number']} titled {filing.get('title')!r} "
        f"records cultivar {cultivar!r}. Assignee/applicant as listed: {assignee_label}. "
        f"Inventors as listed: {inventor_label}. Botanical name: {filing.get('botanical_name') or 'not captured'}."
    )
    why = (
        f"A plant-patent filing is an authoritative IP event for {cultivar}. "
        "Treat it as evidence that this genetics identity was claimed, not as proof of "
        "commercial acreage, launch, or market success."
    )
    published = filing.get("grant_date") or filing.get("publication_date") or filing.get("filing_date")
    return {
        "id": draft_id_for_publication(filing["publication_number"]),
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        # source_authority (the registry/source itself) vs. verification_state
        # (how independently corroborated this specific claim is) vs.
        # information_confidence (omitted -- genuinely unknown until a human
        # or corroborating Evidence establishes it; "unknown" is not a valid
        # information_confidence value, unlike the other two fields).
        "source_authority": "high",
        "source_tier": "tier_1_primary",
        "verification_state": "unverified",
        "does_not_prove": list(PATENT_DOES_NOT_PROVE),
        # Every patent draft here already passed relevance_decision()'s
        # named-berry match in discover() -- the same one-mention-is-enough
        # bar app/services/relevance_screen.py documents for its own DIRECT
        # tier. Without this, a patent falls through app/services/
        # morning_brief.py's relevance_tier-based ranking as neither direct
        # nor adjacent.
        "relevance_tier": "direct",
        "intake_type": "patent_filing",
        "source_type": "patent_record",
        "title": filing.get("title") or filing["publication_number"],
        "source_name": "USPTO plant patent (Google Patents discovery)"
        if filing.get("acquisition_method") == "google_patents_json"
        else "USPTO Open Data Portal",
        "source_url": filing.get("source_url") or "",
        "published_date": published,
        "event_date": filing.get("filing_date") or published,
        "captured_date": captured_date,
        "summary": summary,
        "why_it_matters": why,
        "submitted_by": "patent-monitor",
        "berry_ids": berry_ids,
        "geography_ids": ["geography-united-states"] if filing.get("jurisdiction") == "US" else [],
        "entity_ids": entity_ids,
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": ["patent", "plant-patent", "alternative-data"],
        "auto_captured": False,
        "validated": False,
        "source_id": source_id,
        "evidence_role": "publication_artifact",
        "priority": {
            **PRIORITY_NONE,
            "monitoring": {
                "level": "high",
                "rationale": "New or recently published plant-patent activity on in-scope berry genetics.",
            },
        },
        "patent_filing": filing,
        "entity_link_suggestions": suggestions,
        "evidence_links": evidence_links,
    }


@dataclass
class PatentMonitorService:
    data_dir: Path
    inbox_dir: Path
    watchlist: dict[str, Any]
    google_search: Callable[..., dict[str, Any]] = search_google_patents
    odp_search: Callable[..., dict[str, Any]] = search_uspto_odp
    source_id: str = "source-uspto-plant-patents"
    failures: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.operations_dir = self.inbox_dir / "operations" / "patent_monitor"
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

    def _trusted_evidence(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        folder = self.data_dir / "evidence"
        if not folder.is_dir():
            return records
        for path in folder.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                records.append(payload)
        return records

    def discover(self, *, max_candidates: int | None = None) -> dict[str, Any]:
        provider = choose_provider(self.watchlist.get("provider_preference"))
        after = self.watchlist.get("publication_after")
        cap = int(max_candidates or self.watchlist.get("max_candidates_per_run") or 50)
        queries = [query for query in (self.watchlist.get("queries") or []) if query.get("q")]
        per_query = max(5, cap // max(1, len(queries)))
        exclude = self.watchlist.get("exclude_terms") or []
        seen: dict[str, dict[str, Any]] = {}
        query_reports: list[dict[str, Any]] = []
        for index, query in enumerate(queries):
            expression = query.get("q")
            query_id = query.get("id") or expression
            if index and provider == "google_patents_json":
                time.sleep(8)
            try:
                result = search_with_provider(
                    provider,
                    expression,
                    after_publication=after,
                    num=min(50, cap),
                    google_search=self.google_search,
                    odp_search=self.odp_search,
                )
            except (GooglePatentsError, UsptoOdpError, PatentMonitorError) as extra:
                self.failures.append(f"{query_id}: {extra}")
                query_reports.append({"id": query_id, "status": "failed", "error": str(extra)})
                continue
            kept = 0
            skipped = 0
            remaining = cap - len(seen)
            query_cap = min(per_query, remaining) if remaining > 0 else 0
            for filing in result.get("hits") or []:
                if kept >= query_cap:
                    break
                number = canonical_publication_number(filing["publication_number"])
                if number in seen:
                    skipped += 1
                    continue
                decision = relevance_decision(filing, berry_hint=query.get("berry_hint"), exclude_terms=exclude)
                filing["_relevance"] = decision
                filing["_query_id"] = query_id
                if not decision["relevant"]:
                    skipped += 1
                    continue
                seen[number] = filing
                kept += 1
            query_reports.append(
                {
                    "id": query_id,
                    "status": "ok",
                    "provider_total": result.get("total"),
                    "kept": kept,
                    "skipped": skipped,
                }
            )
        return {
            "provider": provider,
            "filings": list(seen.values()),
            "queries": query_reports,
            "discovered": sum((row.get("provider_total") or 0) if row.get("status") == "ok" else 0 for row in query_reports),
        }

    def persist_drafts(
        self,
        filings: list[dict[str, Any]],
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        state = load_monitor_state(self.state_path)
        seen = {canonical_publication_number(value) for value in state.get("seen_publication_numbers") or []}
        entities = self._entities()
        trusted = self._trusted_evidence()
        captured = date.today().isoformat()
        created: list[str] = []
        duplicates: list[str] = []
        review_ready: list[str] = []
        for filing in filings:
            number = canonical_publication_number(filing["publication_number"])
            draft_id = draft_id_for_publication(number)
            draft_path = self.evidence_dir / f"{draft_id}.json"
            if number in seen or draft_path.is_file():
                duplicates.append(number)
                continue
            berry_ids = list((filing.get("_relevance") or {}).get("berry_ids") or [])
            suggestions = suggest_entity_links(filing, entities)
            entity_ids = matched_entity_ids(suggestions)
            links = propose_corroboration_links(
                filing,
                trusted_evidence=trusted,
                matched_entity_ids=entity_ids,
                berry_ids=berry_ids,
            )
            clean_filing = {key: value for key, value in filing.items() if not key.startswith("_")}
            draft = build_review_draft(
                clean_filing,
                berry_ids=berry_ids,
                suggestions=suggestions,
                evidence_links=links,
                source_id=self.source_id,
                captured_date=captured,
            )
            review_ready.append(draft_id)
            if not dry_run:
                _write_json(draft_path, draft)
                seen.add(number)
                created.append(draft_id)
        if not dry_run:
            state["seen_publication_numbers"] = sorted(seen)
            state["last_run_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            state["runs"] = (state.get("runs") or [])[-19:] + [
                {
                    "at": state["last_run_at"],
                    "created": created,
                    "duplicates": duplicates,
                    "failures": self.failures,
                }
            ]
            _write_json(self.state_path, state)
        return {
            "created": created,
            "duplicates": duplicates,
            "review_ready": review_ready,
            "failures": self.failures,
        }


def run_patent_monitor(
    *,
    data_dir: Path,
    inbox_dir: Path,
    watchlist_path: Path | None = None,
    max_candidates: int | None = None,
    dry_run: bool = False,
    google_search: Callable[..., dict[str, Any]] | None = None,
    odp_search: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    watchlist = load_watchlist(watchlist_path)
    service = PatentMonitorService(
        data_dir=data_dir,
        inbox_dir=inbox_dir,
        watchlist=watchlist,
        google_search=google_search or search_google_patents,
        odp_search=odp_search or search_uspto_odp,
    )
    discovery = service.discover(max_candidates=max_candidates)
    persisted = service.persist_drafts(discovery["filings"], dry_run=dry_run)
    skipped = 0
    for query in discovery["queries"]:
        skipped += int(query.get("skipped") or 0)
    return {
        "provider": discovery["provider"],
        "discovered": discovery["discovered"],
        "berry_relevant": len(discovery["filings"]),
        "skipped": skipped,
        "duplicates": len(persisted["duplicates"]),
        "review_ready": len(persisted["review_ready"]),
        "created": persisted["created"],
        "failed": persisted["failures"],
        "queries": discovery["queries"],
        "dry_run": dry_run,
        "filings": discovery["filings"],
    }
