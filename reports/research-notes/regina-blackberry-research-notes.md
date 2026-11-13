# Regina Blackberry — Supporting Research Notes

Research dates: 12–13 November 2026.

## Standard format and platform library · 13 November 2026

The approved descriptive profile is the reusable example for `reports/templates/variety-commercial-profile.md` and its shared stylesheet. `scripts/render_variety_report.py` produces self-contained HTML and a locally authored PDF; downloads do not run a generator or research provider. The explicit `reports/library.json` catalog connects Regina to the existing private Reports area at `/reports/library/regina-blackberry`, with the finished PDF at `/reports/library/regina-blackberry/download.pdf`. Only the allowlisted HTML/PDF pair is served; these notes and the other working assets remain outside the report routes. No variety, breeder, company, patent, evidence, or production record was created or modified by this integration.

## Report purpose and research navigation · 13 November 2026

The executive report is a descriptive variety and commercial profile for review and further investigation. It does not recommend monitoring, investment, licensing, or field evaluation. The prior decision gates, numerical thresholds, functional leads, review deadline, and archive/reopen instructions have been removed. The closing table organizes unanswered questions and the records or data relevant to resolving them.

The report expands Black Venture Farm (BVF) and names Frutura at first use, uses positive statements, and labels the consolidated table “Evidence position.” Tupy is explicitly a Brazilian agronomic reference; no Mexican adoption claim depends on the Embrapa description. The exact-name CPVO result is included with its query date and scope caveat; it is not an assertion of worldwide absence of protection.

All citation clusters resolve to individual external source links, with comma separators. The research index supplies source scope and reading locations. The downloaded Frutura report has 48 physical pages; physical PDF page 12 contains printed pp. 24–25 and the October 2024 Giddings entry statement. Its link uses `#page=12`. The Aketzali certificate opens on page 1. The source profile entries use consistent publication-based titles; abbreviated personal names are not expanded beyond the available source.

## Editorial and factual update · 13 November 2026

The executive report distinguishes production geography from destination markets, consolidates unknowns, and compares Regina with Aketzali, Tupy, Black Sultana, and Sweet Karoline. Its purpose is to describe the available information, without a performance ranking or proposed decision.

Corporate context was corrected using dated coverage: BVF was Giddings’ wholly owned subsidiary when acquisition agreements were announced in October 2023; Frutura’s company report records Giddings joining in October 2024; December 2024 coverage identifies BVF as wholly owned by Sun Belle Mexico and describes the group’s berry consolidation under Sun Belle. The corporate platform is established; this does not confirm Regina-specific programs, rights, destinations, or exclusivity.

The USDA Aketzali document was checked as an issued certificate, dated 4 June 2021. Planasa’s Mexican Black Sultana catalog attributes its numerical measurements to Cartaya, Spain; those figures were omitted from the comparison. Berry Fresh identifies Sweet Karoline production in Jalisco, but its sweetness numbers are marketing claims and were also omitted. February 2015 is the date of the Traveler announcement, not the release year.

Additional sources accessed 13 November 2026:

