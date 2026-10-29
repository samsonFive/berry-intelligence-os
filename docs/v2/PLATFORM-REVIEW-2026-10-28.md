# Platform review candidate — October 28, 2026

This candidate brings five platform follow-ups together for one release review.
It starts from canonical `e24b566b`; it excludes catalog imports, new photo
references, patent observations and their review decisions. Production remains
on its recovered, unchanged release. Component notes elsewhere retain their
original dates; they do not prove this combined candidate is deployed or tested.

| Component | Result | Frozen source head |
| --- | --- | --- |
| #410 | Load private variety-name checks on demand; avoid repeated photo matching in coverage and repeated Reader display work | `bf31b8fe85cb2f87c2547dbf57a2a2d5e1cd6be7` |
| #412 | Keep Workspaces, company lists/marks and research shared; scope Digest saves, progress, position and subscriptions to the signed-in account | `78e03e31e9da08662d5bacdef285a9ec0d400efb` |
| #414 | Keep section destinations below the actual wrapped header | `95eaa71bf4551bd448e2ff9e0fe4b5e41696034d` |
| #416 | Serialize and limit offline VPS review containers, with a production-health and capacity preflight | `6d5c4b5494bafb21ee7883fdf09cbd48bab3d05f` |
| #420 | Explain shared Workspaces, the analyst workflow and cited Markdown/JSON exports in Help | `78c6bb2ba1a40edb894eb3e5ce0244116afab527` |

The Digest's configured original analyst retains access to older saves and
reading state. Those original fields remain stored; new account-specific edits
use the same authoritative stores. Other accounts start with their own empty
Digest. This does not invent historical authorship or introduce private
Workspace ownership. Layouts remain personal. Login and human review gates stay.

Integration preserves all dated component notes. The overlapping guide changes
are reconciled into one featured Workspaces explanation, twelve other section
cards and six existing reporting cards, plus the Workspace export panel. Shared
research, personal reading and analyst annotation wording remain consistent.
The public snapshot receives descriptions without live Workspaces links or
private research. No source images are loaded or published by this change.

All 31 accepted requirement definitions and the immutable expansion guide are
preserved. Component tests and browser evidence remain useful; combined tests,
native review, exact-head required CI, isolated current-data preservation and
release approval must apply to this candidate before shipping. Release-time
backup, account/mount checks and rollback remain required. The bounded rehearsal
script is tooling; including it does not itself change live container limits or
prove the VPS can support another public preview.

Catalog #399/#400/#418/#419 remains separate. Complete global/historical catalog
coverage, original current-rights verification, source/identity/image-use
decisions, the independent human worksheet, unclear photo cells, wider Learn
and statistics content and remaining performance work are not declared complete.
