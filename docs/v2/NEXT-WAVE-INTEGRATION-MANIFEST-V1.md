# Next-Wave Integration Manifest V1

**Purpose:** Git- and documentation-only integration plan. No branch is merged by this manifest.

**Base:** `origin/integration/competitor-intelligence-v1`
**Base SHA:** `031c9b6a80bd72ce3f271933d8a1ea302decb077`
**Prepared:** 2026-09-15

## Branch inventory

| Branch | Required/observed HEAD | Merge base with required base | Status | Scope |
|---|---|---|---|---|
| `origin/research/competitor-identity-genetics-verification-v1` | `4bff239967036542a5a4ee67d39d1d86d43d1ee6` | `031c9b6a80bd72ce3f271933d8a1ea302decb077` | frozen | canonical identity/genetics verification; data-bearing |
| `origin/feature/competitor-source-activation-wave1` | `6cc49278856768de05efe52c7c5d9fcb96d980c7` | `031c9b6a80bd72ce3f271933d8a1ea302decb077` | frozen | source strategy, activation code/data, canary artifacts |
| `origin/planning/product-experience-roadmap-v1` | `f2021d4b1709629cb20bc81c609a9ea644142950` | `031c9b6a80bd72ce3f271933d8a1ea302decb077` | frozen | documentation only |
| `origin/prototype/daily-intelligence-briefing-v2` | `a6f307b5d62315c21bd3c07faa297cb43eee496f` | `bd96fca1231dc97ae4ec3fc316743b0a3f2e8427` | frozen prototype | standalone briefing prototype; includes old landscape parent |

Pending/incoming and deliberately not treated as complete: `feature/daily-intelligence-briefing-v2-slice1`, `feature/competitor-profile-data-v1`, and `feature/trust-feedback-domain-v1`. Remote inspection found no current refs for these names; wait for their checkpoints rather than inferring content.

## Exact commit map

### Identity/genetics

1. `e2ff81b04dbe85f44782016fbd21089376c9d094` — provisional identity verification and Planasa duplicate-note correction.
2. `7bba0df483b385a9d29770dc672efca0fe199656` — genetics verification, one corroborated relationship, withheld mappings.
3. `4bff239967036542a5a4ee67d39d1d86d43d1ee6` — tests, checkpoint, and documentation.

### Source Activation Wave 1

1. `49b4db74cc764659f74464e4d7c5484b907b05b7` — source-strategy research/import planning.
2. `84f5b4e99e036e123bbee9a1a295f3e2efe32737` — activation implementation and reconciliation.
3. `6cc49278856768de05efe52c7c5d9fcb96d980c7` — canary artifacts and checkpoint.

### Product roadmap

- `f2021d4b1709629cb20bc81c609a9ea644142950` — documentation-only Product Experience Roadmap V1.

### Daily Briefing prototype

- `d44e3e3d753e4f796151e75c6747214b92c8232e` — competitor landscape parent already represented in integration as rehashed `d36f6785afbbb2785a3915c312dda45d87a71b14`.
- `a6f307b5d62315c21bd3c07faa297cb43eee496f` — standalone Daily Intelligence Briefing V2 prototype.

The prototype’s `d44e3e3` logical change is already in the integration lineage. Do not cherry-pick it or the prototype branch wholesale. If the prototype is accepted later, review only its prototype contract/assets or a newly rebased production slice.

## Changed-file classification

Counts are calculated from each frozen ref against the required integration base, not from another branch’s working tree.

| Branch | Total | Production code | Canonical data | Tests | Artifacts | Screenshots/media | Docs | Prototype files |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Identity/genetics | 34 | 1 | 27 | 2 | 4 | 0 | 0 | 0 |
| Source activation | 41 | 5 | 7 | 2 | 25 | 0 | 2 | 0 |
| Product roadmap | 7 | 0 | 0 | 0 | 6 | 0 | 1 | 0 |
| Briefing prototype | 127 | 17 | 42 | 7 | 26 | 17 | 6 | 11 |

Classification is path-based for review triage, with prototype verification media counted separately from planning artifacts. It is not a trust or quality score.

## Changed-path intersection matrix

