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


## October 13 release readiness refresh

Previous preamble and four superseded status rows retained verbatim.

## Current release review — October 13 UTC, 2026

The combined review is reconciled onto canonical `642bc556`, retaining the merged
manual Social Listening controls, their guarded provider behavior and pinned
language dependency. The governing guide and all 31 IDs/order remain unchanged.
The [combined release](CANONICAL-RELEASE-INTEGRATION-REVIEW.md) needs its own
exact-head checks and release rehearsal; the earlier results below are component
evidence. Broad catalog completion and actual human decisions remain distinct.

The parent draft #396 passes all four required checks on aa6a68fb:
4,956 passed / 11 skipped / two existing warnings. Child draft #398's capture
repair at f93aa702 also passes all four checks: 4,972 passed / 11 skipped / two
existing warnings, plus isolated host/restart/recovery/rollback verification.
The subsequent [labelled-list detection repair](PUBLISHER-DISCLOSURE-SOURCE-REVIEW.md)
now finds 23 printed entries where that detector returned zero on the same
unchanged pending copy. Twenty-one synthetic parser/integration tests and native
desktop/412px review pass; this later change still requires fresh pushed-head CI.
Ten entries match existing varieties; thirteen need review, not automatic catalog
creation. Twenty more source copies and one repaired proposal remain pending in
separate local review inboxes. The original 32-source worksheets, all 31 IDs/order,
canonical 64 varieties and actual human decisions remain unchanged.

The blueberry checkpoint was approved October 12. Draft #396 now implements
the remaining four-crop Landscape scope: All berries, paired comparison,
existing-store saved selections, cited traits, shared company marks/lists and
complete PDF/HTML/SVG/CSV exports. The visual guide has twelve section cards,
four workflow steps and six reporting choices. No repeated blueberry feedback
or local review-download approval is required.

Application head `ec80d8afdb6dbc1558c05d292d250d03296c3c24` passed an
authenticated isolated host rehearsal: fifteen sections, twelve crop/format
exports, original register references, restart preservation, 2,961-file empty
target recovery and prior-image rollback. The 32 pending source copies and
original draft remain protected. A separate fresh production backup verifies
14,051 files; the live application and its configuration were unchanged.

Its full CI found one historical test-corpus boundary failure (4,954 passed /
11 skipped / two warnings). The correction explicitly compares the journal's
actual before/after corpus and separately checks that saved operator IDs,
rejections, notes and photos survive the later register capture. Forty related
tests pass. Fresh checks on the corrected review head still gate release.

The [current combined review](CURRENT-BLUEBERRY-CATALOG-REVIEW.md) and
[release review](RELEASE-REVIEW.md) distinguish these current results from the
accepted October 6 redesign in PR #312 and its historical evidence. All 31
requirement IDs and their order remain unchanged. CAT-01/CAT-02 remain open;
bounded source coverage is not global completeness. Source, identity, catalog,
Atomic, qualification and photo decisions remain separate human gates. Merge
and production deployment require subsequent release approval.


| CAT-01 | Reconcile sources against the variety catalog so visible named varieties cannot disappear silently | Stored corpus discovery, automatic known-article-text checks plus explicit additive Keep and original portfolio observations feed private identity review. Exact names, dates, codes, provenance and human decisions survive; existing intake retains separate source/claim review. The native Hortifrut capture finds 24 names and the #368 private article audit reaches 103 / 32 catalog matches / 71 discoveries before human decisions, with 750 combined candidate keys in the isolated preview after the original trial image-table observations; see [pending article review](PENDING-ARTICLE-VARIETY-COVERAGE-REVIEW.md). Test-only article hierarchy preview copies are excluded from those coverage counts. Current bounded portfolio audit and preservation proof are in [ROYALBERRIES-CAS-SOURCE-PLAN-REVIEW.md](ROYALBERRIES-CAS-SOURCE-PLAN-REVIEW.md); latest observations are measured by `scripts/audit_variety_portfolios.py`. GDR/GRIN comparisons retain original-name handoff without automatic identity decisions. | The current read-only published audit finds 95 explicit named identity strings / 32 catalog matches / 63 review needs. Saved published records still have zero readable bodies out of 1,269 (1,198 unavailable and 71 access screens), excluding pending/runtime capture. Further acquisition, declaration formats/languages, independently reviewed recall and actual human identity/catalog additions remain. Original synthetic diagnostic reaches 60/64; four legacy raw body fields are intentionally outside the supported Article path. The 32-copy profile diagnostic improves 28 to 35 occurrences, without independent human recall qualification; see [profile-name review](ARTICLE-PROFILE-NAME-RECALL-REVIEW.md). |
| CAT-02 | Build toward the most comprehensive berry variety resource, with measurable gaps and refreshed provenance | Four-berry original-source coverage, original patent/PDF links, attributed session photo previews, company/program handoffs and analyst website overrides are implemented. Latest bounded audit and source limits are in [current combined review](CURRENT-BLUEBERRY-CATALOG-REVIEW.md): 395 sections, 1,572 occurrences (102 catalog-matched; 1,470 requiring review), 1,126 public-source-derived candidate keys (operator-private state counted separately), 64 unchanged canonical records and 126 photo references with no new reuse approvals. The [profile-field inventory](VARIETY-PROFILE-FIELD-COVERAGE-REVIEW.md) exposes scoped per-variety gaps for photos, patent/PVR references, cited traits and company roles without a completeness score. Offline pending-copy detections are a separate diagnostic, not approved catalog additions. The 77-row source plan distinguishes named, incomplete, unavailable, unstarted and identity/scope holds; no fabricated company closes a gap. Independent GDR/GRIN are scoped collections, not complete global catalogs. | 14 entries have incomplete lists, one has unavailable sources and two supplied labels are held; zero unstarted in the full view does not mean complete portfolios. Existing numbered register references now appear privately in profiles and profile-field inventory; a live one-record CPVO recheck and the denomination self-pairing repair retain human/crop/code gates. Ten profiles have imported/rechecked references, and 29 of64 have no patent/PVR reference. The four-berry source recheck adds ten applications across nine more existing names and keeps source-reported status plus archived captures readable. Sixty-five related and 26 final history regressions pass; the preceding reference projection also passes all four required checks with 4,951 tests. A 1,755-page public-exclusion build passes; see IMPORTED-REGISTER-REFERENCE-REVIEW.md. Full/current/historical release and rights verification, hybrid crop resolution, human catalog authoring, cited traits/images/regions, refresh reconciliation and independently scored recall remain. No global completeness or web-leading claim. |
| LAND-02 | Evidence-backed multi-berry Landscape, dense narrative, source/variety and dossier handoffs, comparison, saved views and complete visual exports | User explicitly approved blueberry October 12. Consolidated draft #396 enables all four existing crops, All berries and two-crop comparison with distinct genetics and shared actors; 123 related tests and trusted static build pass. Saved Explorer selections reuse the existing revision-checked store, with 91 persistence/auth/controller tests passing. CAT-01/CAT-02 source-name repair remains behind human review. | Complete PDF/HTML/SVG/CSV browser downloads and 100 focused regressions pass; All/comparison and 412px light/dark review are complete. Saved update/archive/restore/copy and restart preservation are browser-verified; the twelve-section guide is refreshed for Social Listening and full Landscape reporting. Existing cited traits/sensory context now preserves source basis, units, conditions and qualifications in Explorer/PDF/HTML/SVG; 107 related and 15 final export tests pass. Shared favorites/tier/list scope and saved-selector fixes pass 120 focused tests; actual copied-runtime browser creation, applied-crop saving, nine-page PDF and 17-association CSV preserve the 13 selected connections. Company marks remain separate from evidence approval. Wider performance, fresh current-head CI and final release review remain against the retained brief. This approval does not authorize merging or deployment. |
| REL-01 | Integrate approved stack, reconcile canonical, run all gates and prepare release/rollback plan for intel.johnnyaceii.com | Canonical `7360c5821c009484381394ed8afa9fb91e322a50` was reconciled before this candidate, preserving the governing guide. Application head ec80d8af has a verified 3,679-file committed package and authenticated fifteen-section/twelve-export/restart/2,961-file recovery/prior-image rollback rehearsal. Thirty-two pending source copies and original draft are preserved. A fresh actual production backup verifies 14,051 files and records the available previous image/configuration without restarting or editing production. See RELEASE-REVIEW.md. | ec80 full CI found one historical replay-test boundary error; 4,954 passed. Forty corrected replay/reference checks pass. Required fresh checks on the corrected head and a final canonical/head reconciliation remain. No deployment, merge or independent human source/catalog decision is implied by these results. |


## November 4, 2026 — previous active status before live411 reconciliation

