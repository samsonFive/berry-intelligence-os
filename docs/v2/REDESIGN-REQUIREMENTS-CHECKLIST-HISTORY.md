# Redesign and consolidation requirements — historical updates

October 9 UF cultivar photographs: [review](UF-CULTIVAR-PHOTO-REFERENCES-REVIEW.md) adds eight source-labeled
photo references to existing blueberry profiles, held by default with the
approved session-only reveal. Photo references: 122; zero new reuse approvals.
Current bounded audit: 363 sections / 1,140 occurrences / 72 matched /
1,068 needing review; canonical catalog remains 64. 92 targeted tests and
the 1,755-page static build pass. Parent #378 is all-green (4,553 tests).
CAT-01/CAT-02/TD-116 and blueberry feedback/release gates remain open.

October 9 explicit article-text recall auditing: [review](ARTICLE-SOURCE-RECALL-AUDIT-REVIEW.md) adds
opt-in supported Article inputs to the offline scorer and refuses unfinished
expectations before score output. 54 affected tests pass; the original
synthetic fixture stays 60/64. A private 32-copy human packet has blank
expectations and no approvals or recall score. CAT-01/CAT-02/TD-116,
independent human review and blueberry feedback/release gates remain open.

October 9 article profile-name detection: [review](ARTICLE-PROFILE-NAME-RECALL-REVIEW.md) records eight
previously missed explicit cultivar/code fields and removal of a generic
Rabbiteye false lead. Same 32 pending copies: 28 before / 35 after offline
mentions; no independent recall score, acceptance or catalog writes.
104 affected tests, preservation and the 1,755-page static build pass.
Parent #376 is all-green (4,527 passed / 11 skipped / two warnings).
CAT-01/CAT-02/TD-116 remain open; blueberry feedback gates rollout.

October 9 original public-program grants: [review](PUBLIC-PROGRAM-ORIGINAL-GRANTS-REVIEW.md) connects
Onyx, APF-77 / Black Magic and Columbia Giant to their original cultivar claims
and printed filing/grant dates. Two attributed fruit figures stay permission-held
and session-only; Onyx remains PDF-only. Coverage is 355 sections / 1,132 name
occurrences / 64 catalog matches / 1,068 needing review, with 788 public keys
unchanged. Ninety-two focused tests, validation, 2,771-file preservation,
32-copy private preservation and 1,755-page static safety pass. Parent #375 is
all-green on cf8272f: 4,525 passed / 11 skipped / two warnings / 458.38s.
Source selection codes, trial sites and printed assignees do not approve aliases,
roles, regions, current rights or photo reuse. CAT-01/CAT-02/TD-116, wider
portfolios/corpus/recall/rights/photos, human authoring and integrated release
remain open. Blueberry feedback still gates remaining Landscape; no merge/deploy.

October 9 public-program release coverage: [review](OSU-HISTORICAL-RELEASE-COVERAGE-REVIEW.md) adds all 45 entries
from OSU’s four-berry historical release list to identity review: 39 new keys
and six additional references. Coverage is 352 sections / 1,129 name occurrences
/ 64 catalog matches / 1,065 requiring review; 788 public derived keys. The
64 canonical varieties and 32 pending source copies are unchanged. Partner
credits, source code/name pairings and historical rights wording do not
approve identities, roles or current rights. Ninety targeted tests pass;
validation and original-data/private-payload preservation pass. Parent #374
is all-green on 3a82617: 4,524 passed / 11 skipped / two warnings / 627.09s.
CAT-01/CAT-02/TD-116, full portfolios/corpus/recall/rights/photos, human catalog
authoring and integrated release remain open. Blueberry feedback still gates
remaining Landscape rollout; no merge or deployment.

October 9 integrated blueberry handoff: [current review](BLUEBERRY-INTEGRATED-REVIEW-HANDOFF.md)
records denser, direction-preserving portfolio roles; publisher-named catalog
links; repaired focus/evidence URL restoration; and the updated visual guide
with eleven section homes and six reporting outputs. Native HTML/SVG/CSV retain
82 relationships / 47 sources / 97 relationship-source rows. Final changed
suite: 66 passed / one existing warning / 34.89s; earlier overlapping suite 120
passed / one warning / 118.04s. Validation, 2,771-file preservation and final
1,755-page static safety pass. Parent #373 is all-green: 4,522 passed / 11 skipped
/ two warnings / 756.73s on 5a707a0; new draft CI remains separate. This handoff
changes no catalog records or human reviews: 64 canonical varieties and 32
pending source copies remain. CAT-01/CAT-02/TD-116, full corpus/portfolios/recall,
rights/photos, human catalog work and integrated release remain open. Blueberry
feedback is required before other-berry Landscape rollout; no merge/deploy.

October 9 original corpus follow-up: [review](ORIGINAL-CORPUS-AND-SOURCE-REVIEW-READABILITY.md) records 22 private
pending copies from 25 existing URLs; two access blocks and one body failure
remain explicit. Together with the preceding cohort there are 32 pending copies
from 35 unique source IDs, with no source acceptance or new extraction readiness.
Source authenticity review now retains publisher headings and secondary passage
references instead of repeated system labels. 77 affected tests, validation,
2,771-file preservation, 1,755-page static safety and native desktop/375px review
pass. Parent #372 is all-green: 4,520 passed / 11 skipped / two warnings / 767.96s
on 88138b2. The current pushed-head checks remain separate. CAT-01/CAT-02/TD-116,
human identity/catalog work, wider corpus/portfolios/recall/rights/photos and
integrated release remain open. No merge/deployment or other-berry rollout.

October 9 trial report coverage: [review](ARTICLE-PROSE-AND-TRIAL-IMAGE-REVIEW.md) recovers report prose
mis-tagged as navigation, then retains twenty manually read image-table names
as unreviewed identity leads. Ten current-page copies await separate source-text
review; none is accepted or extraction-enabled. The trial publisher is not
inferred to be the breeder. Portfolio audit: 348 sections / 1,084 occurrences /
749 combined candidate keys; isolated preview 750 including its existing pending
Italian Berry source. All 64 canonical varieties remain unchanged. 166 affected
tests, 44 overlapping focused checks, validation, 2,771-file preservation,
1,755-page static safety and desktop/375px native review pass. Parent #371 is
all-green: 4,506 passed / 11 skipped / two warnings / 733.78s on c87d366.
Current pushed-head CI is a separate gate. CAT-01/CAT-02/TD-116 and integrated
release remain open. No merge/deployment or other-berry Landscape rollout.

October 8 accepted original reading: [review](REVIEWED-ORIGINAL-READING-REVIEW.md)
connects existing human-accepted article copies to selected private readers and
variety-name discovery, with identity/URL/payload checks and no canonical writes.
Pending, rejected and changed copies stay excluded; original user text wins.
193 affected tests and final 52 overlapping POST/public checks pass, with
validation, original-data preservation, 1,755-page static safety and fictional
desktop/375px browser acceptance/rejection verified. Real audit stays 103 names /
32 matches / 71 discoveries; 64 canonical varieties unchanged. Parent #370 is
all-green: 4,487 tests, 11 skipped, two warnings, 750.46s on 69c0447.
Draft #371 passes all four checks on c87d366: 4,506 passed / 11 skipped /
two warnings / 733.78s. CAT-01/CAT-02/TD-116, corpus,
portfolios, real recall, rights/photos, authoring and integrated release remain
open. No merge, deployment or other-berry Landscape rollout.

October 8 captured News/Digest inventory: [review](PENDING-NEWS-DIGEST-INVENTORY-REVIEW.md) connects active
publication metadata to Unreviewed News and subscribed Personal Digest lists
before individual saving. Real Italian Berry source/image, explicit subscribe
and unsubscribe, original Reader, 375px phone width and unchanged draft bytes
verified. Article-pipeline web captures now pass the News format gate; audio,
video and registry-like captures remain excluded. Archived/rejected sources no
longer resurface through the personal reader fallback. 165 affected tests,
119 final overlapping tests, record validation, original-data preservation and
1,755-page static safety pass. Draft #370 passes all four checks on 69c0447: 4,487 tests / 11 skipped / two warnings / 750.46s. CAT-01/CAT-02/TD-116, corpus acquisition, portfolios,
independent recall and integrated release remain open. No merge/deployment.

