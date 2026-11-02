# April–October 2026 patent variety research integration

User-authorised local import into the selected `berry-bounded-rehearsals`
snapshot, with existing publication and identity trust boundaries retained.
This is a local authoring database update, not a production deployment or a
published catalog promotion.

- 340 photographed patent/PBR rows, retained as 276 input research groups.
- 257 named profile destinations: 15 existing catalog pages gain private
  research sections; 242 missing names have persistent unverified research pages.
- The two resolved Swiss applications join the same literal cultivar codes
  already represented elsewhere in the packet. They do not create duplicate pages.
- 17 missing-name application leads remain in the unresolved worklist.
- 62 groups / 90 rows have source-supported commercial contact routes, with
  nursery, licensing and programme roles labelled separately.
- 215 source-page captures and publisher image references retain source credits.
  Unknown reuse remains labelled and publisher photographs are links, not
  silently approved portraits. Captures are explicitly source-page evidence.
- 15 previously absent commercial contact entities have unverified private
  records. Existing organizations reuse their IDs; no trusted role edges added.

## Persistence and navigation

`/varieties/research` is linked from the normal variety directory. It searches
names, codes, companies and application numbers, and filters by crop or existing
versus new page. New pages use the normal `/entities/variety/{id}` route and
display unverified identity status. Existing catalog identity fields are not
rewritten from proposed source aliases.

`scripts/import_patent_variety_research.py` installs the hashed, immutable packet
under `inbox/variety_research/imports/{batch}/`. The compact manifest maps actual
entity IDs to dossiers; individual profile JSON files keep all source rows,
summaries, proposed aliases, company contacts, availability caveats, prior
database references, sources and captures. The manifest is written last so a
partial installation is not visible. Replaying the same packet returns the
existing receipt without overwriting subsequent analyst edits. A new packet
creates a new dated/hash-addressed batch.

The additive `source_sheet_rows.json` sidecar preserves all fourteen original
photo columns for all 340 rows, including grants, dates, countries, legal parties
and transcription-review warnings. Its source SHA256 is recorded. These rows
are explicitly labelled unverified photo transcription inside the research
section, never silently presented as approved registry facts or growing regions.

The source packet is `outputs/01a19784-119c-72c2-89e1-62ff346b59e6/Variety_Research/research-data.json`
in the parent workspace. Its SHA256 is recorded in the manifest. No article
bodies or extraction output enter the tracked source tree. Runtime contents
are gitignored and require runtime backup when moving to another machine.

## Trust and safety

Private research entities do not enter `all_entities()`, canonical repositories,
Facts, active company-role edges, commercial footprints, region maps, trusted
coverage counts, global published search or the static builder. The private
entity fallback resolves only exact, persisted IDs, and only in authoring mode.
Existing pages read dossiers by their canonical ID. No inferred fuzzy-name
merges or human approval markers are generated. Missing crop identity and the
CIVH725 strawberry-versus-raspberry conflict remain visible holds.

The route, template and capture endpoint independently enforce private access.
Capture names must be on the import allowlist and resolve within that batch's
capture directory. Responses carry `private, no-store` and `noindex` headers.
No source or commercial entity is automatically enrolled in monitoring.

## Validation

The installer records equal SHA256 fingerprints for canonical JSON data before
and after installation. Replay must preserve dossier bytes and analyst notes.
Targeted tests cover crop separation, resolved-name deduplication, missing-name
holds, private-only rendering, HTTP access, capture traversal and idempotence.
Browser checks cover an existing profile, new strawberry profile, identity
conflict, commercial-contact search, and source-image captures. Repository record
validation, full tests and the static build provide the broader checks; retain
their actual results with the local delivery receipt.

Local validation on November 1: 5,293 full-suite tests passed, 10 skipped;
64 focused navigation/photo/import regressions passed, and 11 final import tests
passed. Record validation passed. The static build produced 1,797 pages with
zero imported-private identifiers or capture routes in the generated HTML.
Browser checks passed for existing/new profiles, crop-conflict warnings,
commercial contacts and filters; the 412-pixel directory has no page-wide overflow.