| Pair | Shared paths | Handling |
|---|---:|---|
| Identity × Source activation | 0 | Semantic dependency only; identity must precede source-link interpretation. |
| Identity × Roadmap | 0 | Roadmap is descriptive; update no application files. |
| Identity × Briefing | 22 | Prototype carries older copies/deletions of canonical entities, registry reconciliation, relationships, and registry tests. Do not merge those copies; use identity/integration canonical data. |
| Source activation × Roadmap | 0 | No textual overlap. |
| Source activation × Briefing | 3 | `app/services/competitor_registry.py`, `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`, `scripts/run_collection.py`; resolve against activation/integration code, not prototype deletions. |
| Roadmap × Briefing | 0 | Use roadmap as planning guidance only. |

The briefing prototype’s broad diff is relative to the integration base and includes inherited/removed files because its parent is older than the published integration. It is not a clean production delta.

## Semantic-dependency matrix

| Concern | Identity/genetics | Source activation | Roadmap | Briefing prototype | Required decision |
|---|---|---|---|---|---|
| Canonical entity identity | owns updates | consumes IDs | documents contract | contains stale copies | identity data wins; rebase before any production briefing slice |
| Genetics roles/status | owns verified/pending states | must not alter | preserves role distinctions | prototype only displays honesty states | keep disputed/pending visible; no inferred relationship |
| Monitoring maturity | does not change | owns 5-stage activation/readability facts | describes sequence | fixture-only | do not confuse active identity with operational source |
| Source linkage | untouched by identity | owns approved links and outcomes | plans telemetry | prototype fixtures only | activate only through governed Source config and outcomes |
| Canary records | none | private ignored canary artifacts | excludes runtime | fixture records are not production | never copy `inbox/`, canary JSON, drafts, or runtime state |
| Today/briefing presentation | not touched | limited Source Health integration | plans Reader/feed | standalone HTML prototype | implement over existing services; no second store/engine |
| Trust/review | identity evidence remains governed | canary drafts unapproved | typed feedback is planned | prototype states only | existing publication review remains the trust gate |
| Static output | record artifacts only | static-build evidence | docs only | prototype media/static assets | regenerate from clean runtime; exclude private data |

## Stale and duplicate artifacts

- The integration checkpoint’s current 33-row audit supersedes the historical Sol 11/33 audit; retain the latter only as explicitly historical.
- Source activation `monitoring-audit-before` is a before-state, not current truth; use `monitoring-audit-after` for its checkpoint and never mix canary counts into deployed coverage.
- Activation `application-data-mutations.json`, `canary-results.json`, operation items, and acquisition outcomes describe private/unapproved canary activity; they are audit evidence, not import input.
- The prototype’s inherited `d44e3e3` landscape parent is stale relative to the rehashed integrated landscape commit. Do not cherry-pick it twice.
- Prototype fixture JSON/JS and verification screenshots/video demonstrate view states only. They are not production adapters, trusted Evidence, or runtime source data.
- The Product Experience Roadmap is frozen planning guidance. Later implementation branches may supersede status claims only through a new dated checkpoint; do not rewrite the frozen roadmap during integration.
- Any generated `generated/`, ignored `inbox/`, local reports, Pagefind output, browser captures, or temporary logs must be regenerated in the target integration environment, not copied from a sibling worktree.

## Live/generated-data exclusion list

Never import or commit from another worktree:

- `inbox/`, `demo-runtime/inbox/`, discovered-media state, transcripts, draft Evidence, signal candidates, analyst queue state, review events, operation logs, and canary runtime files;
- activation canary discoveries, run records, acquisition outcomes, and private draft IDs;
- prototype fixture payloads as Evidence or Sources;
- `generated/`, Pagefind indexes, browser screenshots/video, PDFs, caches, or temporary logs as application data;
- credentials, `.env` files, model responses, or qualification packets;
- historical audit artifacts as current coverage or current source health.

Only canonical `data/` changes explicitly reviewed from the identity/activation checkpoints may enter a merge. Every private runtime item remains private and unpublished.

## Recommended integration order

