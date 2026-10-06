# Mission 21 — One published-library reading experience

Continues from draft #293 head `f6ff1b8e84e3cc297c0f4beb315fe648934f77d2`. All four required checks passed, run `37086165073`: 3,636 passed / 11 skipped / two warnings in 304.61 seconds. No merge or deployment.

## Delivered change

The remaining generated feed, source pages, entity directories/profiles/portfolios, Markets, Scanner, Morning Brief, Sources, priority collections, Landscape and Executive View now share the public Glasshouse header and grouped More menu. Public links remain relative to their generated file and resolve within the snapshot. The existing live inheritance, routes, data services, controls and review gates are retained. A public-only bridge keeps the original content styles while overriding reading roles and palette; specialist layouts are not replaced with new stores or workflows.

Source pages put the unchanged source summary before detailed metadata. Read original source stays visible beside the actual publication date, or an explicit missing-date label. Source details and stored interpretation start closed; keyboard users can expand either. Source wording, brackets, qualifiers, identities, review status, capture date and links remain literal. Published-source reading does not recover bodies, call a provider or write a decision. The public feed identifies itself as a published snapshot rather than continuously updated intelligence.

Public titles, section headings and body text have distinct sizes. Cards use light paper, green borders and restrained shadows, with original status colors retained. Existing balanced-card collections now actually use a responsive grid rather than full-width stacked cards; there are three columns in the inspected desktop Executive View and one on a phone. Supporting tables and all existing source content remain available.

## Verification

Final focused run: **69 passed / one existing reportlab warning in 39.30 seconds** across static/private-sentinel safety, report readability, company portfolios, Markets and read-only publication review. The full static fixture now requires the shared header on every generated page, verifies all header links resolve inside the output, retains search-index marking on document pages, checks literal source context and summary-first order, and rejects the old desktop sidebar/stakeholder topbar. Search itself is intentionally not indexed as a document. An initial assertion incorrectly required that marking on Search; it was corrected, with 68 other tests already passing. No private or review guard was relaxed. Canonical records validated.

The production build wrote 1,755 pages and its unpublished-ID/title check passed. Browser inspection used the isolated public snapshot: Planasa's original URL and literal summary were present; all three supporting disclosures started closed; Source details opened and closed with Enter. Actual desktop article sizes were 33.28px title, 22px section heading and 16px body. At 390px they were 28px / 20px / 16px, with a 375px page width. More opened with Enter at bounds left 12 / right 363 / top 112 / bottom 736 inside the 844px screen. Markets fit the same phone width. Executive View retained its source counts and existing interpretation, with a three-column card grid. No private save, provider request or review action was performed. Viewport override reset; review tab retained for continuing work. Proof: `public-article-summary-first.png`, `public-article-mobile.png`, `public-markets-mobile.png`, `public-executive-view.png`.

## Remaining work

This completes the shared navigation pass for generated template families, not every specialist layout or source-quality problem. Public/canonical Signal and Assessment eligibility and inherited “trusted” captions still need a separate status audit; no stored record is made reviewed by this change. Wider content/plain-language refinement, live specialist routes, sources/body/images, metrics, protected enrichment, regions, production persistence and canonical/active-PR reconciliation remain in the requirements ledger. Preserve the canonical expansion guide, human identity/publication/statement/model gates and production runtime. Exact pushed-head CI and combined release/rollback review remain required. No merge or deployment without final approval.

## Initial full-suite follow-up

Draft #294 initial head `db7e75d980ecf3ca166608495337e479edd666d9` passed three checks. Python tests run `37087628404` had 3,634 passed / two failed / 11 skipped / two warnings in 337.13 seconds. Both assertions prohibited even a different parent shell for public navigation. They now explicitly require the intended public/live parent selection while retaining the ban on any static-only narrative branch and the actual shared-context narrative checks. The content pipeline and review rules are unchanged. A final full production build plus a separate header audit verified all 1,755 pages have shared navigation and every header destination resolves within the snapshot. Fresh exact-head checks remain required.


Final follow-up local run: **67 passed / one existing reportlab warning in 63.92 seconds** across Landscape narrative, synthesis and full static/private-sentinel checks. The public/live shell distinction is explicit; source interpretation and shared narrative remain unchanged.

Final exact-head CI: draft #294 head `27ed8cc7b7137cfaab4df4147cf7df07370a07a4` passed Change scope, Repository integrity, Static public safety and Python tests, run `37088365423`: **3,636 passed / 11 skipped / two warnings in 320.51 seconds**. Earlier failures remain recorded above; canonical integration remains open.
