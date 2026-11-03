# Faster company tabs and a more compact profile

The company workspace was building full News cards and operating-region tables
on every tab, including People, Profile & links, Intelligence and Varieties.
Those pages do not render those models. This also caused unrelated source work
before a contact or profile editor could be displayed.

`profile_context` now prepares full News for Overview/News, and full operating
regions for Overview/Regions. All company destinations, source-name tables,
backbone/dossier content, people/contact/profile authoring, research/history,
tracking and human review gates remain. Unknown tab values still fall back to
Overview. Article classification, source/discovery/identity rules, data and
schemas remain unchanged. Offscreen context explicitly contains `None` for unused
News and an empty list for unused region rows; this is not a cache or persisted
data removal.

Native phone review also found that secondary research links pushed the selected
tab's content below the screen. The existing workspace, unreviewed social and
Landscape links now sit in a closed-by-default **Related research** menu beside
the Companies link. The workspace loader hooks and scoped destinations remain;
the seven primary tabs, tracking, contacts and profile editors remain directly
available. Compact identity, action and tab spacing brings the first content
panel 178px higher in the reviewed 412×915 phone viewport (775px to 597px).
The menu stays within that viewport and supports the native keyboard toggle.
No additional JavaScript or separate company reader was introduced.

## Verified development evidence

The first performance head (`79f62d0a`) passes all four required checks. Its
**76 affected tests** pass. New cases require visible data on every tab and
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

These are local public-fixture measurements from the first performance head,
not live latency promises. Global News varied slightly slower and is not a gain
claimed by this change. The fresh isolated production-data comparison at that
head also passes all 64 complete rendered-response and active/other context
checks; its complete workflow is 21.41s → 18.89s (about 12%). People and Profile
& links improve materially; first Splendor Varieties is essentially flat
(5.90s → 5.87s), and global News is slightly slower (3.50s → 3.64s).

That isolated run preserves all five accounts (including Chris.H), 65 profiles,
10,537 protected JSON records, four databases and 1,115 private research files.
It adds or changes no runtime data and makes no real provider requests. The
review container is removed and production remains unchanged and healthy.

The subsequent density change intentionally changes the template and stylesheet.
The earlier HTML-equality result is **not** evidence that this new UI is identical
to the live UI. Renewed comparisons use the same final template for both old and
new preparation functions; native geometry checks separately verify the intended
layout change. The expanded change passes **79 affected tests** and renewed
64-response/active-context comparison using that final template. The local
comparison ran alongside another test process, so its timings are not used as
new performance claims. New navigation/access-boundary cases cover the collapsed menu,
all scoped destinations and workspace hooks, private/public visibility, and the
unchanged primary tabs. Restricted Windows ASGI execution stalled; its retained
test process was verified and stopped. The complete run with local socket access
passes in 31.83s; no application workaround was introduced. Final-head CI,
browser review and a new fresh isolated
production-copy check remain release requirements. First source-heavy visits
remain slow; TD-122 stays open.

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
