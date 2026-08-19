"""Propose untrusted evidence-to-evidence corroboration links.

Never sets status=accepted. Human review is required.
"""

from __future__ import annotations

from datetime import date
import re
from typing import Any

from app.services.patent_monitor.normalize import canonical_publication_number, strip_markup

PREDICATE_CORROBORATES = "corroborates"
PREDICATE_SAME_SIGNAL = "same_signal"


def _fold(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


def _evidence_haystack(record: dict[str, Any]) -> str:
    return " ".join(
        [
            strip_markup(record.get("title") or ""),
            strip_markup(record.get("summary") or ""),
            strip_markup(record.get("why_it_matters") or ""),
            " ".join(record.get("tags") or []),
        ]
    )


def propose_corroboration_links(
    filing: dict[str, Any],
    *,
    trusted_evidence: list[dict[str, Any]],
    matched_entity_ids: list[str],
    berry_ids: list[str] | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    cultivar = _fold(str(filing.get("cultivar_name") or ""))
    number = canonical_publication_number(str(filing.get("publication_number") or ""))
    number_fold = _fold(number)
    patent_berries = set(berry_ids or [])
    ranked: list[tuple[int, dict[str, Any]]] = []
    today = date.today().isoformat()

    for record in trusted_evidence:
        if record.get("status") != "published":
            continue
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id.startswith("ev-"):
            continue
        haystack = _fold(_evidence_haystack(record))
        record_berries = set(record.get("berry_ids") or [])
        berry_overlap = bool(patent_berries & record_berries) if patent_berries and record_berries else False
        entity_overlap = bool(set(matched_entity_ids) & set(record.get("entity_ids") or []))
        same_number = bool(number_fold) and number_fold in haystack
        cultivar_hit = (
            bool(cultivar)
            and len(cultivar) >= 8
            and f" {cultivar} " in f" {haystack} "
            and (berry_overlap or not record_berries)
        )
        if same_number:
            predicate = PREDICATE_SAME_SIGNAL
            notes = f"Same patent number {number} appears in existing Evidence {record_id}."
            rank = 0
        elif cultivar_hit:
            predicate = PREDICATE_CORROBORATES
            notes = (
                f"Existing Evidence mentions cultivar {filing.get('cultivar_name')!r}; "
                "patent filing is a proposed IP corroboration, not a commercial proof."
            )
            rank = 1
        elif entity_overlap:
            predicate = PREDICATE_CORROBORATES
            notes = (
                "Assignee/variety entity already linked on existing Evidence; "
                "patent filing proposed as additional IP documentation of genetics activity."
            )
            rank = 4
            if berry_overlap:
                rank -= 2
            if record.get("source_type") in {"patent_record", "patent"}:
                rank -= 1
        else:
            continue
        ranked.append(
            (
                rank,
                {
                    "predicate": predicate,
                    "target_evidence_id": record_id,
                    "status": "proposed",
                    "notes": notes,
                    "proposed_by": "patent-monitor",
                    "proposed_at": today,
                },
            )
        )
    ranked.sort(key=lambda item: item[0])
    return [item[1] for item in ranked[:limit]]
