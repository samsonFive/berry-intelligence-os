#!/usr/bin/env python3
"""Materialize Claude's reviewed Markdown Gold Set as an executable fixture.

The Markdown document remains the human-owned source of truth.  This adapter
copies its proposition tables and exact repository source text into the JSON
contract consumed by the deterministic qualification harness.  It does not
create or mutate trusted records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCUMENT = ROOT / "docs" / "v2" / "ATOMIC-EVIDENCE-GOLD-SET-V1.md"
DEFAULT_OUTPUT = ROOT / "benchmarks" / "atomic-evidence-gold-set-v1.json"

PRIMARY_SOURCE_IDS = {
    1: "ev-hortifrut-mbo-genetics-2026",
    2: "ev-costa-ownership-2024",
    3: "ev-agrovision-10-years-2024",
    4: "ev-driscolls-cbc-appeal-2025",
    5: "ev-producereport-blugenix-2026",
    6: "ev-blueberriesconsulting-agrovision-2024",
    7: "ev-italianberry-peru-varieties-2025",
    8: "ev-fruitnet-ozblu-dispute-2020",
    9: "ev-leadersleague-atlantic-blue-2021",
    10: "ev-fruitnet-eureka-sunrise-2023",
    11: "ev-hortweek-driscolls-victoria-award",
    12: "ev-fruitnet-driscolls-zara-best-strawberry",
}
REGISTRY_SOURCE_IDS = {
    13: "ev-uspp031605-ridley-1602",
    14: "ev-cfia-pbr-sekoya-grande",
}
THIN_CASES = {
    15: (
        "ev-20260806173539-86c2-tsbc-partners-with-berrytech-on-new-rasp",
        "TSBC signed an exclusive UK/Ireland/Portugal grow-and-distribute deal with Berrytech for raspberry variety Amalia Rossa on 2023-10-20.",
        "relationship",
    ),
    16: (
        "ev-20260806173540-a6ec-new-year-round-premium-blackberry-platfo",
        "PSG's year-round Rejoice blackberry platform is built around the named cultivar BK 6-13.",
        "identity",
    ),
}

GLOBAL_FORBIDDEN = [
    {
        "id": "ownership-implies-control",
        "phrases": ["ownership proves operational control", "owns all variety-release decisions"],
        "severity": "critical",
        "reason": "Ownership alone does not establish operational control or decision rights.",
    },
    {
        "id": "unsupported-causality",
        "phrases": ["therefore caused", "proves that it caused", "was caused by"],
        "severity": "critical",
        "reason": "Sequence or association is not evidence of causality.",
    },
    {
        "id": "registry-implies-commercialization",
        "phrases": ["patent proves commercial success", "filing proves market adoption", "grant proves commercialization"],
        "severity": "critical",
        "reason": "A filing or grant establishes an IP event, not commercialization or adoption.",
    },
    {
        "id": "interest-implies-commitment",
        "phrases": ["interest is a purchase commitment", "visit created a signed supply agreement", "feedback is a purchase order"],
        "severity": "critical",
        "reason": "Interest, a visit, or feedback is not a purchase/listing commitment.",
    },
    {
        "id": "award-implies-general-preference",
        "phrases": ["award proves general consumer preference", "preferred by consumers in all markets"],
        "severity": "critical",
        "reason": "One award or panel does not establish general consumer preference.",
    },
    {
        "id": "local-trial-implies-universal-trait",
        "phrases": ["trial proves the trait universally", "performs identically in all regions", "universal agronomic trait"],
        "severity": "critical",
        "reason": "A located, dated trial cannot be generalized to every region or production system.",
    },
    {
        "id": "marketing-implies-independent-verification",
        "phrases": ["marketing claim is independently verified", "company statement is proven fact", "slogan proves"],
        "severity": "critical",
        "reason": "First-party marketing language is not independent verification.",
    },
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cells(line: str) -> list[str]:
    return [cell.strip().replace("`", "") for cell in line.strip().strip("|").split("|")]


def _table_after(lines: list[str], start: int) -> tuple[list[str], list[list[str]]]:
    index = start
    while index < len(lines) and not lines[index].startswith("|"):
        index += 1
    if index + 1 >= len(lines):
        raise ValueError(f"no Markdown table found after line {start + 1}")
    header = _cells(lines[index])
    index += 2
    rows: list[list[str]] = []
    while index < len(lines) and lines[index].startswith("|"):
        rows.append(_cells(lines[index]))
        index += 1
    return header, rows


def _heading_index(lines: list[str], pattern: str) -> int:
    regex = re.compile(pattern)
    for index, line in enumerate(lines):
        if regex.search(line):
            return index
    raise ValueError(f"Gold Set section missing: {pattern}")


def _record(source_id: str) -> dict[str, Any]:
    path = ROOT / "data" / "evidence" / f"{source_id}.json"
    if not path.exists():
        raise ValueError(f"trusted source is missing: {path.relative_to(ROOT)}")
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("status") != "published":
        raise ValueError(f"Gold Set source is not trusted/published: {source_id}")
    return record


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _token_f1(left: str, right: str) -> float:
    a, b = set(_normalized(left).split()), set(_normalized(right).split())
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    return 2 * overlap / (len(a) + len(b))


def _best_excerpt(statement: str, record: dict[str, Any]) -> str:
    candidates = [
        value.strip()
        for field in ("summary", "why_it_matters")
        if isinstance((value := record.get(field)), str) and value.strip()
    ]
    if not candidates:
        raise ValueError(f"Gold Set source has no trusted text: {record['id']}")
    return max(candidates, key=lambda value: (_token_f1(statement, value), -len(value)))


def _matching_ids(statement: str, record: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    normalized = _normalized(statement)
    entity_ids: list[str] = []
    geography_ids: list[str] = []
    for identifier in record.get("entity_ids", []):
        prefix, _, slug = identifier.partition("-")
        phrase = slug.replace("-", " ")
        if phrase and phrase in normalized:
            (geography_ids if prefix == "geography" else entity_ids).append(identifier)
    berry_ids = [
        identifier for identifier in record.get("berry_ids", [])
        if identifier.removeprefix("berry-").replace("-", " ") in normalized
    ]
    return entity_ids, geography_ids, berry_ids


def _scope(statement: str, limitation: str, record: dict[str, Any], predicate: str = "") -> dict[str, Any]:
    qualifiers = [
        word for word in ("claims", "reports", "states", "announced", "asserted", "filed", "exclusive", "exclusively")
        if re.search(rf"\b{word}\b", statement, re.IGNORECASE)
    ]
    dates = re.findall(r"\b(?:19|20)\d{2}(?:-\d{2}-\d{2})?\b", statement)
    return {
        "source_id": record["id"],
        "published_date": record.get("published_date"),
        "source_type": record.get("source_type"),
        "relationship_predicate": predicate or "none",
        "limitation": limitation,
        "required_terms": [*qualifiers, *dates],
    }


def _expected(
    proposition_id: str,
    statement: str,
    claim_type: str,
    limitation: str,
    predicate: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    entity_ids, geography_ids, berry_ids = _matching_ids(statement, record)
    return {
        "id": proposition_id,
        "statement": statement,
        "exact_excerpt": _best_excerpt(statement, record),
        "entity_ids": entity_ids,
        "geography_ids": geography_ids,
        "berry_ids": berry_ids,
        "claim_type": claim_type,
        "scope": _scope(statement, limitation, record, predicate),
    }


def _case(number: int, source_id: str, propositions: list[dict[str, str]]) -> dict[str, Any]:
    record = _record(source_id)
    segments = [
        {"text": record[field], "source_location": field}
        for field in ("summary", "why_it_matters")
        if isinstance(record.get(field), str) and record[field].strip()
    ]
    expected = [
        _expected(item["id"], item["statement"], item["claim_type"], item["limitation"], item.get("predicate", ""), record)
        for item in propositions
    ]
    return {
        "id": f"gold-{number:02d}-{source_id.removeprefix('ev-')}",
        "title": record["title"],
        "source_artifact": {
            "id": source_id,
            "title": record["title"],
            "source_name": record["source_name"],
            "source_url": record["source_url"],
            "captured_date": record["captured_date"],
            "published_date": record.get("published_date"),
            "language": record.get("language", "en"),
            "locator_kind": "written_text",
            "segments": segments,
            "entity_ids": record.get("entity_ids", []),
            "geography_ids": record.get("geography_ids", []),
            "berry_ids": record.get("berry_ids", []),
        },
        "expected_propositions": expected,
        "forbidden_propositions": GLOBAL_FORBIDDEN,
        "scoring_metadata": {
            "annotation_source": "docs/v2/ATOMIC-EVIDENCE-GOLD-SET-V1.md",
            "source_number": number,
            "text_basis": [segment["source_location"] for segment in segments],
            "expected_count": len(expected),
            "record_entity_ids": record.get("entity_ids", []),
            "record_berry_ids": record.get("berry_ids", []),
        },
    }


def _primary_propositions(lines: list[str], number: int, source_id: str) -> list[dict[str, str]]:
    if number == 10:
        start = _heading_index(lines, rf"^\*\*Flagship: `{re.escape(source_id)}`")
        header, rows = _table_after(lines, start)
        if header[:3] != ["Dimension", "Claim", "Must NOT collapse into"]:
            raise ValueError("unexpected Source 10 table contract")
        letters = "abcdef"
        return [
            {
                "id": f"10{letters[index]}",
                "statement": row[1],
                "claim_type": row[0].casefold().replace("/", "_or_").replace(" ", "_"),
                "predicate": "",
                "limitation": row[2],
            }
            for index, row in enumerate(rows)
        ]
    start = _heading_index(lines, rf"^\*\*Source {number} .+`{re.escape(source_id)}`")
    header, rows = _table_after(lines, start)
    if header[0] != "Claim" or header[1] not in {"Text", "Text (near-verbatim to the real trusted Fact)"}:
        raise ValueError(f"unexpected Source {number} table contract")
    output = []
    for row in rows:
        predicate = row[3] if len(header) == 5 else ""
        limitation = row[4] if len(header) == 5 else row[3]
        output.append({
            "id": row[0], "statement": row[1], "claim_type": row[2],
            "predicate": predicate, "limitation": limitation,
        })
    return output


def _registry_propositions(lines: list[str], number: int, source_id: str) -> list[dict[str, str]]:
    start = _heading_index(lines, rf"^\*\*`{re.escape(source_id)}`")
    header, rows = _table_after(lines, start)
    if header != ["Field", "Value", "Does NOT establish"]:
        raise ValueError(f"unexpected registry table contract for {source_id}")
    letters = "abcdefghijklmnopqrstuvwxyz"
    return [
        {
            "id": f"{number}{letters[index]}",
            "statement": f"{row[0]}: {row[1]}",
            "claim_type": "registry_filing" if row[0] not in {"Parentage", "Independent examiner description"} else "attribute",
            "predicate": "",
            "limitation": row[2],
        }
        for index, row in enumerate(rows)
    ]


def materialize(document: Path = DEFAULT_DOCUMENT) -> dict[str, Any]:
    lines = document.read_text(encoding="utf-8").splitlines()
    cases: list[dict[str, Any]] = []
    for number, source_id in PRIMARY_SOURCE_IDS.items():
        cases.append(_case(number, source_id, _primary_propositions(lines, number, source_id)))
    for number, source_id in REGISTRY_SOURCE_IDS.items():
        cases.append(_case(number, source_id, _registry_propositions(lines, number, source_id)))
    for number, (source_id, statement, claim_type) in THIN_CASES.items():
        cases.append(_case(number, source_id, [{
            "id": f"{number}a", "statement": statement, "claim_type": claim_type,
            "predicate": "", "limitation": "Thin source: do not pad with unsupported roles or claims.",
        }]))
    return {
        "contract_version": "atomic-evidence-gold-set-v1",
        "gold_set_id": "atomic-evidence-gold-set-v1",
        "version": 1,
        "description": "Executable representation of the human-reviewed Atomic Evidence Gold Set V1; 16 trusted written-text cases, with the pending Planasa flagship and transcript-less spoken-media source correctly excluded from scoring.",
        "source_document": document.relative_to(ROOT).as_posix(),
        "source_document_sha256": _sha256(document),
        "thresholds": {
            "precision": 0.9, "recall": 0.9, "atomicity": 0.9, "grounding": 1.0,
            "entity_resolution": 0.9, "scope_preservation": 0.9,
            "overreach": 1.0, "duplication": 0.95,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", type=Path, default=DEFAULT_DOCUMENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in fixture is stale; do not write")
    args = parser.parse_args()
    rendered = json.dumps(materialize(args.document), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            print(f"stale Atomic Evidence Gold Set fixture: {args.output}", file=sys.stderr)
            return 1
        print(f"Atomic Evidence Gold Set fixture is current: {args.output}")
        return 0
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {len(json.loads(rendered)['cases'])} scored cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
