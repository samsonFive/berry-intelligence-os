# Scoped competitive evaluation

Current implementation is undergoing integrated acceptance review. The historical Stage 1 inventory remains frozen; it is not regenerated from later findings. This document separates captured research, structural acceptance, source checks and capability decisions.

## Private storage and trust

`app/services/competitive_evaluation.py` extends the existing living-workspace SQLite object store under the configured `BIOS_INBOX_DIR`. New object kinds are `competitive_record`, `competitive_batch`, `capability_automatic`, `capability_decision` and `competitive_comparison`. The existing transaction, history and revision guards remain authoritative. There is no second entity registry or comparison database, and no schema migration of trusted Evidence, Variety, Trade or Weather.

Canonical entities come from the existing repositories. Every retained research row has its batch/local identity, original-return SHA-256, original fields and resolution status. Invalid mappings stay inspectable. Source inspection is separate from structural acceptance. Neither imports, source captures nor capability decisions publish Evidence or create Atomic Facts.

Capability identity includes entity, role, berry, destination, origin, programme/variety, period, use/system, capability and rubric version. No crop, market, programme or parent capability expansion is inferred. Only an exact, fully documented anchor supported by explicitly inspected original sources can produce a provisional number. Confidence records six evidence factors; High additionally requires distinct inspected source families and original URLs. Unknown and Not applicable are unscored, with no overall total or average.

Automatic proposals and analyst decisions have separate histories. Analyst overrides survive reimport and reassessment. Source/observation changes and mapping invalidation flag reconsideration. Scope corrections retain the original automatic scope and observations; they are explicit analyst overrides with a separate effective scope key and Unknown evidence confidence. Stale decision submissions return 409.

## Import and continuation

Run from the repository root with its Python environment:

```powershell
python -m scripts.import_competitive_research
python -m scripts.import_competitive_research --apply --source-checks inbox/competitive_landscape/source-inspections-2026-10-30.json
python -m scripts.assess_competitive_research inbox/competitive_landscape/anchor-checks-2026-10-30.json
python -m scripts.capture_competitive_sources inbox/competitive_landscape/capture-selection-2026-10-31.json
```

The first command is a dry run. The import verifies the original web-return lineage and direct-return hashes/derived tables, then writes only private workspace objects. Identical retries replay without duplicate rows. Later parser policies can revalidate existing mappings; old automatic proposals remain in history. Source inspections survive an ordinary reimport; changed source fields require reinspection. The assessment command applies explicit, source-grounded anchor checks rather than accepting an opaque suggested score. Selection/inspection files and original research remain private and are not Git inputs.

Source capture writes metadata into the existing retained News packet path and links research sources to canonical article identities. It does not fetch, invent article bodies, promote claims or turn ordinary vacancy searches into news. Unknown publication dates remain unknown. Existing source acquisition, Reader, personal saving and workspace capture handle later reading. Explicit destination annotations require canonical geography IDs and a source-based rationale; licence territories, trial sites, headquarters and origins never supply fruit destinations automatically.

## Captured research and current coverage

All 46 profile batches and R01/R02 are captured: B01–B15 through the authorized Perplexity web UI, then B16–B46 and follow-ups through authorized direct public-source research after the monthly Deep Research limit. No paid API or upgrade was used.

The 48 inputs contain 4,109 retained rows: 498 profile observations, 668 capability observations, 924 source-ledger entries, 315 people/employment observations, 197 job observations, 96 hiring/leadership observations, 263 relationships, 195 exposures, 949 gaps and four unsupported-context rows retained for resolution. These are observations, not unique people, independent sources, confirmed hires or trusted facts.

Current validation accepts 3,907 rows structurally and retains 202 for resolution. Profiles cover all 166 frozen entities; one canonical placeholder, Genetics Uruguay, remains an explicit identity hold. Its three profile observations are unresolved. Role aliases/ineligible mappings, ambiguous entity references, missing source references and unsupported context are not silently repaired. Repeated source-ledger entries do not establish independent corroboration.

Four narrow automatic assessments are provisional; remaining automatic cells are Unknown:

| Entity / programme | Capability | Level | Evidence boundary |
|---|---|---|---|
| NC State | Breeding programme | 3 | One completed, replicated, three-site strawberry trial cycle, 2025–26. Sites are research locations, not fruit destinations. [Original report](https://content.ces.ncsu.edu/strawberry-cultivar-evaluation-in-north-carolina-results-2025-2026-season). |
| The Summer Berry Company | Operating resilience | 2 | Implemented UK strawberry UV-C mitigation trials; company reductions lack an independent baseline. This is not proof of automated picking or measured recovery from a disruption. [Original company page](https://summerberry.co.uk/innovation/robotics/). |
| Oishii | Sales channels | 2 | Direct consumer delivery/kiosk is one category; grocery retail is another. No third channel, sales volume or nationwide stock is inferred. [Original company page](https://oishii.com/). |
| Florida/Ohalo programme | Crop validation | 2 | Replicated controlled strawberry disease assays; field testing is a future step. No field commercialization or other-crop validation is inferred. [Original collaborator report](https://member.floridastrawberry.org/wp-content/uploads/2025/11/14_FSREF_report_2024-25_S-Lee_2_neopestalotiopsis-resistance.pdf). |

The research does not support an industry league table. Most scopes lack sufficient inspected anchor evidence; compatible, common-period peer comparisons remain sparse. Rights, retail listings, laboratory results, production claims and forecasts retain their distinct meanings.

## Views and isolated preview

`/competitive-evaluation` provides scoped cells and evidence, overview/gaps, selectable numeric/categorical axes, directed relationships, company-specific exposures, people/jobs/events, import resolution and immutable cited comparisons. Saved comparisons link through the existing living-workspace landscape interface; a feed refresh does not rewrite a saved narrative or add feed results to a briefing's source set.

`/coverage/archive` filters the full accessible captured archive before pagination. Company ANY matching is separate from Tags All/Any and from company/shared focus. Explicit enabling connections explain relevance; company ownership alone does not propagate coverage. The shared shell exposes this panel on existing competitor, entity, Landscape/Explorer, Pulse, whitespace and workspace surfaces. Static output excludes the private component and research data. The route checklist records verification separately.

```powershell
python -m scripts.preview_competitive_evaluation --clone-from inbox --inbox competitive-preview/inbox --port 8770
```

The preview copies shared workspace objects/history and the selected public-source metadata captures into a separate inbox only when it does not already exist. It excludes account/provider configuration, disables paid-provider keys and background polling, binds loopback only, and visibly labels rehearsal decisions. Existing main workspace decisions are unaffected. This is a local review preview, not production deployment.

Integrated browser, full-suite, static-safety and current-head PR receipts remain required before final delivery; focused checks alone do not close the mission.
