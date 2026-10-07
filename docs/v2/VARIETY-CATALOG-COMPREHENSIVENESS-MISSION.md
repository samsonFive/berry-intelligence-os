# Variety catalog: comprehensive, source-linked coverage

User direction, October 6–7, 2026: the Hortifrut omission is a warning about
system-wide recall. Build toward the most comprehensive berry variety resource
available, without confusing a discovered name with an approved identity or
promoting source assertions into verified roles, traits or growing footprints.

## Immediate repair, included in the revised blueberry checkpoint

- [x] Audit all 1,269 stored published sources against the 64 canonical varieties.
- [x] Recognize explicit cultivar lists in ordinary stored summaries, alongside
  the existing structured, registry, fact and launch-title discovery paths.
- [x] Capture Hortifrut's eleven portfolio names plus six named licensed blueberries and MBG's sixteen code/name
  pairs; attach evidence IDs, original URLs and codes to the existing candidates.
- [x] Expose missing names beside the source in Landscape Explorer and alongside
  directory searches. The existing identity-review queue remains the decision surface.
- [x] Respect berry boundaries, exact aliases and ambiguous identities; do not
  auto-merge Candycrunch with Candy Crunch or pick the first ambiguous alias.
- [x] Preserve rejected names and other human decisions during rediscovery.
- [x] Avoid treating ordinary company/news sources as official registries.
- [x] Exclude generic variety classes such as June-bearing; preserve name suffixes
  such as `Abril Blue+` and separate a selection code from a marketing name.
- [x] Provide a repeatable audit: `scripts/audit_variety_catalog_coverage.py` and
  `artifacts/landscape-explorer-blueberry/variety-catalog-audit.json`.

Current stored-source audit: **99 explicit named identities, 31 catalog matches,
68 names awaiting identity review**, before loading any operator-private candidate
inbox. Earlier discovery returned 62 mentions and 34 candidates. This is a recall
improvement, not 68 newly approved varieties. Source names may include aliases
and codes. The audit covers stored published summaries and existing typed facts,
not the full text of every publication or the entire internet.

The canonical catalog currently has 41 blueberries, 6 strawberries, 12 raspberries
and 5 blackberries. These are coverage counts, not an estimate of the world's
varieties. In this audit, current parsing yields no strawberry/blackberry names;
that is a coverage gap to investigate, not proof there are no source mentions.
Private photo-import candidates and user edits remain in the operator's existing
inbox; the isolated preview does not copy, replace or erase that state.

## Next acquisition and reconciliation work

October 7 first portfolio slice: a 77-row registry source plan and ten dated primary
page/berry sections now use the existing candidate workflow. Nine readable sections
contain 93 name occurrences: 11 catalog matches and 82 review needs. They add 50
candidates beyond the stored-source audit (118 combined before private inbox state).
Five registry rows have some coverage; 72 need primary checks. This begins the
manifest/reconciliation/freshness work below; those global tasks remain incomplete.
See [first portfolio review](VARIETY-PORTFOLIO-COVERAGE-REVIEW.md) and its body-free
audit. Other-berry Landscape rollout stays behind the blueberry gate.

- [ ] Build a per-company/per-berry source manifest from the approved competitor
  list, with primary breeder portfolios, university releases, trial reports,
  nursery catalogs and official registry coverage. Preserve institutions and
  public-domain/historic cultivars alongside current commercial releases.
- [ ] Reconcile entire portfolios, not a few famous releases. Each enumerating
  source needs a dated check with every visible name matched to a catalog entry,
  a review candidate, or an explicit exclusion and reason. Flag unreadable tables,
  truncated captures, mixed-species ambiguity and unexplained shortfalls.
- [ ] Extend stored acquisition/extraction through existing qualified workflows
  for publication text, tables and linked product sheets. GET requests never
  trigger provider calls. Do not add a parallel scraper or bypass qualification.
- [ ] Use official rights/denomination records to check selection codes and
  aliases. Keep applicants, breeders, rights holders and marketers distinct;
  retain applications, grants, expired rights and jurisdiction-specific status.
- [ ] Resolve the new candidates with human identity review, then use the
  existing canonical authoring workflow for approved additions and aliases.
  Mark-distinct alone currently keeps a candidate; it does not create a catalog
  variety. Do not describe a completed candidate decision as an approved import.
- [ ] Fill source-backed profiles: images where usable, breeder/program,
  maturity/chilling/habit, fruit and storage characteristics, trial context,
  rights/licensing, explicitly supported growing regions and cited release dates.
  Promotional performance stays attributed; missing traits remain missing.
- [ ] Reconcile changes from refreshed primary portfolios through existing
  monitoring/intake. Keep last-checked dates, provenance, review history and user
  corrections. A removed page/name is not automatic withdrawal or deletion.
- [ ] Build a manually verified multi-berry recall benchmark spanning cultivar
  lists, quotes, codes, brand prefixes, tables, multilingual sources and aliases.
  Measure missed names, false positives and unresolved identities separately.
- [ ] Add coverage/freshness views with meaningful denominators: portfolios
  reconciled versus known source portfolios; names accounted for versus names
  enumerated; stale/unreadable sources; fields evidenced; sources awaiting review.
- [ ] Compare against reference resources before making a public superlative.
  Report specific strengths and gaps; no invented global completeness percentage.

## Primary reference sources checked for planning

- [Hortifrut genetic development](https://www.hortifrut.com/innovation/genetic-development/):
  currently enumerates the eleven Berry Blue names and links individual varieties.
  Individual pages can contain useful region and performance assertions that need
  their own source-backed review; the company operating location is not a substitute.
- [MBG Berry Blue portfolio](https://www.blueberries.com/proprietary-berry-varieties-berry-blue-llc/):
  complements Hortifrut; conflicting ownership self-descriptions stay unresolved.
- [CPVO variety databases](https://cpvo.europa.eu/en/applications-and-examinations/cpvo-variety-databases):
  Variety Finder covers registers from more than 70 countries. Use existing CPVO
  adapters and access arrangements; the present fix does not change that backend.
- [UPOV PLUTO](https://www.upov.int/es/find-and-explore/databases/pluto-search):
  a denomination/rights reference, complementary to commercial breeder catalogs.

## Scope and release gates

This requirement remains open in the ongoing redesign/consolidation goal.
The immediate shared discovery fix is necessary for an honest blueberry review;
it does not authorize rollout of other berries in Landscape Explorer. Continue
the catalog mission through acquisition, verification and draft PRs under the
existing human trust gates. Obtain required access or approval only when actually
needed. No merge or deployment is part of this review checkpoint.
