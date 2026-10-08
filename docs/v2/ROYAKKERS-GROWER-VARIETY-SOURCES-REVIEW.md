# Royakkers: named grower varieties and unresolved nursery coverage

Royakkers' original strawberry page explicitly lists **Elsanta and Portola as
varieties it grows**. Both names already exist in the candidate queue. This packet
adds Royakkers provenance to those entries, preserving their IDs and prior sources.
It creates no duplicate candidates, trusted varieties or company relationships.

## Sources and remaining gaps

Ten source sections were read in the native browser. The English strawberry page
contains two explicit names. The other nine sections remain partial: unnamed fruit
and nursery ranges, an unnamed research program, and two English nursery paths
that showed homepage content. No HTTP redirect or response-status assertion is
made for those two attempted paths. The linked Dutch nursery details were also
read; they describe plant preparation, advice and follow-up without cultivar names.

| Original source | Captured result |
| --- | --- |
| [English strawberry fruit](https://www.softfruit.be/en/products/fruit/strawberries/) | Elsanta and Portola; explicitly a grower listing |
| [English raspberry fruit](https://www.softfruit.be/en/products/fruit/raspberries/) | No cultivar names captured |
| [Attempted English raspberry nursery](https://www.softfruit.be/en/products/plants/frambozen/) | Homepage content shown; nursery detail not captured |
| [English plant index](https://www.softfruit.be/en/products/plants/) | No cultivar assortment named |
| [Royakkers Explore](https://www.softfruit.be/en/royakkers-explore/) | Research department; no named selections or releases |
| [English blackberry fruit](https://www.softfruit.be/en/products/fruit/blackberries/) | No cultivar names captured |
| [Attempted English blackberry nursery](https://www.softfruit.be/en/products/plants/braambessen/) | Homepage content shown; nursery detail not captured |
| [Dutch plant index](https://www.softfruit.be/producten/planten/) | Nursery detail links checked; no cultivar names |
| [Dutch raspberry nursery](https://www.softfruit.be/producten/planten/frambozenplanten/) | Nursery detail read; no named varieties |
| [Dutch blackberry nursery](https://www.softfruit.be/producten/planten/bramenplanten/) | Nursery detail read; no named varieties |

All checks are dated October 8, 2026. No publication date was printed or inferred
from company age, harvest duration or footer text. Original capture hashes remain
attached to the additive observations; full page captures remain private in `inbox/`.

## Boundaries

Growing a variety does not establish that Royakkers bred it, owns it, licenses it,
or supplies its plants. The research-department name is not a cultivar. No aliases,
legal status, historic release dates, trial traits or growing footprints are approved.
The source's strawberry identity takes precedence over older registry crop tags for
this source observation; those canonical company tags are not rewritten.

Generic fruit and nursery images have no named-variety captions. They are excluded,
rather than assigned to Elsanta or Portola. Human identity review, catalog authoring
and source/statement review remain separate. Public output never exposes this queue.

## Measured result and validation

The body-free audit now reports 292 source sections, 1,013 name occurrences,
62 catalog text matches and 951 review needs. It derives 719 candidate keys:
63 stored-source keys plus 656 additional primary-source keys, unchanged by this
packet. The 64 mixed-status catalog records also remain unchanged. Berry occurrence
counts are Blueberry 255, Strawberry 478, Raspberry 189 and Blackberry 91.
58/77 registry entries have some bounded names checked; 19 still need an initial
enumeration, and 74 source sections need follow-up. These are not global completeness
or independently measured recall scores.

38 affected tests pass, including four new tests for grower/crop boundaries,
unnamed/multilingual gaps, unchanged candidate IDs and human edits, and private
company-scoped review without writes. One existing ReportLab deprecation warning
remains. Native desktop review shows both shared candidates and the original grower
context. A 390px phone check has no horizontal overflow; the captured phone view
shows the expanded candidate and navigation, not every source reference below it.
No review form was submitted. All 2,771 original JSON records and the canonical
expansion guide are preserved.

Parent draft #359 passes all four checks, with 4,370 Python tests. This packet
requires its own checks before release. CAT-01/CAT-02/TD-116 remain open for whole
portfolios, independent recall, profiles, historical/current rights and user review.
No merge, deployment or later-berry Landscape rollout; the blueberry gate remains.

CI verification: draft #360 head `a198ea70a7fec4c88254f9bd267dd8988100cdcd`
passes Change scope, Repository integrity, Static public safety and Python tests.
Actions run 37837269202: 4,374 passed, 11 skipped, two warnings, 668.14 seconds.
Full catalog completeness and human review/release gates remain open.
