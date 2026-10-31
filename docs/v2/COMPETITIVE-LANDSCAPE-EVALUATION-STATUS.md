# October 31 implementation and research receipt

This current account supersedes the historical Stage 1/pending checkpoints below. Johnny authorized direct public-source continuation after the Perplexity limit. All 46 profile batches and R01/R02 are captured; all 166 frozen entities have profiles. The private application retains 4,109 rows: 3,907 structurally accepted and 202 unresolved. Structural acceptance does not verify claims. Four narrowly scoped assessments are Provisional; 340 eligible cells remain Unknown. Genetics Uruguay remains an identity hold.

The feature now includes additive searchable entity checkboxes, scoped matrix/evidence/correction history, overview, compatible-axis plot, directed relationships, exposure, people/hiring, import resolution, immutable cited export and shared captured coverage across existing routes. Real-data browser rehearsals use a separate, visibly labeled inbox; Johnny's main assessments remain four Provisional with no analyst override.

See the [implementation and import instructions](COMPETITIVE-EVALUATION-IMPLEMENTATION.md), [acceptance walkthrough](COMPETITIVE-EVALUATION-ACCEPTANCE.md) and [route receipt](../research/competitive-landscape-2026-10-30-v1/feed-route-checklist.md). The branch is rebased on canonical `3b0b4acc`. Full local suite: 5,537 passed, ten skipped; subsequent final affected checks and PR checks are recorded in the walkthrough. No merge or production deployment.

## Historical checkpoints retained below

# Competitive landscape evaluation — Stage 1 handoff

## October 30 web-research checkpoint

Johnny subsequently authorized running the prompts through the signed-in Perplexity web UI and explicitly approved uploading the combined public-only instruction pack. This supersedes the original manual-execution handoff for research execution only. No API, upgrade, purchase, scheduled research or trust-gate change was authorized or performed.

B01–B15 returned research. Original PDFs and 152 CSV tables were preserved privately with SHA-256 provenance; CSVs avoid the clipping observed in wide PDF tables. The candidate assembler produced 2,576 records including 575 source-ledger rows, zero malformed rows, and 67 unresolved mapping/reference/metadata items. These counts describe returned candidates, not verified facts or unique independent sources. Original-source validation, application import and ratings remain pending. B04's blank first attempt was retained in the run history and a successful retry was captured. Metadata prose in B10/B13 remains visible for resolution.

Perplexity then displayed **“You've reached the deep research limit this month.”** B16 returned an attachment-access error and no research; the monthly-limit banner followed. B16–B46 and R01/R02 remain pending. Selecting Deep Research on a freshly loaded page also opened the upgrade dialog. No reset timestamp was displayed. Do not mark B16 complete, silently downgrade research, or purchase an upgrade. When execution resumes, confirm the attachment has finished uploading before submitting B16.

Local continuation state is in gitignored `inbox/competitive_landscape/web-research-2026-10-30/`: `run.json`, `capture-manifest.json`, `assembly-summary.json`, original `raw/` exports and `assembled/B##/` readable tables/candidate JSON. The scripts `capture_competitive_web_returns.py` and `assemble_competitive_research_returns.py` preserve and reconstruct explicit UI downloads; they do not call Perplexity or import into application storage. The frozen inventory/prompts were not regenerated. The full feature remains unfinished; the earlier Stage 1 account below records the state before web execution.

The retained [mission](COMPETITIVE-LANDSCAPE-EVALUATION-MISSION.md) defines the full project. The current increment completes inventory/contracts/prompts; it does not complete the application or its real-return acceptance scenarios. Continue Stage 2 on `feature/competitive-landscape-evaluation-v1` when Johnny returns manual research. Do not replace this inventory silently.

Start with the [research handoff](../research/competitive-landscape-2026-10-30-v1/README.md). The actual canonical revision inspected was `1aef8862ee32fc07d91b3e09b66f85e2939cd975`, fetched on October 30, 2026. Existing working changes and older feature checkouts were left intact in a separate checkout.

## Completed