October 8 original article hierarchy: [review](PUBLISHER-ARTICLE-HIERARCHY-REVIEW.md) preserves
publisher headings through new normalized article acquisition and explicit
Reader capture. The real Italian Berry proof retains all 35 paragraph texts,
indexes and content SHA while recovering 12 source headings. No existing draft
or canonical record changed. Desktop and 375px mobile reviewed; mobile sticky
actions fixed; 168 affected tests, validation and original-data preservation pass.
Draft #369 is now all-green on 267389e: all four checks, 4,452 tests /
11 skipped / two warnings / 797.24s; watch 24224 consumed terminal success. Legacy body migration, wider acquisition, source/identity review, portfolio
completion and integrated release remain open. No merge or deployment.

October 8 pending-article coverage: [review](PENDING-ARTICLE-VARIETY-COVERAGE-REVIEW.md) connects active publication
draft bodies to private identity review and selected original reading. A real
Italian Berry acquisition exposed and repaired the G‑Viva naming miss; 35
indexed paragraphs remain private/unreviewed, with no AI or publication action.
Private audit: 103 names / 32 catalog matches / 71 discoveries before human
decisions; 739 combined candidate keys; 64 canonical varieties unchanged.
157 affected tests and final 82 overlapping focused tests pass; desktop/phone,
saved Digest, alphabetical G jump and original-data preservation verified.
Parents #367 and #368 pass all four checks (4,418 and 4,441 tests). CAT-01/CAT-02/TD-116, article acquisition/layout, full portfolios,
real recall, rights/profile depth, human catalog authoring and integrated release
remain open. No merge, deployment or other-berry Landscape rollout.

October 8 article-to-catalog connection: [review](CAPTURED-ARTICLE-VARIETY-COVERAGE-REVIEW.md) now includes
known, already-readable news automatically in private variety identity views.
The native Hortifrut capture finds 24 explicit names; private audit 102 source
names / 32 catalog matches / 70 discoveries before private decisions, versus
99 / 31 / 68 from summaries alone. Combined portfolio queue remains 738 keys;
64 canonical varieties and human decisions unchanged. One private readable
article does not repair the 1,269-record acquisition gap; canonical bodies
remain 0/1,269. 132 affected tests and final 13 overlapping focused tests pass;
desktop/phone review, record validation and original-data preservation pass.
Draft #367 is now green on e494eb9: all four checks; 4,418 tests / 11 skipped / two warnings / 486.63s.
CAT-01/CAT-02/TD-116, full portfolios, real recall, rights/profile depth, human
catalog authoring and tested release remain open. No merge/deploy or berry-gate bypass.

October 8 Royal Berries/CAS: [original-source and identity-scope review](ROYALBERRIES-CAS-SOURCE-PLAN-REVIEW.md)
adds twelve patent subjects, ten new review keys and three held fruit scans.
CAS strawberry research names no cultivar releases. Two excluded labels now show
their identity/scope reasons rather than posing as unchecked company portfolios.
Current: 347 sections / 1,064 occurrences / 738 candidate keys; 60/77 named-source
entries, 14 incomplete, one unavailable, zero unstarted in the full view and two
held identities; 103 source follow-ups. This is not complete portfolio coverage.
64 canonical records unchanged; 112 photo references, no new public approvals.
55 affected tests pass; desktop/390px review and original-data preservation pass.
Parent #365 passes all four checks (4,397 tests); this child still requires CI.
CAT-01/CAT-02/TD-116, real recall, article bodies, rights/profile depth and tested
release/human catalog decisions remain open. No merge/deployment or berry-gate bypass.

October 8 Expoberries/Splendor: [original-source review](EXPOBERRIES-SPLENDOR-ORIGINAL-SOURCES-REVIEW.md)
adds two exact patent denominations with historical metadata and held fruit
figures; three Splendor pages remain unnamed. 334 sections / 1,052 occurrences /
728 candidate keys; 59/77 named-source entries, 13 incomplete, one unavailable,
four unstarted; 96 follow-ups. Canonical 64 unchanged; 109 photo refs. 49 affected
tests and native desktop/phone review pass; original data/human gates preserved.
Corrected parent #364 passes all four checks (4,392 tests); this child needs CI.
CAT-01/CAT-02/TD-116 and catalog/release work remain open.

October 8 source-plan correction: [review](PORTFOLIO-SOURCE-PLAN-STATUS-REVIEW.md)
records accurate berry/company/source scope and a direct table jump. Current:
329 sections / 1,050 occurrences / 726 keys; 58/77 entries with named-source
checks, 12 incomplete, one unavailable, six unstarted; 93 follow-ups. The previous
59/77 included Benning's empty list. Collective refresh keeps its identity
unverified. 50 affected tests and desktop/phone review pass; original data and
human gates remain. Parents #362/#363 now pass all four checks; this child needs
its own CI. CAT-01/CAT-02/TD-116 and the full catalog/release mission remain open.

October 8 Smart Berries: [nine original source gaps](SMARTBERRIES-BRAND-CULTIVAR-GAPS-REVIEW.md)
keep wholesale brands out of cultivar identities and preserve the unchecked video
boundary. 328 source sections / 1,050 occurrences / 726 queue keys; 18 initial
enumeration gaps and 92 follow-ups. CAT-01/CAT-02/TD-116 and human catalog/release
gates remain open; this addition does not close worldwide or historical coverage.

October 8 APG continuation: [original strawberry review](APG-ORIGINAL-STRAWBERRY-PORTFOLIO-REVIEW.md)
adds ten source subjects and seven new queue keys; no automatic catalog promotion.
Critical source conflicts are prominent; secondary context remains collapsed.
70 focused tests and desktop/phone review pass. Audit: 319 sections, 1,050 name
occurrences, 726 candidate keys, 59/77 partly checked companies, 18 enumeration
gaps and 83 follow-ups. CAT-01/CAT-02/TD-116 remain open. Parent #361 is green;
this child requires its own checks. Human catalog and blueberry release gates remain.

October 8 original company-range follow-up: Surexport and Gem-Pack retain
unnamed-variety gaps after original pages and two complete one-page PDFs were read.
Eight existing section IDs are refreshed without duplicate rows; four sections are
new. Pack labels, brands, company names and generic pictures create no candidates,
aliases or variety/company roles. Source scope is prominent; secondary context
starts collapsed while name/code, missing-item and website warnings stay available.
Actual audit: 296 sections / 1,013 occurrences / 719 candidate keys / 64 unchanged
mixed-status catalog records. 58/77 registry entries have some named-source checks;
19 lack initial named enumeration, including companies with attempted unnamed
pages. 78 source follow-ups remain. 44 affected data tests and 39 presentation /
source tests pass. Original data, user edits and trust gates are preserved.
Parent #360 passes all four checks (4,374 tests); this packet needs its own CI.
CAT-01/CAT-02/TD-116 and independent recall, rights/profile depth remain open.
No merge, deployment or rollout past the blueberry checkpoint.
See COMPANY-UNNAMED-PORTFOLIO-AUDIT-REVIEW.md.

October 8 Royakkers grower-source continuation: ten original page sections
add provenance for Elsanta and Portola, both already in the review queue. Neither
is duplicated or automatically approved. The strawberry page says Royakkers grows
them; breeding, ownership, nursery supply, rights and growing regions stay unapproved.
Nine unnamed or wrong-content sections remain partial, including Dutch nursery
details. Generic pictures are excluded because they do not identify a variety.
Actual audit: 292 sections / 1,013 name occurrences / 719 candidate keys / 64
unchanged mixed-status catalog records; 58/77 registry entries partly checked,
19 initial enumeration gaps and 74 source follow-ups. 38 affected tests pass.
Native desktop and phone review checked; 2,771 original JSON records and the
expansion guide remain unchanged. Parent draft #359 passes all four checks,
including 4,370 tests; this addition requires its own CI. CAT-01/CAT-02/TD-116
remain open, as does independent recall and full profile/rights coverage.
No merge, deployment or other-berry Landscape rollout; the blueberry gate remains.
See ROYAKKERS-GROWER-VARIETY-SOURCES-REVIEW.md.

