"""Audit trusted canonical Entity/Evidence recall without mutating records.

The report is internal operator output. It reads only canonical trusted data;
it never reads ``inbox/`` and therefore cannot leak pending/private drafts.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.entity_alias_recall import MIN_ALIAS_LENGTH, TEXT_FIELDS, linked_evidence_for_entity


def _load_records(folder: Path) -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))]


def _legacy_text_link(entity: dict[str, Any], record: dict[str, Any]) -> bool:
    entity_id = str(entity.get("id") or "")
    if entity_id in (record.get("entity_ids") or []):
        return True
    values = [entity.get("name"), *(entity.get("aliases") or [])]
    aliases = [value for value in values if isinstance(value, str) and len(value) >= MIN_ALIAS_LENGTH]
    text = " ".join(str(record.get(field) or "") for field in TEXT_FIELDS)
    return any(re.search(re.escape(alias), text, re.IGNORECASE) for alias in aliases)


def _score(cases: list[dict[str, Any]], predictions: dict[tuple[str, str], bool]) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for case in cases:
        expected = bool(case["expected"])
        predicted = predictions[(case["entity_id"], case["evidence_id"])]
        if expected and predicted:
            tp += 1
        elif expected:
            fn += 1
        elif predicted:
            fp += 1
        else:
            tn += 1
    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else 1.0,
        "recall": round(tp / (tp + fn), 4) if tp + fn else 1.0,
    }


def main() -> int:
    entities_list: list[dict[str, Any]] = []
    for folder in sorted((ROOT / "data" / "entities").iterdir()):
        if folder.is_dir():
            entities_list.extend(_load_records(folder))
    entities = {str(entity["id"]): entity for entity in entities_list}
    evidence = [
        record
        for record in _load_records(ROOT / "data" / "evidence")
        if record.get("status") == "published"
    ]
    evidence_by_id = {str(record["id"]): record for record in evidence}
    benchmark = json.loads(
        (ROOT / "benchmarks" / "entity-linking-precision-v1.json").read_text(encoding="utf-8")
    )
    cases = list(benchmark["cases"])

    legacy_pairs: set[tuple[str, str]] = set()
    current_pairs: set[tuple[str, str]] = set()
    current_recall_by_entity: Counter[str] = Counter()
    for entity in entities_list:
        if entity.get("entity_type") not in {"company", "variety"}:
            continue
        entity_id = str(entity["id"])
        direct_ids = {
            str(record["id"])
            for record in evidence
            if entity_id in (record.get("entity_ids") or [])
        }
        legacy_pairs.update(
            (entity_id, str(record["id"]))
            for record in evidence
            if str(record["id"]) not in direct_ids and _legacy_text_link(entity, record)
        )
        for record in linked_evidence_for_entity(entity, evidence, entities=entities):
            if record.get("link_mechanism") == "alias_recall":
                pair = (entity_id, str(record["id"]))
                current_pairs.add(pair)
                current_recall_by_entity[entity_id] += 1

    legacy_predictions: dict[tuple[str, str], bool] = {}
    current_predictions: dict[tuple[str, str], bool] = {}
    for case in cases:
        pair = (str(case["entity_id"]), str(case["evidence_id"]))
        entity = entities[pair[0]]
        record = evidence_by_id[pair[1]]
        legacy_predictions[pair] = _legacy_text_link(entity, record)
        current_predictions[pair] = any(
            linked.get("id") == pair[1]
            for linked in linked_evidence_for_entity(entity, [record], entities=entities)
        )

    types = {entity_id: entities[entity_id].get("entity_type") for entity_id, _ in legacy_pairs | current_pairs}
    ambiguous_aliases = []
    for entity in entities_list:
        if entity.get("entity_type") not in {"company", "variety"}:
            continue
        aliases = [entity.get("name"), *(entity.get("aliases") or [])]
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            tokens = re.findall(r"[A-Za-z]+", alias)
            if len(tokens) != 1 or len(alias) < MIN_ALIAS_LENGTH or len(alias) > 12:
                continue
            entity_id = str(entity["id"])
            old_count = sum(pair[0] == entity_id for pair in legacy_pairs)
            new_count = current_recall_by_entity[entity_id]
            if old_count:
                ambiguous_aliases.append({
                    "entity_id": entity_id,
                    "entity_type": entity.get("entity_type"),
                    "alias": alias,
                    "legacy_linked_evidence": old_count,
                    "current_linked_evidence": new_count,
                })

    sample_entity_ids = {str(case["entity_id"]) for case in cases}
    report = {
        "status": "complete",
        "scope": "canonical trusted data only; inbox not read",
        "entities_audited": {
            "company": sum(entity.get("entity_type") == "company" for entity in entities_list),
            "variety": sum(entity.get("entity_type") == "variety" for entity in entities_list),
        },
        "reviewed_sample": {
            "cases": len(cases),
            "companies": sum(entities[entity_id].get("entity_type") == "company" for entity_id in sample_entity_ids),
            "varieties": sum(entities[entity_id].get("entity_type") == "variety" for entity_id in sample_entity_ids),
            "berries": sorted({
                berry
                for entity_id in sample_entity_ids
                for berry in (entities[entity_id].get("berry_ids") or [])
            }),
            "before": _score(cases, legacy_predictions),
            "after": _score(cases, current_predictions),
        },
        "fallback_corpus": {
            "before": {
                kind: sum(types.get(entity_id) == kind for entity_id, _ in legacy_pairs)
                for kind in ("company", "variety")
            },
            "after": {
                kind: sum(types.get(entity_id) == kind for entity_id, _ in current_pairs)
                for kind in ("company", "variety")
            },
            "corrected": {
                kind: sum(types.get(entity_id) == kind for entity_id, _ in legacy_pairs - current_pairs)
                for kind in ("company", "variety")
            },
            "newly_recalled": {
                kind: sum(types.get(entity_id) == kind for entity_id, _ in current_pairs - legacy_pairs)
                for kind in ("company", "variety")
            },
        },
        "ambiguous_alias_candidates": sorted(
            ambiguous_aliases,
            key=lambda row: (str(row["entity_type"]), -int(row["legacy_linked_evidence"]), str(row["alias"]).casefold()),
        ),
        "reviewed_false_positive_classes": dict(sorted(Counter(
            str(case["class"])
            for case in cases
            if not case["expected"] and legacy_predictions[(case["entity_id"], case["evidence_id"])]
        ).items())),
        "corpus_corrected_pairs": [
            {"entity_id": entity_id, "evidence_id": evidence_id}
            for entity_id, evidence_id in sorted(legacy_pairs - current_pairs)
        ],
        "reviewed_corrected_pairs": [
            {"entity_id": case["entity_id"], "evidence_id": case["evidence_id"], "class": case["class"]}
            for case in cases
            if not case["expected"]
            and legacy_predictions[(case["entity_id"], case["evidence_id"])]
            and not current_predictions[(case["entity_id"], case["evidence_id"])]
        ],
        "reviewed_legitimate_matches_retained": [
            {"entity_id": case["entity_id"], "evidence_id": case["evidence_id"], "class": case["class"]}
            for case in cases
            if case["expected"] and current_predictions[(case["entity_id"], case["evidence_id"])]
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