- Frozen all 169 canonical ecosystem records in the four relevant entity types: 110 company, 41 program, 10 brand, eight retailer records. Excluded two fictional company fixtures and one fictional retailer. The 166 included nodes comprise 108 company records, 41 programs, 10 brands and seven retailers. Institutions and support actors retain their existing type and role labels.
- Retained multi-role classification and all 33 legacy roster entries; did not treat the historical roster as the whole universe. Primary-versus-secondary role dominance remains Unknown because the registry does not declare it. Proposed technology/breeder roles from existing research are questions, not promoted classifications.
- Preserved one explicitly unresolved company identity, Genetics Uruguay, and 19 prior unresolved relationship leads. The existing identity audit found no additional exact-name or alias collisions in the 110 company records; it retained the existing Planasa duplicate redirect. Brand/program/legal-company distinctions and the PSI/PSG historical monitoring lineage remain explicit.
- Captured all linked evidence references. Forty-six unique source records occur only in the existing October 28 Gene Editing import, rather than the canonical evidence folder. They are import-only, not broken references or newly trusted publications. No linked reference remains missing after checking that import. This is a tracked-checkout observation; no production inbox was inspected or synchronized.
- Defined 21 capability rubrics across the four rated roles before scoring. Defined separate Unknown/N/A states, scope/period requirements, confidence, provisional visibility and override precedence. No company rating was applied.
- Generated 46 self-contained profile batches covering every included node once, plus R01 reconciliation and R02 gap follow-up. Each includes the exact Markdown return contract. Public-only field projection excludes private analyst/provenance notes.
- Recorded input and prompt SHA-256 hashes normalized to UTF-8/LF for portable checkout verification, batch coverage, research dates/statuses and import instructions. Original future research-return byte hashes remain separate. No Perplexity call or paid research was run.

The inventory's raw peer-role counts include program nodes: breeder 49, grower 36, marketer 36 and technology provider three. These are recorded classifications, not counts of verified competitive capabilities. The technology company count needs reconciliation against newer gene-program research; missing tags do not imply no technology capability.

## Source and integration inspection

The registry, explicit identity redirects, company/program/brand/retailer records, relationships, captured Evidence, source configuration, roster reconciliation/unresolved queue, and Gene Editing research snapshot were read. Existing dossier/portfolio, variety-footprint, company comparison, Landscape/Explorer, shared Workspace feed and persistence contracts were inspected. There is no general destination-market axis on existing company `operates_in` links. One Driscoll's–Portugal link explicitly describes an IP examination. Treating all these links as production would misstate the footprint, so origin/destination remain Unknown until scoped observations are validated.

Existing source checks are retained in the [identity receipt](../research/competitive-landscape-2026-10-30-v1/identity-source-checks.md). They support identity questions only, not automatic capability ratings or company-wide production aggregation.

See the [route checklist](../research/competitive-landscape-2026-10-30-v1/feed-route-checklist.md) for code-inspected feed gaps. None is claimed fixed or browser-verified. Existing shared reader, tag semantics, Workspace SQLite revision checks, JSON repositories and runtime lock/atomic-write conventions must be reused. A selected feed does not silently become a report's source set. Source/Atomic Evidence human gates remain distinct from the explicitly authorized provisional capability layer.

## Stage 2 continuation

1. Preserve original returned Markdown/attachments and batch metadata. Parse and validate with per-row failures and visible resolution queues; inspect original citations. Retain date, unit, source-family and scope distinctions.
2. Extend the existing storage/retrieval model for scoped observations, research batches, roles, people/jobs/events, assessment revisions/overrides and saved comparisons. Reimport idempotently; protect manual and concurrent changes.
3. Automatically show source-supported assessments as Provisional, with anchor/rationale/confidence and correction actions. Unknown stays unscored. Preserve analyst overrides through new imports and reruns.
4. Build company overview, matrix, compatible strategic axes, directional relationships, exposures and People and Hiring views. Connect shared captured-archive feeds across every route in the checklist. Preserve existing live research as a separate lane.
5. Demonstrate a real returned batch, reimport, a multi-role company, scope separation, cohort-stable ratings, preserved correction, jobs/reposts, feeds with either-company and market-context matching, refresh, reader-state preservation and cited save/export. Run focused domain/integration tests plus desktop/narrow/keyboard browser checks. Report missing role/crop/market coverage honestly.
6. Deliver the working preview, focused PR, migrations/import instructions and walkthrough; follow the release process. No production deployment was requested by this brief.

## Validation

Eight focused handoff-integrity tests passed. Canonical record validation passed. The offline validator verifies source hashes, complete non-fictional entity coverage, public-field projection, exact return fields, prompt hashes and five-level rubric anchors. The tests intentionally introduce missing batches, input/manifest drift, prompt corruption and a rehashed private-field injection to verify visible failure, and check Windows/Unix newline portability. These are Stage 1 checks, not evidence of a functioning Stage 2 importer or UI.

No runtime application, trusted data, scheduled task or production state changed. No preview is claimed for an unimplemented application increment. Research validation, ratings, population and full mission completion depend on returned research.
