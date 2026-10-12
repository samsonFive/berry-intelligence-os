# University of Florida cultivar photo references

Eight existing blueberry profiles now have a source-labeled photograph to inspect:
Colossus, Emerald, Farthing, Jewel, Meadowlark, Optimus, Patrecia and Sentinel.
Each reference retains the original profile link, publisher credit and a visible
permission status. It uses the existing photo gallery and approved session-only
**Ignore permission** control. No canonical variety, alias, role, region, trait,
right or human review decision was created.

Review branch: `feature/uf-cultivar-photo-references`, stacked on draft #378.

## Original sources and limits

| Existing cultivar | Original source | Visible photograph |
|---|---|---|
| Colossus | [UF profile](https://www.blueberrybreeding.com/colossus) | Fruit cluster |
| Emerald | [UF profile](https://www.blueberrybreeding.com/emerald) | Fruit |
| Farthing | [UF profile](https://www.blueberrybreeding.com/farthing) | Fruit |
| Jewel | [UF profile](https://www.blueberrybreeding.com/jewel) | Fruit |
| Meadowlark | [UF profile](https://www.blueberrybreeding.com/meadowlark-fl01-173) | Fruit |
| Optimus | [UF profile](https://www.blueberrybreeding.com/optimus) | Fruit-bearing plant |
| Patrecia | [UF profile](https://www.blueberrybreeding.com/patrecia) | Fruit-bearing plant |
| Sentinel | [UF profile](https://www.blueberrybreeding.com/sentinel) | Fruit |

All eight original pages and photographs were inspected in the native browser.
URLs were copied unchanged from the source image elements. The supplied assets
are small: 199 by 179 pixels, or 199 by 180 for Farthing and Jewel. No higher
resolution URL was guessed, and no remote image was downloaded or committed.
The publisher is credited; the photographer is not identified by these sources.

Image-specific reuse permission remains unknown for every new reference.
Cultivar or nursery licensing does not establish permission to reuse photographs.
Images stay held by default and excluded from the public static gallery. A
session reveal does not approve reuse or publish the photo. Source headings
provide a reviewable association, not independent cultivar identification.

Each source observation covers one focal name and its photograph. Comparison
names elsewhere on the page are outside this bounded scope; the observations do
not claim complete page or portfolio enumeration. Printed selection codes remain
separate source context, without automatic alias or ownership decisions.

## Browser and automated verification

On the actual Colossus and Patrecia profiles, the default card showed permission
unconfirmed with no loaded image. The approved session reveal loaded each source
image at 199 by 179 pixels. **Hide photo** restored the held card. Patrecia's
session preview survived a reload while still showing permission unconfirmed;
this is session persistence, not reusable-image approval. No identity, source,
claim or permission forms were submitted.

The committed [held-card screenshot](../../artifacts/uf-cultivar-photo-review-2026-10-09/held-patrecia-profile.png)
contains no loaded source photograph. Loaded-image review screenshots remain in
ignored local runtime storage. The body-free
[verification record](../../artifacts/uf-cultivar-photo-review-2026-10-09/verification.json)
records the source associations, limits and checks.

**92 targeted tests passed**, one existing ReportLab warning, 106.05 seconds.
Record validation and the **1,755-page static build with Pagefind** pass. Static
output contains none of the eight held asset identifiers, private pending-source
IDs or fictional profile-field test content. All original 2,771 canonical JSON
files, the expansion guide and pending source-copy hashes remain unchanged.

The targeted suite covers photo permission boundaries, portfolio accounting and
catalog handoffs. It does not prove independently reviewed name recall, current
rights, complete portfolios or global catalog completeness. Parent draft #378
passes all four required checks on `188c4ded47e0e95cedfec948f7778253965119e5`:
**4,553 passed / 11 skipped / two warnings / 775.79 seconds**. This new draft
requires its own checks.

## Current coverage and remaining work

The bounded portfolio audit now has **363 source sections, 1,140 name occurrences,
72 catalog-matched occurrences and 1,068 occurrences requiring review**. There
are still 788 public derived candidate keys and 789 in the actual isolated
preview; the canonical catalog remains 64 varieties. Occurrences are not unique
or approved varieties. Photo references increased from 114 to **122**, with zero
new reuse approvals.

The 77-entry company source plan still has 60 named checks, 14 incomplete checks,
one unavailable source and two identity holds. There are 107 source follow-ups.
The 32 captured source copies remain pending; the separate human expected-name
packet is unfinished and has no recall score or approvals.

CAT-01, CAT-02 and TD-116 remain open for complete current/historical portfolios,
source corpus, cited profiles, current rights, photos, independent human recall
and canonical authoring. Revised blueberry feedback still gates the remaining
Landscape rollout. No merge or deployment is included.
