# Independent public variety coverage comparison

The Hortifrut omission is part of a wider coverage problem. A native public
Genome Database for Rosaceae (GDR) export contains **2,267 crop-group/name
pairs with no exact label match** in the current catalog or derived candidate
queue. These are research leads, including breeding selections and historical
material, not 2,267 confirmed missing cultivar identities.

## Source and denominator

- Public source: https://www.rosaceae.org/tripal_megasearch?datatype=tripal_megasearch_stock
- Native query checked October 7, 2026: Germplasm, Type = accession; all 203
  available Fragaria and Rubus organism options selected; All Fields export.
- Search reported 6,453 germplasm stocks. The CSV has 26,905 joined rows and
  **6,453 distinct (Unique Name, Organism) keys**, matching that bounded count.
- 2,794 keys have a nonblank Cultivar field; 3,659 have none. Names, aliases,
  sample names, parents and pedigree text do not supply cultivar labels.
- 2,355 distinct literal Cultivar labels produce 2,372 genus/name pairs:
  2,092 Fragaria labels and 280 Rubus labels. Seventeen labels occur in both
  crop groups. Repeated dataset rows do not become additional varieties.
- Raw CSV SHA256:
  `c9c5b70aa6e3116f5d9982004cb3ebfaef9c8765d619d65d797b59b8b17d9d00`.

The original 10.3 MB CSV, exact native query and comparison report are retained
only in the operator's ignored `inbox/historical-release-coverage/`. The committed
`data/imports/variety-external-baseline-2026-10-07-gdr/comparison.json` retains
literal labels and collection reference identifiers, not article bodies,
pedigree assertions, image legends, downloaded images or trait claims.

GDR's scope is Rosaceae: **this is not a blueberry/Vaccinium baseline** and not
a worldwide completeness score. Wild material, historical selections, uncertain
identifications and experimental crosses can appear in the Cultivar field.
An accession is a collection holding, not a patent or a new variety identity.

## What changed

The existing `/varieties/coverage` page now includes an independent public
comparison with search, crop-group and comparison filters, 50-row pagination
and expandable literal collection references. Missing names are the default.
Exact catalog/queue name matches link to existing profiles and identity review;
ambiguous Lewis results distinguish ORUS 576-47 from the uncoded Lewis lead.
Rubus is deliberately not assigned wholesale to raspberry or blackberry.

The comparison runs against current catalog/candidate inputs. Without private
operator state: 2,267 pairs have no exact name match, 104 have candidate name
matches, and one has a catalog name match (Ouachita). Those counts describe
text coverage, **not confirmed identity matches or approved catalog additions**.
Short labels unsupported by the existing resolver remain unmatched.

The 64 catalog entries, 413 derived candidate keys, 495 primary observations,
20 registry rows with some checks, 57 initial checks and four source gaps remain
unchanged. External labels do not inflate those separate denominators. Human
rejections and edits remain visible and untouched. No Source is onboarded; no
polling, model call, alias decision, release approval, relationship, rights,
trait or growing-region claim is created.

## Reproducible audit

`scripts/audit_variety_external_coverage.py` accepts a supplied native public
CSV, checked date and the displayed stock count. It rejects wrong crops, panels/
populations, malformed rows and unexplained stock-count differences. Output is
private by default; saving a body-free snapshot requires an explicit output and
the captured native query manifest. It does not fetch data or write trust stores.
The loader rejects duplicate genus/name keys and inconsistent reference scope.

## Validation and review

50 focused checks passed, covering independent accounting, name/stock/crop
collisions, exclusions, native-query scope, ambiguity, human-state preservation,
search/pagination and authoring-only read-only presentation. Record validation
and diff checks pass. Parent draft #326 passed all four exact-head gates with
4,070 passed / 11 skipped / two warnings. Current-head full CI is reported in
the follow-up PR, not implied by those parent checks.

Desktop and 390-pixel phone review use the isolated preview on port 18454.
Review checks include missing Rubus pagination, Lewis search, literal collection
references and navigation to the existing code-specific identity review. Local
screenshots stay in `inbox/external-germplasm-coverage/`; cloud agents cannot
assume those operator-local files are available.

## Still required

1. Establish an independent Vaccinium baseline from public germplasm/registry
   sources; reconcile actual cultivar releases separately from wild accessions.
2. Prioritize the unmatched GDR labels, confirm original release/registry
   evidence and prepare existing individual identity/intake reviews. No bulk
   trust or automatic cultivar creation is authorized.
3. Finish the 57 initial company/institution checks and four known source gaps,
   including lifetime portfolios and the unaccounted USDA pedigree.
4. Add cited traits, rights, roles, regions and usable visuals with their proper
   review and reuse gates; improve full-article acquisition and independent
   extraction recall before claiming source-complete discovery.

CAT-01, CAT-02 and TD-116 remain open. The blueberry Landscape review checkpoint
and release approval still apply. Nothing is merged, deployed or rolled out to
other-berry Landscape views by this comparison.