October 8 historical strawberry source continuation: two original patent
subjects (PSI-.118 and PSI-130) describe 1987 trials on a Well-Pict-provided
ranch. Original claim links and six attributed full-resolution photographs enter
private review; unknown reuse stays held. This does not establish current company
ownership, availability, rights or growing footprints. Six Perfection Fresh pages
remain explicitly partial, with unnamed cultivars and no inferred PSI mapping.
Actual audit: 282 sections / 1,011 name occurrences / 719 candidate keys / 64
unchanged mixed-status catalog records. 57/77 registry entries have some bounded
names checked; 20 initial enumeration gaps and 65 source follow-ups remain.
44 affected tests pass; final full-resolution source tests pass again (5 tests).
Native desktop and 390px review passes; all 2,771 original JSON and the expansion
guide are preserved. Parent #358 passes all four exact-head checks (4,365 tests).
The new packet requires its own CI. CAT-01/CAT-02/TD-116 and human catalog/release
work remain open; LAND-02 retains the blueberry feedback gate. No merge,
deployment or other-berry Landscape rollout.
See WELLPICT-HISTORICAL-VARIETY-SOURCES-REVIEW.md.

October 8 CBC original-source follow-up: three remaining technical documents
join eleven profiles, the full 15-page handout and two original patent title/claim
references. Combined CBC addition: 17 sections / 35 name occurrences / seven
held photographs. Four literal field-code leads retain the separate handout's
commercial-name pairings for human review; they are not four approved new varieties.
Performance, estimated value, acreage, nursery access and regions stay source claims.
Actual audit: 274 sections / 1,009 occurrences / 717 candidate keys / 64 mixed-status
catalog records. 56/77 registry entries partly checked; 21 enumeration gaps and
59 source follow-ups remain. 39 affected tests pass (38.72s, 1 existing warning);
all 2,771 original JSON and the governing expansion guide are preserved.
Native code-only source review and scoped alphabet work at desktop and 390px;
no real human review action submitted. The original #358 full suite found one
stale test expectation (4,360 passed); its partial-source and combined-count
assertions are corrected. Fresh exact-head checks remain required.
See CBC-ORIGINAL-FIELDDAY-VARIETIES-REVIEW.md. CAT-01/CAT-02/TD-116, independent
coverage, human catalog and combined release remain open. No merge/deployment
or other-berry Landscape rollout; LAND-02 retains the blueberry feedback gate.

October 8 Camposol original-source continuation: two literal ORIGEN first-generation
names, Sol One and Maia Blue, enter existing identity review with original
February 4, 2026 source and contextual blueberry scope still needing review.
Program/factory labels, seven packaging formats and generic calendar are
excluded; the product page remains partial. No approved roles, aliases, traits,
regions, rights or photos. Actual audit: 257 sections / 974 occurrences /
709 candidate keys / 64 mixed-status catalog records; 55/77 entries partly
checked, 22 enumeration gaps and 59 source follow-ups. 43 affected tests pass
(45.06s, one existing warning); records validate; all 2,771 original JSON and
expansion guide preserved. Native desktop and 390-pixel alphabetical handoff
verified without real review writes. Parent #356 passes all four checks
(4,351 tests); this follow-up needs its own head checks. See
CAMPOSOL-ORIGINAL-VARIETIES-REVIEW.md. CAT-01/CAT-02/TD-116, independent coverage,
rights/photos, human catalog and combined release remain open. No merge/deploy
or other-berry Landscape rollout.

October 8 selected-article discovery repair: the app recovered 18 original
Hortifrut paragraphs with 24 named varieties, but the quick check initially
found only two. Quoted positive declarations and paragraph-local crop scope
now return all 24 with correct berries and no extras. Existing records remain
unchanged; this repairs automation rather than counting manual coverage again.
A negated-list false positive exposed by new tests is corrected. 103 affected
tests pass (73.88s, one existing warning); records validate. Native selected
preview shows 24 names / 23 candidates plus the existing Keepsake catalog link;
Raspberry filtering retains article context and returns five Pacific names.
No real review decision or candidate write. The unchanged summary diagnostic
still has 23/24 cases and 60/64 names; no global recall claim or fixture shortcut.
Default audit remains 255 sections / 972 occurrences / 707 proposed keys /
64 mixed-status catalog records, 23 registry enumeration gaps and 58 follow-ups.
Parent #355 has all four green checks (4,341 tests); draft #356 also passes
all four checks (4,351 tests / 11 skipped / two warnings, 520.89s). See VARIETY-ARTICLE-QUOTED-LISTS-REVIEW.md. CAT-01/CAT-02 /
TD-116, acquisition, independent recall, rights/photos, human catalog and release
remain open. No merge/deploy or other-berry Landscape rollout.

October 8 original company-source gaps: eleven bounded checks cover Singrow,
Biogea, The Berry Collective, Fruitist and Grupo HerEs. Ten readable partial
pages and one native DNS failure remain explicit gaps. Brands, input products,
trial producers and generic Sekoya context are excluded from cultivar identity;
original crop/date/company scope stays intact. No candidates or photos added.
Actual audit: 255 sections / 972 occurrences / 62 text matches / 910 review needs;
707 proposal keys / 64 mixed-status catalog records. 54/77 registry entries have
some names checked; 23 enumeration gaps remain, with 58 source follow-ups.
63 affected tests pass (68.23s, one existing warning); records validate; all
2,771 baseline JSON files and the expansion guide remain unchanged. Native
private coverage shows exclusions and incomplete source plans without writes.
Parent #354 is green (4,336 tests); draft #355 also passes all four checks
(4,341 tests / 11 skipped / two warnings, 441.39s).
See REGISTRY-ORIGINAL-SOURCE-GAPS-REVIEW.md. CAT-01/CAT-02/TD-116, acquisition,
independent recall, rights/photos, human catalog and combined release remain
open. No merge/deploy or other-berry Landscape rollout.

October 8 variety search correction: native review reproduced Merida failing to
find Mérida. Candidate navigation now ignores accents only during search,
retaining literal stored spellings, code punctuation, non-Latin letters, IDs,
user aliases/decisions and company/crop/source/status filters. 55 focused tests
pass (102.43s, one existing warning); the updated browser returns the correct
scoped entry with its original name and unresolved identity intact. No data,
schema or rights/reuse changes. Parent draft #353 passes all four required checks
(4,331 tests); search draft #354 also passes all four checks (4,336 tests). See
VARIETY-ACCENT-SEARCH-REVIEW.md. CAT-01/CAT-02/TD-116 and combined release remain
open. No merge/deploy or other-berry Landscape rollout.

October 8 Berries del Oeste originals: seven named strawberries now appear in
the company source table, with exact review links and 21 attributed photo
references. All seven original profiles, the family context and five brochures
(29 pages, including two distinct Áurea versions) were read and visually checked.
Marketing families are excluded from cultivar counts; original spellings and
claims stay provisional. No identity, alias, company role, traits, geography or
current-rights approval. Photos remain hidden, unknown reuse and private to the
session preview choice; no public image publication.
Real audit: 244 sections / 972 occurrences / 62 catalog text matches / 910 review
needs; 707 proposed keys (63 stored / 644 primary). Catalog remains 64 mixed-status.
54/77 registry entries partly checked; 23 named-enumeration gaps and 47 source
follow-ups remain. 68 affected tests pass (63.90s, one existing warning); original
2,771 JSON files and expansion guide preserved. Native company search, exact
Áurea handoff, both brochure URLs and photo reveal/refresh/hide verified. Phone
acceptance remains unverified. Parent #352 has all four green checks (4,327 tests);
draft #353 passes all four checks (4,331 tests). See
BERRIESOESTE-ORIGINAL-VARIETIES-REVIEW.md. CAT-01/CAT-02/TD-116, independent recall,
rights depth and human catalog authoring remain open. No merge/deploy or
other-berry Landscape rollout.

