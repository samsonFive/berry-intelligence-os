# Editable, populated variety catalog

The operator's November 3 instruction is to turn the accumulated spreadsheet
images and research into real catalog records, with editable fields and the
ability to remove a whole variety. Earlier candidate-workflow completion did
not deliver that outcome: production had 65 entities despite 257 private
research profiles and the separate spreadsheet/source inventories.

This change authors persistent **unverified workspace catalog entities**.
Catalog membership no longer requires pretending that an identity or every
attached claim has been independently approved. Publication review, Atomic
Evidence qualification, reviewed Facts, image reuse and reviewed relationship
decisions remain separate. The import does not mark candidates reviewed,
create Facts, publish Evidence, approve aliases, or activate company roles.

## Product behavior

- Add variety and Edit actions are available from the directory and profiles.
- Edit name, crop, aliases, status, description, denomination, commercial name,
  codes, breeder, parentage, origin, geography notes and rights pointers.
- Add/edit/remove rows for source references, commercial connections with
  precise roles and territories, rights references and performance notes.
- Add custom fields; preserve the types of existing structured attributes.
- Use the existing photo and growing-region editors from the same page.
- Explicitly review published supporting sources to add or edit a canonical
  relationship. Active/historical/disputed remain the existing vocabulary.
  Historical removes an active role without discarding its source history.
- Remove an entire variety after typing its name. The row and profile disappear;
  Removed varieties restores it. Original evidence is retained for provenance.
- Save conflicts fail visibly rather than overwrite another editor. Private
  change history retains editor, time and exact before/after records.
- Status/company/crop/search filters and 100-row pages support the larger set.
  Attributed connections remain visibly separate from reviewed graph roles.

## Population and preservation

`scripts/populate_variety_catalog.py` plans first, then applies a specific
digest-bound plan. It uses the existing entity repository's validated bulk
create hook. A durable private batch journal precedes writes; interrupted
imports can be replayed without overwriting existing records or edits.

The captured live baseline produced a plan with **1,167 new unverified variety
entities**, **73 unverified organization entities**, and private enrichment for
**59 existing profiles**: **1,232 varieties** overall. The first isolated
rehearsal preserved all **2,935 pre-existing data JSON files byte for byte**.
These are the isolated copy's preservation denominator, not a claim about every
production runtime file, database or account. Production release must use a
fresh complete backup and its actual preservation inventory.

The new variety set spans 322 blueberries, 490 strawberries, 237 raspberries
and 118 blackberries. 902 have source-attributed organization connections;
222 have photographed patent/PBR application references. Public URLs and
original spreadsheet references remain distinguishable. An organization named
in a rights source is not relabeled as a commercial supplier.

525 **source occurrences** are held, not 525 distinct missing varieties.
Holds retain explicit identity issues, unclear/short labels, source warnings,
rejected identities, saved unresolved decisions and ambiguous matches.
Exact crop-scoped name/code reconciliation does not use fuzzy identity merges.
Source-reported codes/trade names on newly added unverified entries remain
attributed; existing canonical identities and bytes are not rewritten.

The complete original research/transcriptions remain in the existing private
research store. New research IDs preserve their existing profile links.
Workspace additions, private enrichment and edit history are excluded from
the public static snapshot. No private research runtime is committed.

## Acceptance state

The initial 49 focused checks and a wider 156-check catalog/identity/research/
static regression passed locally. Final-head verification must include the
later relationship, source-provenance, filtering and bulk-journal changes.
Record validation passed. The isolated import completed in 8.8 seconds using
the existing bulk repository hook. These are local measurements, not production
page latency or worldwide catalog-completeness claims.

Local browser automation currently reports disabled in Work settings. The
operator selected enabling browser access; the tool continued to report it
disabled. Do not claim a native visual review until it actually succeeds.
Final CI, final isolated workflow/preservation, visual review and any required
scoped release decision remain to be recorded before calling this live.
