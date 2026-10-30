# Keep source gaps visible after names are found

The Perfection Fresh browser review exposed a misleading coverage badge.
Its scoped view showed one entry with named varieties and eight incomplete
source checks, beside “0 entries · checked, list incomplete.” That zero came
from a different count: entries with only partial source coverage. Finding
names moved the company out of that bucket without finishing its other checks.

The displayed gap count now uses the existing `has_source_gaps` flag on the
filtered subject rows. Perfection therefore shows one entry with source gaps
alongside its named-variety count and the eight individual incomplete checks.
The caption explains that names found and source gaps can overlap. Counts
remain scoped to the selected company, berry and source search.

This changes only the shared coverage partial. No service, domain schema,
source status, machine-readable counter, candidate, catalog record, review
decision, source text or photo permission is changed. The existing partial-only
metric remains available to its callers; the badge no longer mislabels it as
every incomplete portfolio. Empty/unreadable/identity-held states retain their
own labels. The counters do not claim complete current or historical coverage.

Focused checks cover the real named-company case, singular/plural rendering,
filtered subject counts rather than source-row totals, unchanged input data,
live rendering without private writes, and the existing public-output guard.
All 44 focused checks pass with one existing warning in 53.26 seconds.
Native desktop/412px review shows one named entry and one entry with source
gaps, alongside the eight incomplete source checks. Selecting Blueberry keeps
Perfection in scope and shows zero names with three open checks. Both phone
views fit within 397px at a 412px viewport. Exact-head CI remains required.

This child follows source #435 on tested catalog/platform #434. Their frozen
heads, preservation proofs and actual pending release questions are unchanged.
A changed intended release still requires current canonical reconciliation,
fresh checks/live-data preservation and the user’s release approval. This
presentation correction does not close CAT-01/CAT-02 or source/content debt.
