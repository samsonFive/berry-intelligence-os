# Cultivar planting evidence integration

The November 2026 strawberry study can now enter the existing private platform
without converting catalogs, trials or commercial estimates into approved facts.
The source-native research is a review projection, distinct from Market Reality.

## Delivered research and initial live registration

On 15 November 2026 the regional report (11 pages), audit (10 pages) and workbook
were installed additively in the persistent private finished-report library.
Two entries were appended; 22 prior combined report readers and 103 preexisting
files were preserved. The combined library contains 24 reports. Anonymous reads
redirected to login, authenticated PDF/XLSX bytes matched their authored hashes,
and research notes were not exposed by the report routes.

The live research artifacts are:

- `/reports/library/strawberry-regional-varieties-final`
- `/reports/library/strawberry-platform-audit-final`

This registration is independent of the code release below. It does not approve
an Evidence record or any claim.

## Why a narrow new private contract was required

The live Market Observation schema represents named authoritative crop statistics
without an analyst claim-review step. It has no cultivar, denominator, plant-share
or plant-count dimension, and its revision key omits cultivar/source dataset.
Adding breeder estimates to that store would conflate distinct trust and
measurement semantics. Retail `commercial_observation` also cannot represent a
planting census faithfully. Neither model was changed.

`schemas/cultivar-measurement.schema.json` instead validates private source-bound
proposals in `inbox/cultivar_measurements/`. These are not a new trusted object.
An approved projection requires an exact active Fact/Claim created through the
existing source-publication and individual Fact/Claim review gate. An approved
source alone never approves a measurement.

## Data and import contract

`scripts/import_strawberry_research.py` builds or stages a versioned packet.
Import is dry-run by default and requires explicit source and destination paths.
New source-publication drafts require an explicit substantive-source allowlist.
Owner pages, access inventories, a blank levy form and an indexed-only supplier
lead are retained as acquisition/context references rather than silently becoming
supporting publications.

The frozen research packet contains:

| Content | Count / scope |
| --- | --- |
| Source-native observations | 613, including history, trials and extra geography context |
| Numeric observations | 184; these are not all planting shares |
| Source/access entries | 190 across 178 exact document URL groups |
| Substantive publication-eligible documents | 117; eligible only for pending source review |
| Retained primary-capture documents | 28 |
| Original/visual capture artifacts | 39, 245,173,188 bytes |
| Selectable source-text extracts | 15, all explicitly partial |
| Regional conclusions / acquisition requests | 15 requested regions |

The packet digest is
`52ec5e856fc06c234795adbf4be1d65004664004c0d3522f5597068fe2e89c1e`.
The complete private packet and research text are not committed to this repository.

Packet layout is
`inbox/cultivar_measurement_imports/<batch>/packet.json`, the original ledger,
hash-addressed `artifacts/`, supporting audit/backlog files and append-only source
binding snapshots. Copies refuse symlink escapes and conflicting destination
bytes. Existing source publications/drafts are reused only when deterministic
document identity/version checks permit it. Reviewed state is never copied from
one source version to another. No source registry or recurring acquisition
schedule is auto-enabled.

Every observation retains its literal cultivar label, record kind, exact region
and surveyed population, crop period, metric, value, unit, denominator, cohort,
production system, source references and original row. Unknowns remain unknown;
values are not normalized to make incompatible populations comparable. The series
key includes cultivar or aggregate, source dataset, metric, unit, denominator,
place, period and cohort. Revised content creates a new immutable proposal ID.

Multiple candidate identities remain holds, even if an earlier ledger preferred
one ID. A human may select one existing, same-crop candidate for this observation.
That creates an audited revised proposal, preserves the original, and changes no
catalog alias or entity status. Import replay preserves those human revisions and
their review events. Different crops with the same commercial name never match.

## Private workspace and trust controls

`/variety-plantings` filters by berry, region, cultivar, text and review state.
Variety profiles, the variety directory, geography profiles and Reports link to
it without making new planting or growing-region claims in the entity graph.
Detail pages show the exact population, period, unit and denominator beside the
source locator, original-source link and registered retained captures. Capture
downloads verify size/hash and stay session-protected, path-confined, no-store
and attachment-only; imported HTML is not executed as an in-app reader.

Numeric list rows also display the original attributed claim beside the scalar
and basis, preserving qualifications such as "more than", "approximately" and
commercial estimates without inferring a new numeric operator or editing the
source-native ledger.

Approval is one proposition at a time. The reviewer must select its primary
substantive source, confirm the individual proposition and source passage, and
supply exact version confirmation where a retained hash cannot establish it.
The authenticated session identity wins over a posted reviewer name. Stale form
hashes fail closed. Pending, blocked, deferred, rejected, superseded and reviewed
states are distinct. No bulk approval or automatic extraction is introduced.

`ReviewPublishService.approve_claim()` received only an optional explicit entity
scope. Existing callers retain their prior behavior. A source containing many
cultivars no longer forces a measurement Fact to inherit every cultivar in that
source. The measurement wrapper supplies only the crop and selected cultivar.
Later changes to source content, the linked active Fact or identity dependencies
invalidate the reviewed projection; they do not silently withdraw the canonical
Fact. Existing Fact governance remains responsible for that separate decision.

List views use streaming publication previews and hydrate full source bodies only
for active measurement-origin Fact dependencies. They do not read retained binary
captures. Existing social-deletion exclusion behavior is preserved; its rare
transitive full-repository scan remains separately tracked performance debt.

## Acquisition and completion boundary

The imported backlog specifies the owner route, required dataset, denominator,
coverage fields and current unresolved conclusion for every requested region.
It is visible in the planting workspace and remains unacquired until actual
authorized data arrive. Current national Portugal ordering and a current named
Pemberton leader remain unresolved; complete current cultivar distributions are
also absent for several other regions. Restricted CSC/CSO tables and private
grower/nursery returns were not fabricated or replaced by trial lists.

No external organization was contacted, paid report purchased or recurring
automation created. Those acquisition actions remain separate from this
authorized platform implementation. All new research initially remains pending
human claim review, as required by the existing trust rules.

## Validation and release requirements

Acceptance covers import/replay with canonical bytes unchanged, preservation of
identity-review descendants, crop collisions, source-version changes, partial
bodies, all record kinds, no automatic trust, individual review CAS, narrowed
Fact scope, anonymous/read-only protection, capture confinement and exact bytes.
The initial 613-row local rehearsal created 117 schema-valid source drafts and
reused all 613 observations on replay while all 3,393 canonical JSON files stayed
unchanged. These are local rehearsal counts, not a claim about the live import.

The code release requires the normal full suite, record validation, static build
and private-leak check, exact-head GitHub checks, canonical merge and production
smoke. Runtime data/inbox mounts, the paired command sidecar, existing report
catalog and all human review state must be preserved. The release receipt records
actual live import counts and post-install replay separately.
