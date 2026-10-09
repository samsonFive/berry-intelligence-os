# Original trial reports and image-table variety names

The University of Arkansas blueberry trial report was accessible but our
article extractor returned no body. Its publisher places the report prose
inside an HTML navigation element. This change recovers that bounded report
without admitting ordinary menus. Separately, the original image table supplies
twenty literal variety-name observations for human identity review.

## Article acquisition

Normal extraction remains first. Only when it returns no text does a conservative
in-memory fallback consider one prose-heavy navigation region inside declared
main/article content. Its enclosing section must contain exactly one H1 matching
the page title. Hidden, interactive, link-heavy, ambiguous and menu-only regions
remain excluded. The same original HTTP response is used; there is no second
fetch, browser rendering, access-wall workaround or model call. Existing access
checks still run first. Recovered paragraphs retain publisher headings and
acquisition provenance now records `article-acquisition-v3`.

A bounded capture of ten existing source URLs initially created nine private
pending copies; the trial report failed. After diagnosing and fixing its actual
HTML response, a one-source retry created the tenth pending copy: twenty
paragraphs, 1,015 words and 6,235 source characters. These are current-page
copies, not proven historical originals. Automatic similarity outcomes are not
human source-authenticity decisions. Some other captures remain short or partial.
No real copy was accepted, no extraction was enabled, and no canonical record or
analyst decision was changed. Captures stay in ignored local runtime, outside
Git, public/static output and release data.

## Image-table names

The [original November 22, 2024 report](https://www.uaex.uada.edu/farm-ranch/crops-commercial-horticulture/horticulture/ar-fruit-veg-nut-update-blog/posts/2024-blueberry-variety-trial.aspx)
enumerates its full twenty-variety list in
[Table 1](https://www.uaex.uada.edu/farm-ranch/crops-commercial-horticulture/horticulture/ar-fruit-veg-nut-update-blog/posts/images/2024%20blueberry%20variety%20trial%20list%20table1.png).
That image was visually read on October 9, 2026. Five Northern Highbush, four
Southern Highbush and eleven Rabbiteye names are retained, including the literal
spelling **Tiftblue**. No alias correction or equivalence is inferred.

The university is the report publisher, not an inferred breeder, owner or
license holder for these entries. These observations establish neither universal
traits nor growing footprints. The separate current university breeding listing
still names Norman. The image is linked for verification, not hosted; image reuse
permission is not inferred. Recovering prose is not OCR or proof of complete
image coverage. This manual enumeration covers Table 1 only.

The additional observations produce eleven more combined candidate keys:
**749** across stored and primary-source observations, **750** in the isolated
preview with its existing unreviewed Italian Berry article. The portfolio audit
now contains **348 source sections / 1,084 name occurrences / 64 catalog matches
/ 1,020 occurrences needing review**. Occurrences and candidate keys are different
denominators. The **64 canonical variety records remain unchanged**.
The registry remains 77 entries: 60 with named checks, 14 partial, one unavailable
and two identity holds. None is newly declared globally complete.

## Verification and remaining gates

- Final affected acquisition, dates, heading, refresh, ingestion, candidate and
  university-portfolio regressions: **166 passed**, 99 existing warnings,
  **77.40 seconds**. Final overlapping focused checks: **44 passed**, one
  existing warning, 77.20 seconds. Counts are not added together.
- Record validation and preservation of all **2,771 original data JSON files**
  and the canonical expansion guide passed.
- Static build passed: **1,755 pages**, Pagefind complete, unpublished IDs and
  titles excluded.
- Native candidate review shows the original report and Table 1 links, publication
  and check dates, absent applicant/breeder attribution, and unpressed human
  identity controls. Phone client/scroll width is **375/375 px**, with floating
  alphabetical navigation available while viewing the source context. No real
  identity or source-copy approval was performed.

Private proof files are `article-prose-trial-candidate-desktop.png`,
`article-prose-trial-candidate-phone.png` and `article-prose-trial-table-proof.png`
under ignored `inbox/european-portfolio-followup/`. Initial tests caught two
incorrect new fixture assumptions (synthetic extraction failure and the separate
Norman listing); the assumptions were corrected, not production trust gates.
One later command used a nonexistent test filename and ran no tests; the final
166-test result above is the corrected command's result.

Parent draft [#371](https://github.com/samsonFive/berry-intelligence-os/pull/371)
passes all four checks on `c87d366856866675927ea29e183e5dbfa6e4590c`:
**4,506 passed / 11 skipped / two warnings / 733.78 seconds**, run 37895614737.
This change's pushed-head CI remains a separate gate.

CAT-01/CAT-02/TD-116 remain open: wider original corpus, complete current and
historical portfolios, independently human-qualified real recall, rights/profile
depth and attributed photos, actual human catalog authoring, and integrated
release review. Source-copy authenticity and variety identity remain distinct
human decisions. No merge, deployment or other-berry Landscape rollout.
