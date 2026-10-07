# Variety portfolio expansion: account for the whole captured page

The Hortifrut omission was systemic: stored summaries and famous-release lists
cannot establish comprehensive variety coverage. This follow-up expands dated
primary-page enumeration and makes mixed crops, pagination, identity discrepancies
and wrong company websites visible. It is stacked on the first portfolio slice;
Landscape remains at its blueberry review checkpoint.

## Captured scope, October 7, 2026

| Primary page section | Berry name occurrences | Accounting and limits |
| --- | ---: | --- |
| Fall Creek commercial catalog | 38 blueberry | All unfiltered product headings; climate categories excluded. Public/partner cultivars do not become Fall Creek-owned varieties. |
| Fresh Forward strawberry navigation | 15 strawberry | All footer product links match the stated 15 total. First page has five cards; full product traits remain unread. Apples are outside the stated strawberry scope. |
| Flevo current product list | 15 strawberry | All linked product cards on the live unfiltered page. |
| Flevo older names | 2 strawberry | Fleurette and Sussette are explicitly called no longer supported; retain that source context, without declaring rights expired or deleting records. |
| Planasa US shop | 38 across four berries | All 53 live cards: 38 berry observations plus 15 exclusions (7 asparagus, 4 garlic, 4 endive). |
| Planasa Spanish shop | 38 across four berries | All 54 live cards: 38 berry observations plus 15 non-berry exclusions and Demoiselle, whose species was not established by the captured card. Matching uncategorized labels use US crop context only where both label and code agree. |
| Oregon Blueberry nursery | 36 blueberry | Load-more pagination expanded until its control disappeared. The linked flipbook and historical catalog remain separate work. |

Original URLs and body-free names/codes are in
`data/imports/variety-portfolio-observations-2026-10-07-expansion/observations.json`.
Product links are retained when read from live cards. Trademark glyphs are omitted
from identity strings; selection-code punctuation is preserved. Source assertions
about performance, roles, patent numbers and geographic adaptation are not imported
as approved facts. `observed_at` records the capture session, not a release date.

Combined with the first slice: **275 source occurrences**, **25 exact catalog
matches**, **250 review needs** across 17 sections (16 readable, one unreadable).
Existing discovery derives **239 candidate keys before private inbox state**:
68 stored-source candidates and 171 additional primary-page candidates. These
keys include unresolved codes, commercial labels and repeated identities; they
are not a count of newly proven distinct varieties. The catalog stays at 64.
Eleven of the 77 supplied registry rows have some primary coverage; 66 still need
initial checks. Rows can include aliases and multiple companies. No global
completeness percentage or web-leading claim is supported.

## Problems retained for review

- Planasa US displays Black Sultana and Black Rainier with `Plablack 15157`.
  Spanish Black Rainier displays `Plablack 1737`. Both literal readings stay in
  provenance; neither is silently corrected or accepted as an alias. The shared
  code candidate carries both labels. Pink Hudson's winter product also retains
  its cultivation label without claiming a second cultivar.
- Shared codes with different labels and shared labels with different codes
  have plain-language warnings in coverage and identity review. Conflicted source
  pairings do not receive an automatic catalog-match label. Existing compatible
  human decisions still win and are never overwritten.
- Oregon Blueberry's saved website, `oregonblueberry.com`, identifies the Oregon
  Blueberry Commission. The nursery catalog is `www.oblueberry.com`. A source-plan
  warning retains both URLs; the existing company record and user edits remain
  untouched. Profile correction requires the existing review/edit workflow.
- Planasa web index captures differed from the live catalog. Live browser cards
  were enumerated coherently per language; stale 51-result text was not mixed
  with the current 53-card US capture. No private API or hidden browser state was
  used to bypass unavailable pages.

## Behavior and verification

Page accounting reports observed items, names/exclusions accounted for and stated
totals where present. A shortfall or differing total is flagged, not hidden behind
a recently checked date. Filters scope mixed-berry counts and candidate handoffs;
whole-page accounting is explicitly labeled separately. Exclusions have names,
reasons and product links, and never create variety candidates. Malformed observation
shapes fail through the existing recoverable warning. Nursery candidates use the
existing nursery source tier. No new resolver, trusted schema or acquisition engine.

Reproduce the body-free audit with:

```text
python scripts/audit_variety_portfolios.py --output artifacts/variety-portfolio-expansion/coverage-audit.json
```

It reads no private inbox or human notes and writes only the requested artifact.
Verification: 21 focused tests passed (one existing dependency warning). The full
local Windows/Python 3.13 regression run passed **3,984 tests / 9 skipped**, with
629 dependency deprecation warnings, in 842.76 seconds. Canonical record validation
and diff hygiene passed. Required current-head GitHub checks are recorded in the
draft PR; local results do not replace that release gate.

Browser checks covered desktop overview, native Planasa/Blackberry filtering
(six occurrences across two source pages), whole-page accounting, two relevant
name/code discrepancy messages, filtered candidate handoff and retention of both
labels/product URLs on the shared-code candidate. Oregon's site warning and 36
cards were inspected. At a 390px phone viewport the page scroll width was 375px;
620px tables stayed inside their 349px scrolling panels. Keyboard Enter opened the
77-row source plan. Review actions were not submitted. No JSON files appeared in
the isolated inbox during these GET-only checks.

Preview: `http://127.0.0.1:18444/varieties/coverage`, localhost only, polling off,
task-private empty runtime. Proof is under `artifacts/variety-portfolio-expansion/`:
desktop/phone overview, phone source plan, nursery detail and candidate provenance.

## Next work remains open

Complete the remaining breeder/program sources, historic/public-domain releases,
linked sheets and regional catalogs. Check codes, denominations and rights against
existing official-register adapters; preserve breeder/applicant/titleholder/marketer
distinctions. Finish human canonical-authoring handoff, source-backed traits/images/
growing regions, refresh reconciliation and a separately scored manual recall set.
Compare external resources before claiming the most comprehensive resource.
CAT-01, CAT-02, TD-116 and the ongoing goal remain open. No merge, deployment or
other-berry Landscape rollout is included.
