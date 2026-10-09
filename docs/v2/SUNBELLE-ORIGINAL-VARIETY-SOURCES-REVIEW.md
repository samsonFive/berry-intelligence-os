# Sun Belle: original names reach variety review

Sun Belle's older original company pages explicitly name **Aketzali** blackberry
and **Erika** raspberry. Those source references now reach the existing identity
review queue. Aketzali already had another portfolio reference; Erika adds one
public derived candidate key. Neither is silently added to the canonical catalog.

The newer premium-line page remains a separate, incomplete source. CraveABelles
is a product-line label, not a cultivar identity. A readable blueberry Origin
page without cultivar names is retained as a gap rather than proof of no varieties.

## Original-source scope

| Page | Finding | Remaining limit |
|---|---|---|
| [Blackberry Origin](https://www.sunbelle.info/blackberries/13) | Aketzali is explicitly named | No publication/release date; newest does not establish a current launch. Its location, traits and company roles require review. |
| [Raspberry Origin](https://www.sunbelle.info/raspberries/19) | Erika is explicitly named | No publication/release date. Company origin/growing/quality descriptions remain claims, not approved traits or regions. |
| [Blueberry Origin](https://www.sunbelle.info/blueberries/1) | Category/seasonal context, no cultivar denominations | A partial source, not a complete current/historical portfolio or proof of absence. |

All three original pages were read in the native browser on October 9. An indexed
raspberry copy had a different copyright year from the live page; neither is used
as a publication date. Header/background photos lack explicit cultivar captions
and were not assigned to varieties. No generic berry image fills a photo gap.

## Reconciliation and review

The bounded source set is now **366 sections / 1,142 name occurrences / 72 catalog
matches / 1,070 requiring review**, with **789 public derived candidate keys**
(**790** in the actual isolated preview including its preserved private state).
There are still **64 canonical varieties and 122 photo references**. The 77-entry
source plan remains **60 with enumerated names, 14 partial, one unavailable and
two identity holds**; zero unstarted does not imply complete portfolios. The
partial/follow-up source count increases from 107 to **110**, honestly retaining
the three pages' limits.

Native app review verified four Sun Belle sections (including the previous premium
line gap), two named occurrences and the retained partial status. The Erika source
opens the existing source-filtered identity review, with original URL, source
context and separate human actions; no identity decision was submitted. See the
[source handoff screenshot](../../artifacts/sunbelle-original-variety-review-2026-10-09/erika-source-handoff.png)
and [candidate review](../../artifacts/sunbelle-original-variety-review-2026-10-09/erika-candidate-review.png).

## Validation and remaining work

**92 affected tests pass**, one existing ReportLab warning, 102.81
seconds, including the parent stylesheet assertion repair. Exact-head full CI
remains required on this draft. The first local run exposed an outdated
exact-manifest assertion (83 passed / one failed); its total and raspberry/blackberry
denominators were updated against the actual audit, while asserting that Sun Belle
remains partial. Record validation and the 1,755-page static/Pagefind build pass.
All 2,771 original canonical JSON files, the governing guide, 32 pending source
copies and the real pending draft remain unchanged; no new human decisions,
extraction-ready IDs, photo reuse approvals or canonical authoring.

The initial full CI run on `4ed2751b43c5b675ee1189d5c0b5a83400ba35b4`
passed scope, integrity and public safety, but failed one historical batch test:
**4,562 passed / one failed / 11 skipped / two warnings / 806.29 seconds**.
That test removed the earlier Black Venture source, rebuilt Aketzali from the
newer Sun Belle reference, then expected the former ID after restoring the
earlier source. It did not supply the existing queue it claimed to preserve.

The corrected replay test supplies that queue and accounts for overlapping
names instead of assuming every newly read name is new. Two added regressions
verify that the actual Sun Belle addition preserves all earlier freshly derived
IDs, adds only Erika, and preserves existing human notes, rejection, alias and
photo choices even with source order reversed. These are fixture decisions,
not new human reviews. **33 source/identity regression tests pass**, one existing
warning, 42.30 seconds. No application identity code was changed; exact-head
full CI remains required on the repaired draft.

Full current/historical portfolios, current official rights, cited profiles,
original corpus and independent human recall remain incomplete. CAT-01/CAT-02/
TD-116 stay open. The blueprint's phone visual review remains outstanding. Other
Landscape berries await revised blueberry feedback; no merge or deployment.
