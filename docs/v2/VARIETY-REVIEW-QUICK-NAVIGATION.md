# Keep variety review navigation within reach

The long candidate queue now keeps its alphabet below the shared header while
scrolling. Letter selection uses the existing server filter and lands at the
results, retaining search, berry, company, identity status and source scope.
List top and Filters are always available alongside it. On phones, the same
letters use a compact native picker; without JavaScript, the alphabet remains
available as horizontally scrollable links. Candidate anchors clear both bars.
The actual wrapped header and navigation height determine their offset.

## Patent and registry click-through

Variety profiles already retain a Rights / IP section linking stored patent
entities and rights publications through the shared Reader. Candidate review
now adds a named original-record link for a stored tier-1 patent/PVR or registry
source and shows recorded application, grant and expiry dates when present.
The source URL remains unchanged. A registry index remains an index; this UI
does not manufacture an individual patent link or upgrade a breeder catalog.
Candidate identity and legal status still require review.

Users can inspect claims in an available original patent document. Comprehensive
original-document links, claim-level provenance, refresh reconciliation and
dated jurisdiction/status verification remain open under CAT-02 / TD-116.
This slice adds no legal conclusions, claim extraction, retrieval pipeline,
schema, source observations, human review decisions or trusted entities.
The catalog remains 64; primary observations 506 in 46 sections; combined
derived candidate keys 423 before private state.

## Verification

Seventy navigation, catalog-handoff and portfolio tests pass, with one existing
ReportLab warning. Tests cover every retained filter, the special `#` letter,
original patent/registry versus breeder links, recorded dates, unreviewed
status and no writes. Record validation and JavaScript syntax checks pass.
The static build writes 1,755 pages and passes unpublished-content validation.
Native desktop review checked the full 423-name queue at its bottom: navigation
top 64px, shared header bottom 63.33px, no horizontal page overflow. Native
phone review checked the wrapped header (121px) and compact letter picker,
changed M to B and inspected Barbara Ann's unchanged CFIA source URL. Phone
content/scroll widths both measured 360px. Desktop Blueberry scope survived
letter M selection. List top and Filters return to their existing anchors.
Screenshots and source-review preparation remain in ignored private storage.

Parent #329 passed all four exact-head checks, run 37683669650: 4,102 passed /
11 skipped / two warnings. This draft's full CI is pending at this commit.
Current canonical remains `7962ac04dd05855985f51596f3f8070f19990a75` after
fetch; PR #312 is merged. No merge, deployment or other-berry Landscape rollout
occurred. Primary company-source work prepared alongside this fix is still
private research, not imported observations or closed portfolio checks.
