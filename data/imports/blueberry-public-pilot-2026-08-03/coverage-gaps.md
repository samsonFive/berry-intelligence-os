# Coverage gaps

What this package does **not** cover, and why. Gaps are recorded explicitly rather than smoothed
over, because the brief forbids forcing balanced representation where public evidence does not
support it. A gap here is a statement about the public record and about this pilot's search
effort - not a statement that the underlying thing does not exist.

Gaps are grouped by kind. Items marked **backlog** were found and sourced during research but were
deliberately not staged as records; their URLs are carried here so nothing sourced is lost.

---

## 1. Geographic coverage is uneven, and deliberately so

16 geographies are staged: Australia, Canada, Chile, China, Colombia, Germany, Mexico, Morocco,
Netherlands, Peru, Portugal, South Africa, Spain, United States, Zambia, Zimbabwe.

The distribution of evidence across them is heavily skewed:

| Well covered | Thinly covered | Absent |
|---|---|---|
| United States, Australia, South Africa, Peru, Spain | Chile, Mexico, Morocco, China, Canada, Portugal, Zimbabwe | Argentina, Brazil, Egypt, India, Poland, Ukraine, Serbia, Romania, Georgia, Turkey, Japan, Korea |

Reasons for the skew, in order of weight:

1. **Registry availability.** The United States (USPTO plant patents), Canada (CFIA PBR) and
   Australia (IP Australia Plant Varieties Journal) publish searchable, free, English-language
   variety records. CPVO, Chile's SAG, Peru's INDECOPI, Mexico's DOV and South Africa's registry
   were not systematically swept in this pilot.
2. **Language.** The research was conducted in English. Spanish- and Chinese-language trade press
   carries material that is not represented here. One Chinese-language Business Wire variant was
   found and not used.
