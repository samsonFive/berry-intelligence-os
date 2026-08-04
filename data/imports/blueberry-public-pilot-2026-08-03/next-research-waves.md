# Next research waves

Proposed follow-on work, ordered by value per unit of effort. Each wave states what it would add,
what it would cost, and what it would resolve. Nothing here is required for the current package to
be imported.

Waves 1-3 are complete and staged in this package:

- **Wave 1** - foundation: Mountain Blue / Eureka, Fall Creek / SEKOYA, University of Florida /
  FFSP, core geographies and traits.
- **Wave 2** - breadth: United Exports / OZblu, Hortifrut / Berry Blue, Driscoll's, Planasa,
  Costa / BluGenix, Agrovision / Fruitist, IQ Berries / TopFruit, University of Arkansas.
- **Wave 3** - synthesis: proposed signals and priority actions.

---

## Wave 4 - Close the verification backlog

**Effort: low. Value: high. Do this first.**

Purely mechanical retrieval of documents already identified by number or URL.

1. Retrieve the ten patent front pages listed in `coverage-gaps.md` section 3 and stage each as an
   evidence record. This removes all ten `unverified` patent entities and gives their assignee and
   grant-date attributes real support.
2. Resolve the four `unverified` varieties - `variety-arana`, `variety-eterna`,
   `variety-fc11-164`, `variety-twilight` - by finding a registry record, patent or breeder page
   for each, or by withdrawing them.
3. Re-try the sources listed as **Unavailable** in `rejected-or-unusable-sources/README.md`,
   particularly the Hortifrut Atlantic Blue release, the Driscoll's history page and the BluGenix
   variety pages. Three facts currently resting on substitutes would move to primary support.
4. Confirm or discard `brand-sweetest-batch`.

**Resolves:** ten unverified entities, four unverified varieties, three substitute-source
dependencies. **Adds:** roughly 15 evidence records, no new entities.

## Wave 5 - Registry sweep beyond USPTO and CFIA

**Effort: medium. Value: high.**

The strongest finding available from the current package is that registry participation differs
sharply between breeders - the basis of `sig-registry-participation-is-highly-uneven-between-breeders`.
That signal cannot be raised above `proposed` without sweeping the registries that were not
covered.

Registries to sweep, in priority order:

1. **CPVO** (European Union) - would capture Planasa, Advanced Berry Breeding, Atlantic Blue and
   any European filings by Costa or Hortifrut.
2. **IP Australia Plant Varieties Journal**, systematically rather than the two volumes already
   used - would capture the full Mountain Blue and IQ Berries portfolios.
3. **South Africa** - directly relevant to the enforcement pattern in
   `sig-southern-africa-as-licensing-and-enforcement-arena`.
4. **Chile SAG** and **Peru INDECOPI** - the two largest southern-hemisphere export origins.
5. **Mexico DOV** - the gazette PDF that defeated text extraction in Wave 1 should be re-tried with
   a different extraction path.

**Resolves:** whether the registry asymmetry is a filing behaviour or a search artefact - that is,
whether the signal survives. **Adds:** an estimated 40-80 evidence records and 20-40 patent or PBR
entities.

## Wave 6 - Variety backlog

**Effort: medium. Value: medium.**

Stage the varieties listed in `coverage-gaps.md` section 2: the remaining Berry Blue denominations,
the remaining OZblu selections, the Driscoll's Canadian registrations, further Plablue codes, and
the remaining Costa Berry International patents.

This roughly doubles variety coverage. It should follow Wave 5, because a registry sweep will
surface denominations that would otherwise have to be added again afterwards.

**Note on a limit:** Driscoll's registry entries carry denomination and dates but almost no trait
or commercial data. Adding 21 of them increases entity count without increasing analytical value.
Consider staging them as a distinct, clearly-labelled registry cohort rather than mixing them with
varieties that have trait profiles.

## Wave 7 - Independent measurement

**Effort: high. Value: high, and unique.**

The package currently contains **one** independent, method-stating trial: the University of
Arkansas 2024 Clarksville trial
([UA Division of Agriculture](https://www.uaex.uada.edu/farm-ranch/crops-commercial-horticulture/horticulture/ar-fruit-veg-nut-update-blog/posts/2024-blueberry-variety-trial.aspx)).
Everything else measurable comes from owners.

That single trial is what makes
`sig-owner-published-quality-figures-exceed-independent-measurement` possible, and also what makes
it weak: one trial cannot establish a systematic difference.

Targets:

1. Land-grant university extension variety trials - Georgia, Florida, North Carolina, Oregon,
   Michigan, California.
2. Peer-reviewed horticultural literature reporting cultivar comparisons with stated method.
3. Chilean, Peruvian and Spanish public-sector trial reports.

**Resolves:** whether owner-published figures are systematically optimistic. This is the single
highest-value analytical question the package raises and cannot currently answer.

## Wave 8 - Non-English sources

**Effort: high. Value: medium to high, concentrated in specific geographies.**

The entire pilot was conducted in English. Spanish-language trade press covering Chile, Peru,
Mexico and Spain, and Chinese-language coverage of the Yunnan blueberry sector, both carry material
that is absent here. The BluGenix launch was covered in Chinese before it was covered in English.

**Resolves:** the Chile, Peru, Mexico and China gaps in `coverage-gaps.md` section 1.

## Wave 9 - Corporate and ownership records

**Effort: medium. Value: medium.**

Resolves several of the disputed facts directly:

- Michigan LLC filings for Berry Blue, LLC - resolves `fact-berry-blue-ownership-disputed`.
- Corporate registry records for Agrovision - resolves `fact-agrovision-founding-year-conflict`.
- Australian registry records for Mountain Blue - resolves `fact-mbo-history-1`.
- Disclosed shareholdings in the Costa consortium - strengthens
  `sig-financial-owners-taking-positions-in-berry-genetics`.

## Wave 10 - Extend beyond blueberry

**Effort: high. Value: depends entirely on platform direction.**

The repository schema is berry-agnostic; `berry_ids` exists precisely to support this. The pilot
was restricted to blueberry deliberately, to keep scope bounded and to avoid disturbing existing
test fixtures.

Raspberry is the natural next crop: Advanced Berry Breeding, Planasa, Driscoll's and Hortifrut all
operate there, so much of the entity graph is already staged and would only need new varieties,
evidence and relationships hung off it.

**Before starting this wave**, confirm that the feed filter tests in the repository behave as
expected with multi-berry data. `test_feed_filters_combine_with_no_matches` and its siblings were
a specific reason for keeping this pilot single-crop.

---

## Standing monitoring, rather than a wave

Independent of the waves above, four sources warrant recurring checks because they are where
material change appears first:

| Source | Cadence | Why |
|---|---|---|
| [CFIA blueberry PBR index](https://active.inspection.gc.ca/english/plaveg/pbrpov/cropreport/ble.shtml) | Monthly | New denominations appear here before they appear in marketing |
| [Justia - Costa Berry International](https://patents.justia.com/assignee/costa-berry-international-pty-ltd) | Monthly | The active filing front for the BluGenix programme |
| [CIOPORA](https://www.ciopora.org/) | Quarterly | Where enforcement actions are reported |
| [Produce Report](https://www.producereport.com/) and equivalent trade press | Weekly | Launch announcements, which are leads rather than evidence |
