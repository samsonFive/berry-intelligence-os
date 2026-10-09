# Historical public-program releases: four-berry review

The official Oregon State University release list adds **45 source entries**
to the existing identity-review workspace: 19 blackberry, 11 strawberry,
9 red raspberry and 6 blueberry. This finds **39 additional candidate keys**;
six entries add provenance to keys already present. It creates no canonical
varieties, approved roles, traits, growing regions, current rights or review
decisions. The 64-entry canonical catalog is unchanged.

Review branch: `feature/public-program-release-coverage`, stacked on
`feature/blueberry-review-handoff`.

## What was checked

[Oregon State University — Small Fruit Breeding Program](https://plantbreeding.oregonstate.edu/plantbreeding/research/small-fruit-breeding-program),
the **Publications & Varieties Released** section, checked October 9, 2026.
The web reader and original browser DOM independently supplied the same four
lists. The original accordion link updated its fragment but did not visibly
expand; this limitation is retained. No access restriction was bypassed.

All 45 bullet entries are accounted for. Code/name pairs remain one observed
entry each: APF-77 / Black Magic, ORUS 2240-1 / Sweet Sunrise, and ORUS 2262-2 /
Charm. Schwartz / Puget Summer remains an unreviewed pairing. Unpaired codes
ORUS 2427-4 and ORUS 1939-4 are retained literally, without guessed cultivar
names. Perpetua is retained despite its ornamental context.

The list credits other primary releasing institutions on several entries.
No company/institution identity is created just to attach this source, and
`company_ids` stays empty. Original credit wording is available in each
entry's source context. Site publication does not assign a breeder, owner
or licensee. The Onyx reference to USPP 22,358 is historical source wording,
not verification of today's legal status.

Release years remain attributed text, not invented ISO publication dates.
The list ends with 2015 releases; **current and lifetime coverage remains
incomplete**. No generic group photo is assigned to a cultivar. No full article
body or private review state is committed.

## Review in the app

The current PC preview is `http://127.0.0.1:18568`:

- `/varieties/coverage?q=Oregon%20State` shows the four lists and 45 entries.
- Expand Strawberry, then Sweet Sunrise: its code opens
  `/varieties/candidates?q=ORUS%202240-1&berry=berry-strawberry`.
- Original source and fragment links remain available. Applicant/breeder and
  registration stay blank. The candidate is untrusted and requires a human
  name decision before existing catalog authoring can proceed.

Native browser review verified all four list counts, the code/name display,
original source links and the pending identity gate. No review form was submitted.
Actual capture: [Sweet Sunrise identity review](../../artifacts/osu-public-program-review-2026-10-09/sweet-sunrise-identity-review.png).

## Coverage and checks

The read-only audit now reports **352 source sections / 1,129 source name
occurrences / 64 catalog-matched occurrences / 1,065 needing review**.
These are occurrences, not unique approved varieties or a global completeness
percentage. Public derived candidate keys increase from 749 to **788**;
the isolated preview has **789** because it also contains the retained private
pending article candidate.

The 77-entry competitor roster remains **60 with named findings / 14 partial /
1 unreadable / 0 not started / 2 identity holds**. This institution list does not
turn an undisclosed company portfolio into a completed check. All four new
sections remain follow-up work because the historical list is incomplete.

- Catalog reconciliation, human authoring and photo-gate suite: **90 passed**,
  one existing warning, 73.40s. The new regression verifies four-berry accounting,
  code/name pairing, partner credits, no guessed aliases and no trust promotion.
- Record validation passes; all 2,771 original data JSON files and the canonical
  expansion guide remain unchanged.
- Private audit preserves 32 pending source copies, their payload hashes and
  the real pending article bytes; zero new human source decisions or extraction
  readiness.
- Public output: **1,755 HTML pages**, unpublished draft ID/title exclusion and
  new unreviewed source-ID/code exclusion pass. Pagefind succeeds after an
  escalated retry of its output step; the initial sandboxed build reached the
  output write and failed with PermissionDenied. Both handles are terminal and
  consumed; no checks were bypassed.
- Parent blueberry draft #374 is all-green on `3a8261769768588009fa507d113d197c644b5e43`:
  **4,524 passed / 11 skipped / 2 warnings / 627.09s**. New draft CI is separate.

## Remaining mission

CAT-01/CAT-02/TD-116 remain open: complete current/historical portfolios,
official code/rights checks, deeper cited profiles, usable photos, independent
human-qualified recall, original article coverage and human-approved catalog
additions. The integrated release is not ready for merge or deployment.
The revised blueberry review still gates remaining Landscape rollout.
