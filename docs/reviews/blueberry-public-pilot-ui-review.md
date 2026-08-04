# UI/data review — `blueberry-public-pilot-2026-08-03`

Manual inspection of the running application after `import_package.py --apply`
(674 files written, all evidence `status: in_review`), before `--approve`.
Branch `data/blueberry-public-pilot-2026-08-03`. This is an observation
record, not a redesign — no interface changes were made as part of this
review.

## Routes/screens inspected

`/`, `/?q=hortifrut`, `/?berry=berry-blueberry`, `/work-queue`, `/review`,
`/entities/company`, `/entities/variety`, `/entities/patent`,
`/entities/company/company-berry-blue-llc`, `/entities/variety/variety-bonita`,
`/entities/variety/variety-arana`, `/entities/patent/patent-uspp025358p3`,
`/evidence/ev-hortifrut-integrated-report-2023`, `/strategic-questions`,
`/signals`, `/api/feed`, `/api/search?q=hortifrut`.

No server errors and no 404s were observed on any of the above.

## Findings

### 1. Missing UI support — no queue surfaces `in_review` evidence for review

**Severity: high — this is the main gap for actually reviewing 121 records.**

`/work-queue`'s "Awaiting review" panel and the dedicated `/review` queue
both read only `inbox/` (draft) records via `list_drafts()`. Neither is aware
of `data/evidence` records sitting at `status: "in_review"`. After `--apply`,
`/work-queue` reports **"Awaiting review (0)" / "Nothing waiting for
review."** even though 121 records need exactly that.

The records are not hidden — `/evidence/{id}` renders any evidence
regardless of status and clearly labels it (`Status: in_review`) — but there
is no listing page to discover them from. A reviewer currently has to know
IDs in advance or search `data/evidence/*.json` outside the app.

This is a direct consequence of the app's review workflow being built around
one path only (intake → `inbox/` draft → `/review/{id}` → publish). Bulk
import writes straight into `data/` at `in_review`, which is a second,
valid-per-schema path the UI never anticipated.

**Not fixed in this task** (out of scope — "do not redesign the interface
during this task"). Flagging as the top priority for before routine bulk
imports become normal.

### 2. Missing UI support — entity pages hide facts' supporting evidence while it's unpublished

**Severity: medium.**

On an entity detail page, `linked_facts` displays regardless of the
underlying evidence's status, but `linked_evidence` (and the derived "Trust
summary" counts) is filtered to `published_evidence()` only. Example:
`/entities/variety/variety-bonita` shows 2 facts (correctly, including the
patent mis-citation correction) but "Linked evidence: No published evidence
links to this entity yet" and a trust summary of "0 linked evidence / 0
independent sources." The provenance chain looks broken during the review
window even though the evidence exists and is one click away by direct URL.

### 3. Usability improvement — disputed facts are not visually distinguished

**Severity: low-medium, but worth prioritizing given real data now has it.**

Fact status (`active`/`disputed`/`superseded`/`withdrawn`) is appended as
plain text after the reviewer/date line — e.g. "Reviewed by ... · disputed"
— with the same styling as "· active". Confirmed on
`/entities/company/company-berry-blue-llc`, where a real disputed fact
(conflicting Hortifrut/MBG ownership claims) reads identically to the active
facts around it apart from that one word. `DESIGN-SYSTEM.md` calls for
status to be visible without relying on a single easy-to-miss cue; this is
the first real disputed data the app has rendered, and the gap is now
concrete rather than theoretical.

### 4. Not an issue, but worth knowing — filter options stay empty until approval

The newsfeed's Competitor/Geography filter dropdowns derive their options
from `published_evidence()`, so none of the 32 imported companies or 16
imported geographies appear as filter choices until their evidence is
approved. This is correct, consistent behavior (same rule as the feed
itself), not a defect — noted so it isn't mistaken for one during review.

## What was not found

- No data-quality issues beyond what the package's own `qa-report.md` and
  `coverage-gaps.md` already surface and explain (mis-cited patent number,
  disputed Berry Blue ownership, unverified patents/varieties, uneven
  geographic coverage). Independent spot checks did not turn up anything the
  package's own QA missed.
- No rendering bugs — no exceptions, no broken layout, no 404s across every
  route listed above.
- No schema violations — confirmed separately by `scripts/validate_records.py`
  passing clean after import.
- Schema limitations (relationship confidence encoded in `notes`, trait
  provenance not read anywhere in the app, no signal schema, etc.) are
  already fully catalogued in the package's own `schema-assessment.md`
  (L-1…L-10) and are not repeated here.

## Confirmed correct

- Imported entities are visible and browsable (indexes and detail pages for
  company, variety, patent all render).
- Evidence is reachable for review at its direct URL, correctly labeled
  `in_review`.
- Imported evidence is **not** visible in the published feed, `/api/feed`,
  or `/api/search` (feed stayed at 3 of 3 throughout; `/api/feed` returned
  exactly 3 records).
- Entity links resolve — no 404s encountered on any linked entity.
- Unverified patent and variety entities retain `status: "unverified"`
  (checked `patent-uspp012165p2` on the index and
  `/entities/variety/variety-arana` directly).
- A `historical`-status patent (the mis-cited Aglaonema record,
  `patent-uspp025358p3`) renders correctly and distinctly from
  `active`/`unverified`.
- No company is visually privileged — the company index renders all 32
  entities with identical card styling; roles (breeder, licensor, grower,
  marketer, etc.) are shown as plain text, not as a "competitor vs. us"
  distinction.
