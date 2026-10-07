# Variety coverage: university and historical sources

October 7, 2026. Stacked on draft #321; blueberry Landscape gate remains held.
This slice adds primary-source depth through the existing unreviewed name
observation path. It makes no real identity, publication or claim decisions.

## Source scope

| Source section | Occurrences | Boundaries |
| --- | ---: | --- |
| Cornell current licensing catalog | 9 | Six raspberry and three strawberry headings. Golden Blush, Red Raspberries and June-Bearing are group headings. Other crops and comparison names are outside this scope. |
| Cornell historical raspberry chart | 6 | Six names with D-codes, visually checked on PDF page two. The first page repeats them in a harvest chart and is not counted again. The filename is historical context, not a publication date. |
| Cornell April 30, 2012 release | 5 | Two focal raspberry releases and three named earlier berry releases. The actual publication date remains separate from the October 7, 2026 source check. |
| Arkansas current blackberry page | 9 | All nine variety sections and their adjacent Cultivar codes. The separate “43 varieties developed” program total is not 43 visible cards or a completed historical portfolio. |
| Arkansas current blueberry page | 1 | Norman is the one displayed variety. This is not the university's full historical blueberry portfolio. |
| Arkansas extension refresh | 18, already counted | Retains every original name in the same order under the existing section ID. Adds direct description-sheet links and historical context. This refresh is not another 18-name coverage gain. |

**Thirty occurrences are added in five new sections.** The existing 18-name
Arkansas section is refreshed without duplication; its older snapshot remains
intact. Combined primary scope is **411 occurrences / 33 exact catalog matches /
378 occurrence review needs**, in 37 sections (36 readable, one unreadable).
Sixteen of 77 registry rows have some checked pages; **61 need initial checks**.
These numbers account for bounded pages, not complete historical portfolios.

The queue derives **355 combined candidate keys before private state**, versus
336 in #321: 63 stored-source keys and 292 additional primary-source keys.
The catalog stays at 64 entries: 57 active, six unverified and one historical.
Occurrences repeat across sources; candidate keys are not approved cultivars.
Stored-source discovery remains 95 observations / 32 matches / 63 candidates.

## Identity, source and date fidelity

Double Gold and Crimson Night already have catalog entries; they link there
instead of generating duplicates. Their stored Cornell summary is still missed
by deterministic discovery. This source reconciliation fills the visible
provenance gap but does not claim to repair summary/full-text recall. Crimson
Giant, Purple Wonder and other unmatched identities remain in human review.

Arkansas's code/display-name pairs remain separate assertions, without automatic
aliases, rights, company roles or release-date facts. A code can suggest an
existing trade name but that overlap alone is not an exact code match. Display
labels retain trademark context; identity strings do not acquire glyph aliases.
Cards lead with the literal source display name, with codes below it; the
review target and identity fields retain their original values.
Current pages and earlier description sheets differ on some release years;
no date is selected or normalized into a trusted fact. Adaptability maps and
university locations are not planted growing regions. No images or contacts
are copied; profile imagery and traits remain separately sourced work.

The read-only presentation carries an explicitly recorded publication date
into candidate provenance, validates its ISO date, and displays it separately
from the check date. Missing dates remain missing. Institution links now use
their actual entity type, including Cornell's existing breeding-program profile.
No duplicate university entity is created.

AAES pages returned 502 through the web reader but loaded normally in the native
browser. Full visible sections and adjacent codes were inspected there. The
extension page and its actual linked sheets were also checked. No replacement
scraper, provider call, source onboarding or qualification was introduced.

## Acceptance

Repeat the body-free audit with:

```text
python scripts/audit_variety_portfolios.py --output artifacts/variety-university-portfolios/coverage-audit.json
```

98 related tests passed / one existing ReportLab warning / 64.99 seconds.
The initial acceptance test incorrectly expected a review candidate for Double
Gold, which already exists in the catalog; the correction verifies its profile
link and uses unmatched Crimson Giant for the dated review handoff. That
preserves duplicate prevention rather than forcing a new candidate.

Tests cover single-count refresh, literal codes with unapproved trade-name
suggestions, unchanged input identities, historical versus check dates, program
links, invalid-date rejection, no GET writes and existing human-review guards.
Native desktop review checked the global and Cornell scopes, the source-to-review
link and keyboard disclosure. A 390px candidate view remains 375px wide and retains
the 2012 publication date. Browser acceptance made no POSTs. Ignored proof and
the task-private polling-disabled localhost preview are in
`inbox/university-portfolios/`. Canonical record and whitespace validation pass;
exact-head CI must be recorded in the draft PR before calling this tested.

After the name-first card change, 45 portfolio/university/navigation checks
passed / one existing warning / 35.02 seconds. Native review verified the new
name/code hierarchy and followed Cornell's institution link into its actual
profile. No tier, favorite, list, identity or claim action was submitted.

Parent #321 head `d8df470f8754ef82bfbc6f558edd5350651d7d4e` passed all four
required checks, run `37613126355`: 4,021 passed / 11 skipped / two warnings /
384.79 seconds. Its precision diagnostic still has one F1 title miss; the
original 24-case diagnostic still has 14 table/language/body misses.

## Remaining work

CAT-01/CAT-02/TD-116 stay open: 61 initial primary checks; full historical
portfolios; actual table/multilingual/body acquisition and independently scored
recall; denomination/alias and jurisdiction-specific rights checks; cited traits,
pictures and growing regions; refresh reconciliation; external resource comparison.
No model qualification, global completeness, human approval, canonical migration,
merge, deployment or other-berry Landscape rollout is implied.