1. **Identity/genetics verification:** review the three exact commits as one logical unit. Accept canonical entity/status/alias changes, verified relationship change, preserved pending relationships, and tests/artifacts. Confirm no tier/priority/Source/Variety changes beyond the checkpoint.
2. **Source Activation Wave 1:** after identity review, take the source-strategy planning commit and activation implementation as a governed unit, then review the canary checkpoint. Accept only approved Source configuration, existing adapters, boundedness, separate discovery/body outcomes, and no private runtime import. Do not rerun collection during merge.
3. **Product Experience Roadmap:** documentation-only; cherry-pick `f2021d4...` after the data foundation or retain it as a separately reviewable planning branch. It has no application dependency and must not be used to claim implementation.
4. **Daily Briefing production:** wait for a production slice derived from the prototype and rebased onto the then-current integration. Take only a reviewed read model/route slice; do not take the old landscape parent, deleted acquisition/content-honesty files, stale entity copies, or fixture data.
5. **Competitor profile service:** accept `feature/competitor-profile-data-v1` only after its branch appears with a checkpoint. Rebase onto the identity + activation base and verify canonical IDs, monitoring maturity separation, and no duplicate profile store.
6. **Trust-feedback domain:** accept `feature/trust-feedback-domain-v1` after the Reader/object contract is stable. Require typed analyst-only feedback, undo/idempotency, actor/time, provenance retention, and no automatic publication/trust mutation.
7. **Future Grok trust UI:** accept only after the trust domain and production Reader are integrated. It must consume the existing state model and queues, not infer trust from visual reactions or reintroduce prototype fixtures.

## Incoming-branch acceptance checklist

For every pending branch when it arrives:

- exact branch/ref and full HEAD verified; merge base recorded;
- checkpoint identifies owner, scope, base, runtime/data boundary, and whether work is prototype or production;
- changed-file manifest reviewed; no unexpected `data/`, `inbox/`, generated, credential, or vendor changes;
- logical commits compared with `git patch-id`/equivalent history review so rehashed commits are not duplicated;
- canonical IDs and entity types resolve through current identity data;
- monitoring maturity remains separate from profile identity and current coverage;
- focused tests cover the changed service/routes and existing regression boundaries;
- record validation passes for canonical data changes;
- static build uses a clean/isolated output and proves no private IDs/titles/bodies leak;
- browser checks cover desktop/mobile, keyboard/focus, Reader, filters, empty/blocked states, and route deep links where relevant;
- artifacts are regenerated from the target worktree, while old screenshots/audits are labeled historical;
- final Linux/CI deterministic full suite passes before release;
- no live collection, model calls, publication, approval, deployment, or external merge occurs as part of review.

## Final validation checklist

1. Confirm base and each accepted commit SHA; confirm no duplicate logical parent.
2. Run canonical focused tests for identity, source activation, competitor landscape/profile, acquisition outcomes, Reader/Today, and trust state as applicable.
3. Run `python scripts/validate_records.py`.
4. Run static-public safety tests, then `python scripts/build_static.py` in clean output; verify required public files and no private draft IDs/titles.
5. Perform browser checks for `/competitors`, `/sources`, Today/Reader, profiles, and any new briefing/profile/trust route.
6. Run the full deterministic suite once on Linux/CI with no live collection/model calls.
7. Recheck exact HEAD, clean tracked tree, ignored runtime boundaries, and no data publication/approval.

## Provisional acceptance criteria by wave

| Wave | Accept when | Reject/defer when |
|---|---|---|
| Identity | canonical 33 roster remains represented; statuses/aliases/roles match checkpoint; pending evidence remains pending; tests/records pass | relationship inferred, tier changed, duplicate entity created, or stale prototype data is included |
| Activation | 12-row reconciliation and approved Source links are explicit; adapters are existing; discovery/body/relevance/current states remain separate; canary is private | canary drafts copied, blocked body treated readable, or source registration lacks governance |
| Roadmap | seven documentation files only; no application claims beyond evidence | used as proof of deployed behavior or revised during merge |
| Briefing | read model is over existing trusted/pending/query services; date/content-honesty gates pass; Reader/landscape deep links work | fixture data acts as production data, second feed store/engine appears, or old parent is cherry-picked |
| Profile | canonical profile data is reusable by landscape/Today/Reader; no duplicate entity or maturity field | identity and monitoring status are flattened or a parallel profile store is introduced |
| Trust domain | feedback is reversible/audited and distinct from publication approval; provenance survives down actions | thumbs automatically publishes, deletes, confirms, or mutates trusted data |
| Trust UI | consumes the approved domain state and existing queues with keyboard/mobile/a11y coverage | visual affordance becomes an ungrounded trust shortcut |