Draft #352 full-check follow-up: 4,326 passed / one failed exposed a hidden
user-edited website link after portfolio capture. The source plan now displays
both the checked source and current company website, with explicit clears and
private/public boundaries retained. All 64 affected tests pass (60.84s, one
existing warning). Corrected-head full checks remain required;
neither the catalog coverage nor release gates are closed by this fix.

October 8 Black Venture Farm original portfolio continuation: the complete
low-chill and pipeline panels add 21 literal names/codes across four crops.
The company table labels 11 pipeline selections separately from ten offerings,
supports code search and exact review handoff. Nine original named cutout photos
retain attribution, hidden default, unknown reuse and session-only preview.
A compact keyboard-accessible zoom control makes padded source images usable
without altering source assets, persisting permission or approving identity.
No company role, release date, trait, region or rights decision is inferred.
Real audit: 231 sections / 953 occurrences / 62 text matches / 891 review needs /
700 proposed keys (63 stored / 637 primary); catalog remains 64 mixed-status.
53/77 registry entries partly checked, 24 enumeration gaps, 47 source follow-ups.
85 focused tests pass (79.43s, one existing warning); records validate; all 2,771
original JSON files and expansion guide unchanged. Native table/code search,
actual Urani handoff, photo reveal/refresh/hide and zoom checked. Parent #351 has
all four green checks (4,323 tests); this child needs exact-head full checks.
See BLACKVENTURE-ORIGINAL-VARIETIES-REVIEW.md. CAT-01/CAT-02/TD-116 remain open:
source/code/rights depth, remaining photos, independent recall and human catalog
authoring. No completeness claim, merge/deploy or other-berry Landscape rollout.

October 8 EU Plants original YANA continuation: all ten pages of original
USPP34772P3 were read and visually checked, including its single cultivar claim
and seven drawing plates. The existing company Varieties table links one named
raspberry proposal to exact identity review and original patent/claim references.
Nine comparator/reference labels stay outside the company offering enumeration.
Figure 1 has literal attribution and a visually checked original photo, unknown
reuse, hidden default and private session-only Ignore permission / Hide photo.
Printed applicant/assignee, priority and publication dates are historical source
fields, not current legal status, approved company roles or trait/region records.
Real audit: 229 sections / 932 occurrences / 62 text matches / 870 review needs /
679 proposed keys (63 stored / 616 primary); catalog remains 64 mixed-status.
52/77 registry entries partly checked, 25 enumeration gaps, 47 source follow-ups.
81 focused tests pass (45.71s, one existing warning); records validate; all 2,771
original JSON files and expansion guide are unchanged. Native company handoff,
original references and photo reveal/refresh/hide verified. Parent #350 has all
four green checks (4,319 tests); this child needs its own exact-head full checks.
See EUPLANTS-YANA-ORIGINAL-PATENT-REVIEW.md. CAT-01/CAT-02/TD-116, current-rights
verification, embedded technical-sheet photos, independent recall and human
catalog authoring remain open. No merge/deploy or other-berry Landscape rollout.

October 8 IQ Berries source/photo continuation: the complete original homepage
and all seven cultivar detail pages provide fourteen occurrences for seven
blueberry offerings, with original source links and contextual code search.
Each has a visually checked named fruit photograph, source attribution, unknown
reuse, hidden default and session-only Ignore permission / Hide photo. No
permission, company role, rights, trait, region or commercial-name alias approved.
Seasonal diagrams stay available at the original source; generic hero/logos are
not variety photos. Original labels/code pairings remain verbatim; no dates are
guessed from image paths, selection wording or an incomplete trial-yield sentence.
Real audit: 228 sections / 931 occurrences / 62 text matches / 869 review needs /
678 proposed keys (63 stored / 615 primary); catalog remains 64 mixed-status.
51/77 registry entries partly checked, 26 enumeration gaps, 47 source follow-ups.
90 focused tests pass (43.40s, one existing warning); records validate; all 2,771
original JSON files and the expansion guide are unchanged. Native company table,
T11-319 search, exact MEGAEARLY handoff and photo loading/refresh/hide verified.
Parent #349 has all four green checks (4,315 tests). This draft requires its own
exact-head full checks. See IQBERRIES-ORIGINAL-VARIETIES-REVIEW.md. CAT-01/CAT-02/
TD-116, embedded PDF photos, current-rights depth, independent recall and human
catalog authoring remain open. No merge/deploy or other-berry Landscape rollout.

October 8 original rights-source continuation: three complete original PDFs
(12 pages, text and every page visually checked) add five name occurrences for
Enrosadira, ALEL045 and ALEL111. Existing Enrosadira identity/anchor is retained;
the two official code proposals stay separate from EasyStar/EasyRock until human
identity review. Dated printed register details are not verified current rights,
company roles or trait approvals. One attributed Enrosadira patent photo has
unknown reuse: hidden by default, session-only Ignore permission / Hide photo.
Native reveal, refresh, hide and both original register links pass desktop review.
Real audit: 220 sections / 917 occurrences / 62 text matches / 855 review needs /
671 proposed keys (63 stored / 608 primary); catalog remains 64 mixed-status.
50/77 registry entries partly checked, 27 enumeration gaps, 47 source follow-ups.
The only backend change fixes original national-register source classification
using the existing tier; it does not approve the source or current legal status.
86 focused tests pass (44.06s, one existing warning); records validate; all 2,771
original JSON files and the expansion guide are unchanged. Parent #348 has four
green checks (4,310 tests). This draft requires its own exact-head full checks.
See ORIGINAL-RIGHTS-SOURCE-LINKS-REVIEW.md. Embedded technical-sheet photos,
independent recall and human catalog authoring remain open under CAT-01/CAT-02/
TD-116. No merge/deploy or other-berry Landscape rollout.

October 8 G-Berries original-source recovery: the earlier failed homepage
capture is superseded by an original native-browser read, preserving its
historical version. Three explicit crop selectors, GIL page and six complete
original PDFs (18 pages, all visually checked) provide fifteen named occurrences
for eight offering labels. Company code search finds ALEL045/EasyStar and
ALEL111/EasyRock without approving denomination or aliases. Program/club labels,
nurseries and legacy comparison-table varieties are not extra company offerings.
PDF Tafí and website Tafì spellings remain source-specific; no human identity
approval. Original sheet links expose brochure details; patent wording is not
an official register finding. Named PDF photos remain source leads requiring
private embedded-document image support/reuse review, with no new assets.
Real audit: 217 sections / 912 occurrences / 62 text matches / 850 review needs /
669 proposed keys (63 stored / 606 primary); catalog remains 64 mixed-status.
50/77 registry entries partly checked; 27 need enumeration; 47 source follow-ups,
including G-Berries' unnamed blackberry program. All prior anchors and 1,992
original JSON files, user decisions/notes/registration and expansion guide remain
unchanged. 60 focused tests pass (34.07s; one existing warning); native code search
and exact EasyStar handoff pass. This draft needs its own pushed-head checks.
Parent draft #347 is green: 4,304 passed / 11 skipped / 2 warnings.
See GBERRIES-ORIGINAL-VARIETIES-REVIEW.md. CAT-01/CAT-02/TD-116 remain open;
no global completeness claim, merge, deployment or other-berry Landscape rollout.

October 8 Mattivi source/photo continuation: twelve original portfolio and
detail pages provide sixteen named occurrences for eight offering labels
across all four berries. Six displayed name/code pairs remain contextual and
searchable in the company table, without approving aliases or PBR claims.
Codes are not counted as extra cultivars; Duke is a maturity comparator.
Four named raspberry-card photos are credited to Mattivi with original links,
unknown reuse, hidden defaults and session-only preview. No permission saves.
Real audit: 207 sections / 897 occurrences / 62 text matches / 835 review needs /
663 candidate keys (63 stored / 600 primary proposals); catalog 64. Registry:
49/77 partly checked, 28 rows still need named-variety enumeration, 45 source
follow-ups. Photos: 45 references / 44 unknown reuse / zero new public approvals.
All prior IDs, stored registration, aliases, notes and human decisions survive.
Native table alphabet/code search/reset/berry filter and exact Nives handoff
pass; photo rendering, refresh and Hide verified. Phone acceptance unverified.
79 focused tests pass (53.25s; one existing warning); records validate; all
1,992 original JSON files and expansion guide unchanged. Parent draft #346
has all four green exact-head checks (4,298 tests). This draft requires its
own pushed-head checks. See MATTIVI-SOURCE-VARIETIES-REVIEW.md. CAT-01/CAT-02/
TD-116 remain open. No merge/deploy or other-berry Landscape rollout.

