# Executive dataset summary

**Package:** `blueberry-public-pilot-2026-08-03`
**Scope:** global blueberry genetics, varieties, rights and the organizations around them
**Time range:** 2020-2026, plus older records where they anchor identity (patent grants back to 2001)
**Status:** validated, dry-run clean, trial-imported successfully, **not yet imported** into the
working repository

---

## What this is

A staged, additive set of structured records built from public sources only, conforming to the
four schemas in the running repository. It is designed to be reviewed, imported, and then approved
as a separate human step.

| Record type | Count |
|---|---|
| Entities | 155 |
| Evidence | 121 |
| Facts | 186 |
| Relationships | 204 |
| Strategic questions | 8 |
| Signals (not importable) | 6 |
| **Importable files** | **674** |
| Distinct source URLs | 121 |

Entities break down as 40 varieties, 38 patents, 32 companies, 16 geographies, 10 traits, 9
breeding programmes, 8 brands, 1 retailer and 1 berry.

Evidence quality: **92 tier-1** primary sources (patent front pages, plant breeders' rights
registries, court records, company primary documents), 27 tier-2, 2 tier-3. Facts split 132 `fact`
to 54 `claim`; 106 high confidence, 63 medium, 17 low; 10 disputed.

## The seven findings that matter most

**1. A widely repeated patent number for a commercial variety is wrong.** OZblu Bonita 'EB 9-12' is
US PP28,358. US PP25,358, which circulates in its place, is an Aglaonema ornamental patent
([PP25,358](https://patents.google.com/patent/USPP25358P3/en) versus
[PP28,358](https://patents.google.com/patent/USPP28358P3/en)). The mis-cited number is preserved in
the data as a historical record so the error stays traceable.

**2. Owner-published fruit quality figures cannot be compared to each other.** Planasa publishes 14
degrees Brix for Blue Manila on its [variety page](https://planasa.com/variety/blueberry-bluemanila/)
and 13 on its own [technical data sheet](https://planasa.com/wp-content/uploads/data-sheet/bl-1545_en.pdf)
for the same selection. Neither states season, method or replication. The only independent trial in
the package, the [University of Arkansas 2024 Clarksville trial](https://www.uaex.uada.edu/farm-ranch/crops-commercial-horticulture/horticulture/ar-fruit-veg-nut-update-blog/posts/2024-blueberry-variety-trial.aspx),
measured 8 to 13.2 degrees Brix across 20 varieties with a stated harvest window. Every owner
figure in this package is therefore classified as a claim with provenance, never as a measurement.

**3. Financial capital is moving through berry genetics.** Hortifrut's
[2023 integrated report](https://investor.hortifrut.com/wp-content/uploads/2024/07/MEMORIA-INTEGRADA-HF-2023_ENGLISH.pdf)
records PSP Investments with SJF at 49.56 per cent. Costa was taken private in February 2024 by
Paine Schwartz Partners, **Driscoll's** and BCI
([Costa](https://costagroup.com.au/2024/02/26/costa-group-enters-new-ownership-phase-as-experienced-consortium-takes-control/)),
and re-registered from Limited to Pty Ltd on 3 June 2024
([ABN Lookup](https://abr.business.gov.au/AbnHistory/View/68151363129)). Cinven agreed to sell
Planasa to the EW Group
([Cinven](https://www.cinven.com/news-insights/cinven-and-label-investments-to-sell-planasa-to-ew-group/)).
A direct genetics competitor sitting inside the consortium that acquired Costa is the notable
detail.

**4. Southern Africa is where variety rights are actually contested.** United Exports terminated two
South African licences in 2020 and obtained a Dutch Customs alert at Rotterdam against roughly 26
tonnes of OZblu fruit ([CIOPORA](https://www.ciopora.org/post/united-exports-group-enforces-its-pbr-in-blueberries-south-african-grower-in-breach-of-contract)),
settled on 17 November 2020 ([Harvest SA](https://www.harvestsa.co.za/2020/11/18/rossouw-farming-group-concedes-united-exports-rights-over-ozblu-varieties/)).
Costa's African Blue is extending into Zimbabwe ([Costa](https://costagroup.com.au/2023/04/03/african-blue-broadens-supply/)),
and TopFruit manages IQ Berries genetics for the region
([TopFruit](https://www.topfruit.co.za/fruit/megacrisp/)).

**5. Breeders differ sharply in how visible they are.** The
[Canadian PBR blueberry register](https://active.inspection.gc.ca/english/plaveg/pbrpov/cropreport/ble.shtml)
carries 21 Driscoll's denominations, plus Fall Creek, Berry Blue, Michigan State, USDA and New
Zealand entries - and, as retrieved, no blueberry variety held by Costa, Planasa, Hortifrut or
Advanced Berry Breeding. Costa's filings appear instead in the United States, jointly with Florida
Foundation Seed Producers ([Justia](https://patents.justia.com/assignee/costa-berry-international-pty-ltd)).
Any competitive picture built from registries alone will systematically under-represent the second
group.

**6. Four attribution errors were found in circulating sources.** Beyond the Bonita patent number:
the OZblu breeder of record is Vincent David Mazzardis, not the breeder usually associated with
Australian blueberry genetics; Advanced Berry Breeding lists
[raspberry cultivars only](https://www.abbreeding.nl/varieties/) and is not a blueberry breeder;
and Michigan Blueberry Growers is routinely confused with Mountain Blue Orchards, two different
companies on two continents that Hortifrut deals with separately.

**7. Breeding programmes are being sold as branded platforms.** Costa launched BluGenix on 29 May
2026 with five varieties at once
([Produce Report](https://www.producereport.com/article/costa-launches-blugenix-5-blueberry-varieties-suited-yunnan)).
Fall Creek runs the closed SEKOYA member platform. United Exports sells 'EB' and 'NS' selections
under one OZblu brand. If the commercial unit is shifting from cultivar to platform membership,
variety-level tracking alone will under-describe the market.

## What the package deliberately does not claim

- **Ten disputed facts are staged as disputed, not resolved.** Where two sources conflict and no
  arbitrating record was found, both positions are recorded. No number was chosen for plausibility.
  See `conflicting-claims.md`.
- **Six signals are `proposed`, none `confirmed`.** Each states what would confirm it and what
  would falsify it. They are excluded from import because the repository has no signal schema.
- **Ten patent entities carry `status: "unverified"`** with an attribute saying that no evidence
  record captures the patent document, so their assignee and grant-date attributes are unsupported
  within the package. Four varieties are likewise unverified.
- **Geographic coverage is uneven and is recorded as uneven.** The United States, Australia, South
  Africa, Peru and Spain are well covered; Chile, Mexico, Morocco, China and Canada are thin;
  Argentina, Brazil, Egypt, Poland and others are absent. The cause is registry availability,
  language and corporate disclosure, not market importance. See `coverage-gaps.md`.
- **No royalty rates, licence terms, planted hectares or propagation volumes.** These are not
  published. Nothing was inferred to fill the space.
- **No company is treated as the reader's employer.** Every organization is an ordinary market
  entity under the same evidence and classification rules.

## Scope against the brief

| Target | Brief | Package | Note |
|---|---|---|---|
| Varieties | 25-40 | 40 | at the top of range |
| Strategic questions | 5-8 | 8 | at the top of range |
| Proposed signals | 3-6 | 6 | at the top of range, none confirmed |
| Priority actions | 10-20 | 16 | in `priority-actions.md` |
| Organizations | 8-12 | 32 companies, of which 21 are market participants | over; rationale in `qa-report.md` 6.1 |
| Evidence records | 50-80 | 121 | over; every opened source became a record |
| Atomic facts | 75-150 | 186 | over; consequence of the atomicity rule |
| Monitored sources | 20-30 | 4 proposed for standing monitoring; 121 distinct URLs consulted | see `qa-report.md` 6.4 |

The four overshoots are each a consequence of following another instruction in the brief. A trimmed
variant can be produced on request, but it would mean deleting sourced records to hit a number.

## Validation status

`validate_package.py` **PASSED** - schema, id conventions and referential integrity all clean.
176 warnings, all advisory: 172 are notices that a `roles[]` value sits outside a proposed
vocabulary the schema does not enforce, and 4 are false positives from a regex that checks whether
a claim names its claimant.

A trial import into a scratch copy of the repository wrote all 674 files, after which the
repository's own `validate_records.py` reported `All validated records passed`, `pytest` reported
`28 passed`, and 23 application routes returned HTTP 200.

## To proceed

```bash
python data/imports/blueberry-public-pilot-2026-08-03/scripts/validate_package.py
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --dry-run
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --apply
# review the staged evidence in the application, then:
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --approve
```

Evidence lands as `in_review` and is invisible in the feed until `--approve` is run.
`--rollback` removes exactly the files this package wrote. Full sequence and expected output in
`import-order.md`.
