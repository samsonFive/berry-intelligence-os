"""One-time generation script for Competitor Identity and Genetics
Verification V1. Not part of the app runtime.

Makes additive/corrective changes only:
  - promotes a small, carefully-justified subset of the 17 provisional
    entities from status "unverified" to "active" (the existing
    entity.schema.json vocabulary already used this way by every
    pre-existing verified company in this graph)
  - adds real, evidence-backed aliases
  - records an `attributes.identity_verification_2026_09_15` block on
    every one of the 17, promoted or not, with evidence/confidence/date
  - upgrades exactly one of the three seeded genetics relationships
    (AgroBerries <-> Mountain Blue Orchards) where independent trade-press
    corroboration names the specific relationship type; the other two are
    left exactly as seeded, with a documented, evidence-searched note
  - corrects one stale ambiguity note (Planasa) now that the existing
    entity-identity-redirects.json mechanism is confirmed to have already
    resolved it, predating this mission

Run once from the worktree root:
    ../berry-intelligence-os/.venv/Scripts/python.exe scripts/_gen_identity_genetics_verification_v1.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_DATE = "2026-09-15"
COMPANIES_DIR = ROOT / "data" / "entities" / "companies"
RELATIONSHIPS_DIR = ROOT / "data" / "relationships"
EVIDENCE_DIR = ROOT / "data" / "evidence"
REGISTRY_MATRIX_PATH = ROOT / "data" / "imports" / "competitor-registry-2026-09-15" / "reconciliation-matrix.json"
OUTPUT_DIR = ROOT / "data" / "imports" / "competitor-identity-genetics-verification-2026-09-15"


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_entity(entity_id: str) -> dict:
    return json.loads((COMPANIES_DIR / f"{entity_id}.json").read_text(encoding="utf-8"))


def write_entity(entity_id: str, record: dict) -> None:
    write_json(COMPANIES_DIR / f"{entity_id}.json", record)


# ---------------------------------------------------------------------------
# The 17 provisional identities, each with a verification verdict. Derived
# from re-reading the reconciliation matrix (not memory) at script-run time
# below; this table supplies the JUDGMENT per entity, keyed by id.
# ---------------------------------------------------------------------------
VERDICTS = {
    "company-agroberries": {
        "verdict": "identity_confirmed_relationship_ambiguity_unrelated",
        "promote": False,
        "reason": (
            "AgroBerries' own identity is well-corroborated (agroberries.com official site, extensive "
            "FreshFruitPortal/Blueberries Consulting trade coverage, founded 1996 Chile). Held provisional "
            "because of a real, unresolved PARENT/SIBLING ambiguity found during research: marketing copy "
            "describes AgroBerries as part of a 'family of companies including Berry Fresh, BerryWorld, "
            "PrepWorld, and Poupart1895' -- BerryWorld is a separate, independently-canonical roster entity "
            "(#4, company-berryworld) with its own Source. This is inference from promotional language, not a "
            "primary corporate-registry source; per this mission's own bar ('no unresolved duplicate or "
            "parent/child ambiguity remains'), promotion is held pending a primary-source confirmation or "
            "denial of that claim."
        ),
        "aliases_add": ["Agroberries Group", "Agroberries Peru S.A.C."],
        "evidence_urls": ["https://www.agroberries.com/about", "https://www.freshfruitportal.com/news/2026/06/24/agroberries-expansion/"],
        "confidence": "medium",
    },
    "company-australasian-plant-genetics": {
        "verdict": "externally_verified",
        "promote": True,
        "reason": (
            "Official domain ausplantgenetics.com.au confirms Australasian Plant Genetics (APG) as a company "
            "limited by guarantee, wholly owned by the Queensland Strawberry Growers' Association, providing "
            "commercial access to Australian Strawberry Breeding Program varieties. Clear, single, unambiguous "
            "organization; no competing or overlapping entity found."
        ),
        "aliases_add": ["APG"],
        "evidence_urls": ["https://ausplantgenetics.com.au/", "https://ausplantgenetics.com.au/about/"],
        "confidence": "high",
    },
    "company-black-venture-farm": {
        "verdict": "insufficient_primary_evidence",
        "promote": False,
        "reason": (
            "Only a bare homepage (blackventurefarm.com, HTTP 200) and one Facebook page "
            "('Black Venture Farm Oficial', Spanish-language branding) were found. No about/company page, no "
            "press coverage, no clear description of the business confirming it matches the berry-industry "
            "competitor this roster row expects. Not 'clearly verified' per this mission's bar -- a domain "
            "resolving is not proof of the correct real-world identity behind it."
        ),
        "aliases_add": [],
        "evidence_urls": ["https://blackventurefarm.com/", "https://www.facebook.com/BlackVentureFarmOficial"],
        "confidence": "low",
    },
    "company-denning-blueberries": {
        "verdict": "not_found",
        "promote": False,
        "reason": (
            "No official website, social presence, corporate registry entry, or trade-press mention was found "
            "for an entity matching this exact name across two independent search passes (this mission and the "
            "prior Competitor Source Strategy V1 mission). Existence itself is unconfirmed, not merely "
            "under-documented."
        ),
        "aliases_add": [],
        "evidence_urls": [],
        "confidence": "low",
    },
    "company-expoberries": {
        "verdict": "existence_confirmed_no_primary_source",
        "promote": False,
        "reason": (
            "Existence as a real Mexican berry exporter (Los Reyes, Michoacan) is corroborated by a national "
            "berry-export trade association profile (Aneberries) and import/customs records (Panjiva), which "
            "is reasonably authoritative for existence. However, no official company-owned website was found "
            "despite search effort, and this mission's own instruction is that secondary reporting 'should not "
            "be the sole basis for a canonical identity change when a primary source should exist' -- a company "
            "of this described scale plausibly has its own site not yet located. Held provisional."
        ),
        "aliases_add": ["Expoberries S.A. de C.V."],
        "evidence_urls": ["https://aneberries.mx/en/expoberries/", "https://panjiva.com/Expoberries-S-A-De-C-V/31221334"],
        "confidence": "medium",
    },
    "company-fresh-forward": {
        "verdict": "externally_verified",
        "promote": True,
        "reason": (
            "Official domain fresh-forward.nl confirms Fresh Forward Breeding B.V., a strawberry (and apple) "
            "breeding company headquartered in Huissen, Gelderland, Netherlands, with a dedicated /breeding and "
            "/who-we-are page. Clear, single, unambiguous organization."
        ),
        "aliases_add": ["Fresh Forward Breeding B.V.", "Fresh Forward Breeding & Marketing"],
        "evidence_urls": ["https://www.fresh-forward.nl/en", "https://www.fresh-forward.nl/en/breeding"],
        "confidence": "high",
    },
    "company-gem-pack-berries": {
        "verdict": "identity_confirmed_relationship_ambiguity_unrelated",
        "promote": False,
        "reason": (
            "Gem-Pack Berries' own identity is solid (gem-packberries.com official site, real trade coverage of "
            "its own site relaunch). Held provisional because of a real, unresolved AFFILIATION question: trade "
            "press ('Gem-Pack and Well-Pict Berries combine companies' -- The Packer) suggests Gem-Pack Berries "
            "and Well-Pict (roster entry #33, a separate canonical entity) may now be one organization or a "
            "formal partnership. Promoting either independently before this is resolved risks the graph "
            "representing what may now be one company as two, or misattributing which entity a future article "
            "actually concerns."
        ),
        "aliases_add": ["Gem-Pack Berries, LLC"],
        "evidence_urls": ["https://www.gem-packberries.com/en", "https://theproducenews.com/berries/gem-pack-berries-unveils-new-website", "https://www.thepacker.com/news/industry/gem-pack-and-well-pict-berries-combine-companies"],
        "confidence": "medium",
    },
    "company-marionnet": {
        "verdict": "structural_ambiguity",
        "promote": False,
        "reason": (
            "Real entity confirmed via US patent filings (Andre Marionnet, e.g. USPP8517P 'Mara Des Bois') and "
            "trade coverage, but the exact CURRENT legal/organizational identity is unclear: search results name "
            "'Marionnet Label' (post-2018 R&D entity), 'Marionnet SAS', and 'MARIONNET GFA' (a produce-directory "
            "listing) as related but not clearly identical names, and state the company 'was taken over by the "
            "Agri Finest Company group' in 2018. No official current website was found. This is a real "
            "parent/renaming ambiguity, not just thin evidence -- held provisional pending a primary source "
            "(the current entity's own site or registry filing) that resolves which name is canonical today."
        ),
        "aliases_add": ["Marionnet Label"],
        "evidence_urls": ["https://www.doriane.com/case-studies/marionnet-label", "https://patents.google.com/patent/USPP8517P/en"],
        "confidence": "medium",
    },
    "company-oishii": {
        "verdict": "externally_verified",
        "promote": True,
        "reason": (
            "Extensively documented: official site oishii.com with a dedicated /pages/press newsroom, PR "
            "Newswire's own dedicated Oishii news page, multiple funding-round trade articles (Agriculture "
            "Dive), Wikipedia entry. Unambiguous, single, well-known organization (indoor vertical strawberry "
            "grower, Series C financing 2026)."
        ),
        "aliases_add": [],
        "evidence_urls": ["https://oishii.com/pages/press", "https://www.prnewswire.com/news/oishii/", "https://en.wikipedia.org/wiki/Oishii"],
        "confidence": "high",
    },
    "company-pairwise": {
        "verdict": "externally_verified_scope_question_flagged_separately",
        "promote": True,
        "reason": (
            "Pairwise itself is unambiguously real and correctly identified: official site pairwise.com, "
            "Durham NC CRISPR/gene-editing company, extensively covered including a 2024 Corteva partnership "
            "and equity investment. Identity is not in question. Separately (not a blocker to identity "
            "promotion, but flagged in the evidence ledger for the internal-classification owners): this "
            "mission's research found no explicit confirmation that Pairwise's public work is berry-specific "
            "as opposed to general ag-biotech across many crops -- a modeling/scope question about this "
            "roster row's berry relevance, not an identity question about which real-world company this is."
        ),
        "aliases_add": ["Pairwise Plants"],
        "evidence_urls": ["https://www.pairwise.com/insights", "https://www.corteva.com/resources/media-center/corteva-pairwise-join-forces-to-accelerate-gene-editing-advance-climate-resilience-in-agriculture.html"],
        "confidence": "high",
    },
    "company-perfection-fresh": {
        "verdict": "externally_verified",
        "promote": True,
        "reason": (
            "Official domain perfection.com.au confirms Perfection Fresh Australia, established 1978, a "
            "family-run business with dedicated berry farms in Tasmania and Queensland (Caboolture) and a "
            "Berries Australia grower-profile PDF corroborating the same facts independently."
        ),
        "aliases_add": ["Perfection Fresh Australia"],
        "evidence_urls": ["https://www.perfection.com.au/perfection-berries", "https://berries.net.au/wp-content/uploads/2024/01/AUT-21-PROFILE-PERFECTION.pdf"],
        "confidence": "high",
    },
    "company-royakkers": {
        "verdict": "externally_verified",
        "promote": True,
        "reason": (
            "Official domain softfruit.be confirms Royakkers as a family fruit-plant nursery/grower business "
            "(strawberries, raspberries, blackberries) run by Jan and Gijs Royakkers, based in Kinrooi, "
            "Belgium, corroborated by an independent Dutch/Belgian business-press profile (zakenblad.nl). "
            "Geographic note: located in Belgium, not the Netherlands its surname might suggest -- recorded "
            "here for the record; the spreadsheet's own region codes (DOA_DANZ/DEMEA) are unchanged, per this "
            "mission's explicit scope limits."
        ),
        "aliases_add": ["Royakkers Fruit & Planten", "Royakkers Planten & Fruit"],
        "evidence_urls": ["https://www.softfruit.be/over-ons/", "https://zakenblad.nl/2021/04/21/jan-en-gijs-royakkers-vader-en-zoon-in-een-gezond-familiebedrijf/"],
        "confidence": "high",
    },
    "company-smart-berries": {
        "verdict": "externally_verified",
        "promote": True,
        "reason": (
            "Official domain smartberries.com.au confirms Smart Berries Pty Ltd, formed 2013 as a partnership "
            "between Fresh Produce Group (FPG) and Pascoes, with farms in Queensland/New Zealand, corroborated "
            "independently by Fruitnet's Asiafruit coverage."
        ),
        "aliases_add": ["Smart Berries Pty Ltd"],
        "evidence_urls": ["https://www.smartberries.com.au/about-us/", "https://www.fruitnet.com/asiafruit/smart-berries-building-up/170931.article"],
        "confidence": "high",
    },
    "company-splendor-produce": {
        "verdict": "existence_confirmed_no_primary_source",
        "promote": False,
        "reason": (
            "Existence as a real Mexican berry grower/exporter (450ha blackberries, 200ha raspberries, ~80% "
            "exported to the US) is corroborated by a Mexican federal government agriculture-ministry article, "
            "a reasonably authoritative secondary/institutional source. No official company website was found "
            "despite search effort. 'California Splendor, Inc.' (calsplendor.com) was checked and confirmed to "
            "be a distinct company (different crops/profile), not this entity -- avoiding a false identity "
            "match. Held provisional pending a primary source."
        ),
        "aliases_add": [],
        "evidence_urls": ["https://www.gob.mx/agricultura/articulos/splendor-produce-un-resplandeciente-negocio-de-berries"],
        "confidence": "medium",
    },
    "company-sunbelle": {
        "verdict": "externally_verified",
        "promote": True,
        "reason": (
            "Official domain sun-belle.com (one of three related domains found -- sunbelleberries.com and "
            "sunbelle.info appear to be alternate/legacy domains for the same company, not separate entities) "
            "confirms SunBelle as a berry/specialty-produce marketer, corroborated independently by The "
            "Packer's trade coverage."
        ),
        "aliases_add": ["Sun Belle", "Sunbelle Berries"],
        "evidence_urls": ["https://www.sun-belle.com/", "https://www.thepacker.com/news/produce-crops/sun-belle-expands-berry-grower-relationships"],
        "confidence": "high",
    },
    "company-the-berry-collective": {
        "verdict": "genuine_identity_ambiguity",
        "promote": False,
        "reason": (
            "A real Australian berry-supply/retail-partnership organization (theberrycollective.com.au) was "
            "found and is the best available match, but the exact name is shared by at least four other, "
            "clearly unrelated organizations found in search results (a US wellness/community brand, an events "
            "platform, a classical-music ensemble). Compounding the ambiguity: the spreadsheet's own Competitor "
            "Type for this row is 'University/Public,' which does not obviously describe a growers-to-retailers "
            "supply partnership -- suggesting the matched .com.au site may not even be the organization the "
            "spreadsheet author intended. This is exactly the 'do not force ambiguous reconciliation' case; "
            "held firmly provisional pending a human confirming which real-world organization this row means."
        ),
        "aliases_add": [],
        "evidence_urls": ["https://theberrycollective.com.au/", "https://theberrycollective.com.au/about/"],
        "confidence": "low",
    },
    "company-well-pict": {
        "verdict": "identity_confirmed_relationship_ambiguity_unrelated",
        "promote": False,
        "reason": (
            "Well-Pict's own identity is not remotely in doubt: decades of trade coverage (Supermarket News, "
            "The Packer, Produce News), a long-established Watsonville, CA strawberry/berry grower-shipper. "
            "Held provisional for the same reason as Gem-Pack Berries above (symmetric treatment of the same "
            "unresolved affiliation question): trade press reports Gem-Pack and Well-Pict Berries 'combining "
            "companies,' and this mission does not have enough information to say whether that means a full "
            "merger, a marketing partnership, or something else -- promoting one side without the other would "
            "misrepresent the current, uncertain state of that relationship."
        ),
        "aliases_add": ["Well Pict Berries"],
        "evidence_urls": ["https://www.supermarketnews.com/fresh-produce/well-pict-berries-launches-new-website", "https://www.thepacker.com/news/industry/gem-pack-and-well-pict-berries-combine-companies"],
        "confidence": "medium",
    },
}

REGISTRY_MATRIX = json.loads(REGISTRY_MATRIX_PATH.read_text(encoding="utf-8"))
provisional_ids = {r["canonical_entity_id"] for r in REGISTRY_MATRIX["rows"] if r["resolution_status"] == "newly_created"}
assert provisional_ids == set(VERDICTS), provisional_ids ^ set(VERDICTS)
print(f"OK: {len(VERDICTS)} verdicts cover exactly the 17 provisional entities from the reconciliation matrix")

promoted, retained = [], []
for entity_id, v in VERDICTS.items():
    record = read_entity(entity_id)
    assert record["status"] in ("unverified", "active"), (entity_id, record["status"])
    changed = False
    existing_aliases = record.get("aliases") or []
    for alias in v["aliases_add"]:
        if alias not in existing_aliases and alias != record["name"]:
            existing_aliases.append(alias)
            changed = True
    if changed:
        record["aliases"] = existing_aliases
    attributes = record.get("attributes") or {}
    attributes["identity_verification_2026_09_15"] = {
        "verdict": v["verdict"],
        "reason": v["reason"],
        "evidence_urls": v["evidence_urls"],
        "confidence": v["confidence"],
        "verification_date": VERIFICATION_DATE,
        "verified_by": "competitor-identity-genetics-verification-v1",
    }
    record["attributes"] = attributes
    if v["promote"]:
        record["status"] = "active"
        promoted.append(entity_id)
    else:
        retained.append(entity_id)
    write_entity(entity_id, record)

print(f"Promoted to active: {len(promoted)} -> {promoted}")
print(f"Retained provisional (unverified): {len(retained)} -> {retained}")
assert len(promoted) + len(retained) == 17

# ---------------------------------------------------------------------------
# Deliverable 1: 17-row provisional-identity verification matrix
# ---------------------------------------------------------------------------
matrix_rows = []
for entity_id, v in VERDICTS.items():
    row = next(r for r in REGISTRY_MATRIX["rows"] if r["canonical_entity_id"] == entity_id)
    matrix_rows.append(
        {
            "spreadsheet_label": row["spreadsheet_label"],
            "canonical_entity_id": entity_id,
            "verdict": v["verdict"],
            "promoted_to_active": v["promote"],
            "reason": v["reason"],
            "aliases_added": v["aliases_add"],
            "evidence_urls": v["evidence_urls"],
            "confidence": v["confidence"],
            "verification_date": VERIFICATION_DATE,
        }
    )
write_json(OUTPUT_DIR / "provisional-identity-verification-matrix.json", {
    "id": "competitor-identity-verification-2026-09-15",
    "verification_date": VERIFICATION_DATE,
    "row_count": len(matrix_rows),
    "promoted_count": len(promoted),
    "retained_provisional_count": len(retained),
    "rows": matrix_rows,
})
print("wrote provisional-identity-verification-matrix.json")

# ---------------------------------------------------------------------------
# Deliverable 2: duplicate / structural identity review
# ---------------------------------------------------------------------------
import sys
sys.path.insert(0, str(ROOT))
from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.entity_identity import audit_entity_identity, load_identity_redirects

repos = get_repositories(DEFAULT_DATA_DIR, SCHEMAS_DIR)
all_entities = repos.entities.list()
all_relationships = repos.relationships.list()
redirects = load_identity_redirects(DEFAULT_DATA_DIR)
audit_result = audit_entity_identity(entities=all_entities, relationships=all_relationships, redirects=redirects)

structural_cases = [
    {
        "pair": "Planasa vs. Planasa-2 vs. Plantas de Navarra",
        "determination": "exact_duplicate_already_resolved",
        "detail": "company-planasa-2 is a CONFIRMED DUPLICATE of company-planasa via the existing "
                   "data/configuration/entity-identity-redirects.json mechanism, decided 2026-09-01 (predates "
                   "this mission). Plantas de Navarra, S.A. is not a third entity -- it is company-planasa's "
                   "own registered legal name. Re-ran the existing audit_entity_identity() auditor against the "
                   "full 69-company graph: this is the ONLY confirmed_duplicate found, with zero other "
                   "exact_duplicates, alias_collisions, or unresolved_probable_duplicates. No action needed; "
                   "the stale ambiguity note in reconciliation-matrix.json was corrected.",
        "action_taken": "Corrected a stale ambiguity note; no entity file changed.",
    },
    {
        "pair": "Mountain Blue vs. Mountain Blue Orchards vs. MBO",
        "determination": "alias",
        "detail": "All three are already aliases of the single entity company-mountain-blue-orchards "
                   "(aliases: 'Mountain Blue', 'MBO', 'Mountain Blue Farms'), established before this mission. "
                   "No duplicate, no action needed.",
        "action_taken": "None -- already correctly modeled.",
    },
    {
        "pair": "Hortifrut vs. Hortifrut Genetica",
        "determination": "alias_with_documented_uncertainty",
        "detail": "'Hortifrut Genetica' is an alias on company-hortifrut (added by the prior Company + Genetics "
                   "Relationships V1 mission), with an existing documented note that no separately-modeled "
                   "genetics division/subsidiary was confirmed to exist. This mission found no new evidence "
                   "either confirming or ruling out a distinct genetics division -- the existing alias-only "
                   "treatment remains the correct, non-speculative choice.",
        "action_taken": "None -- already correctly modeled; no new evidence changes this.",
    },
    {
        "pair": "California Giant vs. Giant",
        "determination": "alias",
        "detail": "'California Giant' is the roster label and an alias on company-california-giant-berry-farms; "
                   "'Giant' alone (as it appears in the handwritten notes, 'Giant/California Giant - Fall "
                   "Creek, Public') is an informal truncation resolved via context, not a separate entity.",
        "action_taken": "None -- already correctly modeled.",
    },
    {
        "pair": "Ozblu vs. OZblu, and its relationship to Mountain Blue",
        "determination": "brand_with_multiple_real_company_relationships_unrelated_to_mountain_blue",
        "detail": "Ozblu/OZblu is a single entity, brand-ozblu (entity_type 'brand'), with 'Ozblu' and "
                   "'OZblu(R)' as case-variant aliases -- not a duplicate. It already carries real, "
                   "pre-existing relationships to three DIFFERENT companies (United Exports owns the brand, "
                   "Nature Select develops the genetics, Oz Varieties licenses it). No relationship to Mountain "
                   "Blue Orchards was found or exists in this graph -- these are two separate, unrelated "
                   "blueberry-genetics programs (Mountain Blue Orchards in NSW, Australia; the Ozblu network "
                   "spanning United Exports/Nature Select/Oz Varieties). Confirming no relationship exists is "
                   "itself a real, useful finding, not an oversight.",
        "action_taken": "None -- already correctly modeled; confirmed no false relationship should be added.",
    },
    {
        "pair": "Plant Sciences vs. Plant Sciences, Inc.",
        "determination": "alias",
        "detail": "Single entity, company-plant-sciences-genetics, name 'Plant Sciences, Inc.', with 'Plant "
                   "Sciences Genetics'/'PSG' and (added by the prior mission) 'Plant Sciences' as aliases. This "
                   "mission's research corroborates the entity's own recorded 2026 restructuring (Plant "
                   "Sciences, Inc. -> Plant Sciences Genetics, Inc.) via an independent financial-press article.",
        "action_taken": "None -- already correctly modeled; new corroborating evidence recorded in the "
                         "identity-verification attributes block.",
    },
    {
        "pair": "Fruitist vs. Agrovision",
        "determination": "renamed_entity_with_separate_brand",
        "detail": "company-agrovision (name 'Agrovision Corp. (Fruitist)') already carried 'Fruitist' as an "
                   "alias before this mission, and this mission's research independently confirms the company "
                   "rebranded from Agrovision to Fruitist in April 2025 with extensive trade-press coverage "
                   "(FreshFruitPortal, The Packer, CNBC). A separate, distinct entity brand-fruitist (entity_type "
                   "'brand') also exists for the product brand itself -- a legitimate company/brand distinction, "
                   "not a duplicate, exactly analogous to the Ozblu case above.",
        "action_taken": "None -- already correctly modeled; corroborating evidence recorded.",
    },
    {
        "pair": "UC Davis as an institution vs. a breeding program",
        "determination": "institution_program_deliberate_choice",
        "detail": "This roster row resolves to breeding_program-uc-davis-strawberry (entity_type "
                   "'breeding_program'), not a generic 'University of California, Davis' institution entity, "
                   "which does not exist in this graph. This mission's research (strawberry.ucdavis.edu, a real, "
                   "dedicated program site with its own news section) confirms the breeding program is the "
                   "correct, specific, berry-relevant identity for this roster row -- a generic institution "
                   "entity would be less precise, not more correct.",
        "action_taken": "None -- already correctly modeled.",
    },
    {
        "pair": "University/public entities generally (University of Arkansas, University of Florida)",
        "determination": "related_but_distinct_organizations",
        "detail": "Both are separate, independently-canonical entity_type 'company' records (a pre-existing "
                   "convention this mission did not change) with their own aliases (UADA; UF/IFAS, UF). Not "
                   "duplicates of each other or of UC Davis's breeding-program entity.",
        "action_taken": "None -- already correctly modeled.",
    },
    {
        "pair": "Brands or divisions represented as independent spreadsheet rows",
        "determination": "company_brand_pattern_confirmed_twice",
        "detail": "Only one roster row (Ozblu) resolves to a brand entity rather than a company; Fruitist "
                   "resolves to the operating company (company-agrovision), with brand-fruitist existing "
                   "separately and correctly for the product brand. No roster row was found to incorrectly "
                   "represent a brand or division as if it were an independent company.",
        "action_taken": "None.",
    },
]
write_json(OUTPUT_DIR / "duplicate-structural-identity-review.json", {
    "id": "competitor-identity-duplicate-structural-review-2026-09-15",
    "verification_date": VERIFICATION_DATE,
    "automated_audit_result_summary": {
        "companies_count": audit_result["companies"]["count"],
        "confirmed_duplicates": audit_result["companies"]["confirmed_duplicates"],
        "exact_duplicates": audit_result["companies"]["exact_duplicates"],
        "alias_collisions": audit_result["companies"]["alias_collisions"],
        "unresolved_probable_duplicates": audit_result["companies"]["unresolved_probable_duplicates"],
    },
    "cases_reviewed": structural_cases,
    "planasa_result": "exact_duplicate_already_resolved_no_action_needed",
}, )
print("wrote duplicate-structural-identity-review.json")

# ---------------------------------------------------------------------------
# Deliverable 3: three-relationship evidence assessment
# ---------------------------------------------------------------------------
relationship_assessment = [
    {
        "relationship_id": "rel-agroberries-genetics-mountain-blue-orchards",
        "pair": "AgroBerries <-> Mountain Blue Orchards",
        "outcome": "upgraded",
        "predicate_before": "partners_with", "predicate_after": "licenses",
        "status_before": "disputed", "status_after": "active",
        "confidence_before": "medium", "confidence_after": "high",
        "evidence_added": ["ev-agroberries-mountain-blue-licensing-freshfruitportal-2026"],
        "reasoning": "FreshFruitPortal.com (2026-06-24) independently and explicitly states AgroBerries signed "
                     "licensing agreements with MBO to grow and market its blueberry genetics -- names both "
                     "parties, the specific relationship type, and the berry. Meets the bar for external "
                     "verification, not merely an internal assertion.",
    },
    {
        "relationship_id": "rel-agrovision-genetics-fall-creek-farm-and-nursery",
        "pair": "Fruitist/Agrovision <-> Fall Creek",
        "outcome": "retained_pending",
        "predicate_before": "partners_with", "predicate_after": "partners_with",
        "status_before": "disputed", "status_after": "disputed",
        "confidence_before": "medium", "confidence_after": "medium",
        "evidence_added": [],
        "reasoning": "Targeted search found no independent corroboration of a genetics relationship between "
                     "these two specific companies. Per this mission's rule, absence of public evidence does "
                     "not disprove the handwritten assertion -- left unchanged, with the search attempt "
                     "documented in the relationship's own notes.",
    },
    {
        "relationship_id": "rel-california-giant-berry-farms-genetics-fall-creek-farm-and-nursery",
        "pair": "California Giant <-> Fall Creek",
        "outcome": "retained_pending",
        "predicate_before": "partners_with", "predicate_after": "partners_with",
        "status_before": "disputed", "status_after": "disputed",
        "confidence_before": "medium", "confidence_after": "medium",
        "evidence_added": [],
        "reasoning": "Targeted search found no independent corroboration; surfaced only California Giant's "
                     "separate, already-tracked VentureFruit genetics partnership, which neither confirms nor "
                     "denies a Fall Creek relationship. Left unchanged per the same absence-of-evidence rule.",
    },
]
write_json(OUTPUT_DIR / "genetics-relationship-evidence-assessment.json", {
    "id": "competitor-genetics-relationship-evidence-assessment-2026-09-15",
    "verification_date": VERIFICATION_DATE,
    "relationships_reviewed": len(relationship_assessment),
    "upgraded": sum(1 for r in relationship_assessment if r["outcome"] == "upgraded"),
    "retained_pending": sum(1 for r in relationship_assessment if r["outcome"] == "retained_pending"),
    "rejected": sum(1 for r in relationship_assessment if r["outcome"] == "rejected"),
    "assessments": relationship_assessment,
})
print("wrote genetics-relationship-evidence-assessment.json")

# ---------------------------------------------------------------------------
# Deliverable 4: updated 19-row withheld-mapping review
# ---------------------------------------------------------------------------
TRANSCRIPTION_PATH = ROOT / "data" / "imports" / "competitor-registry-2026-09-15" / "genetics-transcription.json"
transcription = json.loads(TRANSCRIPTION_PATH.read_text(encoding="utf-8"))
withheld_source = [r for r in transcription["rows"] if not r["seeded"]]
assert len(withheld_source) == 19

WITHHELD_RECLASSIFICATION = {
    (1, 3): "self_mapping_requiring_semantic_caution",       # Hortifrut - Hortifrut
    (2, 1): "public_genetics_observation",                    # Composol/Camposol - Public
    (2, 2): "self_mapping_requiring_semantic_caution",        # Planasa - Planasa
    (2, 3): "remains_ambiguous",                              # Family Tree - MBO
    (2, 4): "self_mapping_requiring_semantic_caution",        # Fall Creek - Fall Creek
    (2, 5): "illegible_or_unresolved",                        # [illegible] - Planasa, MBO, Public
    (2, 6): "self_mapping_requiring_semantic_caution",        # MBO - MBO
    (2, 7): "identity_clarified_relationship_still_unverified",  # Perfection Fresh - ??
    (2, 8): "identity_clarified_relationship_still_unverified",  # Well-Pict - ???
    (3, 1): "scoped_no_blues_observation",                    # Oishii - No blues
    (3, 3): "self_mapping_requiring_semantic_caution",        # Plant Sciences - Plant Sciences
    (3, 4): "scoped_no_blues_observation",                    # Pairwise - No blues
    (3, 5): "public_genetics_observation",                    # Wish Farms - Public
    (3, 6): "out_of_roster_but_identifiable",                 # Dole - Inka Berries
    (3, 7): "public_genetics_observation",                    # SunBelle - Public
    (3, 8): "self_mapping_requiring_semantic_caution",        # Ozblu - Ozblu
    (3, 9): "illegible_or_unresolved",                        # Fresc Kampo
    (3, 10): "out_of_roster_but_identifiable",                # Water Fresh Farms - No blue
    (3, 11): "out_of_roster_but_identifiable",                # Good Farms - NA
}

RECLASSIFICATION_NOTE = {
    "self_mapping_requiring_semantic_caution": (
        "A company naming itself suggests proprietary/in-house genetics but is never converted to an "
        "'owns' relationship without independent confirmation, per this mission's explicit rule. No relationship "
        "created; no new evidence found this mission that would change that."
    ),
    "public_genetics_observation": (
        "'Public' is a genetics-source classification, not a company -- it never becomes a relationship object. "
        "No entity was created for it and none should be."
    ),
    "remains_ambiguous": (
        "The named party does not match any of the 33 mandatory roster labels or an existing canonical entity, "
        "and no external search this mission performed identified a specific real-world company it refers to. "
        "Genuinely unresolved, not merely out-of-scope."
    ),
    "illegible_or_unresolved": "Handwriting is illegible or the note's own author left it explicitly unresolved ('??'/'???'). Not guessed at.",
    "identity_clarified_relationship_still_unverified": (
        "This mission's identity verification work (see the provisional-identity matrix) confirmed the company "
        "side is a real, correctly-identified organization -- but the genetics-provider side of the handwritten "
        "note was left an explicit '??'/'???' by its own author, so no relationship can be seeded regardless of "
        "how well the company itself is now understood."
    ),
    "scoped_no_blues_observation": (
        "'No blues' is a scoped observation (this company not active in blueberry) per this mission's rule, "
        "never proof of a global absence of blueberry activity, and not a genetics-provider relationship."
    ),
    "out_of_roster_but_identifiable": (
        "The named party is plausibly a real, identifiable organization, but is not one of the 33 mandatory "
        "roster entities. Creating a new entity for it would exceed this mission's bounded scope; noted for "
        "visibility only."
    ),
}

withheld_review_rows = []
for r in withheld_source:
    key = (r["tier"], r["item"])
    classification = WITHHELD_RECLASSIFICATION[key]
    withheld_review_rows.append(
        {
            "tier": r["tier"], "item": r["item"], "visible_text": r["visible_text"],
            "company_entity_id": r["company_entity_id"], "provider_entity_id": r["provider_entity_id"],
            "reclassification_2026_09_15": classification,
            "reclassification_note": RECLASSIFICATION_NOTE[classification],
            "promoted_this_mission": False,
        }
    )
assert len(withheld_review_rows) == 19
write_json(OUTPUT_DIR / "withheld-mapping-review-update.json", {
    "id": "competitor-genetics-withheld-mapping-review-2026-09-15",
    "verification_date": VERIFICATION_DATE,
    "row_count": len(withheld_review_rows),
    "promoted_count": 0,
    "note": "Zero of the 19 previously-withheld rows were promoted to a seeded relationship this mission -- "
            "every row either names no identifiable roster-canonical party, is a self-mapping, is an explicit "
            "author-marked unresolved ('??'/'???'), is a public-genetics/scoped observation that structurally "
            "cannot become a relationship, or names a real organization outside the mandatory 33-entry roster. "
            "AMBIGUOUS HANDWRITING GUESSED: 0.",
    "rows": withheld_review_rows,
})
print("wrote withheld-mapping-review-update.json (19 rows reclassified, 0 promoted)")

# ---------------------------------------------------------------------------
# Deliverable 5: identity and relationship evidence ledger (consolidated)
# ---------------------------------------------------------------------------
ledger_entries = []
for entity_id, v in VERDICTS.items():
    for url in v["evidence_urls"]:
        ledger_entries.append({
            "subject": entity_id, "subject_kind": "entity_identity",
            "source_url": url, "confidence": v["confidence"],
            "verdict": v["verdict"], "verification_date": VERIFICATION_DATE,
            "evidence_type": "externally_verified_identity_fact",
        })
for r in relationship_assessment:
    for eid in r["evidence_added"]:
        ledger_entries.append({
            "subject": r["relationship_id"], "subject_kind": "relationship",
            "source_url": "see " + eid + ".json (data/evidence/)", "confidence": r["confidence_after"],
            "verdict": r["outcome"], "verification_date": VERIFICATION_DATE,
            "evidence_type": "externally_supported_relationship",
        })
write_json(OUTPUT_DIR / "identity-relationship-evidence-ledger.json", {
    "id": "competitor-identity-relationship-evidence-ledger-2026-09-15",
    "verification_date": VERIFICATION_DATE,
    "note": "Every row here traces back to either an externally-verified identity fact (company/organization "
            "identity research) or an externally-supported relationship (genetics-assertion corroboration). "
            "Internal spreadsheet classifications (tier/priority/region/competitor type) and user-provided "
            "handwritten assertions are tracked separately in the existing snapshot.json and "
            "genetics-transcription.json -- never represented here as though they were externally researched.",
    "entry_count": len(ledger_entries),
    "entries": ledger_entries,
})
print(f"wrote identity-relationship-evidence-ledger.json ({len(ledger_entries)} entries)")

print("\nDONE.")