October 8 grower-source continuation: eleven complete-page checks add 53
literal name occurrences for FreshKampo, California Giant and Cuna de Platero.
Language spellings, ambiguous newsletter wording, historical dates and the
separate summer strawberry calendar stay explicit. A Cupla image from its
named page has source attribution but unknown reuse: hidden by default, with
session-only Ignore permission / Hide photo verified. No permission is saved.
Real audit: 195 sections / 881 occurrences / 62 text matches / 819 review needs /
655 candidate keys; catalog 64. Registry: 48/77 partly checked, 29 rows still
need named-variety enumeration, with 45 source follow-ups. Batch ordering
preserves every existing provisional ID, including Cleopatra. Human rejection,
registration and user edits win. Final focused tests: 75 passed / one existing
warning in 41.23 seconds. Native alphabet/search/reset, blueberry company
scope, exact Cupla handoff, photo rendering/refresh/hide pass desktop review.
Records validate; all 1,992 original JSON files and expansion guide unchanged.
Parent draft #345 has four green checks (4,291 tests); this draft needs its own
pushed-head checks. See GROWER-SOURCE-VARIETIES-REVIEW.md. CAT-01/CAT-02/TD-116
remain open. No merge/deploy or other-berry Landscape rollout.

October 8 Wish Farms / market-source continuation: fourteen bounded sections
add the four blackberry names in Wish Farms' 2019 grower announcement. Original
publication date and differing article dateline remain separate. Existing IDs,
registration and human decisions win; no inferred spelling aliases or roles.
Gem-Pack's complete original packaging sheet contains labels, not cultivar
denominations. Surexport, Perfection and Pairwise categories, brands and trait
labels remain coverage gaps. A company with zero captured names now gets an
upfront explanation that its varieties may still be missing.
Real audit: 184 sections / 828 occurrences / 58 text matches / 770 review needs /
636 candidate keys; catalog 64. Registry: 45/77 partly checked, 32 rows still
need named-variety enumeration, with 43 source follow-ups. No new gallery assets
or public photo approvals. Final focused tests: 77 passed / one existing warning
in 55.94 seconds. Native Wish search/alphabet/reset and candidate/source handoff,
and Surexport's six read pages / zero captured names, pass desktop review.
Records validate; all 1,992 original JSON files and expansion guide unchanged.
Parent draft #344 has four green checks (4,285 tests); this draft needs its own
pushed-head checks. See WISH-FARMS-MARKET-SOURCE-VARIETIES-REVIEW.md.
CAT-01/CAT-02/TD-116 remain open. No merge/deploy or other-berry rollout.

October 8 Family Tree Farms / Miyoshi source continuation: eight bounded
source sections add four historical Family Tree Farms blueberry labels and
Miyoshi's 19FAG-1 / Berry Pop SAKURA source pairing. Existing Star identity,
saved registration and human decisions win; Snow Chaser remains separate from
Snowchaser pending review. Product categories, comparator Benihope and cached
Japanese labels are excluded. Current inaccessible pages remain explicit gaps.
Real audit: 170 sections / 824 occurrences / 57 text matches / 767 review needs /
635 candidate keys; catalog 64. Registry: 44/77 partly checked, 33 initial checks
and 30 source follow-ups remain. No new photo assets or public image approvals.
Company search, alphabet/reset and candidate handoff pass native browser review.
Review badges use plain language and patent cautions appear only for patents.
All 94 final focused tests pass (57.32s); records and all 1,992 original JSON
files validate/preserve. The expansion guide is unchanged. Parent draft #343's
four exact-head gates are green (4,280 tests); this draft needs its own gates.
CAT-01/CAT-02/TD-116 remain open. No merge/deploy or other-berry rollout.
See FAMILYTREE-MIYOSHI-SOURCE-VARIETIES-REVIEW.md. Earlier counts are historical.

October 8 source-specific patent continuation: later original patent
references now show their own claim links and filing/grant metadata without
replacing existing candidate IDs or saved registration, aliases or decisions.
Lagorai Plus and Dafne original PDFs are fully read/visually checked; Ofelia SO
now has all nine pages checked. Two small named fruit thumbnails remain held
for unknown reuse, with session-only preview. Current company snapshots no
longer say their technical sheets are unread. Sun Belle's brand-only page and
Well-Pict's DNS failure remain explicit source gaps, not empty portfolios.
Real audit: 162 sections / 819 occurrences / 57 text matches / 762 review needs /
631 keys; catalog 64. Registry: 42/77 partly checked, 35 initial checks and 24
follow-ups open. Photos: 40 references / 39 reuse unknown / zero new public.
All 103 final focused tests pass; private browser review confirms hidden,
session preview, reload and Hide behavior. Phone acceptance remains unverified.
Parent #342 is green (4,274 tests); this draft needs its own pushed-head gates.
CAT-01/CAT-02/TD-116 remain open. No merge/deploy or other-berry rollout.
See VARIETY-SOURCE-PATENT-LINKS-REVIEW.md.

October 8 Sant’Orsola original-document continuation: eleven visually
checked technical sheets and the original Ofelia SO patent add twelve source
observations, claim/filing links and one held low-resolution fruit photo.
Ofelia and Ofelia SO stay separate; all eleven older candidate links survive.
Real audit: 158 sections / 817 occurrences / 57 text matches / 760 review needs /
631 candidate keys. Catalog stays 64. Registry: 42/77 partly checked, 35 initial
checks and 22 capture follow-ups open. Photos: 38 references / 37 reuse-unknown /
zero newly approved public. Twenty-one PDF photo objects remain document links,
not gallery assets. No aliases, rights status, traits, roles or growing regions
approved. Native session preview/hide passes; records and 1,992-file preservation
pass. See SANTORSOLA-DOCUMENT-REFERENCES-REVIEW.md. Parent #341 exact-head gates
are green (4,270 tests); this draft requires its own pushed-head checks.
No merge/deploy or other-berry Landscape rollout; CAT-01/CAT-02/TD-116 stay open.

Earlier checkpoints below are historical; current counts are those above.

October 8 Sant’Orsola continuation: the live breeding page adds eleven
name observations, including Delfi and ten raspberry labels, with exact linked
technical-sheet URLs. Two enumerated crop sections and one explicit document
follow-up bring the real audit to 146 sections / 805 occurrences / 57 text
matches / 748 review needs / 630 candidate keys. Catalog stays 64; 42/77
registry rows have some enumeration, 35 initial checks and 22 follow-ups remain.
Photos remain 37 references / 36 reuse-unconfirmed / zero newly approved public.
The technical sheets are linked but not yet read; no patent status, aliases,
roles, traits or growing region is approved. Native company search and scoped
coverage handoff are reviewed. All 37 focused checks, record validation and
1,992-original-JSON preservation pass. See SANTORSOLA-VARIETY-REVIEW.md.
Draft #340 is pushed and all four exact-head checks pass (4,267 tests); this
continuation requires its own exact-head checks. No merge, deployment or
other-berry Landscape rollout. CAT-01/CAT-02/TD-116 remain open.

Earlier checkpoints below are historical. Current source denominators and
delivery state are those above; a checked page is not a complete portfolio.

October 8 BerryWorld/Oishii/Queensland continuation: eleven sections add 57
source-name occurrences and one permission-held Koyo photo. Regional/brand and
historical labels remain separate; the Queensland abstract's seven-versus-six
count conflict is retained. Company coverage links now scope sources, counts
and registry rows and preserve the company through filter submissions. Native
desktop review and 88 unique focused tests pass; phone verification remains open.
Records and original 1,992 JSON preservation pass. Real audit: 143 sections /
794 occurrences / 57 text matches / 737 review needs / 619 keys, catalog 64;
41/77 partly checked, 36 initial checks and 21 follow-ups remain. Photos 37,
36 reuse-unconfirmed, zero newly approved public. See
BERRYWORLD-OISHII-QUEENSLAND-VARIETY-REVIEW.md. Drafts338/339 are pushed and
all four exact-head checks pass (4,202/4,260 tests). This next continuation
still requires its own draft and exact-head checks; no merge, deployment or
other-berry Landscape rollout. CAT-01/CAT-02/TD-116 remain open.

