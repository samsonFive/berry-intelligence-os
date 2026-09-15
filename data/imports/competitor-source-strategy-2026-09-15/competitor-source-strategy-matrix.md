# Competitor Source Strategy V1 — 33-row matrix

Verification date: 2026-09-15. Base commit: `4e54401da040be937cc68877f410b4da7b646d65`.
Research/import-planning only — no live Source created, no collection run, no canonical data changed.

| # | Label | Canonical entity | Domain | Best candidate | Adapter | Maturity | Monitoring state | Priority |
|---|---|---|---|---|---|---|---|---|
| 2 | Advanced Berry Breeding | `company-advanced-berry-breeding` | abbreeding.nl | _n/a — already configured_ | existing (see linked Source) | configured_but_untested | source_configured_never_run | wave_1_already_configured |
| 3 | AgroBerries | `company-agroberries` | agroberries.com | https://www.agroberries.com/sitemaps-1-sitemap.xml | sitemap_xml (existing) | candidate_identified | discovery_pending | wave_2_candidate |
| 4 | Australasian Plant Genetics | `company-australasian-plant-genetics` | ausplantgenetics.com.au | https://ausplantgenetics.com.au/sitemap.xml | sitemap_xml (existing) | discovery_mechanism_understood | discovery_pending | wave_2_candidate |
| 5 | BerryWorld | `company-berryworld` | berryworld.com | _n/a — already configured_ | existing (see linked Source) | configured_but_untested | source_configured_never_run | wave_1_already_configured |
| 6 | Black Venture Farm | `company-black-venture-farm` | blackventurefarm.com | https://blackventurefarm.com/ | unknown -- needs a follow-up technical check | candidate_identified | discovery_pending | wave_3_low_confidence |
| 7 | California Giant | `company-california-giant-berry-farms` | calgiant.com | _none_ | — | known_blocked | source_blocked | see_dedicated_assessment |
| 8 | Costa | `company-costa-group-holdings` | costagroup.com.au | _n/a — already configured_ | existing (see linked Source) | configured_but_untested | source_configured_never_run | wave_1_already_configured |
| 9 | Denning Blueberries | `company-denning-blueberries` | _none found_ | _none_ | — | known_blocked | no_supported_source | identity_search_strategy_pending |
| 10 | Expoberries | `company-expoberries` | _none found_ | https://aneberries.mx/en/expoberries/ | none -- not a publishing source | identity_search_strategy_pending | no_supported_source | identity_search_strategy_pending |
| 11 | Fall Creek | `company-fall-creek-farm-and-nursery` | fallcreeknursery.com | _n/a — already configured_ | existing (see linked Source) | configured_but_untested | source_configured_never_run | wave_1_already_configured |
| 12 | Fresh Forward | `company-fresh-forward` | fresh-forward.nl | https://www.fresh-forward.nl/en | unknown -- needs a follow-up technical check (likely sitemap_xml if a sitemap exists) | candidate_identified | discovery_pending | wave_2_candidate |
| 13 | Fruitist | `company-agrovision` | fruitist.com | https://www.fruitist.com/sitemap.xml | sitemap_xml (existing) | discovery_mechanism_understood | discovery_pending | wave_1_candidate |
| 14 | Gem-Pack Berries | `company-gem-pack-berries` | gem-packberries.com | https://www.gem-packberries.com/en/feed | article_rss (existing) | discovery_mechanism_understood | discovery_pending | wave_2_candidate |
| 15 | Hortifrut Genetica | `company-hortifrut` | hortifrut.com | _n/a — already configured_ | existing (see linked Source) | configured_but_untested | source_configured_never_run | wave_1_already_configured |
| 16 | IQ Berries | `company-iq-berries` | _none found_ | https://www.osirisplant.com/en/iq-berries/ | none -- not a publishing source | identity_search_strategy_pending | no_supported_source | identity_search_strategy_pending |
| 17 | Marionnet | `company-marionnet` | _none found_ | _none_ | — | known_blocked | no_supported_source | identity_search_strategy_pending |
| 18 | Mountain Blue | `company-mountain-blue-orchards` | mountainblue.com.au | https://mountainblue.com.au/sitemap.xml | sitemap_xml (existing) | discovery_mechanism_understood | discovery_pending | wave_2_candidate |
| 19 | Oishii | `company-oishii` | oishii.com | https://oishii.com/blogs/press.atom | article_rss (existing -- Atom is already handled by the same generic feed fetch/list) | discovery_mechanism_understood | discovery_pending | wave_1_candidate |
| 20 | Ozblu | `brand-ozblu` | ozblu.com | https://www.ozblu.com/news/feed/ | article_rss (existing) | discovery_mechanism_understood | discovery_pending | wave_1_candidate |
| 21 | Pairwise | `company-pairwise` | pairwise.com | https://www.pairwise.com/insights | unknown -- needs a follow-up technical check | candidate_identified | discovery_pending | wave_3_low_confidence |
| 22 | Perfection Fresh | `company-perfection-fresh` | perfection.com.au | https://www.perfection.com.au/blog/rss.xml | article_rss (existing) | discovery_mechanism_understood | discovery_pending | wave_2_candidate |
| 23 | Planasa | `company-planasa` | planasa.com | _n/a — already configured_ | existing (see linked Source) | configured_but_untested | source_configured_never_run | wave_1_already_configured |
| 24 | Plant Sciences | `company-plant-sciences-genetics` | plantsciencesgenetics.com | https://www.plantsciencesgenetics.com/sitemap.xml | sitemap_xml (existing) | discovery_mechanism_understood | discovery_pending | wave_2_candidate |
| 25 | Royakkers | `company-royakkers` | softfruit.be | https://www.softfruit.be/en/ | unknown -- needs a follow-up technical check | candidate_identified | discovery_pending | wave_3_low_confidence |
| 26 | Smart Berries | `company-smart-berries` | smartberries.com.au | https://www.smartberries.com.au/feed/ | article_rss (existing) | discovery_mechanism_understood | discovery_pending | wave_2_candidate |
| 27 | Splendor Produce | `company-splendor-produce` | _none found_ | _none_ | — | known_blocked | no_supported_source | identity_search_strategy_pending |
| 28 | SunBelle | `company-sunbelle` | sun-belle.com | https://www.sun-belle.com/feed/ | article_rss (existing) | discovery_mechanism_understood | discovery_pending | wave_2_candidate |
| 29 | The Berry Collective | `company-the-berry-collective` | theberrycollective.com.au | https://theberrycollective.com.au/feed/ | article_rss (existing) | identity_search_strategy_pending | discovery_pending | wave_3_low_confidence |
| 30 | UC Davis | `breeding_program-uc-davis-strawberry` | strawberry.ucdavis.edu | https://strawberry.ucdavis.edu/news-and-events-0 | sitemap_xml or article_rss, if access is resolved | known_blocked | source_blocked | wave_2_candidate_pending_access_resolution |
| 31 | University of Arkansas | `company-university-of-arkansas` | aaes.uada.edu | _n/a — already configured_ | existing (see linked Source) | configured_but_untested | source_configured_never_run | wave_1_already_configured |
| 32 | University of Florida | `company-university-of-florida` | blogs.ifas.ufl.edu | _n/a — already configured_ | existing (see linked Source) | configured_but_untested | source_configured_never_run | wave_1_already_configured |
| 33 | Well-Pict | `company-well-pict` | wellpict.com | https://www.wellpict.com/ | unknown, pending a successful connection | candidate_identified | discovery_pending | wave_2_candidate_pending_access_resolution |
| 34 | Wish Farms | `company-wish-farms` | wishfarms.com | https://wishfarms.com/newsroom/feed/ | article_rss (existing) | discovery_mechanism_understood | discovery_pending | wave_1_candidate |

