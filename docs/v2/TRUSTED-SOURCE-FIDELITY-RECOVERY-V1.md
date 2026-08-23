# Trusted Source Fidelity Recovery + Re-review Pipeline V1

Status: implementation complete; source recovery remains human-gated and Atomic extraction remains disabled.

## Trust contract

Published Evidence and recovered source content have separate trust decisions. A recovery artifact is private operational data under `inbox/source_fidelity/artifacts/`; it binds the trusted Evidence identity, exact source URL, artifact and source-text hashes, provenance, stable article paragraphs or transcript segments, and a source-fidelity review state. Staging it does not edit `data/evidence`, reopen Publication Review, affirm the artifact, or make it extraction-eligible.

Only `published Evidence + affirmed source-fidelity artifact` is overlaid by the read-only extraction readiness contract. Affirmation changes source-content lineage only. It does not change the Evidence summary, `why_it_matters`, berry/geography/entity links, Facts, Relationships, Assessments, Signals, or the original publication review history. Source-fidelity decisions also emit private append-only `source_fidelity_review` events.

## Deterministic matching

`scripts/source_fidelity_recovery.py` bulk-indexes candidate IDs, canonical URLs, and explicit lineage IDs once. Match precedence is:

1. `EXACT_IDENTITY_MATCH`
2. `EXACT_URL_MATCH`
3. `LINEAGE_MATCH`
4. exact title + Source + publication date is `AMBIGUOUS` and never applicable
5. `NO_MATCH` or `CONFLICT`

A same-ID candidate with a different canonical URL is a conflict. Multiple differing bodies or artifact types on the same strong identity are conflicts. Fuzzy title matching is not used. Apply is additive and idempotent, requires explicit IDs, refuses ambiguous/conflicting rows, and never implies human affirmation.

A source-text hash repeated across three or more distinct trusted publication URLs is also a conflict. This body-level safety gate catches reused acquisition/interstitial payloads before staging while leaving a possible two-publication reprint pair available for human review and later extraction duplicate handling.

Operator examples:

```text
python scripts/source_fidelity_recovery.py --status
python scripts/source_fidelity_recovery.py --id EVIDENCE_ID --json
python scripts/source_fidelity_recovery.py --manifest
python scripts/source_fidelity_recovery.py --apply --id EVIDENCE_ID
```

Default behavior is dry-run. The body-free manifest is private at `inbox/operations/source-fidelity-recovery/recovery-manifest.json`.

## Historical recovery inventory

The audit used the retained 1,268-record production corpus snapshot and every actual local historical Evidence-artifact location found on the operator machine:

| Location | JSON artifacts |
|---|---:|
| Current repository inbox | 1 |
| Current normalized-transcript cache | 1 |
| Acquisition clone inbox | 856 |
| Article-ingestion clone inbox | 12 |
| Freshness clone inbox | 597 |
| Operational-acceleration clone inbox | 25 |
| Operational-acceleration normalized-transcript cache | 2 |
| Pilot-collection clone inbox | 6 |

No other transcript, normalized-media, article-cache, or source-artifact-cache directory containing a recoverable JSON artifact was found. Repository fixtures are test-only and were not treated as production recovery sources. Across the actual directories, 72 unique rich candidate artifacts were indexed. Applying the canonical readiness inventory first excludes the three fictional fixtures and two deterministic duplicates, leaving the authoritative 1,227 `THIN_DESCRIPTION_ONLY` records.

| Recovery classification | Count |
|---|---:|
| Exact full article | 1 |
| Explicit-lineage transcript | 1 |
| Ambiguous | 0 |
| Conflict | 0 |
| No recovered historic artifact | 1,225 |

The article recovery is Raspberry / Planasa / `discovered_media`; explicit language is absent (`undetermined`). The transcript recovery is Blueberry / Lucentlands / `discovered_media`, with explicit artifact language `af`. Raspberry has 1 recoverable source; Blueberry 1; Blackberry 0; Strawberry 0. No Gold Set record or benchmark was changed.

The two trusted spoken-media records were audited explicitly. `ev-lucentlands-scaling-blueberry-industry-2025` persists `transcript.status: not_available`, and no historic transcript was found for it. `ev-media-73ee28a2d5821b9a851d` has no trusted transcript object, but its explicit `discovered_item_id` exactly links to normalized transcript `transcript-discovered-source-lucentlands-podcast-22e7bd9b03f2ce93`. That private artifact contains 2,229 monotonic timestamped segments spanning 2.99–5,409.26 seconds, 59,425 extraction-source characters, no captured speakers, and local faster-whisper provenance (`small`, CPU, 2026-08-16). Its match class is `LINEAGE_MATCH`, not exact ID or URL, and it remains pending source-fidelity review.

