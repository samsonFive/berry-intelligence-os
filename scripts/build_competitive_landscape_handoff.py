"""Freeze the existing ecosystem, then build a manual research handoff.

No network, model, canonical-record mutation, or capability scoring. Input
fingerprints bind prompts to a reviewed inventory instead of a guessed roster.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
VERSION = "competitive-landscape-2026-10-30-v1"
DATE = "2026-10-30"
DATA = ROOT / "data"
SNAPSHOT = DATA / "imports" / VERSION
DOCS = ROOT / "docs" / "research" / VERSION
KINDS = {"company", "brand", "breeding_program", "retailer"}
CORE = {"breeder", "grower", "marketer", "technology_provider"}
ROLE_MAP = {
    "breeder": ["breeder"], "breeding_entity": ["breeder"],
    "grower": ["grower"], "grower_marketer": ["grower", "marketer"],
    "marketer": ["marketer"], "technology_provider": ["technology_provider"],
    "nursery": ["nursery_propagator"], "nursery_propagator": ["nursery_propagator"],
    "plant_producer": ["nursery_propagator"], "grower_cooperative": ["grower"],
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def text_sha256(path):
    """Portable content fingerprint: UTF-8 without BOM, LF newlines."""
    return hashlib.sha256(path.read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def table(headers, rows):
    def cell(v):
        return str(v if v is not None else "Unknown").replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows])


def domain(url):
    host = urlparse(str(url or "")).hostname
    return host.removeprefix("www.") if host and not host.endswith((".invalid", ".example")) else None


def recorded_roles(e):
    roles = sorted({r for raw in e.get("roles", []) for r in ROLE_MAP.get(raw, [])})
    if e["entity_type"] == "breeding_program" and e.get("roles"):
        roles = sorted(set(roles) | {"breeder"})
    return roles


def build_inventory(*, replace_draft=False):
    inputs = sorted((DATA / "entities").rglob("*.json")) + sorted((DATA / "relationships").glob("*.json"))
    inputs += sorted((DATA / "evidence").glob("*.json"))
    inputs += [DATA / "configuration/sources.json", DATA / "configuration/entity-identity-redirects.json"]
    inputs += sorted((DATA / "imports/competitor-registry-2026-09-15").glob("*.json"))
    inputs += [DATA / "imports/gene-editing-2026-10-28/snapshot.json"]
    entities = {e["id"]: (e, p) for p in sorted((DATA / "entities").rglob("*.json")) for e in [read(p)]}
    evidence = {e["id"]: e for p in sorted((DATA / "evidence").glob("*.json")) for e in [read(p)]}
    relationships = [read(p) for p in sorted((DATA / "relationships").glob("*.json"))]
    sources = read(DATA / "configuration/sources.json")
    redirects = read(DATA / "configuration/entity-identity-redirects.json")["redirects"]
    gene = read(DATA / "imports/gene-editing-2026-10-28/snapshot.json")
    gene_companies = {r["entity_id"]: r for r in gene["companies"]}
    import_evidence = {r["id"]: r for r in gene["evidence"]}
    roster = read(DATA / "imports/competitor-registry-2026-09-15/reconciliation-matrix.json")["rows"]
    roster_by_id = {r["canonical_entity_id"]: r for r in roster}
    rows = []
    for eid, (e, path) in sorted(entities.items()):
        if e.get("entity_type") not in KINDS:
            continue
        attrs = e.get("attributes") or {}
        gene_row = gene_companies.get(eid, {})
        fictional = eid in {"company-example-genetics", "company-example-nursery", "retailer-example-market"}
        roles = recorded_roles(e)
        links = [r for r in relationships if eid in (r.get("subject_id"), r.get("object_id"))]
        ev_ids = set(e.get("evidence_ids", [])) | set(gene_row.get("evidence_ids", []))
        ev_ids |= {r for ev in evidence.values() if eid in ev.get("entity_ids", []) for r in [ev["id"]]}
        linked_sources = [s for s in sources if eid in s.get("linked_competitor_ids", [])]
        website = attrs.get("official_domain") or attrs.get("website") or gene_row.get("official_domain")
        official = domain(website)
        domain_basis = ("existing entity attribute" if attrs.get("official_domain") or attrs.get("website") else "existing original-source gene-editing audit") if official else None
        if not official and domain(gene_row.get("official_domain")):
            website = gene_row["official_domain"]
            official, domain_basis = domain(website), "existing original-source gene-editing audit"
        if not domain_basis and official:
            domain_basis = "existing original-source gene-editing audit"
        if not official:
            names = [re.sub(r"[^a-z0-9]+", " ", str(v).casefold()).strip() for v in [e["name"], *e.get("aliases", [])]]
            # A linked search/press outlet is not an official domain. Only an
            # explicitly named entity newsroom with a matching name is eligible.
            newsroom_candidates = []
            for source in linked_sources:
                label = str(source.get("label") or "").casefold()
                if not label.endswith(" newsroom") or "search" in label:
                    continue
                subject = re.sub(r"[^a-z0-9]+", " ", label.removesuffix(" newsroom")).strip()
                host = domain(source.get("url"))
                if host and len(subject) >= 5 and any(f" {subject} " in f" {name} " for name in names):
                    newsroom_candidates.append(source)
            hosts = {domain(s["url"]) for s in newsroom_candidates}
            if len(hosts) == 1:
                website = newsroom_candidates[0]["url"]
                official = domain(website)
                domain_basis = "existing named entity newsroom: " + newsroom_candidates[0]["id"]
        proposed_roles = []
        if gene_row and not fictional:
            proposed_roles = sorted({"breeder", "technology_provider"} - set(roles))
        program_context = attrs.get("gene_editing") or {}
        if program_context:
            proposed_roles = sorted(set(proposed_roles) | {"technology_provider"})
        gaps = ["Production origins and destination markets require explicit evidence; geography links are context only.",
                "Existing entity berry tags do not establish every crop/market capability.",
                "Current people, vacancies and 24-month leadership events require research."]
        if not official:
            gaps.append("Official domain not established from explicit website/domain attributes.")
        if not roles:
            gaps.append("No normalized operating role recorded; confirm role before rating.")
        if e.get("status") == "unverified":
            gaps.append("Canonical entity remains unverified; preserve existing trust status.")
        if eid == "company-plant-sciences-genetics":
            gaps.append("Historical PSI/PSG monitoring lineage spans distinct legal/service/IP roles; do not merge legal persons.")
        if eid == "company-pairwise":
            gaps.append("Legacy grower_marketer classification conflicts with newer editing-program context; roles need reconciliation.")
        if eid == "company-advanced-berry-breeding":
            gaps.append("Separate common-shareholder history from direct Planasa ownership; verify dated current control.")
        linked_programs = [p[0]["id"] for p in entities.values() if p[0].get("entity_type") == "breeding_program"
                           and eid in (p[0].get("attributes", {}).get("gene_editing", {}).get("company_ids", []))]
        dates = [attrs[k].get("verification_date") for k in attrs if k.startswith("identity_verification") and isinstance(attrs[k], dict)]
        if program_context.get("research_reviewed_at"):
            dates.append(program_context["research_reviewed_at"])
        if gene_row:
            dates.append(gene.get("research_date"))
        dates = sorted(d for d in dates if d)
        geo = [r for r in links if r.get("predicate") == "operates_in"]
        identity_unresolved = bool(attrs.get("identity_review_required"))
        status = "out_of_scope" if fictional else "unresolved_identity" if identity_unresolved else "existing_in_scope"
        if any(r["retired_id"] == eid for r in redirects):
            status = "duplicate_candidate"
        row = {
            "entity_id": eid, "display_name": e["name"], "legal_name": attrs.get("legal_name"),
            "aliases": e.get("aliases", []), "entity_type": e["entity_type"], "entity_status": e.get("status"),
            "official_domain": official, "official_url": website if official else None,
            "domain_status": "recorded_not_rechecked" if official else "unknown", "domain_basis": domain_basis,
            "inclusion_status": status, "inclusion_reason": "Fictional demonstration fixture" if fictional else "Existing canonical ecosystem record",
            "recorded_roles": e.get("roles", []), "primary_role": None,
            "primary_role_basis": "Unknown: source registry does not declare a primary-versus-secondary ordering",
            "secondary_roles": [], "unranked_roles": roles, "peer_roles": [r for r in roles if r in CORE],
            "role_status": "recorded_classification_not_new_verification", "proposed_peer_roles": proposed_roles,
            "role_evidence_ids": sorted(ev_ids), "berry_ids": e.get("berry_ids", []),
            "berry_scope_status": "recorded_tags_not_scoped_capability_evidence" if e.get("berry_ids") else "unknown",
            "production_origins": [], "destination_markets": [], "origin_status": "unknown", "destination_status": "unknown",
            "geographic_context_relationships": geo,
            "relationships": links, "linked_program_ids": sorted(linked_programs),
            "program_context": {k: program_context.get(k) for k in ("company_ids", "technology", "crop", "trait", "stage", "milestone_date") if k in program_context},
            "evidence_ids": sorted(ev_ids), "missing_evidence_ids": sorted(ev_ids - evidence.keys() - import_evidence.keys()),
            "import_only_evidence_ids": sorted((ev_ids - evidence.keys()) & import_evidence.keys()),
            "evidence_dates": [{"evidence_id": i, "published_date": evidence[i].get("published_date"),
                                "captured_date": evidence[i].get("captured_date"), "status": evidence[i].get("status")}
                               for i in sorted(ev_ids) if i in evidence],
            "import_evidence_dates": [{"evidence_id": i, "published_date": import_evidence[i].get("published_date"),
                                       "captured_date": import_evidence[i].get("captured_date"), "status": import_evidence[i].get("status"),
                                       "source_ref": "data/imports/gene-editing-2026-10-28/snapshot.json"}
                                      for i in sorted((ev_ids - evidence.keys()) & import_evidence.keys())],
            "linked_source_ids": [s["id"] for s in linked_sources],
            "source_record": path.relative_to(ROOT).as_posix(),
            "dossier_url": f"/entities/{e['entity_type']}/{eid}",
            "last_researched_date": dates[-1] if dates else None,
            "last_researched_basis": "Explicit dated identity/gene audit only; capture and publication dates are not research dates",
            "gaps": gaps, "research_priority": "excluded" if fictional else "P0" if (identity_unresolved or eid in roster_by_id or gene_row) else "P1",
            "legacy_roster": {k: roster_by_id[eid].get(k) for k in ("row_number", "strategic_priority", "berry_tier")} if eid in roster_by_id else None,
        }
        rows.append(row)
    old_queue = read(DATA / "imports/competitor-registry-2026-09-15/unresolved-mapping-queue.json")
    candidates = []
    for n, original in enumerate(old_queue["rows"], 1):
        # Private transcription and analyst notes stay out of the public prompt pack.
        candidates.append({"candidate_id": f"legacy-candidate-{n:02d}", "candidate_company": original.get("candidate_company"),
                           "candidate_provider": original.get("candidate_provider"), "status": "unresolved_legacy_lead",
                           "source_ref": f"data/imports/competitor-registry-2026-09-15/unresolved-mapping-queue.json#/rows/{n-1}",
                           "resolution_rule": "No entity/relationship creation from handwriting or self-mapping; require independent identity evidence."})
    hashes = {p.relative_to(ROOT).as_posix(): text_sha256(p) for p in inputs}
    frozen = SNAPSHOT / "commercial-entity-inventory.json"
    if frozen.exists() and not replace_draft:
        previous = read(frozen)
        if previous["input_hashes"] == hashes:
            print("Reusing the frozen inventory; no source input changed.")
            return previous
        raise ValueError("Source inputs changed. Create a new inventory version and explain reconciliation; do not replace a handed-off snapshot.")
    result = {"inventory_version": VERSION, "snapshot_date": DATE,
              "repository_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "status": "inventory_only_research_and_population_pending", "hash_encoding": "sha256_utf8_lf_no_bom", "input_hashes": hashes,
              "crop_ids": sorted(eid for eid, (e, _) in entities.items() if e.get("entity_type") == "berry"),
              "geography_taxonomy": [{"entity_id": eid, "name": e["name"], "attributes": e.get("attributes", {})}
                                      for eid, (e, _) in entities.items() if e.get("entity_type") == "geography"],
              "canonical_redirects": redirects, "entities": rows, "unresolved_candidates": candidates,
              "counts": {"by_type": dict(Counter(r["entity_type"] for r in rows)),
                         "by_inclusion": dict(Counter(r["inclusion_status"] for r in rows)),
                         "by_recorded_peer_role": dict(Counter(role for r in rows if r["inclusion_status"] != "out_of_scope" for role in r["peer_roles"]))}}
    write_json(SNAPSHOT / "commercial-entity-inventory.json", result)
    text = f"# Commercial entity inventory\n\nVersion: `{VERSION}`. Snapshot: {DATE}. Repository `{result['repository_revision']}`.\n\n"
    text += "Research and application population remain pending. This is an inventory of recorded identities and classifications, not a current factual company assessment. The registry does not declare a primary/secondary role ordering: those fields stay Unknown, with multi-role classifications retained as unranked roles. Legal names are Unknown unless explicitly recorded as legal names.\n\n"
    text += table(["Type", "Records"], sorted(result["counts"]["by_type"].items())) + "\n\n"
    text += "Origin and destination fields intentionally stay Unknown until sources establish their meaning. `operates_in` includes examination/trial/IP context in this repository and is not imported as a farm or sales footprint. Existing crop tags carry their own classification caveats. Existing role classifications, including Pairwise's legacy grower/marketer label, need confirmation; proposed roles from gene-program context are research questions.\n\n"
    text += table(["Canonical ID / dossier", "Name", "Type", "Recorded roles → peer groups", "Berry tags", "Recorded domain", "Status / priority", "Last explicit research"], [
        [f"[{r['entity_id']}]({r['dossier_url']})", r["display_name"], r["entity_type"], ", ".join(r["recorded_roles"]) + " → " + (", ".join(r["peer_roles"]) or "Unknown"),
         ", ".join(r["berry_ids"]) or "Unknown", r["official_domain"], r["inclusion_status"] + " / " + r["research_priority"], r["last_researched_date"]] for r in rows])
    text += "\n\n## Identity and scope resolution\n\nExisting redirects remain canonical: `company-planasa-2` → `company-planasa`. No entity, relationship or trust state was rewritten. Fruitist's brand node and Agrovision's operating-company ID remain distinct. Parent/brand/program records retain their own evidence. PSI/PSG legal/service/IP allocation is unresolved at this inventory's single historical monitoring ID. See structured rows for all relationships with status, direction and original evidence references.\n\n"
    text += "## Unresolved legacy candidates\n\nThese 19 rows are leads from a prior internal reconciliation, not new companies or demonstrated relationships. Names already present elsewhere are still not evidence for the historical mapping. The public prompt pack excludes the internal transcription and analyst notes.\n\n"
    text += table(["Lead", "Company label", "Provider label", "State"], [[r["candidate_id"], r["candidate_company"], r["candidate_provider"], r["status"]] for r in candidates])
    text += "\n\n## Detailed provenance and gaps\n\nThe companion JSON retains every record's aliases, legal name field, evidence IDs/dates/statuses, dossier route, role status, missing evidence IDs, relationship edges and geographic context, official-domain provenance, research-date basis and individual gaps. Geography taxonomy and input file hashes are frozen with the inventory. No aggregate capability score exists.\n"
    write_text(DOCS / "commercial-entity-inventory.md", text)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["inventory", "prompts"])
    parser.add_argument("--replace-draft", action="store_true", help="Explicitly regenerate a draft inventory BEFORE handing it off; never use for returned research")
    args = parser.parse_args()
    if args.stage == "inventory":
        inventory = build_inventory(replace_draft=args.replace_draft)
        print(json.dumps(inventory["counts"], indent=2))
    else:
        from competitive_landscape_prompt_contract import build_pack
        build_pack(read(SNAPSHOT / "commercial-entity-inventory.json"), ROOT, SNAPSHOT, DOCS)


if __name__ == "__main__":
    main()