- [FreshPlaza, acquisition agreements and BVF/Giddings, 17 October 2023](https://www.freshplaza.com/north-america/article/9568700/it-s-a-dream-come-true/).
- [FreshPlaza, Sun Belle consolidation and BVF ownership, 11 December 2024](https://www.freshplaza.com/north-america/article/9686892/berries-are-set-to-be-an-outsized-growth-story-we-re-highly-committed-to/).
- [Frutura 2024 Sustainability Report, pp. 24–25](https://www.daykahackett.com/wp-content/uploads/2025/11/Frutura_2024SustainabilityReport.pdf).
- [Planasa Mexico, Black Sultana / Plablack 15157](https://planasa.com/mx/variedad/black-sultana/).
- [Berry Fresh, Sweet Karoline](https://berryfresh.com/sweet-karoline-blackberry/).

Registry detail, source assessment, and repository integration supporting the executive report.

## Evidence interpretation

| Label | Meaning in this report |
|---|---|
| **Verified fact** | Directly inspected authoritative record or directly attributable publication. A verified publication proves that the publisher made the statement; promotional performance claims remain claims. |
| **Corroborated finding** | Consistent evidence across distinct items supports the conclusion, with source dependence disclosed. Several posts by one business do not constitute independent trial validation. |
| **Provisional information** | Plausible but dependent on indirect retrieval, a single promotional assertion, incomplete identity, or missing supporting records. |
| **Unresolved question** | Adequate evidence was not recovered. This is not proof of absence. |
| **Analyst assessment** | Explicit interpretation or recommended action, conditional on the evidence stated. |

The strongest verified findings concern records and attribution. Confidence in Regina’s commercial identity is greater than confidence in its legal identity, and substantially greater than confidence in its agronomic or economic advantage.

## Raspberry identity and excluded matches

These records establish a different crop identity and must remain separate from the blackberry research subject:

| Record | What it actually establishes | Implication |
|---|---|---|
| German HMB 207 Regina, grant notice | Bundessortenamt lists Regina under **Himbeere** (raspberry); grant date 19 December 2014. | The crop is not blackberry. [2015 gazette, printed p. 13][S08]. |
| German 2016 inventory and address directory | Regina HMB 207 is under raspberry; address identifier 9121 resolves to **Ilario Ioriatti c/o Berryplant**. | Provides a primary documentary bridge for the Ioriatti/Berryplant raspberry attribution. [Inventory, printed pp. 48 and 68][S23]. |
| German HMB 207 termination notice | Protection ended 29 May 2019 under the raspberry heading. | This concerns that German protection record; it does not establish commercial discontinuation or a prohibition on sale. [2019 gazette, printed p. 118][S09]. |
| CPVO application 2011/1395, grant 39542 | Live exact-name result: *Rubus idaeus L.*, breeder reference `vr01`, grant date 23 February 2015; the returned applicant is Berrytech S.r.l. | This is the raspberry identity. Current raw status fields are reproduced in section 3. [CPVO API][S07]. |
| USPP30850P3, ‘BP 1522’ | The patent identifies raspberry Regina, CPVO 39542, as its female parent. | The patent is for the offspring **BP 1522**, not a patent for Regina blackberry. [Patent text][S10]. |
| agronom.cc “Regina — Blackberry” | Associates its entry with Ioriatti/Berryplant and HMB 00207. | **Rejected as blackberry identity/performance evidence** because its crop mapping conflicts with the primary registry. [Secondary entry][S11]. |

The secondary page’s red-fruit measurements, height, thorn, yield, transportability, and disease statements are not usable descriptors of the BVF blackberry. A genus-level *Rubus* heading cannot resolve raspberry versus blackberry.

Other checked false positives include ProSpecieRara’s Regina, explicitly a **strawberry** (*Fragaria × ananassa*), and a Puebla tender that separately requests **raspberry Regina** and **blackberry Tupy**. Neither establishes blackberry Regina cultivation. [ProSpecieRara record][S19]; [Puebla tender][S20].

## Registry lookup and adjacent rights

The repository’s existing `app.services.cpvo_registry.search_cpvo_register` function was invoked read-only with `denomination='Regina'` and `search_type='equals'` on 12 November 2026. It returned eight exact-name records and no blackberry record. The only Rubus result contained:

| API field | Returned value |
|---|---|
| `denomination` | `Regina` |
| `speciesName` / `specieUpovId` | `Rubus idaeus L.` / `RUBUS_IDA` |
| `applicationNumber` / `grantNumber` | `20111395` / `39542` |
| `breedersReference` | `vr01` |
| `applicants` | `Berrytech S.r.l.` |
| `applicationDate` / `grantingDate` | `2011-05-30` / `2015-02-23` |
| `applicationStatus` / `titleStatus` | `T` / `approved` |
| `expirationDate` | `31/10/2023` |

Source: [exact reproducible CPVO API query][S07]. The returned approval field must not be used alone to infer an active right; the status and expiration fields must remain visible. Older lists projecting a 2040 end date are not a substitute for this later result. These fields concern raspberry only.

### Useful adjacent rights evidence

USDA’s official dossier for **Aketzali**, certificate **202000246**, records a BVF blackberry grant dated 4 June 2021 and experimental designation `2000-182`. USDA’s 14 November 2025 issued-certificate list separately names **PBBlack1852-15**, application **202300462**, under Black Venture Farm, S.A. de C.V. These establish concrete BVF rights-search leads, **not Regina synonyms or parentage**. [Aketzali certificate][S12]; [2025 USDA issuance list][S13].

The next useful IP step is a document showing Regina’s commercial name beside its legal denomination or selection code. Without it, searching and comparing coded BVF filings risks attaching the wrong genotype to the report.

## Repository integration

The local repository is a file-backed FastAPI/Jinja intelligence application. Its versioned JSON graph separates entities, evidence, facts, relationships, signals, and assessments; private intake and report state reside in `inbox/`. Findings below describe the inspected checkout, not production or every local worktree. Architecture references: [technical architecture](../../docs/04-technical-architecture/ARCHITECTURE.md), [variety backbone](../../docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md), and [repository instructions](../../AGENTS.md).

| Resource investigated | Existing path / capability | Reuse for Regina |
|---|---|---|
| Variety and breeder/program records | `data/entities/varieties/`, `data/entities/breeding_programs/`, `data/entities/traits/`; `app/services/variety_workspace.py`, `variety_footprint.py` | Resolve the actual variety before attaching traits or rights. No Regina blackberry entity was identified in this checkout. |
| Company profiles | `data/entities/companies/company-black-venture-farm.json`, `company-sunbelle.json` | Reuse these IDs for later reviewed evidence. BVF is currently `unverified`; SunBelle’s stored berry scope is strawberry only. Neither should be silently upgraded by this report. |
| Patent and registration infrastructure | `data/entities/patents/`, `app/services/patent_monitor/`, `app/services/cpvo_registry.py` | Existing CPVO search was reused read-only. After identity resolution, use existing matching/intake and verify species and jurisdiction. |
| News and research collection | `app/services/media_discovery.py`, `collection_runner.py`, `scripts/run_collection.py`, `scripts/discover_media.py`, `scripts/run_recent_batch.py` | Existing source discovery and review pipelines can retain future publications; no collection schedule or source configuration was changed. |
| External research integrations | `app/services/research_desk.py`, `app/services/industry_pulse/providers.py`, `app/services/feed_first_live.py`, `app/services/ai_gateway/`; `.env.example` | Google News RSS discovery and optional Perplexity, Exa, APITube, and NewsCatcher CatchAll paths already exist; CatchAll is kept off the request-time Today path. Acquisition options include Firecrawl and Jina. Code/configuration does not prove credentials or live availability. No paid provider or model was activated for this report. |
| Existing relevant evidence | `data/evidence/ev-20260806181239-d0d4-sun-belle-and-giddings-mexico-sign-berry.json` and acquisition-related Frutura/Sun Belle/Giddings news | Reused as context and search leads. The cited record is a short 2020 news-search summary mentioning Aketzali, with no entity links; it does not mention or establish Regina. |
| Report generation/storage | `app/services/report_builder/packet.py`, `synthesis.py`, `reports_store.py`, `pdf_export.py`; Research Desk handoff | Native saved reports use private `inbox/reports/`. The requested durable Markdown is stored here in `reports/`; it is not automatically a native app report or publicly rendered intelligence record. |

**Recommended entity/evidence connections, after review:**

1. Retain this report as the research asset. Capture each original source separately through existing intake; preserve publication date uncertainty, retrieval form, crop, geography, claim scope, and source independence.
2. Use `company-black-venture-farm`, `company-sunbelle`, `berry-blackberry`, and the existing Mexico geography where appropriate. Resolve Frutura, Giddings, and any breeder/program identity against the actual target runtime before proposing new entities.
3. Establish one blackberry variety entity with authenticated aliases. Keep raspberry Regina / CPVO 39542 separate. Do not attach PBBlack1852-15 or Aketzali as aliases without a documentary bridge.
4. Preserve role distinctions: `develops`, `owns`, `licenses`, and `markets` represent different assertions. Offer a Regina-specific relationship only when the source supports that role; a social assertion of ownership is not a verified title.
5. Attach a patent/PVR entity only after the identity match. Trait claims should retain their own evidence, conditions, and claimant. A social field post belongs in attributed publication evidence; it should not be encoded as a retailer observation or a quantified yield fact.

The repository requires human publication and Atomic Evidence review. This mission therefore saves research and proposes connections without inserting trusted JSON, changing production datasets, adding features, or deploying. No application defect or new platform feature was required to complete the report.

## Research scope and access

Research combined local entity/evidence inspection, an actual read-only call through Berry OS’s existing CPVO client, official registry and patent documents, breeder/university publications, company communications, and targeted public web searches. Searches covered English, Spanish, German, and Portuguese combinations of Regina with blackberry, zarzamora, Brombeere, amora, BVF, Black Venture Farm, Sun Belle, Rubus, patent, and registry terms.

The CPVO exact-name result is a reproducible bounded negative for blackberry, not an exhaustive international registry audit. UPOV PLUTO/Variety Finder account-based coverage and a complete current SNICS register search were not achieved. BVF’s standalone website was not retrievable through the available web fetcher; no technical sheet was recovered from it. Some primary social assertions were accessible only as indexed/reproduced profile activity. That limitation is retained in the confidence labels.

LinkedIn relative labels varied by cached rendering. The image follow-up retrieved the original BVF publication HTML and its `VideoObject` metadata, establishing `datePublished: 2026-04-29T13:47:59.457Z` for S01. Other exact dates were not inferred from relative labels or activity identifiers. Access on 12 November 2026 establishes retrieval, not first commercial use. German registry page references were checked through official extracted text; page-image verification was not completed. Multiple reproductions of the same post count as one assertion. General platform capability, corporate acreage, and category-wide supply must not be mistaken for Regina-specific evidence.

## Image sources

All four original images were visually inspected. The revised executive report uses only a cropped field-video image; the retail and comparison-variety images remain in these supporting files. The HTML embeds the field image and retains its clickable link to the original video.

| Local asset | Source and attribution | Image treatment / scope |
|---|---|---|
| [BVF Tocumbo field](../assets/regina/bvf-tocumbo-field.jpg) | Black Venture Farm, S01, clean `thumbnailUrl` from the publication's VideoObject metadata | Original video-cover JPEG, 1280 × 720. Publication discusses Regina and Aketzali; the individual frame does not identify which cultivar is shown. |
| [Cropped field image](../assets/regina/bvf-tocumbo-field-cropped.jpg) | Derived from the preceding BVF image | Crop rectangle `(365, 85, 1280, 590)`, removing the inset person; resulting image 915 × 505. No generative editing. Cultivar attribution remains unchanged. |
| [Sun Belle retail pack](../assets/regina/sunbelle-retail.jpg) | King Kullen product listing, S24 | Retail image converted to JPEG, 500 × 500. Label says Mexico, 170 g; no cultivar is named. |
| [Aketzali fruit](../assets/regina/aketzali-pvp-fruit.png) | USDA dossier 202000246, S12, PDF page 17 | Rendered page cropped to the fruit photograph and its Aketzali label. Comparison cultivar only. |
| [Ponca patent figure](../assets/regina/ponca-patent-figure2.png) | USPP33330P2, S25, PDF page 6 / drawing sheet 2 | Rendered page cropped to Figure 2. Original monochrome photograph and scale retained. Comparison cultivar only. |

No patent or retail image was identified as Regina blackberry. Aketzali's PVP dossier is a variety-protection filing, distinct from the Ponca plant patent. No alteration of fruit appearance was performed.

The BVF source image URL is `https://media.licdn.com/dms/image/v2/D4E05AQF2rGrROupV2w/videocover-high/B4EZ3UrPQqIoBM-/0/1777389601863?e=2147483647&v=beta&t=b9bGh47LJeaV6L3lkmAlIc0i5MPsTw8fCJpguw_E8JU`. The retail image URL is `https://storage.googleapis.com/images-kkg-prd-dbdfdde.kkg.prd.v8.commerce.mi9cloud.com/product-images/detail/00761635202602_1`.

## Full source register

The original sources below were accessed or queried on **12 November 2026**; the additional 13 November sources are listed above. “Undated” means no reliable exact publication date was established. Patent and certificate dates describe document events, not current legal clearance.

| ID | Source / date | Authority and precise use |
|---|---|---|
| **S01** | [Black Venture Farm: Tocumbo field publication][S01]; 29 April 2026 | Direct company publication. Date recovered from original VideoObject metadata during image research. Named varieties and location; productivity/quality and organic descriptions remain publisher claims. |
| **S02** | [Karina M. activity reproducing BVF plant offer][S02]; undated | Company-origin offer retrieved indirectly. Supports Regina’s presence in a solicitation, not stock or license terms. |
| **S03** | [Daniel Partida activity reproducing Daniel C.’s Regina post][S03]; undated | Indirect retrieval. Explicit blackberry/floricane/BVF attribution; original technical documentation absent. |
| **S04** | [Mauricio Grajeda activity reproducing Daniel Herrera Magaña’s post][S04]; undated | Indirect promotional evidence for Sun Belle association and qualitative fruit claims. |
| **S05** | [Frutura: Companies][S05]; undated | Parent company’s primary account of BVF and Sun Belle roles and locations. |
| **S06** | [Black Venture Farm company profile][S06]; undated | Company self-description of breeding, propagation, geography, and nursery scale. |
| **S07** | [CPVO public register API, exact Regina query][S07]; live query | Authoritative structured record, obtained through existing Berry OS client. Eight exact-name results; raspberry row and raw status fields reproduced above. |
| **S08** | [Bundessortenamt, Blatt für Sortenwesen 2015/1][S08], 15 January 2015; printed p. 13 | Primary German grant notice for raspberry HMB 207 Regina. |
| **S09** | [Bundessortenamt, Blatt für Sortenwesen 2019/6][S09], 15 June 2019; printed p. 118 | Primary German protection termination notice; crop heading and effective date. |
| **S10** | [USPP30850P3, Rubus plant ‘BP 1522’][S10], 27 August 2019 | Primary patent text hosted by Google Patents; explicitly identifies Regina raspberry / CPVO 39542 as parent. |
| **S11** | [agronom.cc, Regina under blackberry][S11]; page description dated 10 August 2026 | Secondary source audited and rejected for blackberry identity/traits because of its registry mismatch. |
| **S12** | [USDA PVP dossier 202000246, Aketzali][S12], grant 4 June 2021; certificate and Exhibit C | Primary certificate and applicant descriptors. Concrete comparator identity and BVF rights lead. |
| **S13** | [USDA: 25 certificates issued 14 November 2025][S13], p. 1 | Primary issuance list; PBBlack1852-15/BVF, not a Regina alias match. |
| **S15** | [Embrapa: Cultivo de amoreira-preta, Tupy section][S15], December 2007; printed p. 36 | Public breeding institution’s historical cultivar description. Regional plant, size, soluble-solids, and harvest benchmarks; not a current acreage estimate. |
| **S16** | [University of Arkansas: Ponca release][S16], 20 December 2019 | Breeder’s primary release, despite the date-like URL slug; fruit/plant characteristics and consumer-panel account. |
| **S17** | [University of Arkansas: Prime-Ark Traveler announcement][S17], February 2015 | Breeder’s announcement, not a release-year assertion. Fruiting habit, fruit size, shipping claims, and Arkansas heat limitation. |
| **S18** | [Sun Belle: Blackberries][S18]; undated | Marketer’s primary product page names Aketzali from Mexico; provides portfolio context only. |
| **S19** | [ProSpecieRara Regina BR-22037][S19]; undated | Germplasm conservation catalog explicitly identifies strawberry; false-positive exclusion. |
| **S20** | [Puebla procurement specifications GESAL-086-439/2020][S20], September 2020; item 14 versus item 15 | Government primary document separates raspberry Regina from blackberry Tupy; procurement intent only. |
| **S21** | [University of Arkansas MP574, What is wrong with my blackberry?][S21] | Extension context for fresh-market disorders and handling; no Regina-specific results. |
| **S22** | [FreshFruitPortal: Sun Belle proprietary blackberry volumes][S22], 3 May 2023 | Industry report attributing commercial information to Sun Belle. Historical comparator supply context, not Regina’s season. |
| **S23** | [Bundessortenamt 2016 inventory][S23]; printed pp. 48 and 68 | Primary raspberry inventory and address directory linking HMB 207 and Ioriatti/Berryplant. |
| **S24** | [King Kullen: Sun Belle blackberries, 6 oz][S24] | Retail listing and packaging image. Variety unspecified; no Regina retail inference. |
| **S25** | [USPP33330P2: Ponca][S25], 10 August 2021 | Comparison-variety patent; Figure 2 reproduced with cultivar-specific caption. |

[S01]: https://es.linkedin.com/posts/black-venture-farm_bvf-gen%C3%A9ticabvf-campoorg%C3%A1nico-activity-7455251541965369344-d7fd
[S02]: https://mx.linkedin.com/in/karina-m-018730219
[S03]: https://mx.linkedin.com/in/daniel-partida-baa7261aa
[S04]: https://mx.linkedin.com/in/mauricio-grajeda-0ba2a0200
[S05]: https://www.fruturaproduce.com/companies/
[S06]: https://www.linkedin.com/company/black-venture-farm
[S07]: https://online.plantvarieties.eu/api/publicSearch/v3/publicSearch?denomination=Regina&denominationSearchType=equals
[S08]: https://www.bundessortenamt.de/bsa/media/Files/BlfS/BlfS_2015_01.pdf
[S09]: https://www.bundessortenamt.de/bsa/media/Files/BlfS/BlfS_2019_06.pdf
[S10]: https://patents.google.com/patent/USPP30850P3/en
[S11]: https://agronom.cc/en/sorta/rubus/regina
[S12]: https://apps.ams.usda.gov/CMS/AdobeImages/202000246.pdf
[S13]: https://www.ams.usda.gov/sites/default/files/media/11-14-2025-25Issued%20Certificates.pdf
[S15]: https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/745965/1/Cultivo-de-amoreira-preta-2007-CPACT.pdf
[S16]: https://uaex.uada.edu/media-resources/news/2019/december2019/12-09-2019_Division_releases_Ponca_blackberry-FM.aspx
[S17]: https://www.uaex.uada.edu/media-resources/news/2015/february2015/02-25-2015-Ark-Thornless-Blackberry.aspx
[S18]: https://www.sunbelle.info/blackberries/13
[S19]: https://www.prospecierara.ch/fr/vegetaux/catalogue-des-varietes/BR-22037
[S20]: https://licitaciones.puebla.gob.mx/images/BasesEstatales2020/Septiembre/GESAL-086-439-2020-ALTO-VALOR-RURAL.pdf
[S21]: https://www.uaex.uada.edu/publications/pdf/MP574.pdf
[S22]: https://www.freshfruitportal.com/news/2023/05/03/sun-belle-expecting-good-volumes-of-proprietary-blackberries/
[S23]: https://www.bundessortenamt.de/bsa/media/Files/BlfS/BlfS_Sonderheft/BlfS_Sonderheft_2016.pdf
[S24]: https://www.shopkingkullen.com/product/sunbelle-blackberries-6-oz-id-00761635202602
[S25]: https://patents.google.com/patent/USPP33330P2/en
