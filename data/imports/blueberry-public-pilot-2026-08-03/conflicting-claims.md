# Conflicting claims

Every case where two sources disagree, or where one source disagrees with itself, and the
disagreement was **not** resolved by the evidence available in this pilot. None of these is
silently reconciled. Each is staged as a `fact` record with `status: "disputed"`, and each
disputed record states both positions and names the sources.

The platform rule applied throughout: where sources conflict and no arbitrating record was
retrieved, the conflict itself is the finding. A single number is not picked.

There are **10 disputed facts** in the package.

---

## 1. Berry Blue, LLC ownership

**Record:** `fact-berry-blue-ownership-disputed`

Hortifrut describes Berry Blue, LLC as a joint venture between Hortifrut and Michigan Blueberry
Growers ([Hortifrut Genetic Development](https://www.hortifrut.com/innovation/genetic-development/)).
Michigan Blueberry Growers describes the Berry Blue programme as one MBG owns and operates
([MBG Berry Blue varieties](https://www.blueberries.com/proprietary-berry-varieties-berry-blue-llc/)).

No ownership instrument, corporate filing or registry record reconciling the two descriptions was
retrieved. Both parties are describing the same entity, and both are self-interested descriptions
of it. This matters because Hortifrut's blueberry IP position depends on which reading is correct.

**To resolve:** a Michigan LLC filing, or the JV agreement, or a third-party record naming the
members and their interests.

## 2. Agrovision founding year

**Record:** `fact-agrovision-founding-year-conflict`

Agrovision's own February 2024 release states the company was established in 2013 and marks a tenth
anniversary ([PR Newswire](https://www.prnewswire.com/news-releases/agrovision-celebrates-10-years-of-bringing-the-world-a-better-berry-302052244.html)).
AgFunderNews gives 2012 ([AgFunderNews](https://agfundernews.com/in-progress-agrovision-rebrands-as-fruitist-notched-up-sales-of-400m-in-2024-after-meteoric-growth)).

No incorporation record was retrieved. A one-year difference is minor in itself; it is recorded
because the company's own arithmetic (2013 plus ten years) does not reach February 2024 either.

**To resolve:** a corporate registry filing.

## 3. Costa Variety Improvement Program age

**Record:** `fact-costa-vip-age-conflict`

Costa's own pages describe the Variety Improvement Program as operating for more than 25 years
([Costa VIP](https://costagroup.com.au/our-categories/berries-international/variety-improvement-program/)).
Trade coverage of the BluGenix launch describes the programme as drawing on close to 40 years of
plant breeding expertise ([Produce Report](https://www.producereport.com/article/costa-launches-blugenix-5-blueberry-varieties-suited-yunnan)).

No founding date or founding document was retrieved. The two figures may describe different things
- the formal programme versus the breeder's personal career - but no source says so.

**To resolve:** a stated founding year for the programme.

## 4. Blue Manila soluble solids

**Record:** `fact-blue-manila-brix-conflict`

Planasa's variety page states 14 degrees Brix
([Planasa Blue Manila](https://planasa.com/variety/blueberry-bluemanila/)); Planasa's own technical
data sheet for the same selection 'Plablue 1545' states 13
([Planasa data sheet](https://planasa.com/wp-content/uploads/data-sheet/bl-1545_en.pdf)).

Neither document states season, replication or measurement method, and the data sheet carries a
NOT CONTRACTUAL marking. This is a single owner disagreeing with itself about its own variety, and
is the clearest illustration in the package of why owner-published trait figures are recorded as
claims with provenance rather than as measurements.

**To resolve:** an independent, method-stating trial of Blue Manila.

## 5. SEKOYA platform membership count

**Record:** `fact-fall-creek-commercial-platforms-2026-3`

Fall Creek states the SEKOYA platform has 14 members; Produce Report states 15 for the same
platform. The SEKOYA members page does not publish a roster, so neither figure can be checked.

**To resolve:** a published member list, or a dated statement from Fall Creek.

## 6. Eureka Sunrise listed twice in one export table

**Record:** `fact-italianberry-peru-varieties-2025-3`

The same Proarandanos table of 2024/25 Peruvian export volumes lists Eureka Sunrise under two
different codes - 'Ridley 160' at 714 tonnes and 'Ridley 1602' at 183 tonnes
([Italian Berry](https://italianberry.it/en/news/Peru-Sekoya-Pop-dominates-ranking-most-exported-varieties-2024-25-season)).

The two entries are **not** summed anywhere in this package. 'Ridley 160' may be a truncation of
'Ridley 1602', or a distinct selection. Summing them would manufacture an 897-tonne figure that no
source states.

**To resolve:** confirmation from Proarandanos or the exporter that the two codes refer to one
cultivar.

## 7. Mountain Blue founding year

**Record:** `fact-mbo-history-1`

Mountain Blue publishes 1975 on its history page and 1978 on its home page - two different founding
years for the same business on the same website. No independent record resolving it was retrieved.

**To resolve:** an Australian corporate registry record.

## 8. Optimus measured trait values

**Record:** `fact-uf-breeding-optimus-3`

The University of Florida breeding programme reports 241 g/mm firmness, 1.7 g berry weight, 15.8 mm
diameter and 12.3 degrees Brix. Florida Foundation Seed Producers, the licensing body for the same
cultivar, reports 220 g/mm, 1.9 g, 16.5 mm and 11.3 degrees Brix.

Neither source states the seasons or sites underlying its figures. Both are institutional sources
for the same variety, which makes this the most instructive conflict in the package: even
programme-published measurements are not comparable without stated method.

**To resolve:** the underlying trial data, or a statement of seasons and sites for each figure set.

## 9. Patrecia patent inventors versus programme breeders

**Record:** `fact-uf-breeding-patrecia-3`

The inventors named on US PP27,740 for Patrecia - David E. Norden and Alto Straughn - do not match
the University of Florida breeders credited in UF/IFAS extension literature for the programme's
releases. No retrieved source explains the discrepancy.

This is left unresolved rather than assumed to be a co-development or an assignment, because the
brief forbids inferring the relationship from the pattern.

**To resolve:** the assignment history, or a UF statement on the cultivar's origin.

## 10. Sentinel machine-harvest suitability

**Record:** `fact-uf-breeding-sentinel-4`

The University of Florida breeding programme page for Sentinel records machine-harvest performance
as "no data yet". UF/IFAS extension publication HS1245 describes the cultivar as suitable for
machine harvest. Both are University of Florida publications.

**To resolve:** the trial data behind HS1245, or a dated correction from either source.

---

## Near-conflicts recorded but not staged as disputed

Two further tensions were found but are **not** staged as disputed facts, because in each case one
side is a demonstrable error rather than a competing view:

- **US PP25,358 versus US PP28,358 for OZblu Bonita 'EB 9-12'.** PP25,358 is an Aglaonema
  ornamental patent ([PP25358](https://patents.google.com/patent/USPP25358P3/en)); the Bonita
  patent is PP28,358 ([PP28358](https://patents.google.com/patent/USPP28358P3/en)). This is
  corrected in the data, and `patent-uspp025358p3` is staged with `status: "historical"`, an empty
  `berry_ids`, and an attribute recording the mis-citation so the error is traceable rather than
  erased.
- **Michigan Blueberry Growers versus Mountain Blue Orchards, both abbreviated "MB".** Hortifrut's
  Berry Blue joint venture is with Michigan Blueberry Growers; the 30 July 2026 transaction is with
  Mountain Blue Orchards. These are different companies on different continents and are staged as
  separate entities.

Both corrections are also the basis of the proposed signal
`sig-breeder-and-patent-attribution-drift-in-public-sources`.
