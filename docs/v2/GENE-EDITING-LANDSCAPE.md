# Gene Editing & Advanced Breeding: integrated research slice

Status: implementation candidate for Johnny's review; **research acceptance is incomplete**. No merge or production deployment is authorized by this slice.

## Open the real-data preview

- Landscape: `http://127.0.0.1:18761/landscapes/explorer?topic=gene-editing`
- Include adjacent platforms: add `&adjacent=1`.
- News: `http://127.0.0.1:18761/today?topic=gene-editing`.
- Comparison/evidence CSV and printable HTML use the existing Explorer export/briefing routes and its analyst authorization gate. This lens does not yet support the existing geographic SVG/PDF renderers; it returns an explicit 422 for those formats. Printable HTML can be printed to PDF by the browser.

The preview uses canonical data and the actual imported private publications, with `BIOS_PUBLICATION_REVIEW_REHEARSAL_UI=0` and `ENABLE_SOURCE_POLLING=false`. There is no mock dataset or generated commercial availability. The branch's ordinary geographic/genetics Explorer remains available from the same page.

## Data and trust

`data/imports/gene-editing-2026-10-20/snapshot.json` is the versioned import package, following the existing dated competitor-registry import convention. It contains 11 resolved roster profiles, 23 unique program/platform descriptions, four partnership claims, 26 Evidence candidates and 53 source configurations. Original-source access checks, feed checks, Perplexity queries/results, conflicts and per-company coverage are adjacent files.

The native Entity registry contains seven new monitoring companies and 23 unverified `breeding_program` entities. Existing Pairwise, PSI/PSG, Planasa and Fall Creek records are preserved. Programs retain their research attributes and evidence links. Native program attributes override the frozen snapshot in the lens, so later analyst corrections survive reruns.

The importer created **25 private publication drafts**, preserving an already-captured Planasa original by canonical URL and mapping its research citation to `ev-planasa-about-us`. It added **52 source configurations**: 41 original-page references and 11 runnable company news-search monitors. The import's 26 candidate Evidence objects therefore correspond to 25 new drafts plus one existing publication. Four partnership claims stay explicitly pending in the research snapshot; **zero trusted relationships, Facts, Signals or publications are automatically created**. Source publication review does not automatically approve a program or relationship claim.

PSI's existing ID is `company-plant-sciences-genetics`, despite its display name being Plant Sciences, Inc. The existing aliases also include PSG. This mismatch is disclosed rather than silently renaming the dossier or creating a duplicate PSI company. Exact PSI/PSG legal restructuring and subsequent alias/entity reconciliation require source-backed analyst review. Simplot Plant Sciences remains a unit of Simplot for this slice and is never merged with PSI.

## Classification and historical backfill

News has multi-select **Gene Editing** and **Advanced Breeding** topics, an explicit adjacent-crop/platform toggle, and publisher filtering. They compose with the existing berry, company, country/region, time, list and tier selectors. Review-lane and pagination URLs retain the same topic scope.

The deterministic `gene-editing-1` classifier requires explicit editing terms and agricultural context, supports selected local-language terms, rejects medical context and negative evidence statements, and never uses company roster membership as a topic trigger. NGT/NBT/precision-breeding acronyms require editing/regulatory context. Boosted Breeding and AI-driven predictive breeding receive Advanced Breeding without automatic CRISPR labeling. Crop-unassigned platforms retain unknown crop assignments. Default topic results require explicit berry relevance; adjacent signals require the toggle.

Each match exposes its reason, supporting text, version and provenance. Existing publication review's Tags field accepts `topic-exclude-gene-editing` and `topic-exclude-advanced-breeding`; those corrections survive classification/backfill and source publication. Explicit analyst-owned classification objects are also preserved. No new review workflow is introduced.

Five historical published records were tagged through the repeatable backfill: two Gene Editing and three Advanced Breeding. Their publication dates and review/trust state are unchanged. The second pass changed zero records. The same check on 25 imported private drafts changed zero records on rerun.

```powershell
python scripts/import_gene_editing.py
python scripts/backfill_gene_editing.py data/evidence --apply
python scripts/backfill_gene_editing.py inbox/evidence --apply
```

`import_gene_editing.py` accepts `--snapshot`, `--data-dir` and `--inbox-dir` for a separate runtime. It takes the existing collection lease, deduplicates IDs and canonical source URLs, only creates missing records, and never overwrites a reviewed/rejected draft, existing entity, program correction or source configuration. It is safe to rerun. Rebuilding the immutable research package is a separate, intentional authoring step; it is not part of runtime import.

## Source health and acquisition

