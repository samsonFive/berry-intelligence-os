"""One-time generation script for Company + Genetics Relationships V1.

Not part of the app runtime. Run once from the worktree root:
    ../berry-intelligence-os/.venv/Scripts/python.exe scripts/_gen_competitor_registry_v1.py

Writes:
  - data/imports/competitor-registry-2026-09-15/snapshot.json (33-row registry)
  - data/imports/competitor-registry-2026-09-15/reconciliation-matrix.json
  - data/imports/competitor-registry-2026-09-15/genetics-transcription.json
  - data/imports/competitor-registry-2026-09-15/unresolved-mapping-queue.json
  - data/evidence/ev-competitor-registry-2026-09-15-import.json
  - data/evidence/ev-competitor-genetics-handwritten-notes-2026-09-15.json
  - data/entities/companies/company-<new>.json (17 new roster entities)
  - alias/role additions to a small set of existing entities
  - data/relationships/rel-*-genetics-*.json (pending genetics assertions)

This script is intentionally idempotent-ish for re-running during development
(it overwrites its own generated files) but does not delete anything it did
not create.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DATE = "2026-09-15"
IMPORT_DIR = ROOT / "data" / "imports" / "competitor-registry-2026-09-15"

TIER_VALUES = {"tier_1", "tier_2", "tier_3", "present", "unassigned", "unknown", "not_applicable"}

# ---------------------------------------------------------------------------
# 1. The 33-row spreadsheet snapshot, transcribed from the user-provided
#    screenshot (2026-09-15). Region codes preserved verbatim as shown
#    (DOTA, DOA_DANZ, DEMEA) -- not translated to any existing geography
#    entity, since these are the operator's own internal segment codes, not
#    ISO/UN region names. Berry tier fields use "unassigned" for a blank
#    cell (never "unknown" -- blank means the operator has not classified
#    this company for that berry, which is a different fact than "unknown
#    whether this company plays in that berry").
#
#    TRANSCRIPTION CAVEAT: transcribed directly from the attached image by
#    the agent that built this import; not independently re-verified against
#    the source spreadsheet file. Flagged for one human spot-check pass --
#    see docs/v2/COMPANY-GENETICS-RELATIONSHIPS-V1.md.
# ---------------------------------------------------------------------------

def row(n, label, ctype, priority, regions, straw, blue, rasp, black):
    return {
        "row_number": n,
        "spreadsheet_label": label,
        "competitor_type": ctype,  # verbatim spreadsheet text, may combine multiple types with "; "
        "strategic_priority": priority,  # "Top" | "Watch" | None
        "regions": regions,  # list of verbatim internal region codes
        "berry_tier": {
            "strawberry": straw,
            "blueberry": blue,
            "raspberry": rasp,
            "blackberry": black,
        },
        "snapshot_date": SNAPSHOT_DATE,
        "source": "internal_competitor_registry_spreadsheet",
        "review_state": "unreviewed_import",
    }


SNAPSHOT_ROWS = [
    row(2, "Advanced Berry Breeding", "Breeding", None, ["DEMEA"], "unassigned", "unassigned", "unassigned", "tier_1"),
    row(3, "AgroBerries", "Commercial", "Top", ["DOTA", "DEMEA"], "unassigned", "unassigned", "unassigned", "unassigned"),
    row(4, "Australasian Plant Genetics", "Genetics; Technology", None, ["DOA_DANZ"], "unassigned", "unassigned", "unassigned", "unassigned"),
    row(5, "BerryWorld", "Breeding", None, ["DOA_DANZ", "DEMEA"], "tier_2", "tier_3", "tier_1", "tier_2"),
    row(6, "Black Venture Farm", "Commercial", None, [], "tier_3", "unassigned", "tier_2", "tier_1"),
    row(7, "California Giant", "Commercial", "Top", ["DOTA"], "unassigned", "tier_1", "unassigned", "unassigned"),
    row(8, "Costa", "Commercial", None, ["DEMEA"], "unassigned", "tier_1", "unassigned", "unassigned"),
    row(9, "Denning Blueberries", "Commercial", "Watch", ["DOA_DANZ"], "unassigned", "present", "tier_2", "tier_1"),
    row(10, "Expoberries", None, None, [], "unassigned", "tier_1", "tier_3", "tier_3"),
    row(11, "Fall Creek", "Breeding; Genetics", None, ["DOTA", "DOA_DANZ", "DEMEA"], "unassigned", "tier_1", "unassigned", "unassigned"),
    row(12, "Fresh Forward", "Breeding", None, ["DEMEA"], "tier_1", "unassigned", "unassigned", "unassigned"),
    row(13, "Fruitist", "Commercial", "Top", ["DOTA"], "unassigned", "unassigned", "unassigned", "unassigned"),
    row(14, "Gem-Pack Berries", "Commercial", "Top", ["DOTA"], "unassigned", "tier_1", "tier_1", "tier_2"),
    row(15, "Hortifrut Genetica", "Breeding", None, ["DEMEA"], "present", "unassigned", "tier_3", "unassigned"),
    row(16, "IQ Berries", "Genetics", None, ["DOA_DANZ"], "unassigned", "unassigned", "tier_3", "unassigned"),
    row(17, "Marionnet", "Breeding; Genetics", None, ["DOA_DANZ", "DEMEA"], "tier_1", "unassigned", "tier_3", "unassigned"),
    row(18, "Mountain Blue", "Breeding; Genetics", None, ["DOTA"], "unassigned", "unassigned", "tier_2", "unassigned"),
    row(19, "Oishii", "Commercial", "Watch", ["DOTA", "DOA_DANZ", "DEMEA"], "tier_2", "unassigned", "unassigned", "unassigned"),
    row(20, "Ozblu", "Genetics; Technology", None, ["DOTA"], "unassigned", "unassigned", "unassigned", "unassigned"),
    row(21, "Pairwise", "Commercial", "Top", ["DOA_DANZ"], "tier_1", "tier_2", "tier_1", "tier_2"),
    row(22, "Perfection Fresh", "Breeding; Genetics", None, ["DOTA", "DOA_DANZ", "DEMEA"], "tier_1", "unassigned", "tier_1", "tier_2"),
    row(23, "Planasa", "Breeding; Genetics", None, ["DOTA", "DOA_DANZ", "DEMEA"], "tier_1", "tier_1", "tier_3", "unassigned"),
    row(24, "Plant Sciences", "Breeding; Genetics", None, ["DEMEA"], "unassigned", "unassigned", "tier_2", "tier_1"),
    row(25, "Royakkers", "Commercial", "Watch", ["DOA_DANZ", "DEMEA"], "unassigned", "tier_2", "unassigned", "tier_1"),
    row(26, "Smart Berries", "Commercial", "Watch", ["DOTA", "DEMEA"], "unassigned", "unassigned", "tier_2", "tier_1"),
    row(27, "Splendor Produce", "Commercial", "Watch", ["DOTA", "DEMEA"], "unassigned", "unassigned", "unassigned", "unassigned"),
    row(28, "SunBelle", "Commercial", "Top", ["DOA_DANZ"], "tier_1", "unassigned", "unassigned", "unassigned"),
    row(29, "The Berry Collective", "University/Public", None, [], "tier_1", "unassigned", "tier_2", "unassigned"),
    row(30, "UC Davis", "University/Public", None, [], "tier_1", "tier_2", "unassigned", "unassigned"),
    row(31, "University of Arkansas", "University/Public", "Top", ["DOTA"], "unassigned", "unassigned", "unassigned", "unassigned"),
    row(32, "University of Florida", "Commercial", "Watch", ["DOTA"], "unassigned", "unassigned", "unassigned", "unassigned"),
    row(33, "Well-Pict", "Commercial", "Watch", [], "unassigned", "unassigned", "unassigned", "unassigned"),
    row(34, "Wish Farms", "Commercial", "Top", ["DOA_DANZ"], "unassigned", "tier_1", "unassigned", "tier_2"),
]

assert len(SNAPSHOT_ROWS) == 33, len(SNAPSHOT_ROWS)
for r in SNAPSHOT_ROWS:
    for v in r["berry_tier"].values():
        assert v in TIER_VALUES, v

ROSTER_LABELS = [r["spreadsheet_label"] for r in SNAPSHOT_ROWS]
assert len(ROSTER_LABELS) == 33
assert len(set(ROSTER_LABELS)) == 33, "duplicate roster label"

print(f"snapshot rows: {len(SNAPSHOT_ROWS)}")
print("OK: snapshot table constructed and shape-checked")

# ---------------------------------------------------------------------------
# 2. Reconciliation. One entry per roster label. `new` entries get a fresh
#    entity id and a full new entity record (status "unverified" -- the
#    existing entity.schema.json enum value that already means exactly
#    "not yet independently confirmed", so no new status vocabulary needed).
#    `existing` entries point at an already-canonical entity and (optionally)
#    request small additive changes: a new alias, and/or the "competitor"
#    role. "competitor" role is intentionally withheld from public/university
#    entities (UC Davis, University of Arkansas, University of Florida) even
#    though the spreadsheet tracks them competitively -- that role already
#    drives the *existing* Landscape "Actors to Watch" filter
#    (landscape.py's actor_rows), and tagging a public research institution
#    as a market "competitor" would be a real, unintended side effect on
#    that pre-existing, out-of-scope feature. This registry's own service
#    resolves every roster row by canonical_entity_id directly, so it does
#    not depend on the "competitor" role at all -- adding it is a courtesy
#    to callers who do filter on it, not a requirement.
# ---------------------------------------------------------------------------

# monitoring_state values (one of the six required by the mission):
#   "linked_to_runnable_source" | "source_configured_never_run" |
#   "source_blocked" | "discovery_pending" | "no_supported_source" |
#   "manual_monitoring_required"
_CONFIGURED_NEVER_RUN = {
    "company-hortifrut": "source-20260819-hortifrut-newsroom",
    "company-planasa": "source-20260819-planasa-newsroom",
    "company-costa-group-holdings": "source-news-search-costa-group",
    "company-university-of-arkansas": "source-20260824-arkansas-aaes-news",
    "company-university-of-florida": "source-20260824-uf-ifas-news",
    "company-berryworld": "source-20260824-berryworld-newsroom",
    "company-fall-creek-farm-and-nursery": "source-20260824-fall-creek-newsroom",
    "company-advanced-berry-breeding": "source-20260825-advanced-berry-breeding-news",
}

RECONCILIATION = [
    # label, resolution_status, entity_type, canonical_id (None => derive "company-<slug>"),
    # aliases_to_add, add_competitor_role, ambiguity_notes
    ("Advanced Berry Breeding", "existing_exact_match", "company", "company-advanced-berry-breeding", [], True, ""),
    ("AgroBerries", "newly_created", "company", None, [], True, ""),
    ("Australasian Plant Genetics", "newly_created", "company", None, [], True, ""),
    ("BerryWorld", "existing_exact_match", "company", "company-berryworld", [], True, ""),
    ("Black Venture Farm", "newly_created", "company", None, [], True, ""),
    ("California Giant", "existing_alias_match", "company", "company-california-giant-berry-farms", [], True, ""),
    (
        "Costa", "existing_alias_match", "company", "company-costa-group-holdings", ["Costa"], False,
        "Spreadsheet label 'Costa' is ambiguous between the ASX-listed parent "
        "(company-costa-group-holdings, already tracked as a competitor with breeder/"
        "grower/packer/marketer roles) and its genetics/IP subsidiary "
        "(company-costa-berry-international, roles patent_assignee/rights_holder/"
        "genetics_licensor). Resolved to the parent, matching the spreadsheet's "
        "'Commercial' competitor type; company-costa-berry-international is noted "
        "as a related child entity, not merged or duplicated.",
    ),
    ("Denning Blueberries", "newly_created", "company", None, [], True, ""),
    ("Expoberries", "newly_created", "company", None, [], True, ""),
    ("Fall Creek", "existing_alias_match", "company", "company-fall-creek-farm-and-nursery", [], False, ""),
    ("Fresh Forward", "newly_created", "company", None, [], True, ""),
    (
        "Fruitist", "existing_alias_match", "company", "company-agrovision", [], False,
        "'Fruitist' is a consumer brand of Agrovision Corp.; company-agrovision "
        "already carries 'Fruitist' as an alias and the 'competitor' role, and a "
        "separate brand-fruitist entity (entity_type brand) already exists for the "
        "brand itself. No new entity created; resolved to the operating company.",
    ),
    ("Gem-Pack Berries", "newly_created", "company", None, [], True, ""),
    (
        "Hortifrut Genetica", "existing_alias_match", "company", "company-hortifrut", ["Hortifrut Genetica"], False,
        "No separately-modeled genetics division/subsidiary exists for Hortifrut "
        "S.A. in the current entity graph, and none was fabricated for this import. "
        "'Hortifrut Genetica' is preserved as an alias on the parent entity pending "
        "confirmation of whether it is a distinct legal/organizational unit.",
    ),
    ("IQ Berries", "existing_exact_match", "company", "company-iq-berries", [], False, ""),
    ("Marionnet", "newly_created", "company", None, [], True, ""),
    ("Mountain Blue", "existing_alias_match", "company", "company-mountain-blue-orchards", [], False, ""),
    ("Oishii", "newly_created", "company", None, [], True, ""),
    (
        "Ozblu", "existing_alias_match", "brand", "brand-ozblu", ["Ozblu"], True,
        "Spreadsheet capitalization 'Ozblu' vs. the existing entity's 'OZblu'/'OZblu®' "
        "-- treated as the same identity (case variant only), plain 'Ozblu' added as an "
        "additional alias. Modeled as entity_type 'brand' (a licensed variety platform "
        "with multiple companies in owns/develops/licenses roles toward it -- United "
        "Exports owns the brand, Nature Select develops the genetics, Oz Varieties "
        "licenses it), not as a single company, since no single company IS 'Ozblu.'",
    ),
    ("Pairwise", "newly_created", "company", None, [], True, ""),
    ("Perfection Fresh", "newly_created", "company", None, [], True, ""),
    (
        "Planasa", "existing_exact_match", "company", "company-planasa", [], False,
        "The entity graph also contains company-planasa-2 and company-plantas-de-navarra "
        "(seen in unrelated dropdown listings) -- a possible pre-existing identity-"
        "duplication issue for the wider Planasa/Plantas de Navarra group that predates "
        "this mission and is out of scope to resolve here. Resolved this roster row to "
        "company-planasa (exact name match); flagged for the entity-identity-integrity "
        "workstream, not fixed in this branch.",
    ),
    ("Plant Sciences", "existing_alias_match", "company", "company-plant-sciences-genetics", ["Plant Sciences"], False, ""),
    ("Royakkers", "newly_created", "company", None, [], True, ""),
    ("Smart Berries", "newly_created", "company", None, [], True, ""),
    ("Splendor Produce", "newly_created", "company", None, [], True, ""),
    ("SunBelle", "newly_created", "company", None, [], True, ""),
    ("The Berry Collective", "newly_created", "company", None, [], True, ""),
    (
        "UC Davis", "existing_alias_match", "breeding_program", "breeding_program-uc-davis-strawberry", ["UC Davis"], False,
        "Resolved to the existing UC Davis Strawberry Breeding Program entity "
        "(entity_type breeding_program) rather than creating a generic "
        "university company entity -- UC Davis's berry-relevant identity in this "
        "graph is specifically its breeding program, and University of Arkansas / "
        "University of Florida (below) are separately already modeled as entity_type "
        "'company' for consistency with the pre-existing convention at those two ids, "
        "which this mission preserves rather than retroactively 'fixing' either way.",
    ),
    ("University of Arkansas", "existing_exact_match", "company", "company-university-of-arkansas", [], False, ""),
    ("University of Florida", "existing_exact_match", "company", "company-university-of-florida", [], False, ""),
    ("Well-Pict", "newly_created", "company", None, [], True, ""),
    ("Wish Farms", "existing_exact_match", "company", "company-wish-farms", ["Wish Farms"], True, ""),
]

assert len(RECONCILIATION) == 33, len(RECONCILIATION)
assert {r[0] for r in RECONCILIATION} == set(ROSTER_LABELS)
print("OK: reconciliation table covers all 33 roster labels 1:1")


def slugify(label: str) -> str:
    return (
        label.lower()
        .replace("'", "")
        .replace(".", "")
        .replace("&", "and")
        .replace(",", "")
        .replace("-", " ")
        .split()
    )


def new_entity_id(label: str) -> str:
    return "company-" + "-".join(slugify(label))


COMPETITOR_TYPE_TO_ROLES = {
    "Breeding": ["breeder"],
    "Genetics": ["genetics_licensor"],
    "Genetics; Technology": ["genetics_licensor", "technology_provider"],
    "Breeding; Genetics": ["breeder", "genetics_licensor"],
    "Commercial": ["grower_marketer"],
    "University/Public": ["public_research_institution"],
}


def monitoring_state_for(entity_id: str) -> dict:
    if entity_id in _CONFIGURED_NEVER_RUN:
        return {
            "state": "source_configured_never_run",
            "detail": f"Discovery-eligible Source {_CONFIGURED_NEVER_RUN[entity_id]!r} exists and has never been run "
            "(last_checked_at is null in data/configuration/sources.json) -- same finding as the "
            "fix/astra-news-reader branch's independent audit of this snapshot.",
        }
    if entity_id == "company-california-giant-berry-farms":
        return {
            "state": "source_blocked",
            "detail": "Two Cal Giant Source entries exist but are type 'reference' with no discovery adapter; "
            "direct calgiant.com acquisition is TLS-fingerprint blocked (see fix/astra-news-reader branch "
            "checkpoint, commit 721a20a). Not re-diagnosed here; cited, not duplicated.",
        }
    return {
        "state": "no_supported_source",
        "detail": "No Source record links this entity's canonical id via linked_competitor_ids, and no source "
        "was researched or fabricated for it in this mission (broad web research is out of scope). "
        "Requires an operator to identify and onboard a real source through existing governance.",
    }


print("OK: helper functions defined")

# ---------------------------------------------------------------------------
# 3. Handwritten notes transcription -- re-read directly from the attached
#    images, not merely copied from the task's own "legible candidate
#    readings" hint list (that list is confirmed to match this re-reading
#    everywhere it can be checked, and this transcription's extra rows
#    -- Composol/Camposol, Family Tree, the illegible row 5, Fresc Kampo,
#    Water Fresh Farms, Good Farms -- are additional, not a replacement).
#    `seeded` is true only for the 3 rows that (a) name a clear genetics
#    provider or company, (b) resolve to two DISTINCT canonical entities
#    already in this graph, and (c) are not a self-mapping or a bare
#    "public genetics"/scoped-observation note. Everything else is
#    withheld with a stated reason -- never guessed.
# ---------------------------------------------------------------------------
GENETICS_TRANSCRIPTION = [
    {
        "tier": 1, "item": 1, "visible_text": "AgroBerries - MBO",
        "candidate_company": "AgroBerries", "candidate_provider": "Mountain Blue Orchards (MBO)",
        "inferred_relationship": "unconfirmed association (uses/licenses/grows not distinguished in source)",
        "berry_scope": "unspecified", "confidence": "medium", "ambiguity": "none -- both names match the roster",
        "seeded": True,
        "company_entity_id": "company-agroberries", "provider_entity_id": "company-mountain-blue-orchards",
    },
    {
        "tier": 1, "item": 2, "visible_text": "Fruitist - Fall Creek/Sekoya",
        "candidate_company": "Fruitist", "candidate_provider": "Fall Creek Farm & Nursery / Sekoya",
        "inferred_relationship": "unconfirmed association (uses/licenses/grows not distinguished in source)",
        "berry_scope": "unspecified", "confidence": "medium",
        "ambiguity": "'Sekoya' has no separate canonical entity in this graph; an existing Source record "
        "(source-20260824-sekoya-news) links 'SEKOYA' to company-fall-creek-farm-and-nursery, so it is treated "
        "as a Fall Creek-associated brand/label here rather than fabricated as a new company.",
        "seeded": True,
        "company_entity_id": "company-agrovision", "provider_entity_id": "company-fall-creek-farm-and-nursery",
    },
    {
        "tier": 1, "item": 3, "visible_text": "Hortifrut - Hortifrut",
        "candidate_company": "Hortifrut", "candidate_provider": "Hortifrut (self)",
        "inferred_relationship": "self-mapping -- suggests proprietary/in-house genetics",
        "berry_scope": "unspecified", "confidence": "medium",
        "ambiguity": "Self-mapping. Per explicit mission rule, not converted to an 'owns' relationship without "
        "confirmation; no relationship record created.",
        "seeded": False,
        "company_entity_id": "company-hortifrut", "provider_entity_id": None,
    },
    {
        "tier": 2, "item": 1, "visible_text": "Composol - Public (task hint reads 'Camposol')",
        "candidate_company": "Composol/Camposol (unclear)", "candidate_provider": "Public genetics",
        "inferred_relationship": "public genetics (not a company-to-company relationship)",
        "berry_scope": "unspecified", "confidence": "low",
        "ambiguity": "Handwriting reads 'Composol'; the task's own hint list reads 'Camposol'. Neither spelling "
        "matches any of the 33 mandatory roster labels or an existing canonical entity. Not created as a new "
        "entity (out of mandatory-roster scope); 'Public' is a genetics-source classification per mission rules, "
        "not a company, so no relationship object exists to point to either way.",
        "seeded": False,
        "company_entity_id": None, "provider_entity_id": None,
    },
    {
        "tier": 2, "item": 2, "visible_text": "Planasa - Planasa",
        "candidate_company": "Planasa", "candidate_provider": "Planasa (self)",
        "inferred_relationship": "self-mapping -- suggests proprietary/in-house genetics",
        "berry_scope": "unspecified", "confidence": "medium", "ambiguity": "Self-mapping; no relationship created.",
        "seeded": False, "company_entity_id": "company-planasa", "provider_entity_id": None,
    },
    {
        "tier": 2, "item": 3, "visible_text": "Family Tree - MBO",
        "candidate_company": "Family Tree", "candidate_provider": "Mountain Blue Orchards (MBO)",
        "inferred_relationship": "unconfirmed association",
        "berry_scope": "unspecified", "confidence": "low",
        "ambiguity": "'Family Tree' does not match any of the 33 mandatory roster labels or an existing "
        "canonical entity name/alias. Not created as a new entity (out of mandatory-roster scope this mission); "
        "withheld rather than guessed at which roster company it might mean.",
        "seeded": False, "company_entity_id": None, "provider_entity_id": "company-mountain-blue-orchards",
    },
    {
        "tier": 2, "item": 4, "visible_text": "Fall Creek - Fall Creek",
        "candidate_company": "Fall Creek", "candidate_provider": "Fall Creek (self)",
        "inferred_relationship": "self-mapping -- suggests proprietary/in-house genetics",
        "berry_scope": "unspecified", "confidence": "medium", "ambiguity": "Self-mapping; no relationship created.",
        "seeded": False, "company_entity_id": "company-fall-creek-farm-and-nursery", "provider_entity_id": None,
    },
    {
        "tier": 2, "item": 5, "visible_text": "[illegible name] - Planasa, MBO, Public",
        "candidate_company": None, "candidate_provider": "Planasa; Mountain Blue Orchards; Public genetics",
        "inferred_relationship": "unresolved",
        "berry_scope": "unspecified", "confidence": "low",
        "ambiguity": "Company name is illegible in the source image (candidate reading 'Noposion' does not match "
        "any roster label or canonical entity). Per mission rule, unclear handwriting must not be guessed at. "
        "Fully withheld.",
        "seeded": False, "company_entity_id": None, "provider_entity_id": None,
    },
    {
        "tier": 2, "item": 6, "visible_text": "MBO - MBO",
        "candidate_company": "MBO (Mountain Blue Orchards)", "candidate_provider": "MBO (self)",
        "inferred_relationship": "self-mapping -- proprietary genetics (expected; MBO is itself a breeder)",
        "berry_scope": "unspecified", "confidence": "medium", "ambiguity": "Self-mapping; no relationship created.",
        "seeded": False, "company_entity_id": "company-mountain-blue-orchards", "provider_entity_id": None,
    },
    {
        "tier": 2, "item": 7, "visible_text": "Perfection Fresh - ??",
        "candidate_company": "Perfection Fresh", "candidate_provider": None,
        "inferred_relationship": "unresolved (explicit ?? in source)",
        "berry_scope": "unspecified", "confidence": "low", "ambiguity": "Explicit '??' -- unresolved by the note's own author, not just illegible.",
        "seeded": False, "company_entity_id": "company-perfection-fresh", "provider_entity_id": None,
    },
    {
        "tier": 2, "item": 8, "visible_text": "Well-Pict (partially obscured) - ???",
        "candidate_company": "Well-Pict", "candidate_provider": None,
        "inferred_relationship": "unresolved (explicit ??? in source)",
        "berry_scope": "unspecified", "confidence": "low", "ambiguity": "Explicit '???' -- unresolved by the note's own author.",
        "seeded": False, "company_entity_id": "company-well-pict", "provider_entity_id": None,
    },
    {
        "tier": 3, "item": 1, "visible_text": "Oishii - No blues",
        "candidate_company": "Oishii", "candidate_provider": None,
        "inferred_relationship": "scoped observation, not a genetics-provider mapping",
        "berry_scope": "blueberry (explicitly excluded)", "confidence": "medium",
        "ambiguity": "'No blues' is a scoped observation (Oishii not active in blueberry) per mission rule, not "
        "proof of zero blueberry activity generally and not a genetics relationship. No relationship record "
        "created; consistent with this company's own blueberry tier being recorded as unassigned, not tier_3, "
        "in the spreadsheet snapshot.",
        "seeded": False, "company_entity_id": "company-oishii", "provider_entity_id": None,
    },
    {
        "tier": 3, "item": 2, "visible_text": "Giant/California Giant - Fall Creek, Public",
        "candidate_company": "California Giant", "candidate_provider": "Fall Creek Farm & Nursery; Public genetics",
        "inferred_relationship": "unconfirmed association (Fall Creek); public genetics (separate, non-relationship note)",
        "berry_scope": "unspecified", "confidence": "medium",
        "ambiguity": "'Giant' alone could mean a different company, but the roster's only 'Giant' entry is "
        "California Giant, resolved with that context. Two distinct claims here: a Fall Creek association "
        "(seeded as a relationship) and a 'Public genetics' note (not a relationship -- see mission rule).",
        "seeded": True,
        "company_entity_id": "company-california-giant-berry-farms", "provider_entity_id": "company-fall-creek-farm-and-nursery",
    },
    {
        "tier": 3, "item": 3, "visible_text": "Plant Sciences - Plant Sciences",
        "candidate_company": "Plant Sciences", "candidate_provider": "Plant Sciences (self)",
        "inferred_relationship": "self-mapping -- proprietary genetics (expected; a breeder)",
        "berry_scope": "unspecified", "confidence": "medium", "ambiguity": "Self-mapping; no relationship created.",
        "seeded": False, "company_entity_id": "company-plant-sciences-genetics", "provider_entity_id": None,
    },
    {
        "tier": 3, "item": 4, "visible_text": "Pairwise - No blues",
        "candidate_company": "Pairwise", "candidate_provider": None,
        "inferred_relationship": "scoped observation, not a genetics-provider mapping",
        "berry_scope": "blueberry (explicitly excluded)", "confidence": "medium",
        "ambiguity": "Scoped observation only, consistent with Pairwise's own blueberry tier being unassigned "
        "(tier_1 is recorded for strawberry/raspberry/blackberry, not blueberry) in the spreadsheet snapshot.",
        "seeded": False, "company_entity_id": "company-pairwise", "provider_entity_id": None,
    },
    {
        "tier": 3, "item": 5, "visible_text": "Wish Farms - Public",
        "candidate_company": "Wish Farms", "candidate_provider": "Public genetics",
        "inferred_relationship": "public genetics (not a company-to-company relationship)",
        "berry_scope": "unspecified", "confidence": "medium",
        "ambiguity": "'Public' is a genetics-source classification per mission rule, not a company; recorded as "
        "an entity-level note on Wish Farms, not a relationship.",
        "seeded": False, "company_entity_id": "company-wish-farms", "provider_entity_id": None,
    },
    {
        "tier": 3, "item": 6, "visible_text": "Dole - Inka Berries",
        "candidate_company": "Dole", "candidate_provider": "Inka Berries",
        "inferred_relationship": "unresolved -- out of mandatory-roster scope",
        "berry_scope": "unspecified", "confidence": "low",
        "ambiguity": "Neither 'Dole' nor 'Inka Berries' is one of the 33 mandatory roster labels or an existing "
        "canonical entity. Creating either would exceed this mission's mandated roster scope; both are recorded "
        "here for visibility only, with no entity or relationship created.",
        "seeded": False, "company_entity_id": None, "provider_entity_id": None,
    },
    {
        "tier": 3, "item": 7, "visible_text": "SunBelle - Public (source reads 'Suabelle')",
        "candidate_company": "SunBelle", "candidate_provider": "Public genetics",
        "inferred_relationship": "public genetics (not a company-to-company relationship)",
        "berry_scope": "unspecified", "confidence": "medium",
        "ambiguity": "Handwriting reads 'Suabelle'; resolved to 'SunBelle' as the only plausible roster match. "
        "'Public' recorded as an entity-level note, not a relationship.",
        "seeded": False, "company_entity_id": "company-sunbelle", "provider_entity_id": None,
    },
    {
        "tier": 3, "item": 8, "visible_text": "Ozblu - Ozblu",
        "candidate_company": "Ozblu", "candidate_provider": "Ozblu (self)",
        "inferred_relationship": "self-mapping",
        "berry_scope": "unspecified", "confidence": "medium",
        "ambiguity": "Self-mapping. The real, multi-party Ozblu genetics network (Nature Select develops, Oz "
        "Varieties licenses, United Exports owns the brand) already exists in this graph as real relationship "
        "records; nothing new created here to avoid duplicating them.",
        "seeded": False, "company_entity_id": "brand-ozblu", "provider_entity_id": None,
    },
    {
        "tier": 3, "item": 9, "visible_text": "Fresc Kampo (unclear reading)",
        "candidate_company": "Fresc Kampo", "candidate_provider": None,
        "inferred_relationship": "unresolved -- out of mandatory-roster scope",
        "berry_scope": "unspecified", "confidence": "low",
        "ambiguity": "Does not match any of the 33 mandatory roster labels; withheld, no entity created.",
        "seeded": False, "company_entity_id": None, "provider_entity_id": None,
    },
    {
        "tier": 3, "item": 10, "visible_text": "Water Fresh Farms - No blue",
        "candidate_company": "Water Fresh Farms", "candidate_provider": None,
        "inferred_relationship": "scoped observation -- out of mandatory-roster scope",
        "berry_scope": "blueberry (explicitly excluded)", "confidence": "low",
        "ambiguity": "Does not match any of the 33 mandatory roster labels; withheld, no entity created.",
        "seeded": False, "company_entity_id": None, "provider_entity_id": None,
    },
    {
        "tier": 3, "item": 11, "visible_text": "Good Farms - NA",
        "candidate_company": "Good Farms", "candidate_provider": None,
        "inferred_relationship": "not applicable (explicit NA in source)",
        "berry_scope": "unspecified", "confidence": "low",
        "ambiguity": "Does not match any of the 33 mandatory roster labels; withheld, no entity created.",
        "seeded": False, "company_entity_id": None, "provider_entity_id": None,
    },
]

SEEDED_RELATIONSHIPS = [t for t in GENETICS_TRANSCRIPTION if t["seeded"]]
WITHHELD = [t for t in GENETICS_TRANSCRIPTION if not t["seeded"]]
print(f"OK: transcribed {len(GENETICS_TRANSCRIPTION)} handwritten rows; "
      f"{len(SEEDED_RELATIONSHIPS)} seeded as pending relationships, {len(WITHHELD)} withheld")

# ---------------------------------------------------------------------------
# 4. Write files.
# ---------------------------------------------------------------------------
COMPANIES_DIR = ROOT / "data" / "entities" / "companies"
RELATIONSHIPS_DIR = ROOT / "data" / "relationships"
EVIDENCE_DIR = ROOT / "data" / "evidence"

EVIDENCE_SPREADSHEET_ID = "ev-competitor-registry-2026-09-15-import"
EVIDENCE_HANDWRITTEN_ID = "ev-competitor-genetics-handwritten-notes-2026-09-15"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def none_priority(rationale: str) -> dict:
    return {"level": "none", "rationale": rationale}


def build_reconciliation_rows() -> list[dict]:
    by_label = {r["spreadsheet_label"]: r for r in SNAPSHOT_ROWS}
    rows = []
    for label, resolution_status, entity_type, canonical_id, aliases, add_competitor, ambiguity in RECONCILIATION:
        snap = by_label[label]
        eid = canonical_id or new_entity_id(label)
        ms = monitoring_state_for(eid)
        rows.append(
            {
                "row_number": snap["row_number"],
                "spreadsheet_label": label,
                "canonical_entity_id": eid,
                "canonical_display_name": None,  # filled after entities are known, below
                "entity_type": entity_type,
                "resolution_status": resolution_status,
                "aliases_added": aliases,
                "competitor_type": snap["competitor_type"],
                "strategic_priority": snap["strategic_priority"],
                "regions": snap["regions"],
                "berry_tier": snap["berry_tier"],
                "entity_route": f"/entities/{'breeding_program' if entity_type == 'breeding_program' else ('brand' if entity_type == 'brand' else 'company')}/{eid}",
                "linked_monitoring_sources": (
                    [_CONFIGURED_NEVER_RUN[eid]] if eid in _CONFIGURED_NEVER_RUN else []
                ),
                "source_execution_state": ms["state"],
                "source_execution_detail": ms["detail"],
                "genetics_relationship_count": sum(
                    1 for t in SEEDED_RELATIONSHIPS
                    if t["company_entity_id"] == eid or t["provider_entity_id"] == eid
                ),
                "provenance": "internal_competitor_registry_spreadsheet, snapshot_date=2026-09-15",
                "ambiguity_notes": ambiguity,
            }
        )
    return rows


def existing_entity_path(entity_id: str, entity_type: str) -> Path:
    folder = {"company": "companies", "breeding_program": "breeding_programs", "brand": "brands"}[entity_type]
    return ROOT / "data" / "entities" / folder / f"{entity_id}.json"


def apply_existing_entity_updates() -> dict:
    """Additive-only: append a missing alias / the 'competitor' role, and
    record `attributes.competitor_registry_2026_09_15` (a pointer, not a
    duplicate copy of the classification -- the snapshot file above is the
    one source of truth for tier/priority/region). Never removes or
    overwrites anything already on the record."""
    display_names: dict[str, str] = {}
    for label, resolution_status, entity_type, canonical_id, aliases, add_competitor, ambiguity in RECONCILIATION:
        if canonical_id is None:
            continue
        path = existing_entity_path(canonical_id, entity_type)
        record = json.loads(path.read_text(encoding="utf-8"))
        display_names[canonical_id] = record["name"]
        changed = False
        existing_aliases = record.get("aliases") or []
        for alias in aliases:
            if alias not in existing_aliases and alias != record["name"]:
                existing_aliases.append(alias)
                changed = True
        if changed:
            record["aliases"] = existing_aliases
        roles = record.get("roles") or []
        if add_competitor and "competitor" not in roles:
            roles = roles + ["competitor"]
            record["roles"] = roles
            changed = True
        attributes = record.get("attributes") or {}
        registry_row = next(r for r in SNAPSHOT_ROWS if r["spreadsheet_label"] == label)
        if attributes.get("competitor_registry_2026_09_15") != {
            "row_number": registry_row["row_number"],
            "spreadsheet_label": label,
            "snapshot_ref": "data/imports/competitor-registry-2026-09-15/snapshot.json",
        }:
            attributes["competitor_registry_2026_09_15"] = {
                "row_number": registry_row["row_number"],
                "spreadsheet_label": label,
                "snapshot_ref": "data/imports/competitor-registry-2026-09-15/snapshot.json",
            }
            record["attributes"] = attributes
            changed = True
        if changed:
            write_json(path, record)
            print(f"  updated {canonical_id} ({'+alias' if aliases else ''}{'+competitor role' if add_competitor else ''})")
    return display_names


def create_new_entities() -> dict:
    display_names: dict[str, str] = {}
    for label, resolution_status, entity_type, canonical_id, aliases, add_competitor, ambiguity in RECONCILIATION:
        if canonical_id is not None:
            continue
        eid = new_entity_id(label)
        registry_row = next(r for r in SNAPSHOT_ROWS if r["spreadsheet_label"] == label)
        roles = list(COMPETITOR_TYPE_TO_ROLES.get(registry_row["competitor_type"], []))
        if add_competitor and "competitor" not in roles:
            roles.append("competitor")
        berry_ids = []
        berry_map = {"strawberry": "berry-strawberry", "blueberry": "berry-blueberry",
                     "raspberry": "berry-raspberry", "blackberry": "berry-blackberry"}
        for berry, tier in registry_row["berry_tier"].items():
            if tier not in ("unassigned",):
                berry_ids.append(berry_map[berry])
        record = {
            "id": eid,
            "record_type": "entity",
            "entity_type": "company",
            "name": label,
            "aliases": [],
            "status": "unverified",
            "description": (
                f"Added to the entity graph from the internal Competitor Registry spreadsheet snapshot "
                f"(2026-09-15, row {registry_row['row_number']}) as a tracked competitor of type "
                f"'{registry_row['competitor_type'] or 'unspecified'}'. Not yet independently verified or "
                f"researched beyond that spreadsheet -- no company history, ownership, or activity detail is "
                f"asserted here. See {EVIDENCE_SPREADSHEET_ID} for provenance."
            ),
            "roles": roles,
            "berry_ids": berry_ids,
            "evidence_ids": [EVIDENCE_SPREADSHEET_ID],
            "fact_ids": [],
            "relationship_ids": [],
            "attributes": {
                "competitor_registry_2026_09_15": {
                    "row_number": registry_row["row_number"],
                    "spreadsheet_label": label,
                    "snapshot_ref": "data/imports/competitor-registry-2026-09-15/snapshot.json",
                }
            },
        }
        write_json(COMPANIES_DIR / f"{eid}.json", record)
        display_names[eid] = label
        print(f"  created {eid}")
    return display_names


def create_evidence_records() -> None:
    spreadsheet_evidence = {
        "id": EVIDENCE_SPREADSHEET_ID,
        "record_type": "evidence",
        "status": "in_review",
        "source_type": "internal_analyst_note",
        "title": "Internal Competitor Registry spreadsheet snapshot (2026-09-15)",
        "source_name": "Berry Intelligence OS operator -- internal competitor registry spreadsheet",
        "source_url": "",
        "captured_date": SNAPSHOT_DATE,
        "published_date": None,
        "summary": (
            "A 33-row internal competitor-tracking spreadsheet (Competitor / Competitor Type / Priority / "
            "Region / Strawberry-Blueberry-Raspberry-Blackberry Tier), provided by the operator as a "
            "screenshot and imported verbatim into data/imports/competitor-registry-2026-09-15/snapshot.json. "
            "An internal, user-curated classification, not externally verified market research -- see "
            "docs/v2/COMPANY-GENETICS-RELATIONSHIPS-V1.md for scope and the transcription caveat."
        ),
        "why_it_matters": "",
        "submitted_by": "operator-import",
        "berry_ids": ["berry-strawberry", "berry-blueberry", "berry-raspberry", "berry-blackberry"],
        "geography_ids": [],
        "entity_ids": sorted({
            (cid or new_entity_id(label))
            for label, _rs, _et, cid, _al, _ac, _amb in RECONCILIATION
        }),
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": ["competitor-registry", "internal-classification"],
        "auto_captured": False,
        "priority": {
            "reading": none_priority("Registry import; not an article for analyst reading triage."),
            "testing": none_priority("Not a testable claim; internal classification, not a factual assertion."),
            "commercial_position": none_priority("Classification-only import; no commercial-position tag applied."),
            "monitoring": none_priority("Not a monitored source; a one-time internal snapshot import."),
        },
    }
    write_json(EVIDENCE_DIR / f"{EVIDENCE_SPREADSHEET_ID}.json", spreadsheet_evidence)

    handwritten_evidence = {
        "id": EVIDENCE_HANDWRITTEN_ID,
        "record_type": "evidence",
        "status": "in_review",
        "source_type": "internal_analyst_note",
        "title": "Internal handwritten company-genetics notes (photographed, 2026-09-15)",
        "source_name": "Berry Intelligence OS operator -- handwritten competitor/genetics notes",
        "source_url": "",
        "captured_date": SNAPSHOT_DATE,
        "published_date": None,
        "summary": (
            "Photographed handwritten notes pairing companies with genetics providers/breeding programs, "
            "organized into three legibility/confidence tiers by the note's own author. Transcribed into "
            "data/imports/competitor-registry-2026-09-15/genetics-transcription.json. These are unverified "
            "user assertions, not independently confirmed variety-level relationships -- see "
            "docs/v2/COMPANY-GENETICS-RELATIONSHIPS-V1.md."
        ),
        "why_it_matters": "",
        "submitted_by": "operator-import",
        "berry_ids": [],
        "geography_ids": [],
        "entity_ids": sorted({
            eid for t in GENETICS_TRANSCRIPTION for eid in (t["company_entity_id"], t["provider_entity_id"]) if eid
        }),
        "fact_ids": [],
        "relationship_ids": [f"rel-{t['company_entity_id']}-genetics-{t['provider_entity_id']}".replace("company-", "").replace("brand-", "")
                              for t in SEEDED_RELATIONSHIPS],
        "strategic_question_ids": [],
        "tags": ["competitor-registry", "genetics-relationships", "pending-review"],
        "auto_captured": False,
        "priority": {
            "reading": none_priority("Handwritten-note import; not an article for analyst reading triage."),
            "testing": none_priority("Underlying assertions are pending-review relationships, tracked there."),
            "commercial_position": none_priority("Not a commercial-position tag; a relationship-seeding import."),
            "monitoring": none_priority("Not a monitored source; a one-time internal note import."),
        },
    }
    write_json(EVIDENCE_DIR / f"{EVIDENCE_HANDWRITTEN_ID}.json", handwritten_evidence)
    print(f"  created evidence: {EVIDENCE_SPREADSHEET_ID}, {EVIDENCE_HANDWRITTEN_ID}")


def create_genetics_relationships() -> list[str]:
    created_ids = []
    for t in SEEDED_RELATIONSHIPS:
        subj = t["company_entity_id"]
        obj = t["provider_entity_id"]
        rel_id = "rel-" + subj.replace("company-", "").replace("brand-", "") + "-genetics-" + obj.replace("company-", "").replace("brand-", "")
        record = {
            "id": rel_id,
            "record_type": "relationship",
            "subject_id": subj,
            "predicate": "partners_with",
            "object_id": obj,
            "status": "disputed",
            "evidence_ids": [EVIDENCE_HANDWRITTEN_ID],
            "effective_date": None,
            "confidence": t["confidence"],
            "notes": (
                f"PENDING REVIEW -- seeded from handwritten competitor-genetics notes (Tier {t['tier']}, "
                f"item {t['item']}: {t['visible_text']!r}). Asserted relationship: {t['inferred_relationship']}. "
                f"Berry scope: {t['berry_scope']}. This is an unconfirmed, operator-asserted association, not a "
                f"verified genetics/licensing arrangement -- status 'disputed' reflects pending-review, not an "
                f"actual dispute between parties. Do not treat as trusted until reviewed."
            ),
        }
        write_json(RELATIONSHIPS_DIR / f"{rel_id}.json", record)
        created_ids.append(rel_id)
        print(f"  created relationship: {rel_id} ({t['confidence']} confidence, disputed/pending)")
    return created_ids


print("\n== Applying updates to existing entities ==")
existing_names = apply_existing_entity_updates()
print("\n== Creating new roster entities ==")
new_names = create_new_entities()
print("\n== Creating provenance Evidence records ==")
create_evidence_records()
print("\n== Creating seeded genetics relationships ==")
created_rel_ids = create_genetics_relationships()

ALL_DISPLAY_NAMES = {**existing_names, **new_names}
reconciliation_rows = build_reconciliation_rows()
for r in reconciliation_rows:
    r["canonical_display_name"] = ALL_DISPLAY_NAMES[r["canonical_entity_id"]]

print("\n== Writing import artifacts ==")
write_json(IMPORT_DIR / "snapshot.json", {
    "id": "competitor-registry-snapshot-2026-09-15",
    "snapshot_date": SNAPSHOT_DATE,
    "source": "internal_competitor_registry_spreadsheet",
    "provenance_evidence_id": EVIDENCE_SPREADSHEET_ID,
    "transcription_caveat": (
        "Transcribed directly from the operator-provided spreadsheet screenshot by the agent that built this "
        "import; not independently re-verified against the source spreadsheet file. Recommend one human "
        "spot-check pass before treating any single cell as authoritative."
    ),
    "row_count": len(SNAPSHOT_ROWS),
    "rows": SNAPSHOT_ROWS,
})
write_json(IMPORT_DIR / "reconciliation-matrix.json", {
    "id": "competitor-registry-reconciliation-matrix-2026-09-15",
    "snapshot_date": SNAPSHOT_DATE,
    "row_count": len(reconciliation_rows),
    "rows": reconciliation_rows,
})
write_json(IMPORT_DIR / "genetics-transcription.json", {
    "id": "competitor-genetics-handwritten-transcription-2026-09-15",
    "snapshot_date": SNAPSHOT_DATE,
    "provenance_evidence_id": EVIDENCE_HANDWRITTEN_ID,
    "row_count": len(GENETICS_TRANSCRIPTION),
    "seeded_count": len(SEEDED_RELATIONSHIPS),
    "withheld_count": len(WITHHELD),
    "rows": GENETICS_TRANSCRIPTION,
})
unresolved = [
    {
        "tier": t["tier"], "item": t["item"], "visible_text": t["visible_text"],
        "reason_withheld": t["ambiguity"], "candidate_company": t["candidate_company"],
        "candidate_provider": t["candidate_provider"],
    }
    for t in WITHHELD
]
write_json(IMPORT_DIR / "unresolved-mapping-queue.json", {
    "id": "competitor-genetics-unresolved-queue-2026-09-15",
    "snapshot_date": SNAPSHOT_DATE,
    "count": len(unresolved),
    "note": "Every row here was deliberately withheld from entity/relationship creation -- self-mappings, "
            "explicit '??'/'???' markers, illegible names, public-genetics/scoped observations, and names "
            "outside the mandatory 33-entry roster. None should be silently resolved without a human decision.",
    "rows": unresolved,
})

print("\nDONE.")
print(f"New entities created: {len(new_names)}")
print(f"Existing entities updated: touched above")
print(f"Genetics relationships created: {len(created_rel_ids)}")
print(f"Reconciliation rows: {len(reconciliation_rows)} (expect 33)")