These dated records are preserved verbatim. The active checklist supersedes their use of “current,” “live” and “pending.” The preceding Project Status is retained with its original relative-link base in [Project Status history](../../PROJECT-STATUS-HISTORY.md#november-4-2026--previous-active-status-before-live411-reconciliation).

### Previous docs/v2/REDESIGN-REQUIREMENTS-CHECKLIST.md

# Current verified releases and remaining mission — November 3, 2026

[Catalog #488](https://github.com/samsonFive/berry-intelligence-os/pull/488) is
merged and independently verified live at `32eefbd5` (approved `22dcb869`),
retaining News #487, #486 and earlier platform releases. All four final checks
pass: 6,277 tests. Fresh release-time and live checks retain all five accounts
including Chris.H, 65 profiles, 10,539 existing JSON records, four databases and
1,115 research files. One source import is added; no existing data was replaced
or restored. Settings, mounts, proxy, active/enabled News schedule, backup and
rollback are preserved. The #486, #487 and #488 approvals are fulfilled.

The source import recovers three PSG selectors and two related lists: 44
occurrences of 34 printed names/codes, 18 additional review keys and 34 held
photo references. All 1,315 earlier public-source keys remain. The scoped public
corpus is now 539 sections /2,073 occurrences /1,333 review keys, with 11
unreadable sections and 143 follow-ups. These are source observations and review
candidates, not 1,333 approved varieties or proof of worldwide completeness.
Canonical variety identities, company roles, rights, growing footprints and
photo reuse still require their existing human decisions.

News #487 finalizes useful capture as partial when optional tagging fails.
Provider quota is still an operational dependency; no purchase or paid retry is
authorized. The one approved Learn acceptance run completed previously and
remains an editable AI draft. The visual Help explainer and collaborative
Workspaces/private Digest and layout boundaries remain delivered.

Cold catalog visits still take several seconds; TD-122 remains open. The exact
Reader-key implementation in closed, unmerged #489 preserved all eight complete
outputs but gave mixed page/workflow timings. It is excluded from live release;
the stronger prototype figures are not final-code or deployed claims.
[The current investigation](COLD-CATALOG-INVESTIGATION-2026-11-03.md) retains this evidence and earlier
rejected experiments. The independent human expected-name audit, source and
trait/IP/photo depth, held Map selections and broader Learn quality remain in
this mission. Original 31 definitions/order, the governing guide and all human
review gates remain unchanged. Earlier entries below are historical records.

# Catalog source continuation — November 3, 2026

[The PSG recovery proposal](PSG-RENDERED-SELECTOR-REVIEW-2026-11-03.md) recovers
three unreadable country selectors and two detail-page related lists: 44
occurrences, 34 distinct printed names/codes and 34 held photo references. All
1,315 earlier review keys remain; 18 additional keys bring the combined view
to 1,333. The bounded corpus has 539 sections, 2,073 occurrences, 175 text
matches, 1,898 review needs, 11 unreadable sections and 143 follow-ups. The
77-subject plan and all human review gates are unchanged. This is not global
completeness or approved identities. Platform #487 is live at `892f84db`, retaining #486; this
source proposal remains unapproved. Earlier dated
release statements below retain their historical scope. TD-122, source depth,
independent recall and held Map decisions remain open in this mission.

# News refresh completion follow-up — November 3, 2026

Combined #486 is approved and merged at `b8b8b008`; its deployment remains in
progress. A scheduled News run exposed an independent failure: optional AI tag
classification exhausted provider quota and left an otherwise completed capture
marked `running`. The separate repair finalizes useful capture as partial,
retains story counts and the classifier failure, and writes the run receipt.
All 79 affected tests pass with zero attempted external connections. No paid
retry, source review, canonical identity or saved-user-data change is included.
Final CI, browser review, preservation and separate release approval remain.
Cold catalog work and source/name/photo/Map human decisions remain open here.

# Crop-word preparation — November 3, 2026

[The crop-word child](CROP-WORD-PERFORMANCE-REVIEW.md) follows separately tested, unapproved #483/#484.
It retains the full global source corpus and original Unicode matcher, skipping
only scans with no necessary crop prefix. The eight-process prototype preserves
complete typed models/HTML and improves the two measured route medians by about
12% and 6%; final-code acceptance remains. Initial 112 focused tests pass.
No cache, grammar, canonical identity, source addition or human decision changes.
TD-122, source/catalog/photo and held Map reviews remain open. Original 31
definitions/order and the governing guide remain unchanged. #477 remains live.

# Declaration preparation continuation — November 3, 2026

Frozen #483 (`d8a28e31`) passes all four PR and canonical-base checks, 6,214 tests,
native desktop/phone review and fresh isolated preservation; it remains
unapproved and undeployed. The [empty-declaration child](EMPTY-DECLARATION-PERFORMANCE-REVIEW.md)
continues TD-122 with one runtime-file change and 294 passing affected checks.
Its prototype retains complete typed output/HTML, all source and human gates,
and original 31 definitions/order. Final acceptance remains; broad cold loads
and independent catalog/source/photo/Map decisions remain open here.

# Current Reader continuation — November 3, 2026

Approved #477 is deployed at `1ad5084f`; that approval is complete. #480 remains
tested and awaiting its own release approval. #482 passes all four checks
(6,187 tests), native desktop/phone review and fresh isolated preservation; it
has no release approval. The [NEWS-03 source destination follow-up](READER-SOURCE-DESTINATIONS-REVIEW.md)
keeps original URLs/review history while correcting unresolved Google News
labels and publisher navigation. Initial 112 focused checks pass; final
acceptance remains. All original 31 requirement definitions/order and human
source/name/role/photo/Map review gates remain unchanged. Earlier status notes
below retain their dated scope; none supersede these release boundaries.

# Active same-thread mission — November 3, 2026

Approved performance #476 is merged and verified live at `50659fcd`, tested head
`06255cfc`. All four checks /6,109 tests, desktop/phone review, fresh isolated
preservation and independent live image/HTTPS/proxy verification pass. Five
accounts including Chris.H, 65 profiles, 10,537 existing JSON records, four
databases, stored research, settings and mounts are preserved; backup and rollback
are retained. The #476 approval is complete and must not be requested again.

The user explicitly continued the remaining requirements in this mission/thread.
[Current closeout work](MISSION-CLOSEOUT-2026-11-03.md) covers performance,
catalog/source depth, human decisions, held Map figures and real-provider Learn
acceptance. Draft #477 prepares only visible company-tab models; its first head
passes all four checks and fresh production-copy preservation with a 12% faster
complete workflow. Phone review also prompted a compact header and grouped
secondary research links. The expanded head is undergoing renewed acceptance;
no new release is approved.
All original 31 definitions/order and the governing guide remain unchanged.

# Verified live #475 and remaining closeout — November 2, 2026

Approved News performance #475 is merged and independently verified live as
`6c2feaf1`, exact tested head `c666a481`, retaining #474 and the earlier platform.
All four ready-event checks pass /6,094 tests. A fresh bounded rehearsal preserves
all five accounts (including Chris.H),65 profiles,10,536 existing JSON records,
four databases and private research. Backup SHA, rollback, HTTPS and exact proxy
restoration are verified; no data or human decisions were added or restored.
The first switch correctly rolled back on a legitimate concurrent News refresh;
its state and failed-attempt evidence are retained. This release needs no further
approval. Earlier pending statements below retain their historical scopes/dates.

[The closeout audit](MISSION-CLOSEOUT-2026-11-02.md) separates unfinished cold-load
engineering from catalog/content and human-owned decisions. The source-only
company projection prototype was rejected because it moved cost to the next
Candidates click. The replacement draft keeps full portfolio output and tests
company-scoped News preparation plus request-local Candidates lookup preparation.
Its focused checks pass; complete-workflow measurements and final acceptance
remain. No new performance claim or release approval is implied. All original
31 accepted definitions/order and the visual Help guide remain intact.

# Verified live Help and current performance draft — November 2, 2026

Approved Help/checklist #474 is deployed as `7fa7dd53`, retaining #473 and
the platform stack. All four final checks /6,091 tests, desktop/phone review,
39 isolated route/PDF checks and live verification pass. Existing accounts,
data, edits, private research, settings and mounts are preserved, with backup
and rollback retained. Its release approval is complete; earlier pending
statements below retain their historical dates and scopes.

Separate News performance draft #475 preserves all original 31 definitions/order,
data and human review gates. Its 137 focused checks, complete-model/HTML parity
and native review pass. Current-head CI and current-live isolated validation
remain before its own release review. Cold-load debt and human catalog/source/
photo/figure/independent-recall work remain open.

# Verified live release — November 2, 2026, 21:28 UTC

Approved #473 is deployed as `d5b619b2`, retaining completed platform #468 and
#445. All four final checks pass (6,089 tests), the fresh isolated rehearsal
passes 53 route/PDF checks, and live preservation verifies all five accounts,
65 profiles, existing records, four databases and private research. The backup
and rollback are retained. No canonical varieties or human review decisions
are added. Earlier pending-release statements below are dated history.

The original 31 accepted definitions and order remain unchanged. Separate Help
draft #474 explains company comparisons and saved exports; it is not part of
the approved deployment. Human catalog/source/photo/figure decisions, content
completeness, real-provider Learn quality/cost and cold-load performance remain.

# November 2 — original regional names and credited photo references

CAT-01/CAT-02 follow-up: [Maryland Extension review](MARYLAND-ORIGINAL-CULTIVAR-REVIEW.md)
reconciles 53 table names and six photo captions from one publication. Existing
1,258 keys remain and 25 source-backed keys are added; no human decision,
canonical profile or photo permission changes. Exact named photos retain Haley
Sater's credit and existing preview gates. Original 31 definitions/order remain
verbatim. This source-only child retains #461; #462 and #449 stay separate, with
their existing unanswered release questions unchanged. Comprehensive coverage,
independent recall and human source/name/rights/photo decisions remain open.

# Redesign and consolidation requirements

November 2 — [Combined Learn/catalog review](LEARN-CATALOG-CLOSEOUT-REVIEW-2026-11-02.md)
retains all original 31 definitions/order while joining current #464 and #472
on live #445. Component checks and isolated preservation pass, but the joined
candidate requires its own final checks, browser review, current-live rehearsal
and release approval. Completed platform #468 is retained, not reapproved.
Source/name/role/photo/figure/Atomic decisions and broad performance depth stay
independent. Historical notes below retain their original review boundaries.

November 2 UTC — [Combined platform quality review](PLATFORM-QUALITY-COMBINED-REVIEW.md)
retains #460 performance/statement/startup work, #459 Reader capture repair and
the native keyboard-focus fix for one new combined review. Sixteen exact runtime
component files, both dated documentation histories, all original 31 accepted
definitions/order and the guide remain. Combined current-head/native/preservation
acceptance and its own scoped release decision are still required. Catalog/Map
#449 and source #461 are excluded; existing questions retain their scopes.

November 2 UTC — [Candidate keyboard focus](CANDIDATE-KEYBOARD-FOCUS-REVIEW.md)
adds a focused UI-03 repair after a native Shift+Tab failure beneath the sticky
alphabet bar. All 22 affected checks and phone/desktop comparisons pass; visible
controls, filter scope, alphabet navigation and ordinary scrolling remain.
This platform child retains #460 and excludes source #461 records. All original
31 definitions/order and human gates remain. Final acceptance is still required;
no production change or new release approval.

November 1 — [Reader publisher-chrome repair](READER-PUBLISHER-CHROME-REVIEW.md)
keeps header flags/menu graphics and site commerce headings out of new article
captures. Existing article headers, source wording, edited text/images and
explicit reload/cache policies remain. Offline publisher replay preserves all
21 non-header passages and selects the article figure; 125 focused checks pass.
The first isolated rehearsal exposed and now guards existing-image precedence;
new-head acceptance remains required, with the failed attempt retained.
This separate draft adds no catalog data or trust decisions and needs its own
current-head/native/fresh preservation acceptance and release approval. Frozen
#458 and #449 each retain their one unanswered question; source #457 remains
separate. Original 31 accepted definitions/order and guide stay verbatim;
broader TD-122/source/media limitations remain open.

November 1 — [Coverage identity lookup review](COVERAGE-IDENTITY-LOOKUP-REVIEW.md)
records a separate UI-03 performance experiment after #458. Optional read-only
lookup preparation retains matching decisions, same-request edit freshness,
all complete typed models and HTML. The first implementation was slower and
rejected; the revised cold sample improves, with confirmation and final
acceptance pending. No data/source/schema or production change. Original 31
definitions/order and the governing guide remain verbatim; TD-122 stays open.

November 1 — [News-first startup review](NEWS-ONLY-STARTUP-REVIEW.md) retains
the tested #455 platform changes while removing unrelated variety, briefing and
publication preparation from login/health/News readiness. News inputs, auth,
polling and human gates remain. Initial real-lifespan public-fixture comparison
preserves complete models/HTML and all 2,982 data files; specialist cold work
moves to its first visit. All 89 focused checks and record validation pass.
Confirmation/current-head/native/fresh preservation acceptance remains; no new
release approval or deployment. TD-122 stays open. Frozen #449 (one unanswered
question) and source #457 remain separate. Original 31 definitions/order and
the governing guide remain verbatim. Earlier notes are dated evidence.

November 1 — [Combined platform review](PLATFORM-PERFORMANCE-STATEMENTS-RELEASE-REVIEW.md)
brings tested Coverage performance #452 and statement-navigation/audit #453
together on live #443 (`f76080d0`). All ten runtime files retain their exact
component bytes; data, schemas, the governing guide and original 31 accepted
definitions/order remain. This combination requires its own combined tests,
native/static/current-head checks and fresh isolated preservation before any
new scoped merge/deployment approval. Component proofs do not approve it.
Frozen source/Map #449 retains its already-delivered question; source #454
is an independent historical-name follow-up. Neither catalog scope is bundled.
Earlier candidate notes below are dated component evidence, not a claim that
this new combined release is already live or approved.

November 1 — Approved navigation **#443** is live as `f76080d0` after
all four checks / 5,479 tests, fresh backup and preserved accounts, records,
settings, mounts and rollback. The snapshot navigation follow-up is delivered;
do not request that completed approval again. See the
[current completion audit](REQUIREMENTS-COMPLETION-REVIEW-2026-11-01.md) for all
31 requirements and later prompts. Catalog/Map #449 has one unanswered approval
question; original interview #450 and combined performance #452 are separately
tested drafts. This statement-link repair is a new candidate, not part of live
#443. Earlier dated notes below are historical. All original accepted
definitions and ordering remain unchanged.

November 1 — The [combined Coverage performance review](COVERAGE-PERFORMANCE-COMBINED-REVIEW.md)
consolidates tested #448 and #451 into one new review candidate on live #443.
All 133 affected checks and 48 complete-response comparisons pass. Full models,
source rows and profile fields remain; no data, schema or review decision changes.
The combination needs its own remaining acceptance checks. Source/Map #449 and
source #450 retain their separate scopes, and #449's one approval question remains
pending. All original 31 accepted definitions/order below remain unchanged.
The component evidence beneath this note is dated history, not combined proof.

November 1 — Approved navigation release **#443** is live as `f76080d0` from
explicitly approved head `e88fcd36`. Fresh backup, all four checks and offline/live
preservation retained five accounts, 65 profiles, 9,856 existing JSON records,
3,228 data files and four databases. Its release gate is complete. The separate
[photo-reference index](COVERAGE-PHOTO-REFERENCE-INDEX.md) is a performance-only
draft: no catalog data, domain schema or human decisions change. Draft #448,
combined source/Map #449 and historical-source #450 remain separate; #449 has
one pending scoped approval question and is not deployed. All original 31
accepted definitions and their order remain unchanged.

November 1 — Navigation #443 is live as `f76080d0`, following explicit approval
of `e88fcd36`, fresh backup and preservation checks. Independent UI-03 draft
#448 is reconciled onto it. A larger request-projection experiment retained
all content but made broad Coverage slower, so it is excluded from the draft.
The simpler source/field work passes 92 focused checks, full-model/24-response
parity and desktop/412px review; exact-head CI remains. TD-122 stays open. Catalog/Map #449 stays a separate review. All 31 accepted
definitions/order below remain unchanged; dated notes are history.

November 1 — [Combined catalog/Map candidate](CATALOG-MAP-COMBINED-REVIEW.md)
reconciles the CAT-01/CAT-02 and MAP-02 follow-ups with deployed navigation
`f76080d0`. All 181 focused checks, joined desktop/412px/PDF and static review
pass. The same 31 accepted definitions/order and protected guide remain; source,
name, photo, role, figure and model decisions are separate human work. Required
combined-head CI, fresh live-data preservation and actual release approval
remain. No content deployment is approved by navigation #443's completed release.

November 1 — Explicitly approved navigation #443, head `e88fcd36`, is merged as `f76080d0` and live. A new verified backup and bounded offline rehearsal preserved all five accounts including Chris.H, 65 profiles, 9,856 existing JSON records, 3,228 data files and four databases. The deployed image retains original mounts/settings and rollback; no new catalog or market-reference data was deployed. The separate local catalog #444 + Map #447 review candidate is now being reconciled onto this live base. Its earlier 179 focused checks and component browser/static proofs remain dated evidence; the new combined head still requires its own tests, preservation and actual release approval. Performance #448 remains separate. Earlier pending-navigation statements below are historical; the explicit approval question has been answered and the release is complete.

October 31 — [UK official Map references](MAP-UK-OFFICIAL-REFERENCES.md) add a separate explicit national-source check on tested446: three 2025 crop groups / nine figures keep original units, marketed definitions, provisional status and source cell provenance. Two workbook/narrative area differences remain visible rather than reconciled automatically. All159 affected checks, actual capture, canonical validation, desktop/412px/one-page PDF review and the1,797-page trusted static build pass. The public reference seed, human selections and all31 accepted definitions/order are unchanged. Exact-head full CI and separate release acceptance remain required.

Current live release remains approved #442, merge `3b0b4acc`. Navigation #443 passes all four final checks /5,479 tests and fresh isolated preservation, but is not merged or deployed: automatic approval review requires a scoped reply to the new explicit #443 question. Separate source draft #444 passes all four /5,481 tests and is excluded from this Map branch. Historical release notes below retain their dated scopes.

October 31 — [Three-crop official Map check](MAP-THREE-CROP-REFERENCES.md) extends the same bounded seven-country capture from strawberries to separately reported raspberries and blueberries: 21 latest country/crop references / 42 figures are available for explicit review. Original flags and 0n precision qualifications remain readable through Map/PDF; withheld or missing cells cannot become saved figures. All 123 affected checks, desktop/412px/two-page PDF review, canonical validation and a 1,797-page trusted static build pass. Published references and human choices are unchanged; wider world/crop coverage, exact-head full CI and release review remain open. This is separate from navigation #443 and source draft #444.

October 30 — [Gem-Pack interview coverage](GEMPACK-INTERVIEW-VARIETY-COVERAGE.md) adds three unreviewed source sections /ten name occurrences from two dated original interviews. Public-seed totals are525 /1,874 /165 /1,709;64 of77 supplied subjects now have named-source coverage. Gem-Pack retains five incomplete checks. All41 final affected tests and desktop/412px review pass; this source draft still needs its exact-head CI and later release. Canonical3b0b4acc retains approved442; navigation443 is separately tested and unreleased. All31 original accepted definitions/order remain. Earlier pending-release notes below are historical.

November 2 UTC — [Original ABZ infosheets](ABZ-ORIGINAL-INFOSHEETS-REVIEW.md)
adds inspected original PDF references for 18 existing names across six source
sections. CAT-01/CAT-02 depth improves while all 1,258 review keys, prior names,
photo holds and accepted definitions/order remain. Publisher claims, botanical
origin and blanket PBR wording do not become verified traits, planting regions
or rights. All 46 affected checks and local replay/static/native evidence pass
within their stated limits; phone keyboard occlusion remains under TD-122.
Current-head CI/fresh preservation remain; no merge/deployment or new approval.

November 1 — [Current ABZ product photographs](ABZ-CURRENT-PRODUCT-PHOTOS-REVIEW.md)
refresh nine original source sections and retain all 21 names and existing review
keys. Twenty-one credited, permission-held photo references are available through
explicit private-session preview; no image or identity is approved. Shared generic
images and the Milan/Elan mismatch are excluded. The old booklet remains a gap;
18 individual infosheet links are retained without claiming their PDF bodies read.
Source-child counts remain 526 sections / 1,883 occurrences / 165 matches / 1,718
review needs, with 1,258 keys and 66/77 named subjects. Source follow-up sections
are 144 because Milan's specific conflict is disclosed. Original31 definitions,
all previous data and the expansion guide remain unchanged. Live remains #443;
#449 retains its existing unanswered approval question, platform #455 is separate,
and tested source #456 remains the parent until this child independently passes.
Earlier dated notes retain their historical scopes. No merge or deployment.

November 1 — [Recovered Rejoice original sheet](REJOICE-ORIGINAL-TECHNICAL-SHEET-REVIEW.md)
replaces the effective blank-viewer check with one literal printed code, retaining
the original failed attempt. BK 17.006-13, BK3-17.006-13, PS-BK3-17.006-13 and
catalog BK 6-13 remain unresolved; no alias, extra proven cultivar, company role,
trait, photo or growing footprint is approved. Current source child: 526 sections,
420 readable/14 unreadable, 1,883 occurrences, 165 matches, 1,718 review needs,
1,258 combined review keys and unchanged 66/77 named subjects. All 31 accepted
definitions/order and the expansion guide remain unchanged. Live is #443;
#449 retains its existing unanswered approval question. Tested platform #455
supersedes #452/#453. Source #454 remains a tested parent; no release is inferred.
Earlier dated sections below retain their historical scopes.

November 1 — [Historical Singrow/Surexport sources](HISTORICAL-SINGROW-SUREXPORT-REVIEW.md)
add fifteen literal name occurrences from three original documents, retaining
the parent Splendor source and all identity/role/photo/rights gates. Current
source-child counts are 526 sections / 1,882 occurrences / 165 matches / 1,717
review needs; 66 of 77 subjects have named source entries. Existing gaps remain.
Navigation #443 is live as `f76080d0`. Catalog/Map #449 retains its already-asked
approval question; performance #452 and statement/audit #453 are separate tested
drafts. #448/#451 were superseded by #452. Earlier dated notes below retain
their historical scopes. All 31 original accepted definitions/order remain.

November 1 — Navigation #443 is live as `f76080d0` after actual approval of
`e88fcd36`, fresh backup and preservation. Its Help/Snapshot navigation gate is
complete. Performance #448 separately passes all four checks /5,486 tests and
fresh bounded preservation; TD-122 remains open. Catalog/Map #449 remains frozen
with its already delivered release approval pending.

The independent [Splendor historical-source child](SPLENDOR-HISTORICAL-SOURCE-REVIEW.md)
adds three printed blackberry names from an August 2011 company interview,
retaining source gaps and every human gate. All 31 accepted definitions/order
below remain unchanged; current evidence cells supersede dated history.

October 30 — Current live release is **#442**, merged as `3b0b4acc` from
approved head `ab6256c7` and deployed at 18:47 UTC. All four required checks
passed (5,477 tests). A fresh backup, isolated rehearsal and post-switch checks
preserved five accounts including Chris.H, 65 profiles, 9,854 existing JSON
records, 3,228 data files and four databases. Existing settings, persistent
mounts and rollback remain. This performance-only release adds no catalog data
or review decisions; it retains the platform, Tags and combined #440 release.
The large Coverage response is 77.10% smaller on the tested production copy;
repeat-load median improved from 3.41 to 2.72 seconds. Broader performance and
source/profile/media coverage remain open. See the
[source-detail review](COVERAGE-SOURCE-DETAILS-PERFORMANCE.md).

The separate Map snapshot navigation follow-up supplies its missing explicit
authoring context. It retains Workspaces, Social Listening, Landscape and the
one-click News refresh without changing public-mode navigation or snapshot
scope. Seventeen focused checks and isolated desktop/412px review pass; its
own exact-head CI and future release approval remain separate. All 31 original
accepted definitions and their ordering below remain unchanged.

Earlier dated release and pending-approval notes below are historical evidence;
they do not reopen approvals already completed in #433, #440 or #442.

October 31 — UI-03 performance follow-up:
[request-local source work](COVERAGE-REQUEST-WORK-PERFORMANCE.md) preserves the
dense source table, source content, filters, profile gaps and human decisions.
All 90 affected tests, complete-model/24-response parity, desktop/412px and
1,797-page static review pass. Source/profile timings improve in the isolated
sample; overall Coverage timings remain mixed. Exact-head CI and a separate
release review remain; all 31 accepted definitions/order are unchanged.

October30 — Approved combined #440 is merged1aef8862 and live with fresh backup,
bounded preservation, all required checks and native/live verification. The
catalog,27 visual Learn lessons and Map additions retain their human review
gates. Separate441 passes all four checks /5,471 tests; the
[source-detail performance child](COVERAGE-SOURCE-DETAILS-PERFORMANCE.md)
keeps every source row and body accessible while reducing the large measured
HTML77.23%. Its final136 affected checks and desktop/phone review pass; exact-head
CI and later release approval remain. All31 original definitions/order remain.
Older candidate and pending-release notes below are historical.

October 30 — [Combined catalog, Learn and Map review](CATALOG-LEARN-MAP-RELEASE-REVIEW.md) reconciles tested draft439 with deployed canonical6fe8bdeb, retaining the approved platform and subsequent Tags code. This new combination needs its own current-head checks, native review and fresh isolated live-data preservation; earlier component proofs and approval questions retain their scopes. No canonical merge or deployment. All original 31 accepted definitions/order remain.

October 30 — [Map reference country coverage](MAP-REFERENCE-COUNTRY-COVERAGE.md) connects the research picker to existing Map selectors and retains saved ISO references in scoped snapshots. An explicit France-only metadata correction preserves raw geometry; a seven-country Eurostat strawberry capture adds France/Italy/Poland proposals without changing the published reference seed. All 136 affected checks pass; desktop/412px review verifies the shared reference workflow and country-scoped figures. PDF labels use country names and separate dataset updates from publication dates. Broader country/crop coverage and human source decisions remain open. All original 31 accepted definitions/order and protected domain paths remain unchanged. This draft follows #437; exact-head CI and release review remain required.

October 29 — Platform-only #433 was explicitly approved, merged as `24b10f22` and deployed with a fresh backup and retained rollback. Offline and live checks preserved five accounts, 65 variety profiles, 9,822 protected JSON records and four databases. Shared Workspaces and personal Digest/layout boundaries, responsive navigation, the visual guide, News relevance and phone Reader fixes are live. Catalog, Learn curriculum and this Map expansion remain separate drafts; earlier dated candidate notes below retain their historical scopes.

October 28 — [Visual explanations across Learn](LEARN-CURRICULUM-VISUAL-REVIEW.md) extend the bounded curriculum from five to 27 lessons with interactive source-linked explanations, five new schematic designs and one additional attributed public-domain photo used in two lessons. Original records and human edits remain; double-cropping wording is clarified only when its two original fields match exactly. All final 130 affected Learn/static checks pass with one existing warning in 19.14 seconds; desktop/412px review verifies selection, actual photo loading, compact controls and header-safe lesson jumps. Exact-head CI remains required and is tracked in the PR review receipt. This does not close wider lesson/media/source depth, approve scientific claims or alter pending release decisions. No merge/deployment.

October 28 — [Visible source-gap summary](PORTFOLIO-GAP-SUMMARY-REVIEW.md). CAT-01/CAT-02/UI-03 follow-up keeps open source checks visible after a company gains named entries. The existing filtered subject flags drive the badge; services, source status, machine counters and all original 31 accepted definitions/order remain unchanged. This is a separate presentation child of source435; no completeness or trust approval is claimed. All 44 focused checks pass with one existing warning in 53.26 seconds. Native desktop/412px review confirms the corrected gap badge and retained company/berry scope; exact-head CI remains required for this child. Prior433/434 release scopes and source435 review scope remain intact. No merge/deployment or inferred approval.

October 28 — [Original company-release variety depth](COMPANY-RELEASE-VARIETY-DEPTH.md). CAT-01/CAT-02 evidence is refreshed to 522 sections / 1,864 occurrences / 165 matches / 1,699 review needs; six scopes retain ten names and one held photo. Sun Belle and Perfection retain incomplete portfolios despite newly named entries. All original 31 accepted requirement definitions/order are unchanged. Final 61 affected checks pass with one existing warning in 76.42 seconds. Native desktop/412px review confirms attribution, session image loading/hiding, source context, company filters and the visible Autumn 2022 interview period. Exact-head CI remains required for this child. Existing canonical records, guide, 31 accepted definitions and human gates are preserved. No merge/deployment or repeated/inferred release approval.

October 28 — [Catalog/platform compatibility](CATALOG-PLATFORM-COMPATIBILITY-REVIEW.md) reconciles source431 on tested platform433 without changing frozen review heads. Shared photo preparation retains all current catalog output, larger-preview and name/permission holds; all 31 accepted definitions/order remain. Final72 affected checks and full-output parity pass. Public64-profile corpus remains516 sections/1,854 occurrences and field gaps11/13/33/10. Current-head CI/native review and any later release-time live-data proof/approval remain required. Existing actual approval questions are not repeated or reinterpreted.

October 28 — [Combined platform release review](PLATFORM-COMBINED-RELEASE-REVIEW.md) integrates frozen #421 with #432 for one current acceptance check. Shared research/account-private Digest, on-demand profile work, responsive navigation and the visual guide remain; News relevance and phone Reader wrapping are included. Both documentation histories and all 31 accepted definitions/order are preserved. Catalog/source enrichment stays separate. Combined tests, native review, exact-head CI and a fresh isolated live-data preservation check remain required; no merge/deployment or inherited approval.

October 28 — [News company-name relevance](NEWS-COMPANY-NAME-RELEVANCE.md) adds fresh/cached/stored feed controls for a demonstrated software-company mismatch, preserving fruit licensing, agricultural technology, source records, images and user feedback. Initial 108 affected checks pass; native/current-head CI and separate release acceptance remain. All 31 accepted definitions and their order are unchanged; broader relevance and human source/catalog gates remain open.
## Current platform-only review — October 28, 2026

The [integrated platform candidate](PLATFORM-REVIEW-2026-10-28.md) combines
performance #410, personal Digest #412, responsive navigation #414, bounded
rehearsals #416 and the shared-Workspaces visual guide #420. Canonical/live
remains `e24b566b`; catalog #399/#400/#418/#419 is excluded. Shared research,
company lists/marks and review decisions stay shared; only layouts and Digest
state are personal. All original 31 accepted definitions and their order remain.
Individual component checks do not replace combined validation, current-data
preservation, release approval or release-time backup/rollback checks. Earlier
status notes below describe their own dated heads and populations.

## Current continuation — October 27, 2026

Live canonical `94a3b99b` includes shared Workspaces and the earlier platform,
Landscape, News/access and performance releases. Only layout settings and
Personal Digest are account-private; tested Digest isolation remains draft #412.
Draft #410's original current-base profile/Reader implementation passes all four
checks, desktop/412-pixel interaction and isolated preservation. Its coverage-page
photo-lookup extension passes 76 affected tests and preserves identical full
HTML while reducing repeated responses from 3.93 to 2.81–3.01 seconds. Fresh
committed-head filter/browser checks and CI remain. Catalog #399/#400 remains a separate reviewed draft
(5,222 tests), awaiting release approval. No production change is implied.

All 31 original requirement IDs, descriptions and order are retained. Historical
counts below describe their dated source populations, not the current whole
database. CAT-01/CAT-02, human source/name/identity decisions, 32 unclear cells,
current/historical portfolio and profile depth, statistics/Learn media coverage
and broader performance remain open. The independent 52-source worksheet has
not been completed by engineering tests.

## Historical continuation — October 23, 2026

Live canonical `97f9ac3d` includes released platform redesign, four-crop Landscape,
guide, News/access, automatic News, Gene Editing, approved #407 and #409.
The [on-demand profile performance draft](VARIETY-PROFILE-DEMAND-LOADING.md) has
109 passing affected tests and isolated real-data parity/timing proof. Browser
interaction/phone review, current-head full CI and final release approval remain.
No catalog enrichment is deployed; #399/#400 retains its separate release review.
All 31 accepted requirement IDs/descriptions/order below remain unchanged.
CAT-01/CAT-02, independent human answers, 32 unclear photo cells, complete
current/historical portfolios, rights/photos, profile/statistics coverage and
broader TD-122 work remain open. Earlier status notes are historical.

## Account scope confirmed — October 27, 2026

Workspaces are shared, collaborative research across signed-in accounts. Only
layout settings and Personal Digest are account-specific. Company lists,
favorites, tiers, research and human-review decisions remain shared. Personal
Digest includes each person's saves, reading progress/position/priority and
subscriptions to the shared lists. The [implementation and migration review](SHARED-WORKSPACES-PERSONAL-DIGEST.md)
retains older data and all existing review gates. Its final 76 affected tests,
two-account browser review and 412-pixel responsive review pass; full current-head
CI, production-copy preservation and release checks remain. No private Workspace ACL
mission is implied. All original 31 accepted definitions and ordering below
remain preserved.

Live `94a3b99b` includes the approved platform, four-crop Landscape and shared
Workspaces. Catalog #399/#400, performance #410 and account-scope #412 are tested drafts
awaiting their separate release approvals. A separate shared-header navigation
fix follows measured TD-123; it preserves dense layout and existing destinations.
All 31 original requirement IDs, definitions and order below remain. Existing
source/identity/current-rights/photo gates, the independent 52-source worksheet,
32 unclear cells, comprehensive catalog/profile/statistics/Learn coverage and
final release checks remain explicit. Historical counts/heads below are dated
evidence, not the current whole database or a new instruction to repeat a gate.

## Shared Workspaces visual explainer follow-up — October 28

The live `e24b566b` platform includes shared Workspaces. The independent
[guide follow-up](WORKSPACES-VISUAL-GUIDE.md) adds its capture/connect/brief
workflow, shared-page scope and Markdown/JSON output to Help. It retains all
twelve existing section cards and six report cards, with a featured Workspaces
panel and separate briefing explanation. Static-public regressions and native
desktop/phone review pass; exact-head checks precede its draft release review. Catalog/photo
work and Personal Digest account scoping remain separate drafts. All original
31 requirement IDs, accepted descriptions and ordering remain unchanged.
October 28 — [National berry-rights records](NATIONAL-BERRY-RIGHTS-REVIEW.md)
add 19 unreviewed scopes / 69 entries across four crops. Two historical bulletins,
a USDA abstract and an Argentine act retain legal stages, literal numbers and
name bridges; an earlier notice is unavailable. Corpus: 516 sections / 1,854
occurrences / 165 matches / 1,689 review needs. Kwanza's newly documented coded/
uncoded bridge holds its existing photo for name review; public-seed photo gaps
become 11, with rights/traits/company gaps unchanged at 13/33/10. Raw photos,
saved user choices and all canonical records remain. Three direct captures
succeeded and two timed out; 15 selected PDF pages were visually checked.
Initial 40 affected checks pass; final metadata/native/current-head verification
is required. This source-only child stays outside frozen release #430. Its
approval question and the separate #421/#426 scopes remain unchanged. All 31
accepted definitions/order, the guide and human gates remain.

## Current completion audit — October 28, 2026

The [full-thread audit](FULL-THREAD-COMPLETION-AUDIT.md) reconciles all 31 original
requirements and the later account, collaborative Workspace, privacy, Reader,
performance, photo, navigation and server requests. Core redesign is live at
`e24b566b`. Platform #421 and catalog #426 have their own passing full checks,
native review and current-production-copy preservation proof; both await the
actual release decisions already requested. Later #427/#428 pass their exact
head checks with 5,335/5,337 tests and native review but are outside those frozen
release proofs. Human catalog/recall/content work remains open. Later dated
entries below retain their original checkpoint context rather than overriding
this current audit. The primary table's evidence and remaining columns are
reconciled below; its accepted definitions/order are unchanged.

October28 — [Plablue original figures](PLABLUE-ORIGINAL-FIGURES-REVIEW.md) add held
images and exact claims for Blue Manila/Blue Maldiva using existing aliases.
Six scopes retain 15 occurrences; parents, comparisons and printed label errors
remain separate. Public 64-profile photo gaps fall from 12 to 10; other fields
stay 13/33/10. Bounded corpus: 497 / 1,785 / 168 / 1,617. Final 34 affected checks
and native review pass; current-head CI and separate release review still apply.
Frozen #427 has 5,335 tests/native; #426/#421 actual approvals remain pending. No accepted definition,
canonical data, schema, human identity/rights/reuse gate or guide is changed.

October28 — [Held-photo routing](VARIETY-PHOTO-IDENTITY-REVIEW-ROUTING.md) makes an
already captured Rutgers D'Light photo discoverable for name review across the
directory, profiles, editor and coverage. It does not link the photo, approve the
NJ09-2-1 association or change reuse/user choices. All31 definitions/order and
existing gates remain; source/profile-gap counts are unchanged. Final47 affected
checks pass; this follow-up requires native/current-head checks and separate
release review. Frozen426 has5330tests and current-copy preservation. Actual
platform421/catalog426 release decisions remain pending and are not inferred.

October 28 — Rights/IP keeps exact original filing references above a collapsed
Related reports & records group. Reviewed source and Source date distinguish
publication review from a focal grant or current right. Current/legacy views
share the same partial; pending titles, links and counts remain private. Sixteen
focused checks preserve both old Evidence hashes and original claim/correction
links. Frozen #424 passed5,325 tests and native desktop/phone review. Source
counts and all31 accepted definitions/order are unchanged; source metadata
proposals and CAT-01/CAT-02/TD-116 remain open. This UI child requires its own
browser/CI proof and the catalog stack its own production-data preservation and
release review. Platform421 actual approval is still pending; no deployment.

October 28 — [Eureka, Opi and Eterna original images](REMAINING-PROFILE-IMAGE-REVIEW.md)
reduce the public64-profile image-reference gap15→12; rights/traits/company gaps
remain13/33/10. Two original claims, separate comparisons and the correction
retain their scope. Current bounded corpus491/1770/165/1605 and source access/
identity limits are recorded; accepted definitions/order are unchanged. Final56
scope checks pass; native/CI and separate source release review still apply.
Frozen423 passed5,323tests; live65profiles and platform421 approval stay separate.

October 28 — [Larger original filing previews](FULL-IMAGE-PREVIEW-REVIEW.md)
retain stable photo IDs and existing user captions, replacements, hiding and
history for four captured figures. No accepted definition, source/name total,
image permission or review gate changes. The research seed still has15 image
reference gaps; CAT-01/CAT-02 remain open. Frozen422 passed5,305 tests. This
follow-up needs its own browser/CI checks and separate catalog release review;
platform421 remains awaiting actual human approval. All31 definitions below remain.

## Original filing figures and remaining catalog work — October 28, 2026

The [filing-figure follow-up](ORIGINAL-FILING-FIGURES-REVIEW.md) checks ten
original documents, with twenty scopes and 57 name occurrences: ten subjects
plus 47 separately retained parents, siblings and comparisons. Twelve held
image observations use ten full-size figures. Seven existing profiles gain
figures and direct original claim links; the public 64-profile seed's image
reference gaps fall from 22 to 15, with rights/trait/company gaps still 13/33/10.
The corpus now has 484 sections / 1,757 occurrences / 161 matches / 1,596 review
needs. These are scoped observations, not approved cultivars or cleared images.
Current-head browser/CI checks precede this separate catalog release review.

The last verified live release remains canonical `e24b566b`. Platform-only #421
is a separate tested candidate: 5,284 tests, native account/phone checks and a
fresh-copy preservation check passed. Its five original accounts and 65 live
profiles are preserved; actual human release approval is pending. This source
follow-up inherits neither that preservation proof nor its release approval.
Earlier dates/heads below are historical. Gene Editing #417 and News Tags #415
are live; the earlier blueberry stop was approved before the released rollout.
All 31 accepted definitions/order and the immutable expansion guide remain.
CAT-01/CAT-02, the 52-source independent worksheet, 32 unclear cells, broader
current/historical coverage and all existing human gates remain open.

## Verified delivery and remaining work — October 28, 2026

The live release is canonical `e24b566b`, retaining the platform redesign,
shared Workspaces, Gene Editing closeout #417 and News Tags #415. The recovered
server is healthy; temporary review jobs use the bounded offline guard. Only
layouts and Personal Digest should be account-private; the per-account Digest
follow-up #412 remains a separate unreleased draft. Other platform performance
and navigation drafts remain separate from catalog research.

Frozen catalog #418 at `49489128` passes all four checks and 5,300 tests, native
phone/desktop review and a fresh production-copy preservation check: five
original accounts, 65 variety profiles, 9,821 protected JSON records and four
databases retained. Its verified backup has 19,758 files. Production was not
replaced; release approval and a release-time fresh preflight remain required.

The separate [original-photo follow-up](ORIGINAL-VARIETY-PHOTO-FOLLOWUP.md) adds
references for eight more existing profiles. Its public seed's photo gaps fall
from 30 to 22; rights/trait/company gaps remain 13/33/10. Counts are scoped
observations rather than independent sources or a completeness score. CAT-01/
CAT-02, current/historical portfolios, the 52-source human worksheet, 32 unclear
photo cells and human source/identity/catalog/qualification/reuse gates stay open.
All 31 accepted IDs, descriptions and ordering below remain intact. Earlier
dated release/verification statements describe their own snapshots.

October 28 source follow-up: [raspberry patent originals](RASPBERRY-ORIGINAL-PATENT-REVIEW.md)
adds four original filing/claim links and four held, attributed fruit figures.
Nine unreviewed sections retain nineteen focal, commercial-label and separate
parent/comparison occurrences. No canonical alias, organization, role, region,
trait, current right or photo permission is approved; CAT-01/CAT-02 and the
independent human worksheet remain open. All original requirements below remain.

The final named-photo cohort adds thirteen inspected originals: twelve associate
with existing profiles and Rutgers D'Light stays under its identity hold.
Across this draft, nineteen profiles gain held reference metadata; the public
seed's missing-photo-reference count falls from 49 to 30. Precise warning scopes
reduce unrelated candidate cautions without replacing source records, operator
edits or newer captures. Rights, reuse and independent review remain separate.

## Current status — October 23, 2026

Live canonical `97f9ac3d` includes #409 and the approved #407 performance release.
The current release adds broader workspace speedups, selected-publisher Reader
recovery and bounded publisher-first discovery; catalog enrichment is excluded.
Drafts #399/#400 retain their source/identity safeguards after reconciliation
with this release, including its presentation memoization. All 31 accepted
requirement IDs/descriptions/order and the governing guide remain unchanged.
Seventeen original child feature files are byte-identical; the portfolio service
adds only the canonical memo import/decorator. Fresh current-head CI and catalog
release review remain before merge/deploy.

Independent source/name answers, 32 unclear photo cells, CAT-01/CAT-02,
current/historical portfolio completeness, rights/photos and wider performance
remain open. The 52-source worksheet is available but no independent answers
were supplied. A separate on-demand profile optimization has isolated parity
and timing proof; browser review remains pending and it is not deployed.
Earlier release measurements below are dated evidence, not today's live state.

## Verified status — October 22, 2026

Production is canonical `64099c00`, including the approved performance-only
#407 release and all previous platform, News/access, automatic News and Gene
Editing releases. The exact tested tree passed both required check sets with
5,153 tests. A fresh 17,593-file backup and prior image/override are retained.
Ten normal signed-in HTTPS checks pass; Emerald returned in 9.867 seconds and
News in 1.190 seconds. All 9,816 protected files, account/social database rows,
provider settings and seven mounts remain unchanged. Chris.H is enabled with
first-login Help pending. The protected mobile 52-source worksheet remains
available; publishing it did not supply independent human review answers.

Catalog #399/#400 is reconciled onto this release. Original source metadata and
identity safeguards remain; the child corrects a PDF link label without altering
its URL or review state. The original 18 child feature blobs and all 31 accepted
requirement IDs/descriptions/order are preserved. Fresh current-head checks and
catalog release review remain before publishing those changes.

CAT-01/CAT-02, current/historical portfolios, profile completeness, independent
recall and wider TD-122 performance remain open. Research counts below describe
the frozen 64-profile local corpus, not today's 65-profile live runtime. The
[release status](RELEASE-REVIEW.md) separates software delivery from source,
identity, catalog, qualification and photo approval. Earlier notes are history.

## Current release and continuation — October 14, 2026

Live canonical `c354866d` includes #401 and the subsequent #402–403 source-reader
fixes. Chris.H is enabled with first-login Help still pending. Read-only live
News/Help checks pass; News returned in 0.772–0.801 seconds with 60 image elements.
Catalog #399–400 is reconciled onto that release without changing its source
observations or approving any human gate. Fresh current-head checks remain
required. All 31 original IDs, accepted descriptions and ordering are preserved.
The 52-source worksheet still needs real reviewer answers. See
[release review](RELEASE-REVIEW.md) for the authoritative release boundary.

## Previous release audit and review packet — October 13, 2026

The [release audit](RELEASE-REVIEW.md) now distinguishes live #398, tested #401
awaiting release approval, and undeployed catalog #400. All 31 original IDs and
accepted descriptions remain. The original 32-case independent-name worksheet
was too short for the current 52-source reviewer copy; the offline scorer would
correctly refuse it. A fresh private 52-source worksheet now covers the exact
captured inputs with blank answers and current saved-copy links. The original
worksheet/capture hashes and all 332 protected files are retained. No human
decision or four-crop independent recall score is created by this preparation.

## October 13 original-paper follow-through

The [CAS paper review](CAS-ORIGINAL-PAPER-SOURCE-REVIEW.md) recovers Hawaii-4 and
Benihoppe as research material, without declaring CAS breeding releases. Current
bounded scope is 427 source sections / 1,641 occurrences / 119 catalog matches /
1,522 review needs; 64 stored profiles and all 332 protected review files remain.
CAT-01/CAT-02 stay open. News/access PR #401 independently passed all four checks
and 5,030 tests; its release and the staged new account await user approval.

This is the durable inventory of the user's accepted requirements. Keep every
ID and its remaining work visible; passing tests or added source observations
do not complete independent human review or prove catalog completeness.

## October 14 continuation

Verified live canonical `daac479e` includes merged News/access #401, subsequent
source-reader fixes and automatic News collection #404. Chris.H is enabled with
first-login Help pending. Read-only live News/Help checks passed before #404;
their recorded timings describe that earlier release. Catalog #399–400 remains
a separate undeployed draft.
The [candidate normalization improvement](CATALOG-NORMALIZATION-PERFORMANCE.md)
addresses a measured repeated-work bottleneck independently of catalog research;
TD-122 retains the oversized-page and broader performance work. Every accepted
requirement and human gate below remains in scope. The October 13 pending-release
statements below describe the earlier delivery state.

## October 13 live usability feedback

Platform #398 is now released on the live site. The following additional user
requests are tracked independently of catalog #400 and the retained 31
requirements below; no existing requirement or human gate is removed.
See [daily usability fixes](NEWS-ACCESS-USABILITY-FIXES.md).

- [x] Implement additional analyst login and first-successful-login Help while
  retaining the existing operator account and deployed SQLite account history.
- [x] Chris.H is enabled live. His first-login Help remains pending; verification
  did not sign in as him or consume the first-login flag.
- [x] One-click News capture automatically displays the newest matching feed;
  scope is preserved. Native isolated browser proof and four JavaScript
  completion/error/timeout scenarios are recorded privately.
- [x] Exclude Google consent pages from new and stored Reader content; show
  clearly labeled source and available publisher links with a readable summary
  when original article text cannot be recovered.
- [x] Fix measured repeated News metadata/relevance work: identical 784 matches
  over 1,270 local review records, 2.630 s to 0.478 s on the warmed data path.
- [x] News/access #401 is released. Account and source behavior were checked
  after release; subsequent reader, automatic-News and Gene Editing releases
  are preserved. Earlier response timings remain dated measurements.
- [ ] Separate follow-ups: wider performance budgets and job contention;
  publisher-resolution/capture coverage; per-user preferences/digests, roles and
  account administration. Current analyst state remains shared.

## October 13 printed-code follow-up

The [printed-code source review](PRINTED-CODE-REGISTER-FOLLOWUP.md) retains
all six original-code queries for five reference-gap profiles, one original
CPVO filing under its literal denomination, the unresolved Baridi code
conflict, related/comparison names and two attributed Ervin photo references.
The photos remain held for permission and the RedSayra/legal-name association
remains unapproved. All 64 profiles and 332 protected preview files are
byte-preserved. 79 affected checks and record validation pass; catalog #400
needs fresh checks on the next pushed head. CAT-01/CAT-02 remain open.

Platform #401 independently passes all four required checks: 5,030 passed,
11 skipped and two existing warnings. Its release and new analyst activation
await the requested user approval; no deployment is inferred from source work.

## Current release and source work — October 13 UTC, 2026

The separately approved platform release #398 is merged at `a2a6b4ad` and live
at intel.johnnyaceii.com. Its exact tested tree at `1fb75b61` passed all four
required checks and 5,023 tests. A fresh production-data rehearsal passed
17 authenticated routes and 12 exports. Final live checks passed sign-in,
seven main routes and four export formats. The final backup covers 14,060 files;
14,057 existing files retain bytes, a derived index rebuilds, and all 3,933
social rows/schema retain their meaning. Authentication, provider settings,
persistent mounts, user edits and human decisions are preserved. The previous
image and rollback configuration are retained. The live initial competitor
list now contains the 77 supplied subjects without automatically subscribing.
The visual guide contains twelve section cards, four workflow steps and six
reporting choices. Blueberry continuation and review downloads were approved.

Catalog work remains separate. Draft #399 passed all four exact-head checks
with 5,029 tests. Draft #400's Fontana head `7ffe5530` passed all four checks with 5,033 tests.
The new [whole reference-gap cohort](REFERENCE-GAP-COHORT-REVIEW.md) requires
fresh checks. The bounded audit now has 417 sections /1,627 occurrences /114
matches /1,513 review needs and 1,151 public-derived keys. The isolated preview
has 1,152 candidate keys and 64 unchanged stored profiles, including the
explicitly fictional seed. Four further original references reduce its missing
patent/PVR-reference count from 17 to 13. New findings do not
become approved varieties, source decisions, traits, growing regions or rights.

The copied reviewer workspace retains 52 pending source copies and the original
32 human worksheets. The 77-subject source plan has 61 named-source rows,
13 partial checks, one unavailable source and two identity holds. CAT-01/CAT-02
remain open: current/historical coverage, source acceptance, identity/catalog
authoring, current rights and independent recall need their own evidence.
All 31 IDs/order/original requirements and source, identity, catalog, Atomic,
qualification and photo gates remain intact. No catalog follow-up is deployed.

The remaining-work summary follows; detailed implementation history below is
dated evidence, not a new approval request.

| Remaining requirement | Next action | Required evidence or decision |
|---|---|---|
| CAT-01: source names reach catalog review | Recover accessible original text and reconcile every named cultivar without silent omissions | Preserved source passages; independently supplied multi-berry expected names; actual human identity/catalog decisions |
| CAT-02: comprehensive variety resource | Complete current and historical company/program portfolios, profiles, rights and attributed photos | Scope/accounting for every source; documented unresolved identities and missing text; current official rights; reviewed canonical records |

Earlier bounded portfolio/photo evidence (the 395-section snapshot) is in
[the four-berry reference review](CPVO-REFERENCE-COHORT-REVIEW.md): 395 sections,
1,572 name occurrences, 102 matched occurrences and 1,470 requiring review,
with 64 unchanged canonical varieties. Repeated captures are observations,
not additional cultivars or independent corroboration. There are 126
photo references; the eight UF and four Cornell photos remain permission-held. These are source
observations, not a global census or approved catalog growth.

The [four-berry 2024 register intake](REGISTER-LIST-52-INTAKE-REVIEW.md) accounts
for 398 first-name heading contexts: 388 observations, eight referrals and two
held codes. Body/parent/trade-name recall and per-entry company associations remain
partial; no source observation automatically creates an approved variety. The original Lewis/Hutton distinction is retained as
source context for a human decision, not automatic identity approval.

The [searchable organization follow-up](SEARCHABLE-ORIGIN-ORGANIZATIONS-REVIEW.md)
links 160 register entries to 20 existing organizations, including explicit joint
program context. Company tables and source/company filters use those entries;
60 further entries have searchable unresolved organization names. 228 remain
unassigned. No company role, current rights or catalog approval follows.

The [32-copy human name-review worksheet](VARIETY-HUMAN-RECALL-PACKET-REVIEW.md) is prepared; actual human source/name review remains unfinished. Source authenticity,
name/identity review, statement review, extraction qualification and photo reuse
are separate decisions. No automatic gate completion is authorized.

Completion requires implementation, matching source/data proof, native browser
review, meaningful checks, required CI on the release head, preserved user edits
and private/public boundaries, the updated explainer and a reviewable release.
Unavailable text, unresolved images, absent statistics and missing credentials
remain visible gaps. Never substitute a narrow check for a broad requirement.

[Historical progress and checkpoints](REDESIGN-REQUIREMENTS-CHECKLIST-HISTORY.md)
retain the previous updates and decisions verbatim. The complete requirement
table and implementation sequence below are preserved.

| ID | Accepted requirement | Current evidence / state | Remaining verification or implementation |
| --- | --- | --- | --- |
| CAT-01 | Reconcile sources against the variety catalog so visible named varieties cannot disappear silently | Live #488 at `32eefbd5` retains the source-specific company/name handoffs and the captured-article handoff delivered in #486. Companies now reuse explicit article mentions, including the retained Vicentina repair, alongside portfolio observations. The scoped public source view has 1,333 derived review keys across 539 sections; all 1,315 earlier keys and saved decisions remain. Source additions never create canonical varieties. | Human source/name/role/catalog decisions, 32 unclear photographed cells, two organization labels and the independent 32-source expected-name audit remain. Article handoff release acceptance is complete; it does not prove all article names are detected or globally comprehensive coverage. |
| CAT-02 | Build toward the most comprehensive berry variety resource, with measurable gaps and refreshed provenance | Live scoped public seed: 539 sections / 2,073 literal occurrences / 175 catalog text matches / 1,898 review needs / 1,333 derived keys. The 77-subject source plan has 67 named, seven partial, one unavailable and two identity holds. Eleven unreadable sections and 143 follow-ups remain explicit. #488 adds 44 occurrences of 34 printed names/codes and 34 held attributed photo references, without approving an identity or reuse right. | Current/historical completeness, current rights, reviewed identities/canonical authoring, cited traits/growing regions and photo permissions remain open. Source occurrences and text matches are not distinct approved varieties; named-source progress is not full portfolio coverage. |
| UI-01 | Bright, colorful agricultural Glasshouse identity; first berry icon; subtle glass, stronger contrast and hierarchy | Approved Glasshouse identity and first icon across core, intelligence, authoring, public-library and retained shells (M1–21/34/35); source prose stays literal. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| UI-02 | Immersive full-width workspace, compact top navigation, grouped More menu contained within the viewport | Full-width shared top header, contained grouped More, folded specialist destinations; live/private versus generated-public navigation tested (M20/21/35). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| UI-03 | Dense information with useful headlines, summaries, metadata and collapsed secondary context; plain language | Distinct heading/lead/body/metadata roles, compact cards/tables and secondary disclosures remain. Deployed #442 retains every source row with smaller HTML. #486 delivers the Company Intelligence hierarchy and source-text preparation follow-ups; #487/#488 retain them. Desktop/412px,required checks and fresh preservation pass for those approved releases. | The approved rendering and company/Reader presentation releases are complete. Broader TD-122 cold loading remains open. The later Reader-key experiment #489 is closed unmerged after mixed final timings; neither prototype gains nor passing output tests are a live-speed claim. Source/body completeness and human decisions remain separate. |
| NEWS-01 | Primary news-reader experience, image previews, newest first, multi-berry and country scope, custom dates and 7/30 days/YTD | Shared newest-first publication chronology, multi-berry/country/company/list/mark/date scope; 7/30 days, YTD and custom ranges; M29–31 source preview and compact phone filters verified. Desktop-review correction adds publisher-first shared visuals, labeled crop illustrations on missing/broken images, scoped retained-thumbnail capture and WebP delivery; native 36-story check found two publisher thumbnails. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| NEWS-02 | Trusted versus Unreviewed; useful/not-relevant/save/publisher icons, descriptive accessible names, delayed hover tooltips | Trusted requires reviewed source plus active escalated information; raw lane keeps actual source labels. SVG actions, accessible names and two-second hover descriptions retained. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| NEWS-03 | Right-side overlay that closes back to unchanged grid; original article within Reader and separate publisher option | Shared right-side Article/Brief overlay; publisher option, selected-source capture, independent positions and return-to-origin. M30 real article/image and M31 safe bounded capture verified. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| DIGEST-01 | Personal Digest combines saved stories, reading queue and explicitly subscribed lists | Personal Digest is live through approved platform #433, retained by Tags, #440 and #442. Two fictional accounts verified shared Workspaces and independent Digest/layout state; actual deployments preserved all five accounts, private state and databases. | Private/shared boundaries are delivered and retained. Future releases must preserve user state and real first-login history; broader content coverage remains separate. |
| CO-01 | Companies A–Z; independent favorites, Tier 1/2/3/Untiered, editable custom lists carried across views | A–Z/# directory, independent favorites/four tiers/lists across News/Map/Digest; legacy values retained only where already present. M18/35 tracking and specialist preservation; M37 source-scope parity. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| CO-02 | User-editable logo, website, LinkedIn and social links; People only within company profile with editable/highlighted contacts | Manual URL/upload/reset, collected-logo fallback, website/LinkedIn/social edits and company-only People; per-field/contact history recovery (M5/18/23), cited protected suggestions (M26). M38 native chooser/upload/save/reset succeeded in isolated state. | Release acceptance complete; actual deployed persistence is checked only after approved deployment. |
| VAR-01 | Seed supplied photo variety names with supplied companies, without pretending associations prove roles or identities | 143 photo candidates, 144 associations, 32 unclear cells retained; review UI and original photo provenance preserved (M2/6). | Human spelling/identity/role review remains; 32 unclear cells are retained, not guessed. |
| VAR-02 | Varieties visible on Map with editable and source/news-populable Growing regions; company Operating regions as another layer | Shared editable Growing/Operating region tables and country map layers; article/statement prefill (M23), cited editable proposals/current comparisons and protected review/history (M27). | Release acceptance complete. Subnational notes remain notes; exact polygons are later scope. |
| MAP-01 | Real boundary map, multi-country selection, touch/keyboard interaction, connected news/filter state and region tables with A–Z | Boundary map, multiple selected countries, keyboard/touch controls, A–Z region tables, shared news scope and selected-location snapshots (M4/28/29). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| MAP-02 | Market statistics below Map from best available public sources or explicit research population | Approved #473 deploys the explicit official-source capture support: 24 country/crop references and 51 original-unit figures across eight countries, alongside the existing baseline and research workflow. Source periods, provisional labels and two UK area discrepancies remain visible. Desktop/phone/PDF and isolated route checks pass. | Human figure selections and broader world/crop coverage remain open. The deployment does not apply unreviewed figures or resolve held discrepancies; it adds source files and workflow support. |
| PACK-01 | Competitor registry from supplied image, first group/list, export JSON schema and pipeline rules | First competitor list has 77 supplied-photo subjects with provisional identities/programs/brands retained; versioned JSON schema, stable identities and separate association rows (M2). | Schema/registry acceptance complete; unresolved human identities and optional receiving-system integration remain. |
| PACK-02 | Reviewed-news-source-only or all-news toggle; dates at generation; last generated timestamp for each successful export | Reviewed-source-only/all-news choice, generation-time dates and successful export receipts/last-generated history; individual statement approval is not required for source-reviewed packets (M2). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| PACK-03 | Fresh capture before every export, latest capture results, stable source identity, separate relationship rows, original URLs | Export requires explicit fresh per-subject capture with bounded queries, actual outcomes, duplicate handling and unchanged source URLs; failed capture cannot be mislabeled fresh (M2). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| AUDIT-01 | Audit each section's purpose, working state, duplication/zombie risk and appropriate consolidation; preserve every useful workflow | Section purpose/workflow/duplication audit and eleven-home consolidation are delivered. The retained-route audit found statement-link defects; their read-only destinations and static links are repaired in deployed #468, retained by #473. The bounded joined rehearsal passes 53 route/PDF checks. | Route rendering/access checks do not prove every form or indicate actual user adoption. Human source/catalog decisions and deeper performance work remain separate. |
| REPORT-01 | One Reports & Briefings home; executive view, selected briefs, editable reports, snapshots and news packets distinguished | Reports & Briefings task home unifies Executive view, briefs, editable reports, snapshots and packets without flattening their distinct outputs (M7/13/15/24/28/29). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| REPORT-02 | Rename War Room to Meeting Prep, keep its scope, saved takeaways and handoffs | Meeting Prep replaces War Room presentation; scope, saved takeaways, question/refresh actions, history and human handoffs retained (M7). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| REPORT-03 | Reports and exports must read as designed documents: takeaway first, clear hierarchy, no generated internal ID dumps, readable linked sources | Refined takeaway-first PDF/editor, numbered outlined findings, readable linked Source references and named appendix; literal edits/qualifications retained. #300 four checks green; five PDF pages and phone reviewed. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| LAND-01 | Landscape configurable by what/where to include | Multi-subject/place and included-section selections, source-date ranges, shared analyst-only saved views and Reader/report/brief handoffs (M8), four checks green. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| LAND-02 | Evidence-backed multi-berry Landscape, dense narrative, source/variety and dossier handoffs, comparison, saved views and complete visual exports | Blueberry continuation approved October 12. Tested release398 implements all four crops, All berries, paired comparison, shared company marks/lists, cited traits, revision-checked saved views and complete PDF/HTML/SVG/CSV exports. Browser light/dark/412px checks, saved update/archive/restore/copy, restart preservation and full selected-evidence exports pass. The guide explains the workflow and reporting choices. | Platform release #398 is merged at a2a6b4ad and verified live after the approved continuation. Comprehensive source/catalog coverage and actual human trust decisions stay open under CAT-01/CAT-02. |
| LEARN-01 | Top-level expanded Learn, detailed visual lessons/research first, pictures/diagrams/video links, interactive exploration | All27 existing lessons have interactive teaching explanations, including22 new source-linked explorations and five schematic designs; two verified photos and existing video links retain individual credits/rights. These curriculum additions are now live in approved440; original records and human edits remain. | Wider detailed lessons, attributed photos, diagrams, video/source depth and explicit research remain ongoing enrichment; educational content never approves scientific or competitive-intelligence claims. |
| LEARN-02 | Select/highlight content -> research/add to Learn -> explicit Perplexity deep research -> new learning content | Selected-text/Reader Learn actions, explicit context, durable high-effort research jobs and editable cited drafts are delivered. #473 repairs high-depth requests while retaining legacy medium jobs. #486 also delivers the actual-result presentation repair and deterministic visual-context fallback, retaining saved texts, request settings, run IDs, user edits and history. | The single authorized real high-effort request completed at provider-reported USD0.13679 and remains an editable AI draft. #480 is superseded by fulfilled live #486; no release approval is still needed for that repair. Broader citation,media and lesson-quality review remains. No further paid request is authorized; education never approves a scientific/competitive claim. |
| INT-01 | Plain-language investigation workspaces without changing review decisions | Intelligence home preserves Statements, Signals/candidates, Assessments, Recommendations, Questions, Research and native authoring. M11–17/20/35 verify named references, literal source text and separate gates. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| MON-01 | Consolidate Monitor watches/changes/alerts while retaining distinct intent and action | Monitor consolidates Watches, Alerts and Monitoring plans, retaining marks/list/multi-berry predicates, read/dismiss/pause/resume history and Reader; #283 green and M35 retained shell. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| OPS-01 | Consolidate collection, review and quality surfaces without losing specialist tools | Operations consolidates Collect, Review, Data quality and Coverage & health, retaining specialists. Source authenticity (M34) stays separate from publication/statement approval. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| GUIDE-01 | Visual explainer of site sections, analyst workflow and reporting capabilities with clear purpose/how/working state | The visual explainer is live through approved #474, merge7fa7dd53. It retains twelve site-section cards, four analyst steps, prior reporting choices and shared Workspaces guidance, and now explains company comparisons, retained coverage and accurate saved-comparison JSON/CSV behavior. All four checks pass/6,091 tests; desktop/phone, fresh isolated preservation and live verification pass. | The requested visual explainer and follow-up are delivered. Wider educational/media depth and human source/catalog decisions remain open; no new approval is needed for completed #474. |
| REL-01 | Integrate approved stack, reconcile canonical, run all gates and prepare release/rollback plan for intel.johnnyaceii.com | Approved #488 is independently verified live at `32eefbd5`,tested `22dcb869`, retaining #487/#486 and earlier deliveries. All four final checks pass: 6,277 tests, desktop/phone and fresh isolated/live preservation for five accounts including Chris.H, 65 profiles, 10,539 existing JSON records, four databases and 1,115 research files. One source file is added; backup, rollback, settings, mounts, proxy and active/enabled schedule remain. | These approved releases are complete; do not re-request their approvals. #480/#482/#483/#484 were superseded by fulfilled #486; #489 is closed unmerged. Cold performance and human/source/identity/role/rights/photo/Map/independent recall work continue here. A new code release needs its own tested review; no additional paid Learn acceptance request is approved. |

## Historical implementation sequence

1. Reports & Briefings / Meeting Prep (Mission 7): product/UI plus bounded workflow bug fixes. Implemented and pushed as draft #280. Repeated scope, pure reads, Working report visibility, readable editor/PDF and unchanged/literal/empty edit preservation are tested; all four final-head gates passed; integrated print/provider acceptance remains.
2. Configurable Landscape (Mission 8) pushed as draft #281; final-head required checks passed. Visual Learn and research-to-lesson (Mission 9) implemented and browser reviewed; draft #282 is pushed and all four exact-head checks passed.
3. Monitor/Operations and remaining specialist route presentation/consistency.
4. Cross-family outstanding requirements and live-data readiness checks; final visual explainer.
5. Canonical integration and tested release review packet. No merge/deploy before approval.

Routine checkpoint completion does not end the ongoing goal. A genuine input/access blocker should be recorded with the affected requirement and exact missing input, while independent work continues.


**Mission 9 working evidence:** See MISSION-09-VISUAL-LEARN.md. One bounded public research run captured 42 source URLs; no private notes/article body were sent. Browser verified diagram controls, existing-lesson detour, editable draft save/reload and mobile table containment. Original text, sources and human gates remain. Draft #282 passed all four exact-head checks, then work continued into Monitor/Operations and the remaining requirements; this checkpoint does not complete the ongoing goal.

**Mission 10 working evidence:** /monitor and /operations now organize the existing watches/notifications/plans and collector/review/quality routes. 154 focused tests passed; canonical records validated; static build produced 1,755 pages with no unpublished IDs/titles. Isolated browser actions preserved watches, read/dismiss/reopen history, plan pause/reload/resume and shared Reader origin. Operations and Review fit at 390px; remaining responsive review hit a browser-control timeout and is not claimed complete. Final draft-head CI and combined release checks remain. No merge/deployment.

**Mission 10 push/follow-up:** Draft #283 is attached and pushed. Initial exact-head CI found one coverage-copy regression (3,525 passed / one failed / 11 skipped / two warnings); the explicit completeness distinction is restored and a fresh full run is required. Responsive review recovered in a fresh tab: Monitor/Alerts and Coverage page widths stayed contained at 390px, wide tables scrolled within their containers and native two-berry scope survived tab navigation. Deeper specialist and combined release acceptance remain.

**Mission 10 exact-head CI:** Draft #283 final head `cf6798888d2daea1dc33e8c6d983726e695593d8` passed Change scope, Repository integrity, Static public safety and Python tests, run `37018754430`: 3,527 passed / 11 skipped / two warnings. Earlier c87e325 failure remains in the history; the combined release is still pending.

**Mission 11 first controlled slice:** Native /guide now explains the delivered section homes, analyst reading/investigation/reporting loop and five distinct outputs. Radar/detail, company Moves and Coverage & concentration share the approved shell. Stale/empty Radar browse never starts provider research; stale wording no longer implies a refresh is running. Ungrouped cached developments remain visible, unsafe source URLs render as unavailable without altering the original cache, and source history/review controls remain. Coverage uses named selectors, retains CSV bookmarks/repeated query values, rejects unsupported or empty scope and hands exact companies/geographies/window to report preview. 77 focused tests passed, then 18 scope/static tests passed after the final label/static assertions. Canonical records validated and static output produced 1,755 pages without unpublished IDs/titles. Browser proof and final CI are recorded in Mission 11. This does not close the remaining investigation pages or combined release.

**Mission 11 exact-head CI:** Draft #284 head dea2170323206a98f22cfa6222bd3c167e862363 passed all four required checks, run 37024739505: 3,530 passed / 11 skipped / two warnings in 318.20 seconds. The stack now spans drafts #272–284. No merge or deployment.

**Mission 12 local evidence:** Statement-first triage and shared individual Reader review retain all exact passages, original wording and edit/decision history. Triage does not confirm a Fact; confirmation requires a reviewed publication and one pending statement. Authoring/origin/private-read guards fail before mutation. 126 focused tests passed, records validated, desktop/mobile synthetic rehearsal retained source text and Reader origin. Remaining judgment/research, account/source/market and canonical release work remain open. Exact draft-head CI is still required.

**Mission 12 CI follow-up:** Draft #285 first run 37030449938 had 3,541 passing tests and two stale shell/layout assertions. Updated regression expectations cover the approved Statements shell, dense collection and empty state; no old sidebar was restored and no review gate relaxed. Fresh exact-head CI remains required.

**Mission 12 final CI:** Draft #285 head `34406acd8d72d1799b689b16e9c114ee9775ed32` passed all four checks, run 37032353982: 3,543 passed / 11 skipped / two warnings in 228.19 seconds. This verifies its slice, not canonical integration.

**Mission 13 report critique follow-up:** Preparation checklist replaces repeated undrafted PDF sections; edited/literal/blank text stays retained, source references remain traceable, findings are separate reading items and external research markings remain distinct from evidence confirmation. All five sample PDF pages inspected, desktop/mobile app containment checked, 106 focused tests passed. Exact draft-head CI and combined release remain open; see MISSION-13-REPORT-READABILITY-FOLLOWUP.md.

**Mission 13 final CI:** Draft #286 head `4dd928cca2f859f25542064b30ea492a005f5ba4` passed Change scope, Repository integrity, Static public safety and Python tests, run 37051961517: 3,549 passed / 11 skipped / two warnings in 326.38 seconds. This verifies the report slice, not canonical release integration.

**Mission 14 reading hierarchy:** Eight existing judgment catalog/detail routes now share Glasshouse Intelligence navigation; the first authored unit is emphasized, all supporting text stays visible, metadata/scope/related inventories are minimized. Read-only detail skips private decisions; source counterevidence and captured-date labels are repaired. Real-record desktop/mobile, keyboard disclosures and shared Reader were checked. See MISSION-14-INTELLIGENCE-READING-HIERARCHY.md. Research/forms/static-shell and integrated release remain open.

**Mission 14 final local checks:** Final combined local run: 170 focused reading, synthesis, Question, scope, Signal-review/candidate and static tests passed, one existing reportlab warning, in 170.42 seconds. It includes the full static counterevidence build after the final source-date and caption changes. Canonical validation passed; the independent public build produced 1,755 pages with no unpublished IDs/titles. Exact pushed-head CI and combined release remain.

**Mission 14 final CI:** Draft #287 exact head `d6aeadc51096a398d61abfab4d51f368c5e9ebdf` passed all four required checks, run 37057383167: 3,562 passed / 11 skipped / two warnings in 342.24 seconds. This verifies the intelligence reading slice, not the combined canonical release.

**Mission 15 local evidence:** Research shares Intelligence navigation and leads with the question, saved classified findings and numbered sources. Fresh checks require an explicit authoring/same-origin action and report actual complete/partial/failed/unavailable outcomes. Read-only answers skip private caches. Report preview closes the supporting payload while retaining it unchanged for editing/generation. 129 focused tests passed; canonical/static/JavaScript checks passed. Isolated browser review covered comparison scope, unavailable provider state, Reader return, keyboard/mobile containment and report preview without generating a draft or calling a provider. See MISSION-15-RESEARCH-READING-WORKSPACE.md. Final head CI and the remaining goal requirements are still open.

**Mission 15 final CI:** Draft #288 head `c2be282f8f770780c1012e68e5ca75352a209ea3` passed all four required checks, run 37062117468: 3,578 passed / 11 skipped / two warnings in 341.81 seconds. This verifies the Research slice, not canonical release integration.

**Mission 16 working evidence:** Candidate review leads with the proposed pattern, visible limits and source support. Populated groups precede closed empty groups; native history/method disclosures retain original references. Read-only/cross-origin guards precede private reads/decisions. Isolated desktop/mobile, keyboard and Reader return were checked without making any review decision. See MISSION-16-SIGNAL-CANDIDATE-REVIEW.md. Authoring forms, wider accepted requirements and combined release remain open.

**Mission 16 final CI:** Draft #289 head `b7be3e352a4e3e47878c0ea713112ba4309fb967` passed all four required checks, run 37063979566: 3,585 passed / 11 skipped / two warnings in 285.04 seconds. Combined canonical release remains open.

**Mission 17 local evidence:** Signal, Assessment (new/edit) and Recommendation forms share Intelligence navigation and named references. Existing raw values/unknown selections/qualifications are retained; metadata catalog omits article bodies/private proposals. Cross-site saves fail before canonical access/write. 153 focused tests passed; canonical, JavaScript and 1,755-page static/public checks passed. Desktop/mobile named selection and unresolved-reference preservation were checked without any real save or provider call. See MISSION-17-INTELLIGENCE-AUTHORING.md. Exact-head CI and the remaining accepted requirements stay open.

**Mission 17 CI follow-up:** Draft #290 initial head `05a12af9128f097b920da7975e10253df6912d48` passed three required checks. Python tests run `37065661356` had 3,601 passed / one stale visible-caption assertion failed / 11 skipped / two warnings. The decision-workflow regression now checks Supporting statements, the unchanged `fact_ids` field and minimum-statement hint. Fresh exact-head checks remain required.

**Mission 17 final CI:** Draft #290 head `aa76992cc08aae7e1f40f1d25c0483d19bf17b93` passed all four required checks, run `37066747850`: 3,602 passed / 11 skipped / two warnings in 289.55 seconds. This verifies authoring, not canonical release integration.

**Mission 18 local acceptance:** Current-tier assignment choices preserve existing legacy values and filters without changing favorites/lists/watches. Browser manual logo URL/reset returned the exact collected image. Multipart upload/new directory/profile/reset/canonical-preservation checks and Company/News/Map/Digest tests had 71 passed / one warning. The browser file chooser stalled and no selected file was submitted; browser upload remains explicitly unverified. See MISSION-18-COMPANY-TRACKING-ACCEPTANCE.md. Production persistence/enrichment, wider accepted requirements and combined release remain open.

**Mission 18 final CI:** Draft #291 head `2d3218736d37cecd99da4b583d40294dd5471834` passed all four required checks, run `37081601872`: 3,610 passed / 11 skipped / two warnings in 341.97 seconds. The approved stack spans drafts #272–291; this is slice proof, not canonical integration.

**Mission 19 local evidence:** Four original sourced teaching diagrams extend the existing cane-year interaction across all five Learn pillars. Shared live/static rendering retains lesson records, does not start research on reading, embeds only verified media and excludes private controls. Final focused tests: 90 passed / one warning. Desktop and 390px keyboard/click selection and containment reviewed. See MISSION-19-LEARN-TEACHING-VISUALS.md. Wider content, remaining accepted requirements and combined release remain open.

**Mission 19 final CI:** Draft #292 exact head `2610648ea13349f0e2013702c6fd014459f38b5d` passed all four required checks, run `37083812686`: 3,620 passed / 11 skipped / two warnings in 386.97 seconds. The approved stack spans drafts #272–292. Canonical/release integration remains open.

**Mission 20 working evidence:** Public Glasshouse navigation uses generated routes and retains private tools in the live menu; Search, Help and public intelligence share the shell. Search preserves query/scope/sort and shows actual Signal statuses rather than false confirmation. Candidate judgment remains distinct. Original learning summaries lead public previews. Focused tests: 102 passed / one warning. See MISSION-20-PUBLIC-NAVIGATION-AND-SEARCH.md. Other public shells and wider accepted requirements remain open; pushed-head checks still required.


**Mission 20 final CI:** Draft #293 exact head `f6ff1b8e84e3cc297c0f4beb315fe648934f77d2` passed Change scope, Repository integrity, Static public safety and Python tests, run `37086165073`: 3,636 passed / 11 skipped / two warnings in 304.61 seconds. This verifies the slice, not canonical release integration.


**Mission 21 working evidence:** All generated template families share public Glasshouse navigation; source summaries lead and supporting metadata/interpretation start closed, retaining literal records and original links. Public snapshot copy avoids implying live freshness; balanced collections render as compact responsive grids. 69 focused tests passed; canonical records validated; 1,755-page build passed unpublished-content safety. Desktop/phone/keyboard article, menu, Markets and Executive View were inspected. See MISSION-21-PUBLIC-LIBRARY-SHELL.md. Pushed-head checks and status/source/production/release work remain open.


**Mission 21 CI follow-up:** Draft #294 initial db7e75d had three green checks; full tests had 3,634 passed / two old shell-invariant assertions failed / 11 skipped / two warnings, run 37087628404. Regression checks now explicitly allow only the public/live parent-shell choice and keep the narrative/context parity checks. Final follow-up local Landscape/synthesis/static run: 67 passed / one warning. Fresh exact-head checks remain required. No review gate was changed.


**Mission 22 working evidence:** Canonical remains 916b8f09f9ce2a1847335d7990ea80ff921f1cec, an ancestor; expansion guide has no diff. Selected #255 Learner files already match canonical. Older #270/#271 interfaces are not blindly restored; detailed parity stays open. The missing #271 pending content-digest correction is carried forward with same-metadata edit/restart/body-omission tests. Combined 34 tests passed; a 500-file synthetic cache restart reused every projection in 0.331 seconds. See MISSION-22-RELEASE-PARITY-AUDIT.md. Exact-head checks, source-assisted requirements and combined release acceptance remain open.

**Mission 21 final CI:** Draft #294 head `27ed8cc7b7137cfaab4df4147cf7df07370a07a4` passed all four required checks, run `37088365423`: 3,636 passed / 11 skipped / two warnings in 320.51 seconds. Initial shell-assertion failures remain recorded. Canonical integration remains open.

**Mission 22 final CI:** Draft #295 head `58d6c21a1ad68a2970c03d6ebf20d8548fe7171f` passed all four required checks, run `37088603587`: 3,637 passed / 11 skipped / two warnings in 347.12 seconds. This verifies its correction, not the entire goal.

**Mission 23 working evidence:** Stored news/statement sources now prepare unsaved region entries with literal summaries, exact source/date and shared Reader. Company link/contact history recovery is scoped and revision-protected. Combined Company/Map/Varieties/Digest tests had 81 passed / one warning; final follow-up/static checks are recorded in MISSION-23-SOURCE-ASSISTED-REGIONS-AND-RECOVERY.md. Desktop/mobile source hierarchy and synthetic private link restore/reset were browser reviewed. Broader AI enrichment, country/metric/body/media coverage, account/worker production safety and integrated release acceptance remain open. No merge/deployment.

**Mission 23 final CI:** Draft #296 head `3167b2630f1c00812b9bef82efe2397c275645e3` passed all four required checks, run `37090296342`: 3,649 passed / 11 skipped / two warnings in 285.21 seconds. Final focused/static acceptance had 90 passed / one warning. This verifies its slice, not the entire approved mission set.

**Mission 24 review-state correction:** Executive View no longer describes its mixed collection as trusted. Proposed/legacy Signal statuses and AI draft/existing reviewed Assessment states stay explicit; recent-update dates show their actual publication/capture/first-seen/update/creation basis. The canonical absent/false AI-marker contract remains. No eligibility, canonical record, source wording, ranking or human decision is changed. See MISSION-24-EXECUTIVE-REVIEW-STATE-CLARITY.md. Broader public eligibility and release integration remain open.


**Mission 24 final CI:** Draft #297 head `69c631a2a87824d217a00a985291152b6719e224` passed all four required checks, run `37091572718`: 3,652 passed / 11 skipped / two warnings in 352.64 seconds.

**Mission 25 market references and snapshots:** Four bounded official Eurostat strawberry references add eight 2025 production/area figures alongside the six existing USDA figures. The original public response is retained for reproducibility; missing yield/future cells and estimate/provisional flags are preserved. A manual refresh captures original data in a new ignored file without replacing references or trusted records. Snapshot composition now selects individual figures and carries their annual period, units, qualifications and source links into a table-based PDF. No private region notes enter exports. See MISSION-25-MARKET-REFERENCES-SNAPSHOTS.md. Wider FAOSTAT/national coverage, app-assisted refresh/review, Trade/region snapshot choices, source/body/AI enrichment, account/worker safety and canonical release remain open.


**Mission 25 pushed acceptance:** Draft #298 is attached. Market-code head `b8a29039ea35a9623c9c5c964a307cf5410498f2` passed all four required gates, run `37212137821`: 3,666 passed / 11 skipped / two warnings in 244.73 seconds. Final focused acceptance was 131 tests; Guide capability copy then passed 18 Guide/static tests and requires a fresh exact-head run. Canonical remains 916b8f09f9ce2a1847335d7990ea80ff921f1cec, guide unchanged. Broader accepted work and combined release remain active.


**Mission 25 final Guide-head CI:** Draft #298 head `21db634f24e75dd289c4dd38cda7a8da15128360` passed all four required checks, run `37212618775`: 3,666 passed / 11 skipped / two warnings in 341.70 seconds. This includes the Guide follow-up and verifies the slice, not canonical release integration.

**Mission 26 company-detail suggestions:** Company Profile & links and People now offer explicit, resumable public-identity research and individual cited suggestions. Native source provenance, original response, protected manual blanks, selective profile changes, contact history and atomic replay protection are retained; no canonical identity/relationship/trust action occurs. One live public-identity run returned seven suggestions and 56 native source URLs, all unapplied; isolated fixture acceptance and desktop/phone reading were browser reviewed. Provider reference dumps are excluded from visible explanations without deleting the original response. See MISSION-26-COMPANY-DETAIL-SUGGESTIONS.md. Final focused checks, exact draft-head gates, broader approved requirements and combined release remain open.

**Mission 26 final local acceptance:** 135 focused tests passed before the final anchor/threadpool follow-up; its final Company/profile/static run had 53 passed / one warning in 76.69 seconds. Canonical validation passed; the canonical expansion guide has no diff. Exact pushed-head CI and combined release remain.

**Report critique design follow-up (October 4):** REPORT-03 now has a stronger takeaway, numbered outlined findings, plain stock headings, generated reference projection and a stable named source appendix. The editor presents populated findings before supporting disclosures; analyst prose, blank edits, classifications and custom headings remain literal. Captured versus published source dates are distinguished; dates of cited publications contribute to the export cutoff. 95 focused report/static tests passed; records validated; all five final PDF pages, desktop, 390px containment and keyboard editor were checked. See REPORT-READING-DESIGN-FOLLOWUP.md. Exact-head CI and combined release remain open.

**Mission 26 final CI:** Draft #299 head 044b4b9853669034c2146935ce7e40413df9e72a passed all four required checks, run 37222193634: 3,689 passed / 11 skipped / two warnings in 360.37 seconds. The approved goal remains active. Location suggestions are in progress and excluded from the focused report commit.


**Report critique final CI:** Draft #300 head `daa42e04d922c9f1f6b826bee046e0416c493910` passed all four required checks, run `37225686478`: 3,693 passed / 11 skipped / two warnings in 243.04 seconds. All five PDF pages were inspected; this is presentation proof, not completed source analysis or canonical release.

**Mission 27 local acceptance:** Source-led Company/Variety location suggestions now support exact native source provenance, human correction, existing-country/subregion comparison, unknown-date preservation, uncertain-run recovery and atomic save/replay history. Unsupported patent/market/office growing claims remain visibly ineligible. 73 focused location/Map/company/static tests passed; canonical records validated. Isolated company and variety corrections reached the shared map table, with existing company history preserved. Desktop/390px and keyboard disclosure were reviewed. See MISSION-27-SOURCE-LOCATION-SUGGESTIONS.md. Pushed-head CI and combined release remain; no merge/deployment.


**Mission 27 final CI:** Draft #301 head `88ef32ebf456f0af1b5a0fd8fbbfd58c6eec52ba` passed all four required checks, run `37227444237`: 3,719 passed / 11 skipped / two warnings in 360.65 seconds. This verifies the source-location slice, not canonical release integration.

**Mission 28 selected-location snapshots:** Explicitly chosen Company/Variety locations now carry saved status, activity, dates, literal notes/limitations and original source into the composer and a structured PDF. Private annotations remain unreviewed/confidential; stale selections fail, and public/read-only options never read private annotations. Full map scope survives the handoff/return. 132 focused tests passed; records validated; desktop/390px and both illustrative PDF pages were inspected. See MISSION-28-SELECTED-LOCATION-SNAPSHOTS.md. News-section date/company/list scope parity, Trade, broader market/refresh, source/media, account/worker and combined release remain open. Pushed-head checks remain required; no merge/deployment.


**Mission 28 final CI:** Draft #302 head `daf94e2ae0f12e6b99f36da768bb53378340ffff` passed all four required checks, run `37230232484`: 3,729 passed / 11 skipped / two warnings in 426.81 seconds. This verifies its slice, not canonical release integration.

**Mission 29 News/snapshot parity:** Company/list/mark/search/publication-window filtering and actual timestamp ordering now reuse the shared News selector. Plain named scope and source references replace technical generated inventory wording; empty sections remain explicit. Annual figures and selected locations keep their independent dates. Browser review fixed native-control Enter interception and confirmed map/snapshot empty/populated parity, article Enter/Escape and 390px containment. Initial focused acceptance had 164 passed; final plain-language follow-up had 103 passed / one warning. Both scoped PDF pages were inspected. See MISSION-29-SNAPSHOT-NEWS-SCOPE.md. Actual source/body/media capture, broader market/Trade/account/worker, older-PR parity and combined release remain open; no merge/deployment.


**Mission 29 final CI:** Draft #303 head `42331ba77603826eef93cf37a6086dfb657cde70` passed all four required checks, run `37233044785`: 3,742 passed / 11 skipped / two warnings in 350.92 seconds. This verifies the slice, not combined canonical release.

**Mission 30 real Reader/preview acceptance:** One explicit public article capture returned HTTP 200, nine readable paragraphs and eight image references. Browser Reader, News, Map and saved Digest shared its loaded image, with the temporary saved mark restored afterward. Exact-source image sidecars keep body text off card routes; failed explicit captures retry while successful ones remain cached. Initial checks had 71 passed; broader source/Reader/snapshot/static checks had 118 passed / one warning. Canonical validation passed and 390px containment was reviewed. See MISSION-30-READER-PREVIEW-CONTINUITY.md. Final overlong-URL checks, pushed-head CI, broader source/redirect bounds, mobile filter density, market refresh and combined release remain open.

**Mission 30 final local acceptance:** Final source/Reader/News/Map/Digest/snapshot/static run, including original overlong URL preservation: 119 passed / one warning in 13.23 seconds. Exact pushed-head checks and combined release remain.


**Mission 30 final CI:** Draft #304 head `272e946156f0339163163dd81fa99bd73db8afd4` passed Change scope, Repository integrity, Static public safety and Python tests, run `37234337286`: 3,752 passed / 11 skipped / two warnings in 311.37 seconds. This verifies the slice, not combined canonical release.

**Mission 31 compact News and capture bounds:** Native filter disclosure starts collapsed on phones and expanded on desktop, with the complete named scope visible and every control retained. Explicit timezone survives Apply; reversed dates receive native correction. Per-hop redirect preflight, five-redirect limit, bounded streaming/deadline, malformed/private numeric URL rejection and unsuccessful HTML/PDF response handling are tested. Final focused acceptance: 180 passed / one existing warning in 30.84 seconds. Browser 390px containment, loaded source image and keyboard disclosure/date correction were verified; records validated and governing guide stayed unchanged. See MISSION-31-COMPACT-NEWS-AND-CAPTURE-BOUNDS.md. Market refresh, retained-route parity and combined release/rollback acceptance remain open.


**Mission 31 final CI:** Draft #305 head `406c5bd86e8c765e73996a225baba7c615b1e519` passed all four required checks, run `37236909676`: 3,793 passed / 11 skipped / two warnings in 289.85 seconds. No canonical merge or deployment.

**Mission 32 official statistics refresh/review:** Map now offers an explicit bounded Eurostat check, current/new figure comparison and individual country reference acceptance. Supported scope remains strawberries in four European countries. One real capture returned four countries/eight figures; an isolated native Portugal save retained country/berry scope and the October 4 check date in Map and snapshot. Private overlays/history and original captures remain separate from canonical records/public output and source/statement trust gates. Job/retry, stale revision, failed/corrupt state, partial-country preservation and private/public snapshot/PDF parity are tested. See MISSION-32-OFFICIAL-STATISTICS-REFRESH-REVIEW.md. Wider national/other-berry research population, retained-route parity and combined release remain.


**Mission 32 final CI:** Draft #306 final head `ffc881682c7fa65a72b815662639ef5f8a2330f9` passed all four required checks, run `37238760547`: 3,819 passed / 11 skipped / two warnings in 369.79 seconds. This verifies the supported statistics-review slice, not deployment or complete global coverage.

**Mission 33 runtime reference correction:** Release inspection found repository-only market-reference paths incompatible with Docker's seed/persistent runtime layout. The shared loader now follows configured data-directory precedence, preserves existing operator files, keeps missing references unknown and refuses malformed references before capture/apply changes. 107 runtime/Map/snapshot/static/public-safety checks passed / one warning in 13.75 seconds. See MISSION-33-RUNTIME-REFERENCE-PARITY.md. Actual Source authenticity browser inspection still shows older navigation/copy; 34 legacy-shell template references require route classification and retained-workflow review. Wider market population and final combined release/rollback acceptance remain.

**Mission 33 final CI:** PR #307 head `bb7389a70513e2cadb02582fe57c355e0c5e9e43` passed Change scope, Repository integrity, Static public safety and Python tests in run 37240230927: 3,831 passed / 11 skipped / two warnings / 344.05 seconds. This closes the runtime-reference correction slice; actual combined container/release acceptance remains.

**Mission 34 source authenticity:** Both verified recovered-source screens now use Glasshouse / Operations with clearer comparison hierarchy, readable expanded source text and collapsed diagnostics. Individual confirmation/reviewer gates, private events, filters and review-session returns are preserved; broken review-and-next, overwritten berry context and phone checkbox overflow are corrected. Capture and review dates stay separate. Global search retains its functionality with readable instructions/counts. 127 focused tests passed, then 25 final source/date tests; record validation passed. Actual isolated browser proof includes checkbox refusal, explicit one-source acceptance/advance, retained All history, 390-pixel containment, native keyboard disclosures and search. See MISSION-34-SOURCE-AUTHENTICITY-WORKSPACE.md. Other retained specialists, broader market population, old-PR parity and combined release/rollback remain; nothing merged/deployed.

**Mission 34 final CI:** PR #308 head `e948e75ee9f8addb9e9f8d0e887f0f1ae90c8989` passed Change scope, Repository integrity, Static public safety and Python tests in run 37243251516: 3,836 passed / 11 skipped / two warnings / 353.24 seconds.

**Mission 35 retained workflow shell:** Shared Glasshouse replaces the remaining base/sidebar generations while preserving context, search, Reader, session controls, Pagefind and native forms. Specialist links are grouped without deleting compatibility routes; directory/queue counts remain accessible. Comparisons, claim wording and publication history have clearer hierarchy; stale Reader settings and unbuilt-Learn copy are corrected. 193 focused tests passed (one warning, 58.91s); record validation passed. Actual native review covered comparison selection, shared Reader/search, isolated intake and publication-history fixtures, contained 390-pixel screens and menu/table overflow. See MISSION-35-RETAINED-WORKSPACE-SHELL.md. Wider market population, old-PR parity and combined guide/release/backup/rollback remain. Nothing merged/deployed.

**Mission 35 CI repair:** Initial PR #309 head passed three required checks; full Python CI found twelve old-navigation assertions (3,826 passed / 11 skipped / two warnings). Updated assertions follow the approved consolidated homes to the retained tools and verify real action counts. All 198 affected-workflow tests passed locally (one warning, 108.15s). Fresh exact-head full CI is required before reporting this slice green.

**Mission 35 final CI:** Draft #309 head `7a82b7bd52e3967fd383a04b97536bf6ec15ea62` passed all four required checks, run `37247720206`: 3,838 passed / 11 skipped / two warnings / 360.68 seconds. Twelve superseded navigation assertions were repaired; consolidated homes and retained specialist workflows remain covered.

**Mission 36:** MAP-02 now supports explicit bounded country/berry research beyond the agency refresh. 124 focused checks passed (one existing warning, 27.40s); records validated. Native request/progress/confirmation refusal/recovery/fictional acceptance/Map/snapshot/PDF and actual 375-pixel phone containment were reviewed. Genuine Chile/blueberry research completed with one native-cited proposal and 24 citations, remaining unreviewed/unapplied. Reporting-year qualifications and estimate labels stay primary; no inferred production/yield, canonical edits or trust changes. Exact-head required CI and the finite combined release/guide/persistence/backup/rollback acceptance remain. See MISSION-36-MARKET-REFERENCE-RESEARCH.md.

**Mission 36 final CI:** #310 exact head `a421a77ea7b21634dbdcdb7b07cc87a6463630d3` passed all four required checks, run `37332287901`: 3,877 passed / 11 skipped / two warnings in 229.96 seconds. One real public research proposal remains unreviewed and unapplied.

**Mission 37 current ledger:** Primary rows above have been reconciled through M36 rather than leaving completed work in stale Remaining columns. Source/content limitations, human decisions, native chooser failure and the one-shared-analyst/worker boundary remain explicit. Combined release acceptance is still required.

**Final acceptance reconciliation (October 5):** All 28 primary requirements have a delivered purpose, actual evidence and existing regression-suite reference in [RELEASE-REVIEW.md](RELEASE-REVIEW.md). Native real packet All/Reviewed capture, schema-valid download, unchanged re-download timestamp, seven-file restart preservation and scoped Map/snapshot phone/PDF checks passed. Packet source/review columns are kept readable. Photo/identity/figure/source decisions and source-dependent coverage remain honest human/content limits. Fresh exact-head CI and final user review remain release gates; production is unchanged.


**October 7 catalog handoff:** CAT-01 now connects human-reviewed distinct candidates to the existing intake/source/claim review path. Names/berries/source URLs carry forward; changed decisions and catalog name/alias collisions block writes. Explicit reviewer fields work without local login. Existing human review creates only an unverified entity, with statements separately reviewed. No real canonical additions were made. CAT-01/CAT-02 and comprehensive coverage remain open; see VARIETY-CATALOG-REVIEW-HANDOFF.md.


## October 9 follow-up: Rutgers original filing and historical names

See [original Rutgers filing review](RUTGERS-ORIGINAL-FILING-REVIEW.md). One focal
grant plus four separate parent/comparison mentions are now discoverable, including
the source's explicit NJ09-2-1 / Rutgers D'Light pairing. No catalog alias, entity,
company role, current right, region or image permission is approved automatically.
The bounded audit is now 378 sections /1,549 occurrences /88 catalog matches /
1,461 needing review /1,124 source-derived candidate keys. All 31 requirements and
their order are retained; CAT-01, CAT-02, TD-116 and REL-01 stay open. Current and
historical portfolio completeness, original current rights, human authoring,
independent recall, phone review and integrated release preparation remain.


## October 9 follow-up: human variety-name review packet

The [human name-review worksheet](VARIETY-HUMAN-RECALL-PACKET-REVIEW.md) now
prepares all32 retained Article copies with blank expected lists. A read-only
captured-text view hides stored summaries and approval controls. Browser-local
drafts and partial JSON export are verified with fictional sources; none of the
actual32 expected lists is completed. Offline assembly verifies source fingerprints,
refuses unfinished/shortened inputs and uses the existing scorer without a
qualification marker. Source acceptance, catalog authoring and independent
benchmark qualification remain separate. This prepares the human packet; it does
not complete the human-owned recall requirement. Full scope, phone, blueberry
feedback and integrated release gates remain open. All 31 requirement IDs/order stay.


## October 10 UTC: original Chandler source follow-up

Original claim/code references and seven separate parent/comparison observations retain existing candidate anchors, crop boundaries and human decisions. The bounded audit is 380 sections /1,557 occurrences /88 matched /1,469 requiring review /1,126 derived keys, with 64 canonical varieties and 122 unchanged photo references. Parent #390 passes all four required checks /4,618 tests; this child needs fresh CI. The actual 32-source human worksheet remains unfinished. Full corpus/portfolio/rights/profile coverage, independent human recall and catalog authoring, phone review, blueberry feedback and integrated release remain open. See [Chandler source review](CHANDLER-ORIGINAL-FILING-REVIEW.md). No merge/deploy or other-berry Landscape rollout.

## Previous October 13 pre-release status (historical)

## Current release review — October 13 UTC, 2026

The combined software release in draft #398 is reconciled onto canonical
`642bc556` and tested at `1fb75b61`: all four required checks succeed,
5,023 tests pass, and browser/export/host/restart/recovery/rollback checks pass.
The visual guide contains twelve section cards, four workflow steps and six
reporting choices. A committed-code package is prepared. Final merge/deploy
approval is pending; production remains unchanged. The blueberry continuation
and local review downloads were already approved and need no repeated request.

The copied reviewer workspace retains 52 pending source copies, the original
32 human worksheets and saved state. Its first Competitor registry list contains
77 supplied subjects without subscribing the user automatically. CAT-01/CAT-02
remain open: source acceptance, identity/catalog authoring, independent recall,
current rights and comprehensive source/profile coverage are separate tasks.

The isolated patent follow-up #399 fixes false denomination-as-code conflicts.
Its first full run found one genuine multiple-commercial-label regression;
59 affected tests pass after repair. All four exact-head checks now succeed on
`900d655a`: 5,029 passed /11 skipped /two existing warnings.
The [four-berry original-source batch](FOUR-BERRY-ORIGINAL-PATENT-SOURCES-REVIEW.md)
adds five profile references, the unresolved NSG 203 filing and 29 other names.
It brings the bounded audit to 407 sections /1,607 occurrences /110 matches /
1,497 review needs and 1,141 public-derived candidate keys. Those observations
are not new approved varieties. All 64 canonical profiles remain unchanged.

All 31 IDs/order and source, identity, catalog, Atomic, qualification and photo
human gates remain. The previous component/checkpoint evidence is preserved
verbatim in the checklist history and its referenced review documents.


### Previous docs/v2/MISSION-CLOSEOUT-2026-11-03.md

# Current verified releases and remaining mission — November 3, 2026

[Catalog #488](https://github.com/samsonFive/berry-intelligence-os/pull/488) is
merged and independently verified live at `32eefbd5` (approved `22dcb869`),
retaining News #487, #486 and earlier platform releases. All four final checks
pass: 6,277 tests. Fresh release-time and live checks retain all five accounts
including Chris.H, 65 profiles, 10,539 existing JSON records, four databases and
1,115 research files. One source import is added; no existing data was replaced
or restored. Settings, mounts, proxy, active/enabled News schedule, backup and
rollback are preserved. The #486, #487 and #488 approvals are fulfilled.

The source import recovers three PSG selectors and two related lists: 44
occurrences of 34 printed names/codes, 18 additional review keys and 34 held
photo references. All 1,315 earlier public-source keys remain. The scoped public
corpus is now 539 sections /2,073 occurrences /1,333 review keys, with 11
unreadable sections and 143 follow-ups. These are source observations and review
candidates, not 1,333 approved varieties or proof of worldwide completeness.
Canonical variety identities, company roles, rights, growing footprints and
photo reuse still require their existing human decisions.

News #487 finalizes useful capture as partial when optional tagging fails.
Provider quota is still an operational dependency; no purchase or paid retry is
authorized. The one approved Learn acceptance run completed previously and
remains an editable AI draft. The visual Help explainer and collaborative
Workspaces/private Digest and layout boundaries remain delivered.

Cold catalog visits still take several seconds; TD-122 remains open. The exact
Reader-key implementation in closed, unmerged #489 preserved all eight complete
outputs but gave mixed page/workflow timings. It is excluded from live release;
the stronger prototype figures are not final-code or deployed claims.
[The current investigation](COLD-CATALOG-INVESTIGATION-2026-11-03.md) retains this evidence and earlier
rejected experiments. The independent human expected-name audit, source and
trait/IP/photo depth, held Map selections and broader Learn quality remain in
this mission. Original 31 definitions/order, the governing guide and all human
review gates remain unchanged. Earlier entries below are historical records.

# Current closeout continuation — November 3, 2026

#477 is deployed and independently verified at `1ad5084f`. Its approval is
complete. #480 is frozen at `53dd52e3`, tested and awaiting separate release
approval. #482 is frozen at `078efa67`, passes all four checks (6,187 tests),
native desktop/phone review and fresh isolated preservation, and is not
approved or deployed. The ineffective catalog batch481 was withdrawn.

The one authorized real Learn request completed and remains an editable AI
draft; no further paid request is authorized. Cold catalog visits remain slow,
and the independent source/name/role/photo and held Map decisions remain open.
The [Reader source-link child](READER-SOURCE-DESTINATIONS-REVIEW.md) continues
NEWS-03 without changing those review gates or either frozen release head.

# Remaining work in the original Berry Intelligence mission

The user explicitly continued this mission here. The open requirements stay in
this thread and are not reassigned to hypothetical follow-up missions. The
original 31 accepted requirements remain unchanged in the requirements checklist.
This document records the remaining work; it does not mark the goal complete.

## Verified delivery

Performance release #476, approved head `06255cfc`, is merged and independently
verified live at `50659fcd1f710d534d56d54f1d27d7e7a7382ac3`. It retains the
consolidated platform, four-crop Landscape, dense image-rich News and article
Reader, shared Workspaces, private Digest/layout, reporting and visual Help
explainer. Its current-head checks pass with 6,109 tests. The fresh backup,
isolated preservation, live image/HTTPS, unchanged settings/mounts, original proxy
restoration and retained rollback are verified. All five accounts including
Chris.H, 65 profiles, 10,537 existing protected JSON records, four databases and
1,115 stored research files were preserved. This approval/release is complete.

## Work that remains here

| Requirement | Next work | Evidence required for completion |
| --- | --- | --- |
| TD-122: daily-use speed | Continue from the deployed #476 base; profile first company/catalog visits and the full next-click workflow. Reject displaced cost and regressions. | Complete output and current-edit parity, real cold/warm workflow measurements, required checks, browser review and fresh production-copy preservation. Slow first visits remain open; a microbenchmark alone cannot close the item. |
| CAT-01 / VAR-01: supplied names and independent recall | Retain the 143 photo candidates /144 associations, 32 unclear cells and two identity holds; recover source gaps and route actual name/role decisions through review. Complete the independent 32-source audit without using detector answers as its gold set. | Source passages, independently supplied expected names and actual human decisions. Occurrences/candidate keys are not approved varieties or proven company roles. |
| CAT-02 / VAR-02: useful variety depth | Work through the retained 77-subject current/historical source plan, 14 unreadable sections and 146 follow-ups; author cited traits, growing regions, original rights/patent references and attributed images. | Accounted source sections, explicit historical/current scope, readable provenance, reviewed canonical identities and disclosed gaps. Never infer comprehensive worldwide coverage from the 537 sections or 1,315 source-derived keys. |
| MAP-02: useful market context | Review the 24 country/crop references and 51 original-unit figures across eight countries; recover stronger evidence where possible, retaining the two UK discrepancy holds. | Human selections, explicit period/unit/geographic/crop scope, original source links and resolved or visibly held conflicts. No automatic trusted figure selection. |
| LEARN-01 / LEARN-02: deep visual learning | Verify the delivered 27 visual lessons and selected-text research workflow, then perform an explicitly authorized bounded real-provider acceptance test and repair any actual defects. Continue source-linked visual depth. | Actual provider settings/output, cited lesson quality, availability and cost, original lesson/edit/history preservation and human review. Fixture lifecycle tests do not prove real-provider quality. |
| Whole-thread completion | Reconcile every original requirement and subsequent prompt against current code, UI, receipts and actual stored content. | Requirement-by-requirement proof. Open acceptance/content/human items remain open; no handoff or scope reduction substitutes for completion. |

## Current performance investigation

The isolated branch `perf/catalog-cold-path-20261103` starts at deployed `50659fcd`.
The read-only public-fixture profile preserves all 2,997 inputs and forbids
networking. It places much of the remaining company Varieties work in source
reconciliation, current identity lookups and article-source preparation. Profiled
times are diagnostic, not baseline/candidate latency measurements.

An initial article-availability predicate probe encountered no article-body text
checks in the public fixture. That empty population is not acceptance or speed
evidence. The subsequent bounded offline production-copy probe checks 63,113
actual text predicates, including 15,761 positive controls. Both proposed
algorithms preserve decisions but fail to improve consistently, so both are
rejected. No Reader predicate change is retained. No provider requests or
production changes occur.

Draft #477 instead prepares News and regions only on the company tabs that
display them. The first head passes all four checks and a fresh isolated
production-copy comparison: all 64 complete responses and active/other context
match, with the 16-request workflow 21.41s → 18.89s. This is measured evidence,
not a claim that the remaining cold-load issue is solved. A phone review then
identified excess header height: existing secondary research links are grouped
under a collapsed menu and spacing is tightened, bringing the selected tab's
content 178px higher. This expanded head requires renewed tests, browser review,
CI and fresh-copy preservation. See `COMPANY-TAB-PREPARATION-REVIEW.md` for the
scope, measured limits and evidence boundaries.

## Release and review boundaries

No new head has release approval. Continue implementation, tests, fixes, browser
review and draft PRs autonomously; obtain a concrete tested release approval
before a future merge/deployment. Keep source/identity/role/rights/photo/figure,
Atomic Evidence and qualification decisions human-owned. No paid provider call
or human expected-name answer is supplied by this continuation. The earlier
blueberry checkpoint was approved and the all-crop release delivered; do not
reopen that obsolete stop.


End of the retained preceding checklist and closeout records.
