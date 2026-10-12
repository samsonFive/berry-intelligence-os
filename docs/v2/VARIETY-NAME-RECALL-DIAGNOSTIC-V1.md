# Variety-name recall: measured gaps and summary repairs

The Hortifrut omission exposed a wider problem: names can be visible in a source
without being discovered, reconciled or represented in the catalog. Manually
accounting for 381 portfolio occurrences does not demonstrate automated recall.
This pass adds a repeatable diagnostic and fixes two summary defects. It does
not approve varieties.

## Scope and results

`benchmarks/variety-name-recall-v1.json` contains 24 offline cases and 64 expected
name occurrences across all four berries. Expected lists were authored separately
from discovery output. Positive cases use checked factual names from
[Hortifrut](https://www.hortifrut.com/innovation/genetic-development/),
[NIWA](https://en.niwabrzezna.pl/varieties/),
[ABZ](https://www.abzseeds.com/semi-double-flower) and
[Vissers](https://www.vissers.com/en/raspberryplants). Prose, tables and translations
are synthetic paraphrases, not captured live article bodies. Identity, geography,
generic-type and packaging controls are invented and labeled separately.

This agent-curated diagnostic is **not independently human-verified**, the Atomic
Evidence Gold Set, or extraction/model qualification. It does not test live
capture, PDF/OCR, statistical web coverage or authoritative rights verification.
Its 64 expected occurrences are unrelated to the 64 canonical catalog entries.

| Diagnostic | Before | After |
|---|---:|---:|
| Cases satisfying every specified check | 18 / 24 | 20 / 24 |
| Expected occurrences detected | 46 / 64 | 50 / 64 |
| Expected occurrences missed | 18 | 14 |
| Unexpected names returned | 1 | 0 |
| Detected names correct on specified checks | 46 | 50 |

These fixture-specific ratios are not global completeness scores. Unsupported
cases stay in the denominator. Detection, berry, code, catalog link, decision
state and provenance errors are separate. Two ambiguous/cross-species observations
remain unresolved. A correct observation cannot hide an extra wrong species
assignment. Source URLs are compared unchanged.

## Repairs and gaps

Explicit quoted code pairs accept internal spaces, preserving `NR 1849002` and
`NR 1616002`. Bounded explicit-summary parsing preserves long F1 labels, including
`Summer Breeze Cherry Blossom F1`, and refuses an over-limit prefix instead of
inventing a shortened identity. Existing licensed-list and quote tests still pass.
This read-only discovery does not establish denominations, releases or aliases.

| Still unsupported | Missed names | Next step |
|---|---:|---|
| Mixed-berry table | 4 | Capture row/species context through existing intake and qualified extraction; reconcile every row. |
| Spanish declaration | 3 | Add independently reviewed multilingual captures through the approved extraction path. |
| Polish declaration | 3 | Preserve language, species and code context; expand reviewed fixtures. |
| Article-body-only declaration | 4 | Acquire usable publication content and extract explicit names through qualified workflows. Summaries cannot replace sources. |

A diagnostic command can succeed while reporting failed cases. It never qualifies
a model. Add independently reviewed captures before operational targets; never
generate expected names from extractor output. Expand historic/public-domain,
university, rights, PDF and OCR coverage. Keep the existing missed-intelligence
classifier intact: this fixture is outside `data/imports/*/benchmark.json`.

Marking distinct is not catalog creation. Current publication commands link
existing entities without creating them; legacy review has a separate unverified
match/create path. Do not use a legacy shortcut to inflate catalog counts. A
concrete reviewed canonical-authoring handoff remains necessary and open.

## Validation and repeatability

```powershell
python scripts/audit_variety_name_recall.py --output artifacts/variety-name-recall/diagnostic.json
python scripts/audit_variety_catalog_coverage.py --output artifacts/variety-name-recall/stored-corpus-audit.json
python scripts/audit_variety_portfolios.py --output artifacts/variety-name-recall/portfolio-audit.json
```

Reports include fixture SHA-256 and crop/format/language breakdowns. The CLI
refuses output inside canonical `data/`, `benchmarks/`, or its input fixture.
It does not read/write operator inboxes, invoke providers, acquire sources or
change decisions. Reports contain synthetic snippets, not copied article bodies.
`baseline.json` and `diagnostic.json` retain actual before/after results.

89 focused recall/corpus/portfolio/universe/navigation tests passed with one
existing ReportLab warning in 73.62 seconds. Record validation passed. Stored
counts stay 99 identities / 31 matches / 68 candidates; primary counts stay
381 occurrences / 25 matches / 356 review needs; combined keys stay 341 before
private state. Canonical varieties, edits and guide are unchanged. Required
exact-head CI is recorded with the draft PR.

CAT-01/CAT-02 and TD-116 stay open. Human trust gates, blueberry Landscape
checkpoint and release review remain required. No merge or deployment occurred.