42 original-page candidates were checked: **33 readable, five without usable original prose, three unavailable and one blocked**. Readable does not mean independently verified. The Qi investor page returned an unrendered template and is not accepted as small-berry evidence. PSI research/about and Heritable home/products required JavaScript and did not yield usable prose. Qi's official site failed to connect; Shunfeng's English and Chinese sites timed out; the European Commission NGT page was blocked. These references remain disabled with explicit status.

The two RSS links advertised by Planasa's own HTML returned no entries and remain unverified. No official company feed endpoint was invented. Eleven free Google News RSS company queries were verified and configured with the **existing** `news_search_rss` adapter under the existing article/news pipeline. These are ordinary company monitoring, not an alternative provider for Perplexity research. The queries do not automatically classify matches as Gene Editing.

The existing discovery command was exercised on Simplot and Qi: Simplot returned 35 feed items and staged 10 under its existing bound; Qi returned eight and staged eight; neither had item-level failures. Reruns staged zero new items and recognized all 10/eight existing staged items. Monitoring discovery does not establish full-body acquisition or comprehensive recall. No live collection or paid inference runs on the new page's GET path.

## Research capability, cost and remaining gaps

The configured key and existing Perplexity integration were inspected without exposing credentials. All 11 companies have two saved Perplexity Search passes (22 searches, 176 result rows before cross-company deduplication). Eight `sonar-deep-research` responses were saved, but all eight returned `finish_reason=length`: they are **partial**, not complete research reports. Initial Simplot/Ohalo/HRB deep calls received HTTP 429. The account later returned HTTP 401 `insufficient_quota`; further paid calls were stopped. A successful diagnostic Simplot deep response was not retained and does not count toward research acceptance. The standalone cross-company follow-up request was rejected before producing results.

Saved Deep Research usage reports sum to **32,180 tokens and USD 12.27567**. This is a lower bound, not a total bill: the Search adapter does not expose billing; the diagnostic call and interrupted retry have unavailable cost. No subscription, credit purchase, automatic top-up or alternative research-provider substitution was made. Johnny requested a manual Perplexity prompt to supply the missing work through his own interface.

Per-company coverage and evidence gaps are recorded in `coverage.json` and the preview. Key holds:

- Simplot: verify subsequent sales and exact lineage; Defra S4A-210 notice is not proof of completed trials or universal approval.
- PSI/PSG: resolve the legal split with readable original restructuring records; preserve current registry identity pending review.
- Ohalo: verify actual 2026 consortium trials and released varieties; Boosted Breeding remains distinct from CRISPR.
- Pairwise: compact Colombian sales, Fontana introduction and seedless/thornless pipeline remain separate, attributed milestones.
- HRB/Plantik: the 2024 single-cell milestone is enabling technology; tomato demonstrations do not establish strawberry field success or commercialization.
- Fall Creek/Planasa: gene-editing involvement **not established in this research pass**; commercial conventional breeding is documented.
- Heritable: AI strawberry breeding is documented; product-page genome-edit design claims were not independently recovered.
- Qi: the APHIS-hosted RSR PDF is an applicant request, not a decision. Original product/event-specific certificates and the small-berry facility lead remain unresolved; Beijing/Suzhou entities are not legally collapsed.
- Shunfeng: KWS confirms a Cas-SF01/Cas-SF02 license; official domain/legal-equivalence details and berry programs remain unresolved.
- EU/China: no unverified regulatory endpoint is activated or global approval inferred. The Chinese government science-portal report is not substituted for product-specific regulatory certificates.

Generic extraction initially selected related Fontana content on older Pairwise pages. Original article-content DOM was re-read before selecting evidence. HRB's shared metadata dates were corrected to visible article dates (2024-02-06 and 2026-09-28). HortiDaily's discovery date differed from original metadata; the original page date is retained. These conflicts remain in the snapshot.

## Validation

- Focused suite: 156 passed (Gene Editing, News, existing Landscape Explorer, ingestion and collection status).
- Record schemas: passed after initial native import.
- Import second pass: zero companies, programs, publications or sources created; existing records preserved.
- Backfill second passes: zero changes in trusted historical records and private research drafts.
- Live API: 11 companies, 23 programs, four partnership claims, 26 linked sources with adjacent mode enabled. Default berry mode: all 11 companies retained, 12 matching programs and three partnership claims.
- Browser: populated comparison, unknowns, pending-source labels, adjacent toggle and linked evidence inspected with rehearsal disabled.
- Full suite/static build/CI: see the final validation receipt; no merge/deployment is implied by local checks.

Full mission acceptance remains open for manual research completion, PSI/PSG identity review, broader original-source follow-ups and any unresolved validation failures. Stop at this integrated slice; do not expand the monitored roster beyond the requested 11 seeds.