## Unresolved questions (per row, where any exist)

**AgroBerries**
- Search results describe AgroBerries as part of a 'global family of companies including Berry Fresh, BerryWorld, PrepWorld, and Poupart1895' -- BerryWorld is a SEPARATE roster entry (#4) with its own independent canonical entity and Source. This is an inference from marketing copy, not confirmed corporate-structure evidence; flagged for the entity-identity workstream, not resolved or acted on here.
- Feed at /feed/ returned 404 -- site is not WordPress; sitemap is the only discovery path found.

**Australasian Plant Genetics**
- Site is variety-catalog-shaped, not a newsroom -- sitemap discovery may surface mostly static variety pages rather than dated news; cadence is inferred, not observed.

**BerryWorld**
- See AgroBerries entry: found marketing language listing BerryWorld inside an 'AgroBerries family of companies' -- not confirmed, not acted on.

**Black Venture Farm**
- No newsroom/press/blog section identified on the homepage in this pass -- a deeper site-map crawl (out of this mission's bounded scope) would be needed before recommending an adapter.

**California Giant**
- See dedicated assessment document.

**Denning Blueberries**
- No official website, social presence, or trade-press mention was found for an entity matching this exact name in two search passes. May be a smaller/regional operation with no public web presence, a name variant not yet tried, or a misread/abbreviated spreadsheet label.

**Expoberries**
- No dedicated company website found. 'ExpoAgroberries' (expoagroberries.com.mx) is a trade SHOW/event site, not confirmed to be this company's own site -- not treated as the same entity.

**Fresh Forward**
- Discovery mechanism (sitemap vs. RSS vs. none) not yet confirmed -- /feed/ 404'd, no sitemap.xml check completed this mission.

**Fruitist**
- Company rebranded from Agrovision to Fruitist in April 2025 -- canonical entity company-agrovision already carries 'Fruitist' as an alias (Company + Genetics Relationships V1); this mission's own domain finding (fruitist.com replacing agrovisioncorp.com) is consistent with, not a contradiction of, that prior work.

**Gem-Pack Berries**
- Real trade-press coverage ('Gem-Pack and Well-Pict Berries combine companies' -- The Packer) suggests Gem-Pack Berries and Well-Pict (roster entry #33) may now be affiliated or merged. Neither entity's canonical record was modified for this -- flagged as an unresolved question for the entity-identity workstream, not acted on in this mission.

**IQ Berries**
- No independently-owned IQ Berries website was found -- IQ Berries (Brisbane, Australia, breeder Peter Rolfe) appears to publish primarily through its Americas licensing partner Osiris Plant Management and trade press, not its own newsroom.

**Marionnet**
- No official Marionnet/Marionnet Label website was found in two search passes. Company was 'taken over by the Agri Finest Company group' in 2018 per search results -- a parent-company website search was not attempted this mission (would exceed the bounded scope of re-verifying one already-ambiguous name).

**Mountain Blue**
- Site's robots.txt uses the Content-Signal protocol, a newer, distinct mechanism from classic Disallow rules -- this project's collection policy has not yet made an explicit decision on how to interpret Content-Signal ai-input/ai-train values (not fully captured in this pass) for a source it would use in an AI-assisted intelligence pipeline. Recommend a deliberate policy read before onboarding, not a code change in this mission.

**Ozblu**
- Confirms the existing Company + Genetics Relationships V1 finding that brand-ozblu is a multi-party entity (United Exports owns the brand, Nature Select develops genetics, Oz Varieties licenses) -- this source would monitor the brand's own news, not resolve which party issued a given announcement; that attribution stays a human/analyst judgment at review time.

**Pairwise**
- Pairwise's public work is broader ag-biotech (CRISPR platform across multiple crops), not confirmed berry-specific in this pass -- berry relevance for this roster entry should be re-confirmed by whoever activates this source, not assumed from the company's general profile.

**Planasa**
- See Company + Genetics Relationships V1's own flagged pre-existing possible identity duplication (company-planasa / company-planasa-2 / company-plantas-de-navarra) -- not investigated further in this source-strategy mission; out of scope.

**Plant Sciences**
- Company recently restructured into a new entity, Plant Sciences Genetics, Inc., consolidating several prior berry-breeding affiliates (Berry Genetics, Strawberry Sciences, Via Berry Breeding, Vitae Caneberry Breeding, Fragaria Plant Sciences) -- the existing canonical entity company-plant-sciences-genetics already carries this exact alias, so this finding corroborates rather than contradicts the prior mission's reconciliation.

**Royakkers**
- Spreadsheet lists Royakkers under regions DOA_DANZ/DEMEA; search results place the company in Kinrooi, Belgium, not the Netherlands the company's own surname might suggest -- a geographic detail worth a human's attention, not corrected here (this mission does not modify regions).

**Splendor Produce**
- No official company website was found in two search passes despite the company being real and described in a Mexican government trade article (450ha blackberries, 200ha raspberries, ~80% exported to the US). 'California Splendor, Inc.' (calsplendor.com) appeared in results but is a distinct entity (strawberries/blackberries, different profile) -- NOT treated as the same company.

**SunBelle**
- Three related domains found (sun-belle.com, sunbelleberries.com, sunbelle.info) -- sun-belle.com's own confirmed-live feed is proposed as the single candidate; the other two are noted, not separately proposed, to avoid duplicate-content risk (see the duplicate-risk assessment).

**The Berry Collective**
- Multiple, clearly distinct organizations share this exact name: a US/NYC wellness-and-community brand (theberrycollective.co), an events platform, a classical-music ensemble, and this Australian 'berry supply & fruit retailer' partnership (theberrycollective.com.au). The Australian one is the best fit for a berry-industry roster, but the spreadsheet's own Competitor Type for this row is 'University/Public,' which does not obviously match a growers-to-retailers supply partnership -- this mismatch is flagged, not resolved. Do not onboard this source until a human confirms which real-world organization the spreadsheet row actually means.

**UC Davis**
- Whether the 403 is specific to the strawberry.ucdavis.edu subdomain, this project's exact User-Agent string, or a broader ucdavis.edu WAF policy was not determined -- would need the same kind of A/B (curl vs. httpx) diagnostic this project has already applied to California Giant, which was out of this mission's time-bounded scope to repeat for every blocked candidate.

**Well-Pict**
- Connection to wellpict.com failed outright (not a 403/blocked response) during this mission's verification -- could be a transient network condition in this research environment, a DNS/hosting issue, or a genuine access restriction; not distinguishable without a retry from elsewhere.
- See Gem-Pack Berries entry: trade press reports Gem-Pack and Well-Pict Berries 'combining companies' -- a possible merger/affiliation between two separate roster entries, not investigated or acted on further (entity-identity scope, not this mission's).

