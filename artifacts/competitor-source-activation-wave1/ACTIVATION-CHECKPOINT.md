# Competitor Source Activation Wave 1 — checkpoint

Date: 2026-09-15

Branch: `feature/competitor-source-activation-wave1`
Base: `031c9b6a80bd72ce3f271933d8a1ea302decb077`
Research source commit: `da8740cf10660831ecfa5287b15fdb9f6e6c53ee`
Cherry-picked research commit: `49b4db74cc764659f74464e4d7c5484b907b05b7`
Implementation commit: `84f5b4e99e036e123bbee9a1a295f3e2efe32737`

## Implemented

- Reconciled all 12 Wave 1 roster entries to canonical IDs.
- Reused existing linked Sources for eight entries; added the missing canonical link to the existing University of Florida blueberry-breeding sitemap.
- Added four Source records with retained research provenance.
- Fruitist and Oishii are runnable but remain distinct from operational until execution.
- OZblu and Wish Farms are `OPERATOR_ACTION_REQUIRED` after fresh HTTP 403 observations; neither is runnable.
- Added a per-run discovery persistence cap exposed by `scripts/run_collection.py --max-discoveries`.
- Corrected competitor monitoring state to consume gitignored discovery runtime, so successful execution no longer remains labeled never-run.
- Corrected the static-build integration call so the competitor audit receives Source data while its build-time inbox remains deliberately empty; this prevents private drafts from leaking into generated pages.
- Added UC Davis to the explicit blocked-entity presentation based on the research checkpoint; no Source was configured.
- Left California Giant blocked and unconfigured for automated discovery.

## Measured canary

Five permitted Sources ran separately with a five-discovery pre-persistence cap and four-item processing cap. Totals: 25 discoveries, 5 discovery states, 5 run records, 20 operation items, 11 acquisition outcomes, and 10 private unapproved drafts. Eight bodies were readable; three Oishii pages were navigation-only shells. No retryable outcomes occurred.

## Maturity

Across the 33-entry canonical roster:

- represented: 33 → 33
- configured: 8 → 10
- operational: 0 → 5
- readable: 0 → 4
- current usable coverage: 0 → 0
- blocked states expressed: 1 → 4

Current coverage did not rise because the canary never approved or published a draft.

## Data integrity

Tracked changes are Source configuration, boundedness code, tests, documentation, and redacted audits. Every live canary record is under gitignored `inbox/` and is excluded from commits. Competitor identities, tiers, priorities, regions, company/genetics assertions, and trusted Evidence were not changed.

Focused validation passed after the final static-build fix. Record validation passed, and a complete static build produced 1,665 pages with its unpublished-draft leak check passing. The full test suite was not run.

FIRST-WAVE ROSTER: 12/12 reconciled
DUPLICATE SOURCE RECORDS CREATED: 0
CANARY DISCOVERIES: 25
LIVE CANARY RECORDS COMMITTED: 0
PUBLISHED OR APPROVED: 0
