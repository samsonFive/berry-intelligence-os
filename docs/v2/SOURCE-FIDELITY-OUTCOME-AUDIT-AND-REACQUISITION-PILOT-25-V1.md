# Source Fidelity Outcome Audit + Bounded Historical Reacquisition PILOT-25 V1

**Production execution:** 2026-08-24

**Canonical and deployed SHA:** `45b46a5b23821a61521542a514ed775c472ccf62`

**Trust boundary:** unchanged; reacquired bodies are private and pending Source Fidelity Review until a separate human decision

No model was invoked. No Atomic proposal, qualification marker, extraction run, publication, or trusted Evidence mutation occurred.

## PILOT-10 human outcome audit

Durable artifact state and append-only `source_fidelity_review` events agree on the final decisions. Ten Source Fidelity events exist for eight artifacts because Pink Hudson and CIOPORA each received a repeated `affirmed` event; the current artifact state is authoritative and no decision is inferred from queue absence.

| Evidence | Source artifact | Berry | Source group | Technical classification | Human decision |
|---|---|---|---|---|---|
| `ev-media-c8cdb7133db1cae0bf66` | `source-artifact-610b198c98346bfdc78b` | Raspberry | other / Planasa newsroom | `CONTENT_CHANGED` with exact URL/date, 1.0 summary overlap, and historic body-hash cross-check | AFFIRMED |
| `ev-fruitnet-driscolls-zara-best-strawberry` | `source-artifact-8db278db743c5e2a034e` | Strawberry | trade press | `LIKELY_SAME_ARTICLE_CHANGED_FORMATTING` | AFFIRMED |
| `ev-ciopora-united-exports-pbr-2020` | `source-artifact-69e709b78f208a053db5` | Blueberry | association / other | `CONTENT_CHANGED` | AFFIRMED |
| `ev-sekoya-story` | `source-artifact-41961a9ac385d37dee78` | Blueberry | company newsroom | `CONTENT_CHANGED` | NEEDS INVESTIGATION |
| `ev-producereport-blugenix-2026` | `source-artifact-b78102beec91de4d5ca6` | Blueberry | trade press | `CONTENT_CHANGED` | AFFIRMED |
| `ev-delisted-costa` | `source-artifact-62ae13d5efb6efc1da9f` | Blueberry | other | `AMBIGUOUS` | AFFIRMED |
| `ev-costa-african-blue-2023` | `source-artifact-8db5988eb5b05ce0e555` | Blueberry | company newsroom | `LIKELY_SAME_ARTICLE_CHANGED_FORMATTING` | AFFIRMED |
| `ev-costa-ownership-2024` | `source-artifact-c1ba76c1729740964f28` | Blueberry | company newsroom | `LIKELY_SAME_ARTICLE_CHANGED_FORMATTING` | AFFIRMED |

Final totals are seven affirmed, zero rejected, one needs investigation, and zero pending. Human-accepted yield is **7/10 attempted URLs (70%)** and **7/8 rich artifacts staged (87.5%)**. Rejection is 0/10 and 0/8. Needs-investigation is 1/10 (10%) or 1/8 staged (12.5%). The high affirmation rate and mixed, explainable single investigation did not reveal a systemic identity or review-workflow defect, so the PILOT-25 gate was GO.

## Extraction readiness after human review

The canonical overlay contract, using affirmed artifacts only, changed extraction-ready inventory from **36 to 43**:

| Readiness class | Before | After |
|---|---:|---:|
| `READY_FULL_ARTICLE` | 0 | 7 |
| `READY_TRANSCRIPT` | 0 | 0 |
| `READY_STRUCTURED_REGISTRY` | 36 | 36 |
| **Total ready** | **36** | **43** |

Berry distribution after review is Blueberry 41, Strawberry 1, Raspberry 1, Blackberry 0, Multi-berry 0. Pink Hudson (`ev-media-c8cdb7133db1cae0bf66`) is now `READY_FULL_ARTICLE` with 1,794 source characters under the affirmed Source Fidelity overlay. No Atomic Evidence was generated. Blackberry remains a critical zero-ready gap because the Victoria PILOT-10 URL produced no staged artifact.

## Fresh PILOT-25 manifest

The pre-existing PILOT-25 manifest contained all ten PILOT-10 IDs and therefore could not measure a new cohort. PR #141 added the minimal bounded contract fix: exact PILOT-25 execution is accepted, and manifest generation can exclude an earlier manifest while retaining the hard 10/25 limits and shared lock. All required checks passed before merge.

- Manifest: `/opt/berry-intelligence-os/demo-runtime/inbox/operations/source-reacquisition/REACQUISITION-PILOT-25.json`
- SHA-256: `b6a03850058946de4fa0c52beb40b888022a439be985692fa91dc6b6cd80d984`
- Entries: 25 new IDs; overlap with PILOT-10: zero
- Berry mix: 25 Blueberry
- Source mix: 18 company newsroom, 5 trade press, 1 academic, 1 other
- Selection: canonical deterministic priority after excluding all ten prior PILOT-10 attempts

No safely eligible Raspberry or Blackberry candidate remained after that exclusion. The coverage-first selector therefore returned only Blueberry records; no weak URL was forced for balance.

