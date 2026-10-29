# What is delivered, and what remains

Reviewed October 28, 2026, against the live release, exact draft heads, saved
test/browser receipts and all 31 accepted requirements. Later requests are
listed separately below so they do not disappear from the original checklist.
This is a delivery audit, not another redesign proposal or an approval request.

The core redesign and consolidation are live. Remaining platform fixes are
tested in #421; catalog enrichment through #425 is tested separately in #426.
Those two releases await the actual decisions already requested. #427 and #428
are later tested catalog follow-ups, not part of either frozen release.
Research gaps and human review are separate from unfinished software.

## Release boundaries

| Scope | Actual state | Evidence and next step |
| --- | --- | --- |
| Live platform | Canonical `e24b566b49e781d4a95d0e457d57c763f47c4741`; recovered without replacing its release or persistent data | App healthy, HTTPS login 200 in 0.078s, about 2.6 GiB available at October 29 01:11 UTC. This checks availability, not signed-in route speed. |
| Platform #421 | Draft `4cedbdc689750292715a900850d66e3a12c42be0`; all four required checks succeed; 5,284 tests | Includes on-demand profile work, per-account Digest, shared responsive anchors, bounded rehearsals and the shared-Workspace visual guide. Native fictional-account review and a fresh production-copy preservation check pass. Actual merge/deploy approval is pending. |
| Catalog #426 | Draft `87bb0187b03b06bcb54ec03a213c8167c5135651`; all four checks succeed; 5,330 tests | Consolidates #399/#400/#418/#419/#422/#423/#424/#425. New production-copy proof preserves five accounts, 65 profiles, 9,821 protected JSON files and existing contents of four databases. Actual merge/deploy approval is pending. |
| Photo-name review #427 | Draft `fcb8ef74d0619d0c8a45914ca15a2d2b5aa6e24e`; all four checks succeed; 5,335 tests | Native desktop/phone review passes. Existing Rutgers photo leads now reach name review without approving their identity. Based on #426; no inherited combined release or production-copy proof. |
| Original figures #428 | Draft `d5bb84dfd749c03df8f071e69b074041ccb3b659`; all four checks succeed; 5,337 tests | Native desktop/phone review passes for distinct Blue Manila/Blue Maldiva figures and exact original claim links. Based on #427; no inherited combined release or production-copy proof. |

All four required checks were re-read on the release/source heads above, and
canonical was rechecked as unchanged. Releasing either pending candidate still
requires its actual approval, current canonical/check verification, a fresh
release-time backup and the retained image/mounts for rollback. Releasing a
changed combination needs its own proof. Do not treat this document as approval.

## Later requests from the conversation

| Request | Delivered behavior and boundary | Remaining work |
| --- | --- | --- |
| Chris.H account; first login starts at Help | Account was provisioned additively and remains enabled. Earlier production checks preserve his pending Help onboarding without signing in as him. Passwords are absent from repository/review documents. See [News and access](NEWS-ACCESS-USABILITY-FIXES.md). | His actual first login is his action; do not consume it for testing. |
| One click for the newest News | News navigation and Refresh news start bounded collection, retain scope and display completed results without a second click. See [News and access](NEWS-ACCESS-USABILITY-FIXES.md). | New publisher availability and collection failures remain visible; date filters cannot create absent stories. |
| Real article text, clear publisher access, no Google consent blurb | Shared Reader automatically retrieves missing selected content; rejects known consent/wrapper captures, preserves useful earlier text and keeps publisher/retry options visible. | Restricted or unavailable originals remain an honest fallback, not fabricated article text. |
| Images are central to News | Shared publisher-first previews and labeled crop fallbacks are delivered with the redesign. | Publisher-specific image recovery is continuing content work; a fallback is not a photograph of that article. |
| Slow app | Approved performance releases are live; further on-demand profile work is tested in #421. See [performance scope and measured routes](PERFORMANCE-READER-PUBLISHER-COVERAGE.md). | Ship #421 after actual approval; measure signed-in routes on that release. Login timing does not prove every route fast. Wider performance debt stays open. |
| Workspaces are collaborative and universal | Shared Workspaces are live. Shared material, lists and review gates are not made account-owned. “Private” in technical source notes means excluded from unauthenticated/static output. | #421 updates the guide and verifies two fictional users see the same workspace revision. |
| Only layouts and Personal Digest account-private | Layout preferences remain individual. Per-account saved/reading state and explicitly subscribed lists are tested in #421, including migration that does not copy one user's Digest to every account. | #421 is unreleased. Do not claim Digest isolation is already live. |
| Floating alphabetical navigation in candidates | Sticky A–Z/# navigation and return/filter preservation implemented; see [quick navigation](VARIETY-REVIEW-QUICK-NAVIGATION.md). Shared wrapped-header anchor correction is tested in #421. | Retain the correction when integrating that release. |
| Patent information and click-through claims | Exact original filing/claim/figure links and contextual exclusions are prepared in #426 and #428. Related reports remain separate from focal filings. | Current official status/ownership and human identity decisions remain source/review work. An original grant is not proof of a current right. |
| Attributed variety photos; Ignore permission for a session | Existing private gallery supports explicit session-only load/hide with source credit and no public reuse approval; see [session preview](VARIETY-SESSION-PHOTO-PREVIEW.md). More original references are prepared in #426/#428. | Unknown reuse stays held; the user gesture does not establish identity or publication permission. #427 exposes existing identity-held leads. |
| Meaningful dense Landscape, comparison, saved views and exports | Approved blueberry continuation and subsequent four-berry release #398 are live. LAND-02 records tested comparisons, saved selections and complete exports. | Current/historical source coverage and human catalog decisions remain CAT-01/CAT-02; the old blueberry stop is satisfied. |
| Visual explainer of sections, analyst workflow and reporting | Delivered guide has twelve section cards, four workflow steps and six reporting choices. #421 adds shared Workspace purpose/capture/feed/briefing explanation and responsive verification. | Release the tested guide update with #421; preserve capability limits and retained specialist links. |
| Mobile review and deployment access | Protected review access and authenticated SSH deployment/recovery are established. | Temporary review availability must be checked when needed. No permanent public preview or automatic production release is implied. |
| Server recovery and continued work | Original release and mounts recovered; unbounded disposable jobs stopped. Bounded offline rehearsal guard is tested in #421 and installed for host review work. | Keep one bounded rehearsal at a time; retain backup/rollback and availability checks. |

