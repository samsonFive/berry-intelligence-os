# Search Frontier priority sources v1

The first set is drawn from sources used in the blackberry season comparison, plus official registries and scholarly discovery. Cadences are proposals. This inventory records inspection and acquisition options without scheduling collection or granting publication rights.

| Host or path | Language and coverage | Source type | Acquisition lane and proposed cadence | Current evidence |
| --- | --- | --- | --- | --- |
| rubus.ces.ncsu.edu | English, Southeast US, caneberries | Breeder and extension | Original HTML, weekly | Registered host. Ervin introduction inspected. |
| www.globalplantgenetics.com | English, global, multiple berries | Licensee and variety catalog | Original HTML, weekly | Registered host. Ervin international license inspected. |
| smallfruits.org | English, Southeast US, multiple berries | Extension consortium and trials | Original HTML and linked trial PDFs, monthly | Immaculate breeder update inspected. |
| content.ces.ncsu.edu | English, Southeast US, multiple berries | Extension cultivar guides | Original HTML and tables, quarterly | Regional caneberry guide inspected. |
| www.hutton.ac.uk | English, UK and Europe, multiple berries | Breeder and trials | Original HTML, monthly | Registered host. Loch Katrine breeder page inspected. |
| www.berryplant.com | Italian and English, Europe, caneberries | Propagator catalog | Original HTML, monthly | Loch Katrine fruiting habit inspected. |
| extension.oregonstate.edu | English, Pacific Northwest, multiple berries | Extension cultivar guides | Original HTML and PDF, quarterly | Oregon cultivar guide inspected. |
| www.pairwise.com | English, US, blackberry | Breeder announcement | Original HTML, weekly | Registered host. Fontana precision control inspected. |
| scholarworks.uark.edu | English, US, multiple berries | Patent and scholarly repository | Original record and PDF, monthly | Immaculate patent grant inspected. |
| www.agromillora.com | English and Spanish, multiple markets and berries | Nursery catalog | Original HTML, monthly | US listing inspected. Stock is unverified. |
| seregionalconference.org | English, Southeast US, multiple berries | Conference trial literature | Original poster PDF, annual | Mills River NC 740 poster inspected. |
| cpvo.europa.eu and online.plantvarieties.eu | Multilingual, European rights and wider register leads | Official register | Public structured register where permitted, monthly | Existing integration. Status requires authority-specific verification. |
| www.ams.usda.gov/services/plant-variety-protection | English, US, multiple berries | Official variety protection | Published application-status spreadsheet, monthly | Structured export available. Patent grants are a separate lane. |
| api.crossref.org | Multilingual, global, multiple berries | Scholarly metadata | Existing public API, on demand | Discovery metadata. Acquire licensed originals or open copies separately. |
| www.ebi.ac.uk/europepmc | Multilingual, global, multiple berries | Scholarly metadata and open copies | Existing public API, on demand | Verify version and license for each retained copy. |
| www.juntadeandalucia.es/agriculturaypesca/ifapa/servifapa | Spanish, Huelva, strawberry | Official trials and crop reports | Original HTML and linked PDFs, monthly | [2024–25 production systems trial](https://www.juntadeandalucia.es/agriculturaypesca/ifapa/servifapa/registro-servifapa/18a1e98a-e6c8-4a4d-b4fe-32382556972e) is useful background for heat-tolerance queries. Verify measured heat exposure before using it as direct evidence. |
| www.berryneo.com/variedades-berryum/ | Spanish, Spain, blackberry | Commercial variety catalog | Original HTML, monthly | [BerrYum portfolio](https://www.berryneo.com/variedades-berryum/) distinguishes floricane and primocane varieties. Availability requires separate dated evidence. |
| www.plusberries.com/nuestra-fruta/ | Spanish, Spain, multiple berries | Commercial grower | Original HTML, monthly | [Grower portfolio](https://www.plusberries.com/nuestra-fruta/) provides production context. Use named variety sources for fruiting habit. |
| www.ars.usda.gov/research/project/ | English, US, multiple berries | Research project reports | Original accomplishment reports, annually | The [2025 Aurora, Oregon trial](https://www.ars.usda.gov/research/project/?accnNo=444118&fy=2025) reports mechanical harvest of advanced blackberry selections and distinguishes fresh from processing quality. |
| oregon-berries.com | English, Pacific Northwest, caneberries | Commission-funded original research | Research books and individual reports, annually | The [2023–24 book](https://oregon-berries.com/wp-content/uploads/2024/04/2023-24-ORBC-Research-Reports-Book.pdf) contains a Columbia Star machine-harvest trial for processing at OSU-NWREC. Preserve the individual report and page boundaries when indexing the book. |
| www.invenio-fl.fr/framboise/ | French, France, raspberry | Applied horticultural trials | Original trial pages and linked reports, quarterly | [Trial index](https://www.invenio-fl.fr/framboise/experimentation-framboise/materiel-vegetal-framboise?start=9) is a discovery lead. Confirm cultivar, system and location in each original report. |
| adida19.odoo.com | French, Corrèze, raspberry | Original applied trial reports | Inspect stable publisher document links, quarterly | The [2016 Objat report](https://adida19.odoo.com/web/content/466?download=true&unique=1684540123b8cfd44fedb8af848b300723490c54) compares four remontant cultivars under shelter T7. It does not specify the shelter geometry. |

Each new candidate should record the original URL, market, language, evidence type, capture status, and whether it yielded a new identity, event or supported claim. Reconcile host aliases and publisher redirects before counting gaps. Rank sources by the incremental verified evidence they contribute beyond the existing lanes.

Run `python scripts/audit_source_execution.py --season-pilot` for a read-only inventory against the current source registry, published Evidence and local research cache. In the [November 9 snapshot](../../artifacts/search-research-quality/frontier-source-coverage-2026-11-09.json), four of thirteen cited references matched a configured host, eight had cached body captures and zero matched a published Evidence URL. The counts describe exact host or canonical URL matches within this worktree.

The [post-review snapshot](../../artifacts/search-research-quality/frontier-source-coverage-after-review-2026-11-09.json) finds four configured-host matches, nine cached captures, and seven published Evidence URL matches among the same thirteen references. The Evidence matches cover the seven separately reviewed source records. These are branch-local counts. Configured hosts measure collector coverage separately from publications reviewed through the pilot.

Use the catalog, discovery and trust stages independently. A site can be registered without the relevant page being acquired. A captured page can support a comparison as an attributed observation without being approved as a canonical trait or rights record. Search-provider links are discovery leads and do not confer republication rights.

## Provider comparison

Maintain the priority list as versioned publisher paths and original-document acquisition rules. For each provider, measure which distinct events it adds after original capture and deduplication, which questions it leaves unanswered, and the cost and time per supported event. Include a direct-publisher lane and a general-web lane so an unlisted publisher can still surface. Start with publisher content that can be retained under its access and reuse terms. Record links and attributed observations where full-text retention is unavailable.

Google's [Custom Search JSON API documentation](https://developers.google.com/custom-search/v1/overview) says the API is closed to new customers and points to Vertex AI Search for search across up to 50 domains. Keep the manual organic benchmark separate from that prospective curated service. Compare the curated service against direct publisher acquisition on the same independently graded questions before adopting it.

For France, inspect the actual station report and record its protected structure and trial site before grading a tunnel-specific result. For Spain, separate the BerrYum cultivar cards from independent evidence of local trials or commercial production. For Peru, the [INIA Huaral adaptation trial](https://repositorio.inia.gob.pe/items/8fe44ca5-0c8f-451e-beb1-11e55336027b) is a discovery lead. The public record was access-limited in this environment and mechanical harvest remains unverified.