Earlier checkpoints below are historical; their local-only/approval-pending
delivery descriptions are superseded by the pushed drafts above.

October 8 NIAB/Bayer/Masiá source continuation: 12 sections add 44 name
occurrences and five held fruit photos. NIAB's transferred strawberries stay
separate from legacy names and raspberries; Bayer trademark ownership does not
approve cultivar ownership. Baya Solara/EM2836 retains Subject to approval, and
later source codes now appear in the company table. Shared Masia photo withheld;
historical Selene retained; crop headings, propagator repeats and comparators
excluded. 112 unique local tests, records, session JavaScript and preservation
pass; 1,992 original JSON unchanged. Desktop photo/control/code review passes;
mobile sizing could not be applied and remains unverified for this continuation.
Audit: 132 sections / 737 occurrences / 53 matches / 684 review needs / 573 keys;
38/77 partly checked, 39 initial checks and 20 follow-ups; catalog 64, photos
36/35 held/zero newly approved public. See NIAB-BAYER-MASIA-VARIETY-REVIEW.md.
CAT-01/CAT-02/TD-116 and full redesign/release remain open. Local only; pinned
parent push approval unanswered, no new draft/remote CI, merge/deploy or
other-berry Landscape rollout.

October 8 company-page visibility fix: private company Varieties tabs and
detailed portfolios now show additional names from checked sources in a compact
searchable table, with berry/alphabet navigation and exact review destinations.
Catalog matches do not approve company roles; repeated sources retain provenance,
different codes stay separate, and rejected names stay closed. Public/static
views exclude this list. No acquisition or canonical/review/permission writes;
1,992 original JSON files unchanged. Coverage remains 120 sections / 693 name
occurrences / 546 keys / catalog 64, with 42 initial checks and 18 follow-ups.
See COMPANY-SOURCE-VARIETY-VISIBILITY-REVIEW.md; CAT-01/CAT-02/TD-116 remain open.
Local only; exact pinned-parent push approval unanswered, no new PR/remote CI,
merge/deploy or other-berry Landscape rollout.

October 8 local source continuation (checks begun October 7): Marionnet/FNM/
NC State add 16 bounded sections, 45 occurrences and six held fruit photos.
Marvella MAR118/MAR109 and Marly photo captions stay unresolved; Pink Star
codes stay separate. FNM catalog-body names include menu omissions; Noelia
is raspberry. NC State recommendations are separate from release records;
Ervin/NC 740 pairing and source dates remain unreviewed. 66 affected checks
pass, plus six overlapping final checks; records and original 1,992 JSON
preservation pass. Latest audit: 120 sections / 693 occurrences / 53 catalog
text matches / 640 review needs / 546 keys; 35/77 subjects partly checked,
42 initial checks and 18 source follow-ups remain. Blueberry 185, strawberry
328, raspberry 113, blackberry 67. Catalog 64; photos 31/30 held/zero newly
approved public. See MARIONNET-FNM-NCSTATE-PORTFOLIO-REVIEW.md. CAT-01/CAT-02/
TD-116 and full redesign/release goal remain open. Local-only; pinned-parent
push approval unanswered, no new PR/CI, merge/deploy or Landscape rollout.

October 7 selected-article follow-up: the private Reader can find explicit
variety names in one stored/cached article and send new names to identity review.
Catalog matches and earlier human decisions remain intact; publication status,
original URLs and declaration context stay visible. Filters/alphabet preserve
article scope; no provider calls, global body hydration or automatic approval.
The unchanged summary diagnostic remains 60/64, four raw-body misses, zero extras;
selected-article behavior has separate tests, not a new global recall claim.
Default coverage stays 104 sections / 648 occurrences / 518 candidate keys;
45 initial company checks, 17 follow-ups and CAT-01/CAT-02/TD-116 stay open.
See VARIETY-SELECTED-ARTICLE-REVIEW.md. Local only pending pinned-parent push
approval; no new PR/CI, merge/deploy or other-berry Landscape rollout.

October 7 local patent/source recheck: eight original blueberry filing subjects
reuse existing catalog identities; wrong PP25,358 ornamental subject excluded.
OZblu old mapping redirect and blank Rejoice English PDF remain source gaps.
40 focused checks pass; records validate and original 1,992 JSON unchanged.
Latest totals: 104 sections / 648 occurrences / 52 catalog text matches /
596 review needs / 518 candidate keys; 32/77 subjects partly checked, 45
initial checks and 17 follow-ups remain. Blueberry 185, strawberry 306,
raspberry 101, blackberry 56. Catalog 64; photos 25/24 held/zero public.
See docs/v2/OZBLU-PATENT-SOURCE-RECHECK.md (or same-directory note).
CAT-01/CAT-02/TD-116 and full mission stay open. Local-only pending parent
push approval; no new PR/CI, merge/deploy or Landscape rollout.

October 7 PSG/OZblu follow-up: nine source observations and two credited held
photos; three failed catalogs explicitly recorded. Brand/platform/cultivar
codes and the conflicting package photo are kept distinct. Existing Magica
alias is reused without a duplicate candidate. Dense profile photo/content
columns and phone stacking are native-reviewed; 52 profile/photo and 32 public-snapshot/portfolio tests pass.
Original 1,992 JSON unchanged, catalog 64. Latest totals: 93 sections / 640
occurrences / 44 text matches / 596 review needs / 518 keys; 32/77 subjects
partly checked, 45 initial checks and 15 source follow-ups remain. Photos
25/24 held/zero public. CAT-01/CAT-02/TD-116 and full mission remain open.
See PSG-OZBLU-PORTFOLIO-PHOTO-REVIEW.md. Local-only pending parent approval;
no new PR/CI, merge/deploy or other-berry Landscape rollout.

October 7 Mountain Blue/Costa follow-up: 28 original-source observations and
three held attributed fruit images added across seven bounded sections.
Duplicate panels and unnamed placeholders do not inflate variety counts;
ambiguous Dazzle photo is withheld. SI-145 species/status and Nebula text-only
report remain unreviewed. Four new plus 61 existing regressions, records and
native Bounty preview pass; all 1,992 original JSON unchanged, catalog 64.
Current scope: 84 sections / 631 mentions / 42 text matches / 589 review needs /
511 keys; 30/77 subjects partly checked, 47 initial checks and twelve source
gaps remain. Photos 23 / 22 held / zero approved public. Complete portfolios,
independent recall, rights/profile depth stay open; CAT-01/CAT-02/TD-116 open.
See MOUNTAIN-BLUE-COSTA-PORTFOLIO-REVIEW.md. Local-only, pending exact parent
push approval after automatic rejection; no new PR/CI, merge/deploy or rollout.

October 7 CIV sheet follow-up: eleven original technical-sheet attempts add
nine source heading observations and four separate code leads. Seven bounded
checks are enumerated; two partial and two unreadable bodies retain explicit
limits and their original index leads. Comparisons are excluded from own
portfolios; no automatic identity, rights, trait, photo or human review change.
72 regressions, record validation and native candidate review pass; existing
1,992 JSON files unchanged and catalog stays 64. Current scope: 77 sections /
603 mentions / 36 text matches / 567 review needs / 499 derived keys. 49 initial
subject checks and eleven source gaps remain. Photos unchanged: 20 references,
19 holds, zero public approvals. CAT-01/CAT-02/TD-116 remain open. See
CIV-TECHNICAL-SHEET-IDENTITY-REVIEW.md. Local branch; parent push question still
pending after automatic rejection. No new PR/CI, merge/deploy or Landscape rollout.

