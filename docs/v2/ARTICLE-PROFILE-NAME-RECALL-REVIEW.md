# Read cultivar names printed in source profiles

University cultivar profiles explicitly print a name and selection code, but
the article-name check missed their `Cultivar name:` fields. It also mistook
Rabbiteye, a blueberry type, for a cultivar in a trial article. The parser now
reads complete profile fields and excludes generic blueberry types. Names and
codes remain untrusted source assertions; this change approves no identities,
aliases, breeders, growing regions, publication text or claims.

Review branch: `feature/article-profile-name-recall`, stacked on #376.

## What changed

A field must match the complete naming form, including any quoted selection
code. Its crop must be explicit in the field, a nearby short crop/profile
heading, or the captured article title. Publication tags alone cannot supply
the crop. Mixed-crop document text disables title fallback; short headings
scope at most four subsequent paragraphs. Other prose/list grammars keep their
existing paragraph-local crop rules. Incomplete fields and unrelated trailing
prose are refused rather than partially interpreted.

The captured spelling and code survive separately. A printed selection code
does not automatically become an alias or a rights identifier. Earlier human
rejections and notes survive rediscovery. No acquisition, model call, schema
change or source acceptance is introduced.

## Bounded before/after inspection

The same **32 pending source copies** were inspected offline using the exact
#376 parser at `b09d98a89d48e8396fede480b6f00f6751a968b5` and the revised parser.
The audit explicitly supplied copies as unreviewed inputs without hydrating
the app or persisting candidates. It found **28 before / 35 after** mention
occurrences: eight previously missed fields added, one Rabbiteye false lead
removed. Existing Hortifrut, Bounty and UF/IFAS detections remained unchanged.

| Source profile | Printed name | Printed selection code |
| --- | --- | --- |
| [Colossus](https://www.blueberrybreeding.com/colossus) | Colossus | FL11-35 |
| [Emerald](https://www.blueberrybreeding.com/emerald) | Emerald | FL 95-209a |
| [Farthing](https://www.blueberrybreeding.com/farthing) | Farthing | FL00-75 |
| [Jewel](https://www.blueberrybreeding.com/jewel) | Jewel | FL92-176 |
| [Meadowlark](https://www.blueberrybreeding.com/meadowlark-fl01-173) | Meadowlark | FL01-173 |
| [Optimus](https://www.blueberrybreeding.com/optimus) | Optimus | FL08-262 |
| [Patrecia](https://www.blueberrybreeding.com/patrecia) | Patrecia | UF52-20 |
| [Sentinel](https://www.blueberrybreeding.com/sentinel) | Sentinel | FL11-155 |

These are parser observations, not eight new catalog varieties or a measured
recall score. The source copies still await authenticity review. An independent
human-owned expected-name set has not been supplied. Bodies and audit passages
remain in ignored `inbox/`; only bounded metadata and verification are committed.

## Native review and validation

- A clearly fictional isolated article exercised the supported Article fields
  in the native browser. Its whole name and `FL 123` code appeared with source
  attribution, blank breeder/registration fields and unsent review controls.
  [Fictional field review](../../artifacts/article-profile-name-recall-2026-10-09/fictional-profile-field-review.png).
- The actual preview still lists all 24 Hortifrut declarations: 23 identity
  candidates and Keepsake's existing catalog link. The 32 pending copies are
  not automatically accepted or added to the live source denominator.
  [Actual source-name review](../../artifacts/article-profile-name-recall-2026-10-09/actual-hortifrut-source-names.png).
- **104 affected tests passed**, one existing ReportLab warning, 118.69s.
  Cases cover quoted/unquoted fields, code preservation, mixed crops, local
  headings, ambiguous/negated/incomplete forms and preserved human decisions.
- Record validation and the **1,755-page static build / Pagefind** pass;
  unpublished draft IDs and titles remain excluded.
- All **2,771 original data JSON files**, the canonical expansion guide,
  32 pending copies/payload hashes and the retained real pending draft bytes
  are preserved. No human source decision or extraction readiness was created.
- Parent #376 has all four required checks successful on its exact head:
  **4,527 passed / 11 skipped / two warnings / 482.87s**. New draft CI is separate.

The bounded portfolio audit remains 355 source sections / 1,132 occurrences /
64 matches / 1,068 needing review; 788 public derived candidate keys, 789 in
the actual isolated preview, and 64 canonical varieties. Those are separate
from the offline 32-copy diagnostic. The original synthetic diagnostic remains
60/64; four raw legacy `body` cases intentionally do not enter the supported
Article text path. It is not independent human-qualified real-world recall.

CAT-01/CAT-02/TD-116 remain open: complete current/historical portfolios,
original article corpus, cited profiles, official current rights, attributed
photos, independent recall and actual human catalog authoring. Blueberry
feedback still gates the remaining Landscape rollout. No merge or deployment.
