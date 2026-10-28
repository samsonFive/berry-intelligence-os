# Gene Editing & Advanced Breeding: delivery and research closeout

The implemented eleven-company slice was merged in PR #406 and deployed on October 21, 2026 at https://intel.johnnyaceii.com/landscapes/explorer?topic=gene-editing&adjacent=1. Its four required checks passed; the full CI suite recorded 5,115 passes and 11 skips. The corresponding GitHub Pages workflow also succeeded. A verified runtime backup, authenticated route checks and preservation of accounts, existing records and drafts are recorded in the private deployment receipt. Earlier preview-only statements are superseded by this delivery receipt.

The October 28 follow-up completes the public-source closeout and prepares source-review decisions. Its code/data changes require their own current-head CI, merge and live verification; the October 21 receipt is not evidence of this follow-up's deployment.

## Current data

The latest complete package is `data/imports/gene-editing-2026-10-28/snapshot.json`: 11 companies, 28 program/platform/research-affiliation rows, four sourced partnership claims and 46 linked publication candidates. The original October 20 package and October 21 supplement are retained unchanged as historical versions. The latest package references that earlier research rather than copying raw model responses.

The closeout adds 16 source candidates, three bounded program/capability/affiliation rows and 13 deduplicated manual source-registry entries. The total registry is 278: 220 templated collectors and 58 explicitly excluded manual references. Eleven company search monitors remain enabled; no new feed, schedule, paid provider or inference call is introduced. Existing company IDs, dossiers, review decisions and publication dates are preserved.

A prior Planasa original is reused by canonical URL; 46 candidates therefore represent 45 new private drafts across both deliveries and that existing publication. The four relationship claims remain research claims, not automatically trusted canonical relationships. No trusted publication, Fact, Signal, parent/control edge or Atomic Evidence approval is created by this closeout.

## What the follow-up resolved

- **Simplot:** original FDA VPM 0002 records the December 4, 2024 remontant-strawberry meeting; FDA explicitly says a VPM is not its evaluation of a developer safety assessment. Health Canada's S4A non-novel listing and anticipated marketing year are now checked. The July 17, 2026 Defra confirmation and August 21 notice reconcile all eight S4A identifiers. These records do not prove sales, food authorization in England or completed English trials. Simplot's SCRA presentation supplies its own S4A/Gn1 association; confidential FDA Gn1 is not independently equated to TFL1 from the FDA record alone.
- **PSI/PSG:** the issuer's August 2023 restructuring announcement and the rendered PSG history/research pages are now read. PSI contracted services and PSG portfolio/IP holding are distinct roles. PSG describes implementation under its new name in 2024; the announcement date is not silently substituted for implementation. Its current partner page corroborates Simplot strawberry and Pairwise caneberry work. Its statement about Simplot investment does not establish ownership percentages or control. The existing dossier ID is retained as a historical monitoring lineage, not a merged legal person; identity-scope metadata records the separate counterparties.
- **Pairwise:** FDA VPM 0011 records a July 9, 2026 blackberry meeting covering compact architecture, reduced prickles and reduced seed lignification. It does not identify Fontana or prove that sold fruit carried all three traits. Compact Colombian sales, Fontana introduction and seedless/thornless pipeline milestones stay separate.
- **Ohalo:** the original UF/FSREF 2024-25 report names Ohalo as an editing-system collaborator. It reports 138 regenerated lines and 20 selections for 2025-26 field testing after growth-room assays. Methods mention five cultivars; results enumerate four, and the discrepancy is retained. This is stronger evidence than an agreement alone but does not establish completed field trials, a named commercial release, or commercial sales. It is a separate DNA-free editing track, not a blanket CRISPR classification of Boosted Breeding or the true-seed consortium.
- **Heritable:** the rendered product page explicitly offers genome-edit design, CRISPR/targeted-mutagenesis designs, off-target prediction and multi-gene optimization. This closes the missing platform-description gap. It does not demonstrate editing in the CIV/Mastronardi strawberry partnership or independently validate product performance.
- **Qi:** MARA's original list names 苏州齐禾生科生物科技有限公司 and P16, certificate 351, alongside the already checked APHIS response. The Beijing Vilmorin counterparty and Suzhou certificate holder are identified separately. No Beijing/Suzhou equity or IP ownership chain, or exact P16/APHIS line equivalence, is invented.
- **Shunfeng:** the same MARA original names 山东舜丰生物科技有限公司 and GmELF3a soybean 25T93-1, certificate 350. Both listed soybean certificates run nationwide from January 2, 2024 through January 1, 2029. University-hosted company recruitment corroborates bellagen.cn association. A separate BellaGen legal company, formal rebranding and a berry program remain unestablished.
- **Planasa:** the original R&D page explicitly describes molecular markers, phenotyping and crossing. Its issuer IFSI release identifies EW Group membership; the page's May 12, 2026 date and body announcement's May 6 date are retained separately. These sources do not establish berry gene editing.
- **Fall Creek:** the original PubMed record for PMID 41635864 supplies a Fall Creek author affiliation in a strawberry CRISPR paper (October 15, 2025 publication; January 2026 collection). The record is represented as a research-affiliation row, not corporate sponsorship, a Fall Creek blueberry-editing program or a product. The HTTP fetch was blocked; substantive original bibliographic text was recovered through the web tool. Full publisher text was not recovered.
- **HRB/Plantik:** existing regeneration, license and tomato-versus-strawberry stage distinctions remain. The original HRB financing announcement now identifies the named investors without inferring control or an undisclosed amount. Successful strawberry heat-tolerance field outcomes remain unreported in the checked evidence.