## Catalog: finite evidence, honest gaps

The read-only public seed contains **64** variety profiles; production contains
**65**. Never restore the research seed over production. The latest bounded
audit, including #428, has 497 sections: 392 readable, 14 unreadable and 137
needing follow-up. It retains 1,785 name occurrences: 168 catalog matches and
1,617 review needs. These are occurrences, not 1,785 distinct varieties or
independent sources. The states are not disjoint completeness percentages.

The 77 supplied registry subjects have 61 checked entries, 13 partial checks,
one unavailable source and two identity holds. “Checked” is a bounded source
visit, not proof of a complete current and historical portfolio. Remaining
partial subjects are Benning Blueberries, Biogea, Fruitist, Gem-Pack Berries,
Institute of Botany (Chinese Academy of Sciences), Perfection Fresh, Rijk Zwaan,
Singrow, Smart Berries, Splendor Produce, SunBelle, Surexport and The Berry
Collective. Grupo HerEs has an unavailable source. Genetics Uruguay and Mario
Aguas-Alvarado remain identity holds; no company identity is invented.

The public seed has ten profiles without an eligible linked image: eight real
profiles and two examples. Rutgers D'Light already has a source photo held for
name reconciliation; it needs review, not another discovery count. Rights,
cited-trait and company-link gaps remain 13/33/10. Original figure references
reduce the image gap; they do not refresh approved profile prose. Blue Maldiva
still has an outdated historical “no patent found” statement: a private,
hash-guarded proposal preserves it for human refresh, not an automatic rewrite.

## What can continue autonomously

1. Recover accessible originals for the named partial portfolios; retain exact
   wording, dates, source scope and failed access. Keep parents, comparisons,
   brands and illustration codes separate from focal variety claims.
2. Inspect original rights records, cited traits/regions and explicitly named
   images. Record uncertainty and refresh conflicts instead of manufacturing
   aliases, company roles, current legal status or photo reuse permission.
3. Prepare source and catalog proposals through the existing review paths;
   test changes, review actual browser behavior and push drafts. This is not
   permission to supply human answers or auto-author the canonical catalog.
4. Reconcile the tested release stack only when its intended combination is
   clear; preserve exact human edits, account data and existing protected
   records. Ask for genuinely necessary release approval once.

## Human decisions still needed

The 52 copied source proposals still need actual source review. The original
32 independent expected-name worksheets are unfinished. These are different
work inventories; do not add them as 84 distinct sources without comparing
source identities. The supplied spreadsheet also has 32 unclear photo cells,
a different set. Human name/role/catalog,
Atomic Evidence and extraction-qualification decisions stay separate from
source acceptance, photo permission and software release approval. Existing
rejections and edits must survive all enrichment.

Broader market-statistics coverage, visual lesson/media coverage, publisher
text/image availability and current/historical catalog coverage remain content
work. The existing mechanisms are delivered; these are not promises that every
country, berry, publisher or cultivar is already populated. No global or
web-leading completeness claim is established. The goal remains active.

The [31-row requirements checklist](REDESIGN-REQUIREMENTS-CHECKLIST.md) retains
its original definitions and ordering. The [release review](RELEASE-REVIEW.md)
is the operational boundary; earlier dated entries remain historical evidence.
