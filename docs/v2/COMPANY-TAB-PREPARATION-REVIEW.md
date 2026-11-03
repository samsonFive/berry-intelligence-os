# Company tabs: prepare the data the selected page displays

The company workspace was building full News cards and operating-region tables
on every tab, including People, Profile & links, Intelligence and Varieties.
Those pages do not render those models. This also caused unrelated source work
before a contact or profile editor could be displayed.

`profile_context` now prepares full News for Overview/News, and full operating
regions for Overview/Regions. All company destinations, source-name tables,
backbone/dossier content, people/contact/profile authoring, research/history,
tracking and human review gates remain. Unknown tab values still fall back to
Overview. No templates, article classification, source/discovery/identity rules,
data or schemas change. Offscreen context explicitly contains `None` for unused
News and an empty list for unused region rows; this is not a cache or persisted
data removal.

## Verified development evidence

All **76 affected tests** pass. New cases require visible data on every tab and
reject unrelated source, News, fact and region-model calls in both authoring and
read-only modes. Existing integration checks cover actual company tabs, current
profile/contact edits, research guards, company News and source-name navigation.
The first local test attempt encountered the shared Windows pytest directory's
access error before those cases could run; a fresh workspace-local test directory
resolved the environment problem. No application regression was masked.

Four fresh processes, in baseline/candidate/candidate/baseline order, compare
**64 complete rendered responses** across both a provisional and a trusted
company, all seven tabs, the next Candidates click and global News. Every HTML
byte matches. Every active/other context field matches. The only explicit model
exceptions are the unused News/region fields above, and those models are compared
in full on every tab that displays them. Generated fixture form UUIDs and
synthetic candidate timestamps are fixed symmetrically; actual stored dates,
source text, edits and decisions are not normalized. All 2,997 original files
per fixture copy remain unchanged; external connections are forbidden and none
are attempted.

| Development-copy path | Baseline | Candidate |
| --- | ---: | ---: |
| Splendor People | 1.31s | 0.45s |
| Splendor Profile & links | 1.39s | 0.43s |
| Splendor Regions | 1.16s | 0.52s |
| First Splendor Varieties after Overview | 3.07s | 2.77s |
| Hortifrut People | 1.04s | 0.44s |
| Hortifrut Profile & links | 0.83s | 0.42s |
| Complete 16-request workflow | 20.11s | 14.65s |
| Global News control | 1.70s | 1.86s |

These are local public-fixture measurements, not live latency promises. Global
News varied slightly slower and is not a gain claimed by this change. First
source-heavy visits remain slow; TD-122 is open. Private production-copy,
exact-head checks and native browser acceptance remain before a release decision.

An earlier Reader text experiment compared 63,113 predicates with 15,761 positive
controls on the retained offline production-data copy. Both candidate algorithms
preserved all decisions but failed to improve consistently; neither is retained.
An initial public article-only probe had zero eligible text checks and is not
treated as performance or acceptance evidence. A comparison harness's first UUID
stub had the wrong type; that failed attempt is retained, and the successful
attempt uses the original UUID type in both modes.

## Mission and release boundary

This continues the original mission here, including all original 31 definitions
and later content/Map/Learn/human acceptance requirements. See
[current remaining work](MISSION-CLOSEOUT-2026-11-03.md). Approved #476 remains
verified live at `50659fcd`; its approval is complete. This new head is not
approved for merge or deployment. Existing accounts, first-login history, edits,
private research, connection settings, mounts, backup and rollback must remain.