3. **Corporate disclosure.** Listed or recently listed companies (Hortifrut, formerly Costa)
   publish more than privately held ones (Fall Creek, United Exports, Planasa, Driscoll's).

**Zambia** deserves specific mention: it enters the package on a single self-reported, undated
country list on United Exports' own website
([United Exports](https://united-exports.com/what-we-do/)). The relationship
`rel-united-exports-operates-in-zambia` carries `confidence=low` and says so.

**Not a gap in the data - a gap in the world's record:** no source retrieved gives blueberry
variety-level planted area for any country. Peruvian export tonnage by variety is the only
variety-level volume data in the package, and it comes from one trade article reporting a
Proarandanos table.

## 2. Varieties deliberately not staged (backlog)

The brief set a target of 25-40 varieties. The package stages **40**, at the top of that range.
Reaching 40 required cutting sourced material. The following were found, sourced, and left out.
They are the first candidates for Wave 4, not discoveries to be re-made.

| Not staged | Where the evidence already is | Why cut |
|---|---|---|
| ~14 further Berry Blue LLC denominations | [MBG Berry Blue varieties](https://www.blueberries.com/proprietary-berry-varieties-berry-blue-llc/) | Would have consumed the whole variety budget on one programme |
| 7 further OZblu 'EB'/'NS' selections | [OZblu varieties](https://united-exports.com/) and the corresponding USPTO front pages | 8 of 15 staged; the remainder are the same shape of record |
| Further Driscoll's 'DrisBlue' denominations beyond the 3 staged | [CFIA blueberry PBR index](https://active.inspection.gc.ca/english/plaveg/pbrpov/cropreport/ble.shtml) - 21 Driscoll's denominations are registered | Registry entries carry denomination and dates but almost no trait or commercial data |
| Further Planasa 'Plablue' codes | [Planasa variety pages](https://planasa.com/) | The Planasa variety index returned cookie boilerplate; only Blue Manila and Blue Maldiva were retrievable |
| Costa selection codes behind the 5 BluGenix names | [Produce Report BluGenix launch](https://www.producereport.com/article/costa-launches-blugenix-5-blueberry-varieties-suited-yunnan) | No source retrieved maps BluGenix marketing names to breeder selection codes. Staging a code-to-name link would require exactly the inference the brief forbids |
| The 4 remaining Costa Berry International / FFSP joint patents | [Justia - Costa Berry International](https://patents.justia.com/assignee/costa-berry-international-pty-ltd) | 3 of 7 staged; the remainder need individual front-page retrieval |

## 3. Entities with attributes that are not evidence-backed

Ten patent entities carry `status: "unverified"` and an explicit `verification_status` attribute
saying so. In each case the patent number was encountered during research, but **no evidence record
in this package captures the patent document itself**, so the assignee and grant-date attributes on
those entities are unsupported within the package.

Three are patents cited only as *parents* on another patent's front page, which is how they are
known at all:

- `patent-uspp025859p3` - cited on the OZblu 'EB 12-19' front page
- `patent-uspp028334p3` - cited on the 'NS 15-13' and 'NS 16-2' front pages
- `patent-uspp028357p3` - cited on the 'NS 16-2' front page

Seven are Wave 1 patents whose front pages were not staged as evidence:

- `patent-uspp033802p3` (Colossus), `patent-uspp019341p2` (Farthing), `patent-uspp032028p3`
  (Optimus), `patent-uspp031793p3` (SEKOYA Crunch), `patent-uspp033896p2` (Sentinel),
  `patent-uspp021553p2` (Meadowlark), `patent-uspp012165p2` (Emerald)

Retrieving these ten front pages is a bounded, mechanical task and is the cheapest quality
improvement available to the next wave.

Four varieties also carry `status: "unverified"`: `variety-arana`, `variety-eterna`,
`variety-fc11-164` and `variety-twilight`. In each case the name appears in a source but no
registry record, patent or breeder page confirming it as a distinct cultivar was retrieved. The
BerryWorld page for Twilight returns "Page not found".

## 4. Entity drafted and withdrawn

`brand-sweetest-batch` (a Driscoll's premium consumer tier) was drafted during Wave 2 and removed
before staging: no source opened in this pilot names it. It is listed here so the omission is
deliberate and visible rather than an oversight. Confirming or discarding it requires a Driscoll's
brand page.

## 5. Facts that rest on a substitute source

Three material facts rest on something other than the preferred primary because the primary could
not be retrieved. Full detail is in `rejected-or-unusable-sources/README.md`.

- Atlantic Blue acquisition value and date - rests on Leaders League, not the Hortifrut release.
- Driscoll's founding year - rests on secondary sources, not the company history page.
- BluGenix per-variety trait figures - rest on a trade launch article, not breeder variety pages.

## 6. Whole categories not attempted in this pilot

| Category | Status | Note |
|---|---|---|
| Royalty rates and licence terms | **Absent** | Commercially confidential; no public source found. The brief's prohibition on private data applies |
| Planted hectares by variety | **Absent** | Not published by any breeder retrieved |
| Nursery propagation volumes | **Absent** | Not published |
| Retailer-level variety listings | **Almost absent** | One retailer entity is staged. Retail listings are transient and were judged low value per unit of effort |
| Consumer preference or sensory panel data | **Almost absent** | Only the International Taste Institute awards referenced in Wave 1, which are awards rather than published panel data |
| Rabbiteye and northern highbush programmes | **Thin** | The package skews to southern highbush and evergreen types because that is where the commercial and IP activity in the sources sits |
| Non-blueberry berries | **Out of scope by design** | Scope was restricted to blueberry to keep the pilot bounded and to avoid disturbing existing repository test fixtures |
| Financial performance of breeders | **Thin** | Only Hortifrut's integrated report and the reported Fruitist 2024 sales figure |

## 7. Time coverage

The package targets the most recent five complete years plus the current year, with older
foundational records where they anchor identity (patent grants back to 2001 for Emerald).

Uneven within that window:

- **2020 and 2024-2026** are well covered - the OZblu enforcement action, the Costa privatisation,
  the Fruitist rebrand, the BluGenix launch and the Hortifrut/Mountain Blue transaction all fall in
  those years.
- **2021-2023** are thin. The Atlantic Blue acquisition (2021) and the African Blue expansion
  (2023) are nearly the only records.

59 of 121 evidence records have **no published date**, because the underlying page does not carry
one. These are mostly company variety pages and registry records. `captured_date` is always set;
`published_date` is never invented. The full list is in `scripts/_stats.json` under
`evidence_without_published_date`.