October 7 European source follow-up: three more companies now have bounded
portfolio checks: CIV's 29 index names, Hansabred's six cultivars and Nova Siri's
five current products. Four new attributed images use the private session
control. Literal codes, species/use context and human decisions are preserved;
no comparator, filename code or registered-mark legal claim is inferred.
71 regressions, records and native desktop/360px phone acceptance pass.
Current catalog 64; 66 sections / 594 mentions / 36 text matches / 558 review
needs / 495 derived keys; 20 photos / 19 unknown-reuse holds / zero approved
public. 28 of 77 subjects have some enumeration, leaving 49 initial checks.
Seven existing source gaps, complete historical portfolios, technical sheets,
official rights verification, independent recall and profile depth stay open.
See EUROPEAN-PORTFOLIO-NAME-PHOTO-REVIEW.md. Local child branch; prior 0ce865d
push awaits specific approval after two automatic rejections. No new PR/CI,
merge/deploy, trust promotion or other-berry Landscape rollout.

October 7 local follow-up: ASD/Benning/Inka's bounded original-source checks add
12 name mentions and two visibly labeled, credited blueberry images. Generic
images, spelling corrections, ownership and map claims are not inferred.
67 regressions and records pass; native Matías show/hide retains unconfirmed
reuse. Current catalog 64; scope 60 sections / 554 occurrences / 34 matches /
520 review needs / 461 derived keys; 16 photos / 15 held / zero approved public.
25 of 77 subjects have some bounded enumeration; 52 lack an initial checked
section. Full portfolios, named Benning planting sources and the Inka's
historical report still need research. CAT-01/CAT-02/TD-116 remain open.
Delivery is on a separate local branch; prior 0ce865d push was rejected twice by
automatic approval review and the specific authorization question is pending.
No new PR or exact-head CI exists yet; the preceding checkpoint's CI/draft
wording denotes required delivery, not a completed push. See
COMPANY-NAMED-PHOTO-COVERAGE-REVIEW.md. No merge/deploy/other-berry rollout.

October 7 CFIA code-photo follow-up: source-specific exact-code photo preview
now works for ASF218/ASF219 without confirming trade-name aliases or canonical
associations. Four held photo references and two unreviewed registry rows add
bounded source context; source dates, roles and rights remain human-reviewed.
Tall-photo caption overlap and partial card visibility are corrected; native
desktop/360px phone acceptance passes. 144 local regressions, session JavaScript
and records pass; exact-head CI is recorded with the draft. Catalog stays 64;
current counts are 55 sections / 542 occurrences / 34 matches / 508 review needs /
452 candidate keys; 14 photos, 13 held, zero approved public. Two proposed private
candidates are additive and replay-safe; existing records/user state remain
unchanged. CAT-01/CAT-02/TD-116 remain open. See
CFIA-CODED-VARIETY-PHOTO-REVIEW.md. No merge/deploy/other-berry rollout.

October 7 crop-scoped catalog follow-up: the reviewed-candidate authoring path
now separates known disjoint crops sharing a name, while exact same-crop,
unknown-crop and ambiguous matches retain duplicate guards. Review aids cannot
widen the checked name/berry. Native isolated fictional acceptance preserves
the original record and separate source/claim gates; no real human decisions
or catalog additions. 74 focused tests and record validation pass; exact-head CI
is recorded with the draft. The preceding cross-crop authoring blocker is
superseded; actual counts stay unchanged. CAT-01/CAT-02/TD-116 remain open.
See VARIETY-CROP-SCOPED-CATALOG-REVIEW.md. No merge/deploy/other-berry rollout.

October 7 release/patent photo follow-up: three source-labeled images from
the USDA Keepsake strawberry release and FC11-164 patent figure now reach private
galleries with individual session-only Ignore permission controls. Strawberry
Keepsake stays separate from blueberry Keepsake. A misleading cross-crop catalog
shortcut is corrected; catalog preparation remains blocked until crop-specific
creation can preserve the generic writer's duplicate guard. No saved permission,
human identity, canonical variety, rights or region decision changes.
106 focused checks, session JavaScript and record validation pass; native desktop
loads and reversible photo choices are verified without runtime file changes.
Current coverage: 64 catalog varieties, 53 sections, 540 occurrences, 34 text
matches, 506 review needs, 450 derived candidate keys before private state.
Ten source photos: nine held and zero approved public; 55 initial company checks
and seven follow-ups remain. Mobile acceptance of these new views is unverified.
See VARIETY-RELEASE-PATENT-PHOTO-REVIEW.md. CAT-01/CAT-02/TD-116 remain open;
exact-head CI is recorded with the draft. No merge/deploy/other-berry rollout.

Ongoing goal activated October 1, 2026. This checklist is the completion ledger for the accepted conversation requirements, not a claim that all draft work is deployed. Each mission must update its evidence and unresolved work here. Final release requires user review before merge or deployment.

## Checkpoints and completion standard

October 7 patent Reader repair: a real FC11-164 source capture returned only a
legal-event note while its original document contained an abstract, description
and claim. The shared live Reader now preserves bounded plain-text document
sections, headings, lists and table cells, with section jumps and explicit
Reload source text. A failed same-source refresh preserves the previous capture;
source edits and human review gates remain intact. This private reading aid does
not approve identity, traits, rights or legal status, and does not appear in the
readonly/static snapshot. Google Patents semantic HTML is supported; other
registry formats and full PDF text remain coverage gaps. No domain schema,
canonical variety record, model qualification or collection setting changes.
See PATENT-READER-DOCUMENT-REVIEW.md. The parent recall draft #334 passes all four
required checks on 42b7cac: 4,159 passed / 11 skipped / two existing warnings.
The 60/64 synthetic recall diagnostic retains four body-only misses, and actual
catalog/portfolio counts stay unchanged; CAT-01/CAT-02/TD-116 remain open.
No merge, deployment or other-berry Landscape rollout is authorized here.

October 7 explicit-list recall follow-up: the unchanged 24-case diagnostic now
finds 60 of 64 expected name occurrences (previously 50), with zero unexpected
names and 23 cases passing every specified check. Mixed crop/name/code tables
and explicit Spanish/Polish declarations preserve each crop, whole name, code
and original source URL. Unknown/malformed rows are held; article bodies and
unpublished drafts are not scanned. Human rejections and edits remain intact.
This synthetic diagnostic is not independently human-verified, model
qualification or a global completeness measure. Four body-only misses remain.

The actual stored-source audit is unchanged: 1,269 sources / 95 observations /
32 text matches / 63 review needs. Catalog remains 64; primary occurrences
537 / matches 33 / review needs 504 in 51 sections; derived candidate keys 448
before private state. Of 77 registry rows, 22 have some enumerated checks and
55 still need initial checks; seven source follow-ups remain. Seven source-labeled
photos (six held, zero approved public photos) and the session-only Ignore
permission control from draft #333 are retained. That exact parent head passes
all four checks: 4,138 passed / 11 skipped / two existing warnings.

The final focused regression and this draft's executable CI are recorded with
the PR; no source approval, identity decision, canonical addition, merge,
deployment or other-berry Landscape rollout is implied. CAT-01/CAT-02/TD-116
remain open. See VARIETY-EXPLICIT-LIST-RECALL-REVIEW.md and the retained session
photo behavior in VARIETY-SESSION-PHOTO-PREVIEW.md.

October 7 attributed variety-photo requirement: include photos wherever useful
on variety profiles and in review/directory surfaces when the source identifies
the named variety and the image can be reused with recorded attribution. Keep
photographer/publisher credit, original source link, reuse terms, caption and
identity confidence attached. Distinguish trial plants, fruit samples and
patent drawings; candidate photos remain unreviewed and do not approve an alias,
trait, rights holder or growing region. Keep dense tables and the long review
queue compact, with larger photos in profile/expanded detail. The private
gallery/editor/thumbnail slice and one source-labeled Columbia Star ARS photo
are implemented and desktop/phone-reviewed in draft #331. Corrections, hiding,
restoration and reset reuse existing profile history; name/berry compatibility
is enforced. Readonly/static exclude new associations, and unknown reuse stays
source-link only. Full source population and public human publication remain
OPEN. Other existing portfolio PDF/website images have not yet been cleared
for reuse or matched into a photo gallery. See
VARIETY-ATTRIBUTED-PHOTO-COVERAGE.md; CAT-02 includes this explicit requirement.
The previous navigation/rights-reference draft #330 has four green exact-head
checks: 4,106 passed / 11 skipped / two warnings, run 37690588963.

