# Test results

## Required focused validation

| Gate | Result | Evidence |
|---|---|---|
| Claude profile/identity/relationship sweep | **147 passed**, 1 warning, 81.77s | `claude-147-tests.txt` |
| Prior Wave 2 focused suite | **282 passed**, 17 warnings, 123.68s | `wave2-focused-tests.txt` |
| Record validation | **passed** | `record-validation.txt` |
| Static build | **passed**; 1,665 pages; Pagefind completed; unpublished-draft leak check passed | `static-build.txt` |

The focused tests verify 33/33 roster resolution, 33/33 profiles, structurally valid profiles, Unknown/Unassigned semantics, monitoring/integrity separation, identity redirects and duplicate audits, filtered competitor links, Daily Briefing content honesty, in-app reader behavior, absence of production fixture dependency, and the trust prototype's lack of production mutation wiring.

## Full suite

The full suite ran to completion:

- **2,823 passed**
- **16 failed**
- **5 errors**
- 3,771 warnings
- 1,083.86 seconds

The exact failing selection was rerun against frozen base `85a157233674ee5cd3d2e358ea02924d3ac04790` and reproduced identically: **16 failed, 5 errors**. This rules out the Claude delta as their cause.

Inherited categories:

- Five package-export setup errors and one exporter failure: existing `orphan_check is not empty` validation state.
- Three fixed-count failures: Wave 2 has 205 Sources versus older tests expecting 201; 255 relationships versus an older expected count.
- Multiple `/today` and navigation assertions expect the pre-Daily-Briefing front page and legacy navigation.
- One provider/front-page expectation still expects draft material in an older `top_stories` contract.
- One story-thread triage expectation is unchanged from the base and fails there identically.

No full-suite failure names `competitor_profile.py`, `test_competitor_profile_v1.py`, or `test_profile_completeness_semantics_v1.py`.

Captured evidence:

- `full-suite.txt`
- `base-failure-reproduction.txt`
- `verification-summary.json`

## State verification

- Canonical roster rows: 33.
- Profiles returned: 33; `None` profiles: 0.
- Structurally valid: 33.
- Missing required data: 0.
- Invalid references: 0.
- Blocking profile defects: 0.
- Provisional identities: 9.
- Default Blueberry landscape: 33 of 33.
- Missing expected landscape labels: 0.
- Canonical/live/generated data changes from the R1 base: 0.
