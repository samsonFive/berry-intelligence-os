# Mission 19 — Visual learning across the five pillars

Continues from draft #291 head `2d3218736d37cecd99da4b583d40294dd5471834`. All four required checks passed, run `37081601872`: 3,610 passed / 11 skipped / two warnings in 341.97 seconds. This slice expands teaching presentation and aligns public Learn with the accepted Glasshouse design. It is not canonical release approval.

## What changed

Four existing lessons now have original interactive SVG teaching diagrams: IPM's ongoing decision cycle, the separate detection/picking/collection challenges in harvest robotics, the complementary dimensions of flavor, and source/permission/caption boundaries for teaching media. Together with the existing cane-year diagram these provide an interactive representative lesson in all five learning pillars. They do not supply a quantitative simulator, crop prescription, cultivar ranking or company deployment claim.

The diagram has a large explanatory heading, illustrated selection cards, a distinct selected explanation and visible limits. All explanations render before script enhancement; native buttons work by click or Enter, retain focus, report their selected state and announce the changed explanation politely. Phone cards use two columns and at least 44px-high buttons. Original lesson text, IDs, classification, sources and dates remain; no canonical concept JSON was changed.

The shared learner presentation returns independent copies and is idempotent, including video deduplication. Live and public Learn use the same home/concept templates and styles. Public search goes to the real public Search page; Review cadence uses the finite static route. Static related intelligence links directly to published Evidence. The static request has no live app state, so the shared shell no longer assumes it does. Public output does not add private research controls, Reader review actions or draft lessons.

## Sources and media rights

Original graphics are informed by primary sources checked October 2, 2026:

- [UC IPM's framework](https://ipm.ucanr.edu/what-is-ipm/): identify, monitor, decide, prevent, combine management tools and evaluate. Prevention/monitoring remain ongoing; regional action thresholds are not supplied by this graphic.
- [Robofruit research paper, 2023](https://arxiv.org/abs/2301.03947): a schematic research picker, with detection, picking and quality distinguished. A demonstration does not establish commercial use by an entity.
- [Gilbert and colleagues' blueberry flavor study, 2015](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0138494): contextualized to 19 southern highbush genotypes across three years; the graphic has no weighted preference score or universal ranking.
- [Creative Commons license types](https://creativecommons.org/cc-licenses/): the specific license and its conditions matter. A public source page alone is not permission to copy an image.

UC IPM and the Robofruit authors' source-linked video URLs are optional outbound links; playback availability was not verified. Videos were not copied, hosted, embedded or autoplayed. The existing verified raspberry photograph retains Steffen Flor (Pro2), CC BY 2.5, source/license links and a limited caption. Browser confirmed that photograph loaded. Other legacy images without a verified reuse basis remain source links rather than embedded photographs; their source records are retained. No publisher graphics were copied, media downloaded, paid research started or trust/identity decision made in this slice.

## Verification

Final focused run: **90 passed / one existing reportlab warning in 29.11 seconds**, including source/content immutability, independent presentation copies, reading without paid research or inbox writes, rights-aware public rendering and actual static private-sentinel exclusions. The public build fixture verifies attribution, non-embedding of the unverified blueberry photo, published links, search-index inclusion and absence of private Reader actions.

Intermediate failures are retained here: four initial HTML assertions did not account for Jinja's escaped apostrophes; test comparison now unescapes HTML and verifies the literal original text. The first static render exposed an actual shell assumption about `request.app`; that is guarded for static requests. One pre-existing Review cadence assertion then exposed missing explanatory copy; the distinction that this is not a trust queue was restored. Browser search caught missing Pagefind-body marking in the new Learn shell; it is restored on public Learn only and the actual index was rebuilt. No privacy or human review gate was weakened to pass checks.

Browser review covered IPM's Check results by keyboard, Robotics' Collect by click, Flavor's Texture by keyboard on a 390px viewport, Visual sourcing's Explain and credit by click and the existing Primocane-fruiting control. One selected note remains visible and focus remains on the button. Phone page width was 375px at a 390px viewport; four flavor buttons measured 136×44px. The viewport override is reset. Screenshots: `learn-ipm-visual-live.png`, `learn-robotics-visual-live.png`, `learn-flavor-visual-mobile.png`, `learn-visual-sourcing-live.png`. Public build/browser and exact pushed-head CI evidence are recorded in the follow-up below.

## Still open

Canonical record validation and JavaScript syntax checks passed. Final public build wrote **1,755 pages** and found no unpublished IDs/titles. Browser verified the generated IPM diagram's Prevent selection and relative Back to Learn/Search navigation; after the rebuild, IPM search returned nine results with the IPM lesson first. `learn-public-ipm-visual.png` records the public lesson. Static shell links to unavailable interactive routes and the old global Search styling remain known follow-up work, not claimed complete here. Exact pushed-head checks remain required.

This supplies representative diagrams across all pillars, not verified photographs and custom interactions for every lesson. Some retained curriculum wording still uses internal terminology; a plain-language editorial pass must preserve the substantive source limits. Broader static navigation and specialist layouts, real source/body/media capture and packet readiness, market statistics, region suggestions, protected profile enrichment, account/multi-worker persistence, cross-family walkthrough and canonical/release reconciliation remain in the requirements ledger. No merge or deployment without the final user review.