## Source audit and review boundary

`source-audit.json` records 46 source checks: 45 readable captures through public HTTP or rendered browser text, plus one blocked HTTP source whose original bibliographic excerpt was recovered separately. All 30 retained excerpts from the earlier package match the newly recovered original text. Full captures remain private; checked metadata and hashes are versioned. Rendered PSG and Heritable pages close earlier JavaScript extraction gaps. No paid Perplexity calls were made during closeout.

`source-review-packet.json` supplies a source-level outcome, bounded claim synopsis and next review action for all 46 candidates. This completes the autonomous source audit. It is not a human publication decision, performance validation or Atomic Evidence approval. Actual runtime publication/rejection decisions remain authoritative; already published items are not republished and rejected items are not revived. The repository's human gates remain the normal next workflow, not a missing UI feature.

Undisclosed cap tables, executed contracts, unpublished commercial volumes and unreported trial results are closed as **unknown/not established**, with the supported claim boundaries recorded. They are not asserted to be false and are not open-ended tasks to fabricate an answer. No email outreach, account creation, paid subscription or broader company roster is authorized or required.

## Repeatable operations

```powershell
python scripts/audit_gene_editing_closeout.py --fetch
python scripts/prepare_gene_editing_closeout.py
python scripts/import_gene_editing.py --snapshot data/imports/gene-editing-2026-10-28/snapshot.json
python scripts/apply_gene_editing_closeout.py
python scripts/apply_gene_editing_closeout.py --apply
```

The fetch command accesses public originals only. Preparation consumes inspected captures and validates anchors; it cannot replace original-source checking. Import is add-only and URL-deduplicated. Reconciliation is dry-run by default and updates only unchanged prior program payloads plus an absent, namespaced identity note. Existing analyst corrections win. Source health updates preserve enabled/discovery settings. Production apply requires a verified backup and must run as the unprivileged web application user; running source preparation as root masked an alias-file permission problem during the initial release. Unprivileged candidate and live readability checks are required.

## Existing behavior and bounded limitations

Gene Editing and Advanced Breeding remain separate News filters. Classification requires agricultural context and explicit terminology, rejects medical contexts and negated evidence claims, never tags by company membership, and respects analyst exclusions. Historical backfill preserves source publication dates and trust. Company monitoring is independent from classification. Default results require berry relevance; adjacent platforms need the explicit toggle. Headquarters is not program geography.

The integrated Explorer supports comparison, sourced relationship claims, program details, bounded filters, CSV and printable HTML. Native saved-view forms and geographic SVG/PDF renderers are optional future enhancements, not required closeout work; unsupported exports fail explicitly rather than silently changing scope. Browser print-to-PDF remains available. No final research PDF was separately commissioned in this thread.

## Validation record

October 21: PR #406 merged at `219c739a3ce621deb9c61d5db358ad7e8a087c20`; current-head checks succeeded, 5,115 Python tests passed, record validation passed, static build produced 1,794 pages with no unpublished IDs/titles, Pages workflow succeeded, live routes passed, backup verified, accounts/data/drafts preserved.

October 28: source audit, idempotent reimport, guarded reconciliation, focused tests, schema/static checks and current-head CI are recorded in the follow-up PR and release receipt. Do not substitute the earlier validation for a later head. The live site's auth, records, source decisions and persistent inbox must remain intact throughout delivery.
