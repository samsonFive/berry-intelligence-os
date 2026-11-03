# Redesign mission: delivered work and remaining closeout

This separates functioning platform delivery from content completeness and human
decisions. The original 31 accepted requirements and their order remain in
[the requirements checklist](REDESIGN-REQUIREMENTS-CHECKLIST.md). Counts below
describe the bounded retained corpus, not worldwide coverage or approved varieties.

## Delivered platform

The Glasshouse design, full-width navigation, dense News grid, image previews,
right-side Reader and publisher fallbacks, filters, company tracking/lists,
shared Workspaces, account-private Digest/layout settings, entity authoring,
region layers, reporting/packets, Meeting Prep, four-crop Landscape, Learn and
the visual Help explainer are deployed. Chris.H is enabled and existing first-login
history is preserved. Help explains site sections, the analyst workflow,
comparisons and reporting/export choices.

Approved News performance #475 is live as `6c2feaf1`, exact tested head
`c666a481`. All four checks passed /6,094 tests. A fresh isolated rehearsal
preserved all five accounts, 65 profiles, 10,536 existing JSON records, four
databases and private research. Live health, immutable image, release pointer,
backup SHA and rollback were independently verified. The first switch correctly
rolled back on a concurrent legitimate News refresh; that state was retained.
The successful retry used a tested temporary maintenance route and timed cleanup;
the route is absent and the original proxy configuration is restored.

## Remaining engineering and acceptance

| Work | Next concrete action | Completion evidence |
| --- | --- | --- |
| Cold company/catalog/News latency, TD-122 | Profile actual cold requests, remove unused preparation, then measure first visit and the complete next-click workflow. Keep slower or contended experiments as rejected evidence. | Fresh-process baseline/candidate comparisons with identical complete models/HTML; current-head tests; desktop/phone review; bounded fresh live-copy rehearsal. A modest News improvement alone does not close this debt. |
| Current release/status reconciliation | Record #475 as delivered, preserve dated prior evidence and reconcile every original requirement plus later requests. | No obsolete pending approval for an already deployed release; exact original requirement definitions/order retained; durable remaining-work list and release receipts. |
| Integrated next performance release | Prepare a draft PR after measured gains and meaningful regression tests; retain every account, edit, review decision, connection setting and persistent mount. | All four required checks on the exact head, browser/preservation evidence and a reviewable release/rollback plan. A new application head still needs the user's release approval before merge/deploy. |

No additional input is needed to continue these engineering steps. Physical
touch hardware has not been tested; phone viewport checks must not be described
as real-device acceptance.

## Content and human decisions that remain open

| Requirement | Actual gap | What resolves it |
| --- | --- | --- |
| VAR-01 / CAT-01: photographed seeds and identities | 143 photo candidates /144 associations retain 32 unclear cells. Two subject labels need organization/person decisions. A source association does not prove a breeder/owner/license role. | Human spelling/identity/role decisions in the existing queues; preserve uncertainty and original provenance. Do not guess names or create canonical records automatically. |
| CAT-01: independent missed-name recall | The 32-source worksheet is prepared, but its independent expected-name lists remain blank. Detector-derived answers would invalidate this test. | An independent human reads the retained source copies, supplies expected names and reviews actual misses. Source authenticity, identity and statement approval remain separate decisions. |
| CAT-02: comprehensive variety coverage | The bounded seed has 537 source sections, 2,029 literal occurrences, 175 catalog text matches and 1,854 review needs, yielding 1,315 source-derived candidate keys. These are not 1,315 approved varieties. The 77-subject plan has 67 named, seven partial, one unavailable and two identity holds, plus 14 unreadable sections and 146 follow-ups. | Continue documented current/historical portfolios, recover missing source text, review identities and author cited traits, growing regions, original rights/patent references and attributed photos. Publish coverage gaps; do not claim worldwide completeness from these counts. |
| Photos and rights | Some retained references have uncertain variety identity or reuse permission; a patent reference does not establish current legal status. | Human identity/permission decisions, valid attribution and jurisdiction-specific current-rights evidence. Session-only previews remain explicit and never become automatic public reuse. |
| MAP-02: market statistics | 24 country/crop references and 51 original-unit figures across eight countries are available. Two UK area discrepancies are held; figures are not applied automatically. | Human figure selection, explicit period/unit/scope and resolution or continued visible holds. Broader country/crop coverage is continued enrichment. |
| LEARN-01 / LEARN-02: lesson depth and real-provider acceptance | The visual lessons and high-depth research contract are implemented; actual high-depth provider output quality, availability and cost are unverified. Existing tests use fixtures. | An explicitly authorized bounded real-provider acceptance run, then source/quality/cost review; more credited photos, diagrams and useful video links are ongoing curriculum work. No paid acceptance call is assumed authorized here. |
| Trust and qualification | Source, identity, role, Atomic Evidence, model qualification and other human review gates remain human-owned. | Actual proposition-specific decisions through existing workflows. Automated passing tests never supply a human qualification or turn proposed content into trusted facts. |

The platform redesign can be assessed separately from the continuing catalog
research program, as requested earlier in this conversation. Closing this whole
thread's expanded mission still requires accounting for those content/review
items rather than silently dropping them. This document does not narrow scope,
grant approvals or mark the ongoing goal complete.