Selected IDs, in deterministic order: `ev-cinven-planasa-ew-group`, `ev-fall-creek-commercial-platforms-2026`, `ev-harvestsa-rossouw-2020`, `ev-uf-ifas-hs1245`, `ev-brevis-ip-registration-trends`, `ev-hortifrut-genetic-development`, `ev-hortifrut-integrated-report-2023`, `ev-planasa-blue-manila-datasheet`, `ev-planasa-blue-manila-page`, `ev-topfruit-megacrisp`, `ev-freshplaza-fall-creek-chile-2026`, `ev-berryworld-varieties`, `ev-planasa-blue-maldiva`, `ev-abb-varieties`, `ev-agronometrics-prism-2025`, `ev-freshfruitportal-fall-creek-2026`, `ev-hortifrut-mbo-genetics-2026`, `ev-italianberry-peru-varieties-2025`, `ev-mbg-berry-blue-varieties`, `ev-fallcreek-catalog-blue-ribbon`, `ev-fallcreek-catalog-last-call`, `ev-fallcreek-catalog-sekoya-beauty`, `ev-fallcreek-catalog-sekoya-fiesta`, `ev-fallcreek-catalog-sekoya-grande`, and `ev-fallcreek-catalog-sekoya-pop`.

## PILOT-25 outcomes

The exact manifest ran once under the shared collection lock. Its body-free audit is `/app/runtime/inbox/operations/source-reacquisition/runs/REACQUISITION-PILOT-25-20260824T103247067370Z.json`.

| Outcome | Count | Share |
|---|---:|---:|
| Identity-supported rich (`CONTENT_CHANGED` or `LIKELY_SAME_ARTICLE_CHANGED_FORMATTING`) | 15 | 60% |
| Rich but `AMBIGUOUS` | 6 | 24% |
| `ROBOTS_OR_ACCESS_BLOCKED` | 1 | 4% |
| `THIN_BODY` / invalid PDF extraction | 3 | 12% |
| Timeout/network | 0 | 0% |
| Paywall, removed, redirect mismatch, interstitial, unsupported | 0 | 0% |

Raw rich-body staging was **21/25 (84%)**. Conservative useful identity-supported yield was **15/25 (60%)**. All 21 successful artifacts are private and `pending`; none affects extraction readiness until a later human decision.

Source-type results:

| Group | Attempted | Raw rich | Identity-supported | Pending review |
|---|---:|---:|---:|---:|
| Company newsroom | 18 | 16 (88.9%) | 10 (55.6%) | 16 |
| Trade press | 5 | 4 (80%) | 4 (80%) | 4 |
| Academic | 1 | 0 | 0 | 0 |
| Other | 1 | 0 | 0 | 0 |

The PILOT-10 company-newsroom 3/3 result remains directionally strong for raw acquisition (16/18), but does not repeat as 100% identity-supported yield: six rich company/catalog pages were ambiguous and two company PDF paths were thin. Berry results are Blueberry 25 attempted, 21 rich, 15 identity-supported, and 21 pending; Strawberry, Raspberry, Blackberry, and Multi-berry were each zero in this new cohort.

## Combined historical and forward strategy

Across both historical pilots, 35 URLs produced 29 rich artifacts (**82.9% raw rich yield**) and 22 identity-supported useful artifacts (**62.9% conservative technical yield**). PILOT-10 additionally demonstrates that seven of eight staged artifacts were human-affirmed. These results make selective reacquisition valuable for high-priority records, but the identity-review burden and lack of safe caneberry candidates argue against a bulk crawl.

Forward acquisition remains the default investment: its expanded probes were 22/25 full bodies and it is expected to produce 20-40 new rich candidates per month without historical identity ambiguity. Historical work should continue only as small, explainably prioritized batches after the 21 new items are reviewed; engineering effort should primarily strengthen forward coverage and analyst throughput.

## Idempotency and production safety

Only the 21 staged IDs were rerun; the four failures were not retried. Every result was `ALREADY_STAGED / unchanged`, with identical artifact IDs and body hashes, zero duplicate artifacts, and zero duplicate review items. Audit: `/app/runtime/inbox/operations/source-reacquisition/runs/BOUNDED-RUN-20260824T103326133186Z.json`.

Before mutation, the established backup created and independently verified `/var/backups/berry-intelligence-os/berry-runtime-20260824T103015Z.tar.gz`, SHA-256 `852e10649ae7a0eae7195ab2ff70d3ae14d785a5104d5d1df1c90f1d59fc944a`, with 12,617 checksummed `data`/`inbox` entries. Pre/post trusted Evidence tree SHA-256 remained `7a6cc5fae89fa2034f65e2a784386dce3f3ce05673026359bdbd673078c54585`; review-event tree SHA-256 remained `7536cfaecebc9d0a4fd05f7a5c3fe386d22b5fe61697abd5a66648167ff45a52`, with 11 files. Trusted data remained 2,656 files and Publication Review drafts remained 1,660.

The final Source Fidelity inventory is 29 artifacts: 7 affirmed, 1 needs investigation, and 21 pending. Qualification markers remain zero. Operator status reports extraction disabled, unconfigured, unqualified, and unrunnable; the lock is absent; the verified backup is healthy. Internal/public health are 200. The timer is enabled/active, its restored dispatcher exited 0, and the next run is scheduled normally.

Canonical Static Public Safety passed. The non-deploying production-runtime self-check reproduced TD-098's known trusted-page/draft-title collision diagnostic, then a targeted scan of its 1,564 generated files checked 220 new private artifact IDs, body hashes, Source Fidelity paths, and long paragraphs and found zero matches.