## Pink Hudson acceptance proof

Trusted `ev-media-c8cdb7133db1cae0bf66` exists in the production snapshot as published and has no article paragraphs. The acquisition artifact has the same Evidence ID and exact canonical URL, five sequential paragraphs (`0..4`), 266 words, author Paula Crespo, and 1,794 extraction-source characters. Recovery creates:

- source artifact ID `source-artifact-7be1853c58003769fd5c`
- source-text SHA-256 `a96774afb4399108077b2fb7c6f8e82568544466d99924273474f64a32b8a0a1`
- recovery-artifact SHA-256 `7be1853c58003769fd5c737aeb2ba4c945b5dc0c671192df875fb5156578c309`
- the acquisition article's retained content hash `f7f439978358abf697426b109c12c85b6ee0434e3765f306b32606e6746269ec`
- review state `pending`

The different Planasa awards article, `ev-media-d2406f3e7a6de96c4fa1`, has a different ID, URL, seven-paragraph body, and retained content hash `f7a80503465cb2cb30547ff62e0079323ca46a85714e9003c6cefc8a43e24f2c`; it is never attached to Pink Hudson.

Pink remains `THIN_DESCRIPTION_ONLY` while the staged artifact is pending. A non-persisted readiness simulation of both recovered artifacts after their respective human affirmations changes Pink to `READY_FULL_ARTICLE` and the linked Lucentlands item to `READY_TRANSCRIPT`, raising the corpus from 36 to 38 ready inputs and reducing thin descriptions from 1,227 to 1,225. No analyst affirmation was performed.

## Private review workflow

`/source-fidelity` is a bounded queue separate from Publication Review and Atomic Evidence Review. Exact matches and articles sort first, with caneberry sources surfaced before other berries within equivalent candidates. `/source-fidelity/{evidence_id}` shows the trusted shell, recovered full body/transcript, identity proof, provenance, hashes, and current source-fidelity state. The analyst may affirm, reject, or mark needs investigation. Only affirmation changes extraction readiness.

Recovered articles preserve sequential paragraph indexes for future `SOURCE / PARAGRAPH N / EXACT EXCERPT` grounding. This establishes the source-side locator contract but does not modify the Atomic proposal UI or the current Atomic Evidence schema limitation recorded as TD-077. Transcript segments, timestamps, speakers, language, acquisition diagnostics, and transcription metadata are preserved when present. The Lucentlands recovery provides stable timestamp locators but no speaker labels.

## Safety and performance

Normal manifests contain no bodies or local locators. Recovery artifacts, paths, review decisions, and append-only decision events stay under gitignored `inbox/` and are not consumed by the static builder. The implementation does not fetch the web, mutate trusted data, create Atomic Evidence, enable extraction, create a qualification marker, or change publication/static trust rules.

The expanded local artifact index and deterministic match completed in 3.174 seconds in the final development audit; total operator time was 15.124 seconds including the authoritative canonical readiness/duplicate classification. Matching uses prebuilt indexes rather than N x repository scans. The CLI reports both timings separately because duplicate exclusion is part of the authoritative 1,227-record denominator.

For the remaining 1,225 records, future reacquisition must be a separate guarded workflow: capture current content as a new private candidate, compare URL/date/hash/content against the historical identity, and require source-fidelity review. A current webpage must never be silently treated as the historical reviewed source.

## Production proof

PR #119 merged as `f6fbc338` and was deployed through the established verified-backup and Docker rebuild procedure. The first production dry run indexed 1,366 rich runtime candidates. It exposed 65 different Google News publication URLs carrying one identical 1,356-character source-text hash. An in-memory extraction-readiness simulation confirmed 64 would collapse as duplicates and only one could have appeared ready, so counting them as 65 independent recovery wins was misleading. The production-proof follow-up therefore classifies all 65 as `CONFLICT / REUSED_BODY_HASH_ACROSS_DISTINCT_PUBLICATIONS`; none can be staged by the operator CLI.

After that safety gate, production contains one exact-URL recoverable article (Hortifrut) and one explicit-lineage recoverable transcript (Lucentlands), with 65 conflicts, zero ambiguous matches, and 1,160 no-match records. Pink Hudson's exact historic acquisition artifact exists only in the audited local acquisition store, not the production runtime, so the combined all-location inventory is two articles + one transcript recoverable, 65 conflicts, and 1,159 with no historic artifact. Current readiness remains 36. After three separate human source-fidelity affirmations, the realistic combined ceiling is 39: two full articles, one transcript, and the existing 36 registry inputs.