October 7 candidate-review follow-up: keep the alphabet available while deep in
the list; use a compact phone picker and List top / Filters shortcuts. Existing
scope survives letter selection and hash targets clear the shared header. This
UI requirement is implemented with 70 focused tests and native desktop/phone
review; draft full CI is pending. User also asks for patent information and
claims click-through: existing variety Rights / IP remains, and candidate
review now explicitly links stored tier-1 patent/PVR and registry sources,
retaining dates and unreviewed status. An index is not an individual patent.
Full rights coverage, original-document/claim-level provenance and dated
jurisdiction/status verification remain OPEN within CAT-02 / TD-116.
Parent #329 has four green checks (4,102 passed / 11 skipped / two warnings).
See VARIETY-REVIEW-QUICK-NAVIGATION.md. No new source observations or catalog
entries, no human decisions, merge or deployment.

October 7 visual historical-source follow-up: all 38 pages of a UGA public
presentation are accounted for, including two handwritten photograph labels
missed by extracted text. Eleven unreviewed name/code observations add ten
candidate keys; Alapaha remains an explicit ambiguous-label exclusion. Three
named blueberries and six experimental ornamental selections keep separate
contexts; Premier and T-959 are photo-only leads, and T-959 is not an approved
Titan alias. Primary totals are 506 occurrences / 33 catalog matches / 473
review needs in 46 sections, with 423 derived candidate keys before private
state. Canonical catalog remains 64; 57 initial registry checks and four source
gaps remain. GRIN now has 132 missing exact names / 14 queued / two catalog
matches before private state, because Premier has a primary-source lead.
Portfolio-derived references no longer become official registry attribution;
stored human records are preserved. 86 focused/static tests pass. Parent #328 passed
all four exact-head gates (4,100 passed / 11 skipped / two warnings). This draft's
CI is pending; no trust promotion, merge, deployment or Milestone B rollout.
See VARIETY-HISTORICAL-BLUEBERRY-VISUAL-REVIEW.md.

October 7 blueberry public comparison: GRIN's 2,113 search hits reconcile to
315 source-classified Cultivar records; 178 records / 148 names are in four
checked blueberry species, 57 records / 53 labels are generic hybrid crop
questions and 80 cultivar records are outside the checked scope. The other
1,798 material records are excluded. Query/synonym matches include 95 records
from other genera. Before private state, 133 scoped names have no exact catalog
or queue match, 13 have queue matches and two have catalog matches. Individual
missing-name handoff now reuses private additive candidate review and preserves
user edits/decisions; it does not approve identities or catalog entries. 77
focused checks, record validation and desktop/phone review pass; draft CI is
pending. Parent #327 has all four green gates (4,083 / 11 skipped). Catalog 64,
primary 495/33/462, 413 candidate keys, 57 initial checks and four source gaps
remain unchanged before private state. See VARIETY-BLUEBERRY-GERMPLASM-COVERAGE-REVIEW.md.
CAT-01/CAT-02 remain open for verification, authoring, recall and profile depth.

October 7 independent germplasm comparison: GDR's native Fragaria/Rubus export
accounts for 26,905 rows / 6,453 accession-organism keys / 2,355 literal labels /
2,372 genus-name pairs. Before private state, 2,267 pairs have no exact catalog
or queue name match, 104 have queue name matches and one has a catalog match.
The existing coverage page exposes these gaps with search, source identifiers,
50-row pagination and links to existing review. These are unreviewed research
leads, not new approved varieties; raw export remains private. Catalog 64,
primary 495/33/462, candidate keys 413, 57 initial checks and four source gaps
are unchanged. 50 focused checks and record validation pass; parent #326 has
four green gates (4,070 passed / 11 skipped). CAT-01/CAT-02 remain open. See
VARIETY-EXTERNAL-GERMPLASM-COVERAGE-REVIEW.md. Blueberry baseline and profile depth
remain outstanding, alongside individual human identity and claim decisions.

October 7 historical identity follow-up: six Hutton legacy entries and thirteen
USDA paper contexts add 19 observations and 14 candidate keys. Shared labels
with differing/missing codes retain warnings and separate candidate keys until
human review; code/name pairs are visible in summaries. Primary scope is now
495/33/462 in 45 sections; 413 keys before private state, catalog 64, 57 initial
registry checks remaining. Four source gaps remain, including unread PDF
pedigree material. Desktop and phone review preserve source links and human
gates. Parent #325's four exact-head gates pass with 4,063 tests. CAT-01/CAT-02
remain open. See VARIETY-HISTORICAL-IDENTITY-COVERAGE-REVIEW.md. Earlier numbers
below record prior slices.

October 7 public-program follow-up: Hutton, USDA ARS and UGA add 20 name
observations. Latest primary scope is 476/33/443 in 43 sections; 20 registry
rows have some checks and 57 need initial checks. Candidate keys before private
state: 399; catalog remains 64. Three source gaps are prominent, including
Hutton's incomplete lifetime list and UGA's inaccessible licensing listing.
Names, wild selections, species and genome labels retain their distinct scopes.
37 related checks pass; parent #324's four exact-head gates pass with 4,056 tests.
CAT-01/CAT-02 remain open. See VARIETY-PUBLIC-PROGRAM-COVERAGE-REVIEW.md.

October 7 capture/date follow-up (CAT-01/CAT-02/NEWS-01): existing guarded
recovery retrieved two of four public source copies, with two recorded access
failures. Shared acquisition no longer assigns sidebar/update dates as article
publication dates. New captures retain explicit date provenance or unknown;
feed fallback and earlier artifacts are preserved. Native review confirms the
correct June 8 BluGenix date and pending human decisions. No canonical/readiness
additions or independent recall claim. See ARTICLE-PUBLICATION-DATE-FIDELITY-REVIEW.md.

October 7 catalog expansion is an independent draft slice stacked on revised
blueberry checkpoint #313, not merge/deployment or Landscape Milestone B rollout.
The new catalog rows remain open beyond their delivered first slice.

October 7 recall follow-up: CAT-01/CAT-02 retain a 24-case curated synthetic
diagnostic, with actual detection improving from 46/64 to 50/64 after spaced-code
and long-F1 repairs; unexpected names fall from one to zero. Later table, Spanish
and Polish repairs reach 60/64 with four raw-body misses; the selected-article
action is tested separately and does not change the fixture. Independent human
verification, real acquisition, canonical authoring and remaining portfolio
coverage are open. #320 now delivers the candidate-to-existing-authoring
navigation; actual human decisions and catalog growth remain open. See
VARIETY-NAME-RECALL-DIAGNOSTIC-V1.md. No model qualification,
catalog approval, merge or deployment is implied by a passing diagnostic command.

Historical release checkpoint, October 5, 2026: `origin/v2/intelligence-os` is `916b8f09f9ce2a1847335d7990ea80ff921f1cec`, an ancestor of the approved stack. The expansion guide has no diff. At that checkpoint, drafts #272–311 remained unmerged; PR #312 subsequently integrated the approved release. Historical #311 exact head `8be0d39614f3c867f8a93dbcf2da216c191de617` passed all four required checks, run `37338997850`: 3,893 passed / 11 skipped / two warnings / 380.29 seconds. M38 adds authenticated recovery, native guide/upload, real packet capture/download/receipt restart and Map/phone/PDF evidence. RELEASE-REVIEW.md reconciles every requirement. #312 head 60d6f0f passed all four checks (3,895 / 11 / two warnings, run 37349791854); the final acceptance/presentation update requires its own exact-head checks.

Completion means implementation plus appropriate source/data proof, browser review, meaningful automated checks, exact-head required CI, preserved private/public and human-review boundaries, updated guide and a reviewable release. Unavailable source text, unresolved photo identities, absent geographic statistics and missing credentials must be reported honestly. Human confirmation must never be simulated to close a checklist item.

## Archive boundary

Current work continues in [REDESIGN-REQUIREMENTS-CHECKLIST.md](REDESIGN-REQUIREMENTS-CHECKLIST.md).
