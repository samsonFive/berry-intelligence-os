#!/usr/bin/env python3
"""Validate the blueberry public pilot import package.

Reuses the repository's authoritative schemas verbatim -- it does not
reimplement them. Adds the referential-integrity, convention and
evidence-discipline checks that scripts/validate_records.py does not perform.

Usage:
    python scripts/validate_package.py [--verbose]

Exit code 0 = clean, 1 = errors found.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]                      # data/imports/<pkg>/ -> repo root
SCHEMAS = REPO / "schemas"
REPO_DATA = REPO / "data"

# Mirrors app/main.py::ENTITY_FOLDER_OVERRIDES, plus this package's
# hyphenated directory spellings.
ENTITY_DIR_TO_TYPE = {
    "companies": "company",
    "varieties": "variety",
    "geographies": "geography",
    "people": "person",
    "berries": "berry",
    "brands": "brand",
    "breeding-programs": "breeding_program",
    "traits": "trait",
    "patents": "patent",
    "retailers": "retailer",
    "products": "product",
    "sources": "source",
}

VALID_ROLES = {
    "breeder", "genetics_owner", "nursery", "propagator", "license_administrator",
    "marketer", "grower_shipper", "exporter", "importer", "cooperative",
    "branded_berry_company", "research_institution", "university_breeding_program",
    "retailer", "distributor", "packer",
}

VALID_TIERS = {"tier-1", "tier-2", "tier-3"}

VALID_TRAIT_PROVENANCE = {
    "owner_or_marketer_claim",
    "named_trial_measurement",
    "independent_report",
    "regulatory_or_registry_record",
    "analyst_inference",
    "unresolved",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def load_dir(folder: Path) -> list[tuple[Path, dict[str, Any]]]:
    out = []
    if not folder.exists():
        return out
    for path in sorted(folder.rglob("*.json")):
        try:
            out.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as exc:
            err(f"{path.relative_to(PKG)}: invalid JSON -- {exc}")
    return out


def schema_validate(schema_name: str, items: list[tuple[Path, dict]]) -> None:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for path, record in items:
        for e in validator.iter_errors(record):
            loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
            err(f"{path.relative_to(PKG)} [{loc}]: {e.message}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    # ---------- load ----------
    entities = load_dir(PKG / "entities")
    evidence = load_dir(PKG / "evidence")
    facts = load_dir(PKG / "facts")
    relationships = load_dir(PKG / "relationships")
    sqs = load_dir(PKG / "strategic-questions")
    signals = load_dir(PKG / "signals")

    # ---------- 1. schema conformance (repo schemas, verbatim) ----------
    schema_validate("entity.schema.json", entities)
    schema_validate("evidence.schema.json", evidence)
    schema_validate("fact.schema.json", facts)
    schema_validate("relationship.schema.json", relationships)
    # strategic questions and signals have no repo schema -- see schema-assessment.md

    # ---------- 2. build ID universe ----------
    pkg_ids: dict[str, str] = {}          # id -> record kind
    entity_types: dict[str, str] = {}     # entity id -> entity_type

    def register(rec_id: str, kind: str, path: Path) -> None:
        if not rec_id:
            err(f"{path.relative_to(PKG)}: missing id")
            return
        if rec_id in pkg_ids:
            err(f"duplicate id '{rec_id}' ({kind} vs {pkg_ids[rec_id]})")
        pkg_ids[rec_id] = kind

    for p, r in entities:
        register(r.get("id", ""), "entity", p)
        entity_types[r.get("id", "")] = r.get("entity_type", "")
    for p, r in evidence:
        register(r.get("id", ""), "evidence", p)
    for p, r in facts:
        register(r.get("id", ""), "fact", p)
    for p, r in relationships:
        register(r.get("id", ""), "relationship", p)
    for p, r in sqs:
        register(r.get("id", ""), "strategic_question", p)
    for p, r in signals:
        register(r.get("id", ""), "signal", p)

    # existing repository IDs (references may legitimately resolve there)
    repo_ids: set[str] = set()
    for sub in ("entities", "evidence", "facts", "relationships", "strategic-questions"):
        for _p, r in load_dir(REPO_DATA / sub):
            if r.get("id"):
                repo_ids.add(r["id"])

    known = set(pkg_ids) | repo_ids

    # collision with existing repository records
    for rid in pkg_ids:
        if rid in repo_ids:
            err(f"id '{rid}' already exists in the repository -- import would overwrite it")

    # ---------- 3. entity conventions ----------
    for path, r in entities:
        rid, etype = r.get("id", ""), r.get("entity_type", "")
        # A-9: routing depends on the prefix matching the type
        if etype and rid and not rid.startswith(f"{etype}-"):
            err(f"{path.relative_to(PKG)}: id '{rid}' must start with '{etype}-' "
                f"(entity pages 404 silently otherwise)")
        # folder must match declared type
        parent = path.parent.name
        expected = ENTITY_DIR_TO_TYPE.get(parent)
        if expected and etype != expected:
            err(f"{path.relative_to(PKG)}: in '{parent}/' but entity_type is '{etype}' "
                f"(expected '{expected}')")
        # filename must equal id
        if path.stem != rid:
            err(f"{path.relative_to(PKG)}: filename does not match id '{rid}'")
        # role vocabulary (P-9)
        for role in r.get("roles", []):
            if role not in VALID_ROLES:
                warn(f"{path.relative_to(PKG)}: role '{role}' outside proposed vocabulary")
        # variety trait provenance (L-6)
        for i, t in enumerate(r.get("attributes", {}).get("traits", [])):
            prov = t.get("provenance")
            if prov not in VALID_TRAIT_PROVENANCE:
                err(f"{path.relative_to(PKG)}: traits[{i}].provenance '{prov}' invalid")
            if not t.get("evidence_ids"):
                err(f"{path.relative_to(PKG)}: traits[{i}] ('{t.get('trait')}') has no evidence_ids")

    # ---------- 4. evidence discipline ----------
    urls: dict[str, list[str]] = defaultdict(list)
    titles: dict[str, list[str]] = defaultdict(list)
    for path, r in evidence:
        rid = r.get("id", "")
        # staged records must be proposals, not published
        if r.get("status") != "in_review":
            err(f"{path.relative_to(PKG)}: status is '{r.get('status')}'; staged records "
                f"must be 'in_review' until a human approves (WELCOME.md principle 5)")
        # source tier tag (L-1)
        tiers = VALID_TIERS & set(r.get("tags", []))
        if not tiers:
            err(f"{path.relative_to(PKG)}: no source-tier tag ({'/'.join(sorted(VALID_TIERS))})")
        elif len(tiers) > 1:
            err(f"{path.relative_to(PKG)}: multiple source-tier tags {sorted(tiers)}")
        # priority: all four dimensions, rationale required for non-none (A-4)
        prio = r.get("priority", {})
        for dim in ("reading", "testing", "commercial_position", "monitoring"):
            d = prio.get(dim, {})
            if d.get("level") != "none" and not (d.get("rationale") or "").strip():
                err(f"{path.relative_to(PKG)}: priority.{dim} is '{d.get('level')}' "
                    f"but rationale is empty")
        # a real, resolvable URL
        url = (r.get("source_url") or "").strip()
        if not url:
            err(f"{path.relative_to(PKG)}: empty source_url")
        elif not url.startswith(("http://", "https://")):
            err(f"{path.relative_to(PKG)}: source_url is not http(s): '{url}'")
        else:
            urls[url].append(rid)
        titles[re.sub(r"[^a-z0-9]+", " ", r.get("title", "").lower()).strip()].append(rid)
        # date sanity
        pd, cd = r.get("published_date"), r.get("captured_date", "")
        if pd and cd and DATE_RE.match(pd) and DATE_RE.match(cd) and pd > cd:
            err(f"{path.relative_to(PKG)}: published_date {pd} is after captured_date {cd}")
        if not r.get("summary", "").strip():
            err(f"{path.relative_to(PKG)}: empty summary")
        if not r.get("submitted_by", "").strip():
            err(f"{path.relative_to(PKG)}: empty submitted_by")

    for url, ids in urls.items():
        if len(ids) > 1:
            err(f"duplicate canonical URL across {ids}: {url}")
    for t, ids in titles.items():
        if len(ids) > 1:
            warn(f"near-duplicate title across {ids} (app duplicate-check will flag): '{t}'")

    # ---------- 5. facts ----------
    for path, r in facts:
        if not r.get("evidence_ids"):
            err(f"{path.relative_to(PKG)}: fact has no evidence")
        if not r.get("entity_ids"):
            warn(f"{path.relative_to(PKG)}: fact has no entity_ids")
        stmt = r.get("statement", "")
        if r.get("classification") == "claim":
            # a claim must attribute its speaker
            if not re.search(r"\b(describes|claims|states|says|reports|markets|lists|"
                             r"promotes|positions|characteri[sz]es|according to)\b", stmt, re.I):
                warn(f"{path.relative_to(PKG)}: classification 'claim' but statement does not "
                     f"name who is claiming: '{stmt[:70]}...'")

    # ---------- 6. relationships ----------
    for path, r in relationships:
        if not r.get("evidence_ids"):
            err(f"{path.relative_to(PKG)}: relationship has no evidence")
        for side in ("subject_id", "object_id"):
            v = r.get(side)
            if v and v not in known:
                err(f"{path.relative_to(PKG)}: {side} '{v}' does not resolve")
            elif v and v in entity_types and entity_types[v] == "":
                err(f"{path.relative_to(PKG)}: {side} '{v}' has no entity_type")
        if r.get("subject_id") == r.get("object_id"):
            err(f"{path.relative_to(PKG)}: self-referential relationship")
        # L-2: confidence must be encoded in notes until P-3 lands
        if not re.match(r"confidence=(low|medium|high)\b", r.get("notes", "")):
            err(f"{path.relative_to(PKG)}: notes must begin 'confidence=<low|medium|high>; ' "
                f"(L-2 fallback)")

    # ---------- 7. referential integrity, all link fields ----------
    LINK_FIELDS = ("entity_ids", "evidence_ids", "fact_ids", "relationship_ids",
                   "berry_ids", "strategic_question_ids", "geography_ids")
    for kind, items in (("entity", entities), ("evidence", evidence), ("fact", facts),
                        ("relationship", relationships), ("strategic_question", sqs),
                        ("signal", signals)):
        for path, r in items:
            for field in LINK_FIELDS:
                for ref in r.get(field, []) or []:
                    if ref not in known:
                        err(f"{path.relative_to(PKG)}: {field} -> '{ref}' does not resolve "
                            f"in package or repository")

    # ---------- 8. bidirectional consistency ----------
    for path, r in evidence:
        rid = r.get("id")
        for ent_id in r.get("entity_ids", []):
            ent = next((e for _p, e in entities if e.get("id") == ent_id), None)
            if ent is not None and rid not in ent.get("evidence_ids", []):
                err(f"{path.relative_to(PKG)}: evidence lists entity '{ent_id}' but that "
                    f"entity does not list this evidence back")
    for path, r in facts:
        rid = r.get("id")
        for ev_id in r.get("evidence_ids", []):
            ev = next((e for _p, e in evidence if e.get("id") == ev_id), None)
            if ev is not None and rid not in ev.get("fact_ids", []):
                err(f"{path.relative_to(PKG)}: fact cites evidence '{ev_id}' but that evidence "
                    f"does not list this fact back")
    for path, r in relationships:
        rid = r.get("id")
        for ev_id in r.get("evidence_ids", []):
            ev = next((e for _p, e in evidence if e.get("id") == ev_id), None)
            if ev is not None and rid not in ev.get("relationship_ids", []):
                err(f"{path.relative_to(PKG)}: relationship cites evidence '{ev_id}' but that "
                    f"evidence does not list this relationship back")

    # ---------- 9. signals ----------
    for path, r in signals:
        if len(r.get("evidence_ids", [])) < 2:
            err(f"{path.relative_to(PKG)}: signal needs >= 2 evidence records (brief 12)")
        if r.get("status") not in {"proposed", "monitoring"}:
            err(f"{path.relative_to(PKG)}: signal status must be 'proposed' or 'monitoring' "
                f"in an initial package, got '{r.get('status')}'")

    # ---------- report ----------
    counts = Counter(pkg_ids.values())
    print("Package:", PKG.name)
    print("Records:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none")
    print(f"Distinct source URLs: {len(urls)}")

    if warnings and args.verbose:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  ~ {w}")
    elif warnings:
        print(f"\nWarnings: {len(warnings)} (run --verbose to list)")

    if errors:
        print(f"\nFAILED -- {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nPASSED -- schema, conventions, and referential integrity all clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
