"""One-time generation script for Competitor Source Strategy V1.

Not part of the app runtime. Research-only mission -- writes NO live Source
records, NO Evidence, NO canonical entity/relationship changes. Everything
this script produces lands under data/imports/competitor-source-strategy-2026-09-15/
(a noncanonical import-proposal artifact, exactly like the prior
competitor-registry-2026-09-15 import) and artifacts/competitor-source-strategy-v1/.

Run once from the worktree root:
    ../berry-intelligence-os/.venv/Scripts/python.exe scripts/_gen_competitor_source_strategy_v1.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_DATE = "2026-09-15"
IMPORT_DIR = ROOT / "data" / "imports" / "competitor-source-strategy-2026-09-15"
RECONCILIATION_PATH = ROOT / "data" / "imports" / "competitor-registry-2026-09-15" / "reconciliation-matrix.json"

MATURITY_STATES = (
    "candidate_identified", "discovery_mechanism_understood", "compatible_with_existing_adapter",
    "requires_new_adapter", "configured_but_untested", "known_runnable", "known_blocked",
    "manual_monitoring_required", "unsupported", "identity_search_strategy_pending",
)
MONITORING_STATES = (
    "linked_to_runnable_source", "source_configured_never_run", "source_blocked",
    "discovery_pending", "no_supported_source", "manual_monitoring_required",
)


def source(
    *, source_type, url, region_language="unspecified", berry_relevance="unspecified",
    discovery_mechanism, adapter_compatibility, maturity, robots_access_observation,
    cadence_expectation, confidence, evidence_urls, verification_date=VERIFICATION_DATE,
):
    assert maturity in MATURITY_STATES, maturity
    return {
        "source_type": source_type,
        "url": url,
        "region_language_scope": region_language,
        "berry_relevance": berry_relevance,
        "proposed_discovery_mechanism": discovery_mechanism,
        "existing_adapter_compatibility": adapter_compatibility,
        "maturity": maturity,
        "robots_access_observation": robots_access_observation,
        "expected_publication_cadence": cadence_expectation,
        "confidence": confidence,
        "evidence_urls": evidence_urls,
        "verification_date": verification_date,
    }


def entry(
    label, *, official_domain, aliases_search_terms, candidate_sources,
    recommended_monitoring_state, manual_fallback, unresolved_questions,
    proposed_priority,
):
    assert recommended_monitoring_state in MONITORING_STATES, (label, recommended_monitoring_state)
    return {
        "spreadsheet_label": label,
        "official_domain": official_domain,
        "aliases_search_terms": aliases_search_terms,
        "candidate_sources": candidate_sources,
        "recommended_initial_monitoring_state": recommended_monitoring_state,
        "manual_fallback": manual_fallback,
        "unresolved_questions": unresolved_questions,
        "proposed_priority_for_implementation": proposed_priority,
    }


# ---------------------------------------------------------------------------
# 33 entries. `candidate_sources` is empty for the 8 already-configured
# roster entries -- those already have a real, cited Source record (see the
# reconciliation matrix's `linked_monitoring_sources`); this mission does
# not re-propose them as new candidates, only carries their state forward
# and recommends them for the first activation wave (they need zero new
# research, only an operator running collection).
# ---------------------------------------------------------------------------
ENTRIES = {
    "Advanced Berry Breeding": entry(
        "Advanced Berry Breeding", official_domain="abbreeding.nl",
        aliases_search_terms=["ABB", "Advanced Berry Breeding B.V."],
        candidate_sources=[],
        recommended_monitoring_state="source_configured_never_run",
        manual_fallback="n/a -- existing Source source-20260825-advanced-berry-breeding-news covers this",
        unresolved_questions=[],
        proposed_priority="wave_1_already_configured",
    ),
    "AgroBerries": entry(
        "AgroBerries", official_domain="agroberries.com",
        aliases_search_terms=["Agroberries Group", "Agroberries Peru S.A.C.", "Berry Fresh (North American brand)"],
        candidate_sources=[
            source(
                source_type="official_website_sitemap", url="https://www.agroberries.com/sitemaps-1-sitemap.xml",
                region_language="Chile/Peru/Mexico/US/Morocco, English/Spanish", berry_relevance="blueberry, raspberry, blackberry, strawberry",
                discovery_mechanism="sitemap_xml adapter against the declared sitemap", adapter_compatibility="sitemap_xml (existing)",
                maturity="candidate_identified", robots_access_observation="robots.txt 200, permissive (only excludes /cpresources/, /vendor/, /.env, /cache/); sitemap declared in robots.txt",
                cadence_expectation="inference: corporate press-release cadence, likely low-frequency (few per month)",
                confidence="medium", evidence_urls=[
                    "https://www.agroberries.com/about", "https://www.freshfruitportal.com/news/2026/06/24/agroberries-expansion/",
                ],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="Trade-press query (FreshFruitPortal, Blueberries Consulting) already surfaces real AgroBerries news; usable as a manual/analyst check pending sitemap onboarding.",
        unresolved_questions=[
            "Search results describe AgroBerries as part of a 'global family of companies including Berry Fresh, BerryWorld, PrepWorld, and Poupart1895' -- BerryWorld is a SEPARATE roster entry (#4) with its own independent canonical entity and Source. This is an inference from marketing copy, not confirmed corporate-structure evidence; flagged for the entity-identity workstream, not resolved or acted on here.",
            "Feed at /feed/ returned 404 -- site is not WordPress; sitemap is the only discovery path found.",
        ],
        proposed_priority="wave_2_candidate",
    ),
    "Australasian Plant Genetics": entry(
        "Australasian Plant Genetics", official_domain="ausplantgenetics.com.au",
        aliases_search_terms=["APG", "Australian Strawberry Breeding Program commercialisation partner"],
        candidate_sources=[
            source(
                source_type="official_website_sitemap", url="https://ausplantgenetics.com.au/sitemap.xml",
                region_language="Australia, English", berry_relevance="strawberry (and macadamia, non-berry)",
                discovery_mechanism="sitemap_xml adapter", adapter_compatibility="sitemap_xml (existing)",
                maturity="discovery_mechanism_understood", robots_access_observation="robots.txt 200; sitemap.xml reachable (200) to this project's own client",
                cadence_expectation="inference: low-frequency (a small commercialisation body, likely a handful of variety-page updates per year)",
                confidence="medium", evidence_urls=["https://ausplantgenetics.com.au/", "https://ausplantgenetics.com.au/about/"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="Berries Australia (berries.net.au) variety pages reference APG varieties and can be checked manually.",
        unresolved_questions=["Site is variety-catalog-shaped, not a newsroom -- sitemap discovery may surface mostly static variety pages rather than dated news; cadence is inferred, not observed."],
        proposed_priority="wave_2_candidate",
    ),
    "BerryWorld": entry(
        "BerryWorld", official_domain="berryworld.com",
        aliases_search_terms=["BerryWorld Group"],
        candidate_sources=[],
        recommended_monitoring_state="source_configured_never_run",
        manual_fallback="n/a -- existing Source source-20260824-berryworld-newsroom covers this",
        unresolved_questions=["See AgroBerries entry: found marketing language listing BerryWorld inside an 'AgroBerries family of companies' -- not confirmed, not acted on."],
        proposed_priority="wave_1_already_configured",
    ),
    "Black Venture Farm": entry(
        "Black Venture Farm", official_domain="blackventurefarm.com",
        aliases_search_terms=["Black Venture Farm Oficial"],
        candidate_sources=[
            source(
                source_type="official_website", url="https://blackventurefarm.com/",
                region_language="unspecified (a Facebook page uses Spanish-language branding 'Oficial', suggesting a Latin American operation)",
                berry_relevance="unspecified", discovery_mechanism="not yet determined -- homepage reachable (200) but no feed/sitemap probed this mission",
                adapter_compatibility="unknown -- needs a follow-up technical check", maturity="candidate_identified",
                robots_access_observation="robots.txt returned 404 (no robots.txt file); homepage returned 200",
                cadence_expectation="unknown -- no news/press section identified", confidence="low",
                evidence_urls=["https://blackventurefarm.com/", "https://www.facebook.com/BlackVentureFarmOficial"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="Facebook page (facebook.com/BlackVentureFarmOficial) as manual check only -- social platforms are not a supported acquisition adapter in this codebase.",
        unresolved_questions=["No newsroom/press/blog section identified on the homepage in this pass -- a deeper site-map crawl (out of this mission's bounded scope) would be needed before recommending an adapter."],
        proposed_priority="wave_3_low_confidence",
    ),
    "California Giant": entry(
        "California Giant", official_domain="calgiant.com",
        aliases_search_terms=["California Giant Berry Farms", "Cal Giant", "California Giant, Inc."],
        candidate_sources=[],  # see the dedicated California Giant assessment doc -- not duplicated here
        recommended_monitoring_state="source_blocked",
        manual_fallback="See docs/v2/COMPETITOR-SOURCE-STRATEGY-V1.md section 5 (California Giant alternative-coverage assessment) for the full, separately-required treatment.",
        unresolved_questions=["See dedicated assessment document."],
        proposed_priority="see_dedicated_assessment",
    ),
    "Costa": entry(
        "Costa", official_domain="costagroup.com.au",
        aliases_search_terms=["Costa Group Holdings", "Costa Group", "Costa Berry International"],
        candidate_sources=[],
        recommended_monitoring_state="source_configured_never_run",
        manual_fallback="n/a -- existing Sources source-20260824-costa-group-newsroom and source-news-search-costa-group cover this",
        unresolved_questions=[],
        proposed_priority="wave_1_already_configured",
    ),
    "Denning Blueberries": entry(
        "Denning Blueberries", official_domain=None,
        aliases_search_terms=["Denning Blueberry Farm"],
        candidate_sources=[],
        recommended_monitoring_state="no_supported_source",
        manual_fallback="None identified. Australian Blueberry Growers' Association (berries.net.au) member directory is a plausible lead for a human follow-up search, not verified this mission.",
        unresolved_questions=["No official website, social presence, or trade-press mention was found for an entity matching this exact name in two search passes. May be a smaller/regional operation with no public web presence, a name variant not yet tried, or a misread/abbreviated spreadsheet label."],
        proposed_priority="identity_search_strategy_pending",
    ),
    "Expoberries": entry(
        "Expoberries", official_domain=None,
        aliases_search_terms=["Expoberries S.A. de C.V.", "ExpoAgroberries"],
        candidate_sources=[
            source(
                source_type="trade_association_page", url="https://aneberries.mx/en/expoberries/",
                region_language="Mexico (Michoacán/Jalisco), English/Spanish", berry_relevance="blueberry, raspberry, blackberry",
                discovery_mechanism="not a feed -- a static association-directory profile page, not a source that publishes dated updates",
                adapter_compatibility="none -- not a publishing source", maturity="identity_search_strategy_pending",
                robots_access_observation="not checked -- not a candidate for automated discovery",
                cadence_expectation="n/a", confidence="low",
                evidence_urls=["https://aneberries.mx/en/expoberries/", "https://mx.linkedin.com/company/expoberries", "https://panjiva.com/Expoberries-S-A-De-C-V/31221334"],
            ),
        ],
        recommended_monitoring_state="no_supported_source",
        manual_fallback="Aneberries (Mexican berry export association) directory profile and LinkedIn page as manual checks only.",
        unresolved_questions=["No dedicated company website found. 'ExpoAgroberries' (expoagroberries.com.mx) is a trade SHOW/event site, not confirmed to be this company's own site -- not treated as the same entity."],
        proposed_priority="identity_search_strategy_pending",
    ),
    "Fall Creek": entry(
        "Fall Creek", official_domain="fallcreeknursery.com",
        aliases_search_terms=["Fall Creek Farm & Nursery", "Fall Creek Nursery", "Sekoya"],
        candidate_sources=[],
        recommended_monitoring_state="source_configured_never_run",
        manual_fallback="n/a -- existing Sources source-20260824-fall-creek-newsroom and source-20260824-sekoya-news cover this",
        unresolved_questions=[],
        proposed_priority="wave_1_already_configured",
    ),
    "Fresh Forward": entry(
        "Fresh Forward", official_domain="fresh-forward.nl",
        aliases_search_terms=["Fresh Forward Breeding B.V.", "Fresh Forward Breeding & Marketing"],
        candidate_sources=[
            source(
                source_type="official_website", url="https://www.fresh-forward.nl/en",
                region_language="Netherlands, English/Dutch", berry_relevance="strawberry (primary focus per search results; also apples, non-berry)",
                discovery_mechanism="not yet determined -- /feed/ returned 404 (not WordPress); a sitemap.xml was not probed this mission",
                adapter_compatibility="unknown -- needs a follow-up technical check (likely sitemap_xml if a sitemap exists)",
                maturity="candidate_identified", robots_access_observation="not fully probed -- homepage identified, /feed/ absent",
                cadence_expectation="inference: low-frequency (breeding company, not a daily news operation)",
                confidence="medium", evidence_urls=["https://www.fresh-forward.nl/en", "https://www.fresh-forward.nl/en/breeding"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="None beyond the official site itself for manual review.",
        unresolved_questions=["Discovery mechanism (sitemap vs. RSS vs. none) not yet confirmed -- /feed/ 404'd, no sitemap.xml check completed this mission."],
        proposed_priority="wave_2_candidate",
    ),
    "Fruitist": entry(
        "Fruitist", official_domain="fruitist.com",
        aliases_search_terms=["Agrovision Corp.", "Agrovision"],
        candidate_sources=[
            source(
                source_type="official_website_sitemap", url="https://www.fruitist.com/sitemap.xml",
                region_language="United States, English", berry_relevance="blueberry (primary), blackberry, raspberry, cherry",
                discovery_mechanism="sitemap_xml adapter", adapter_compatibility="sitemap_xml (existing)",
                maturity="discovery_mechanism_understood", robots_access_observation="robots.txt 200, declares a sitemap; a guessed Shopify-style .atom blog feed (blogs/news.atom) returned 404, so sitemap is the confirmed path, not a blog feed",
                cadence_expectation="inference: moderate (a fast-growing, well-funded consumer brand -- likely more frequent than a typical grower-shipper)",
                confidence="medium", evidence_urls=[
                    "https://www.fruitist.com/", "https://www.freshfruitportal.com/news/2025/04/22/agrovision-rebrands-say-hello-to-fruitist/",
                    "https://www.thepacker.com/news/industry/look-agrovisions-transition-fruitist",
                ],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="Extensive real trade-press coverage of the Agrovision-to-Fruitist rebrand (FreshFruitPortal, The Packer, CNBC, The Hustle) usable for manual/analyst review pending onboarding.",
        unresolved_questions=["Company rebranded from Agrovision to Fruitist in April 2025 -- canonical entity company-agrovision already carries 'Fruitist' as an alias (Company + Genetics Relationships V1); this mission's own domain finding (fruitist.com replacing agrovisioncorp.com) is consistent with, not a contradiction of, that prior work."],
        proposed_priority="wave_1_candidate",
    ),
    "Gem-Pack Berries": entry(
        "Gem-Pack Berries", official_domain="gem-packberries.com",
        aliases_search_terms=["Gem-Pack Berries, LLC"],
        candidate_sources=[
            source(
                source_type="official_website_feed", url="https://www.gem-packberries.com/en/feed",
                region_language="United States (California, Florida, Mexico), English", berry_relevance="strawberry, blueberry, blackberry, raspberry",
                discovery_mechanism="article_rss adapter against the confirmed-live feed", adapter_compatibility="article_rss (existing)",
                maturity="discovery_mechanism_understood", robots_access_observation="feed URL returned HTTP 200 to this project's own User-Agent",
                cadence_expectation="inference: seasonal harvest-forecast cadence, similar to other grower-shipper Sources already in this registry (e.g. Fall Creek, Costa)",
                confidence="high", evidence_urls=["https://www.gem-packberries.com/en", "https://theproducenews.com/berries/gem-pack-berries-unveils-new-website"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="The Packer / Produce News / Organic Produce Network already carry real Gem-Pack Berries coverage as a manual-check alternative.",
        unresolved_questions=["Real trade-press coverage ('Gem-Pack and Well-Pict Berries combine companies' -- The Packer) suggests Gem-Pack Berries and Well-Pict (roster entry #33) may now be affiliated or merged. Neither entity's canonical record was modified for this -- flagged as an unresolved question for the entity-identity workstream, not acted on in this mission."],
        proposed_priority="wave_2_candidate",
    ),
    "Hortifrut Genetica": entry(
        "Hortifrut Genetica", official_domain="hortifrut.com",
        aliases_search_terms=["Hortifrut S.A.", "Hortifrut Genetica"],
        candidate_sources=[],
        recommended_monitoring_state="source_configured_never_run",
        manual_fallback="n/a -- existing Source source-20260819-hortifrut-newsroom covers this",
        unresolved_questions=[],
        proposed_priority="wave_1_already_configured",
    ),
    "IQ Berries": entry(
        "IQ Berries", official_domain=None,
        aliases_search_terms=["IQB", "Peter Rolfe"],
        candidate_sources=[
            source(
                source_type="licensing_partner_page", url="https://www.osirisplant.com/en/iq-berries/",
                region_language="Australia (breeding) / Americas (via Osiris license), English/Spanish",
                berry_relevance="blueberry", discovery_mechanism="not a feed -- a static partner-page profile, not a dated publishing source",
                adapter_compatibility="none -- not a publishing source", maturity="identity_search_strategy_pending",
                robots_access_observation="not checked -- not a candidate for automated discovery",
                cadence_expectation="n/a", confidence="low",
                evidence_urls=["https://www.osirisplant.com/en/iq-berries/", "https://www.fruitnet.com/iqb-teams-up-with-osiris-to-develop-new-blues-varieties/246169.article"],
            ),
        ],
        recommended_monitoring_state="no_supported_source",
        manual_fallback="Fruitnet / FreshFruitPortal / International Blueberry Organization coverage of IQB-Osiris variety releases as a manual-check alternative.",
        unresolved_questions=["No independently-owned IQ Berries website was found -- IQ Berries (Brisbane, Australia, breeder Peter Rolfe) appears to publish primarily through its Americas licensing partner Osiris Plant Management and trade press, not its own newsroom."],
        proposed_priority="identity_search_strategy_pending",
    ),
    "Marionnet": entry(
        "Marionnet", official_domain=None,
        aliases_search_terms=["Marionnet Label", "Marionnet SAS", "Andre Marionnet"],
        candidate_sources=[],
        recommended_monitoring_state="no_supported_source",
        manual_fallback="Doriane.com case-study page and Google Patents/Justia patent filings under 'Andre Marionnet' as manual-check alternatives; neither is a dated news-publishing source suitable for an adapter.",
        unresolved_questions=["No official Marionnet/Marionnet Label website was found in two search passes. Company was 'taken over by the Agri Finest Company group' in 2018 per search results -- a parent-company website search was not attempted this mission (would exceed the bounded scope of re-verifying one already-ambiguous name)."],
        proposed_priority="identity_search_strategy_pending",
    ),
    "Mountain Blue": entry(
        "Mountain Blue", official_domain="mountainblue.com.au",
        aliases_search_terms=["Mountain Blue Orchards", "MBO", "Mountain Blue Farms"],
        candidate_sources=[
            source(
                source_type="official_website_sitemap", url="https://mountainblue.com.au/sitemap.xml",
                region_language="Australia, English", berry_relevance="blueberry (primary), strawberry",
                discovery_mechanism="sitemap_xml adapter", adapter_compatibility="sitemap_xml (existing)",
                maturity="discovery_mechanism_understood",
                robots_access_observation="robots.txt uses the newer IETF 'Content-Signal' opt-out convention (search/ai-input/ai-train) rather than classic Disallow rules, plus explicit named-bot blocks (Amazonbot, Applebot-Extended, Bytespider); sitemap.xml itself returned HTTP 200 to this project's own client. A dedicated /media page exists.",
                cadence_expectation="inference: moderate (an active, media-page-maintaining breeder/grower)",
                confidence="medium", evidence_urls=["https://www.mountainblue.com.au/media", "https://www.mountainblue.com.au/mountain-blue-genetics"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="Berries Australia (berries.net.au/mountain-blue/) grower profile as a manual-check alternative.",
        unresolved_questions=["Site's robots.txt uses the Content-Signal protocol, a newer, distinct mechanism from classic Disallow rules -- this project's collection policy has not yet made an explicit decision on how to interpret Content-Signal ai-input/ai-train values (not fully captured in this pass) for a source it would use in an AI-assisted intelligence pipeline. Recommend a deliberate policy read before onboarding, not a code change in this mission."],
        proposed_priority="wave_2_candidate",
    ),
    "Oishii": entry(
        "Oishii", official_domain="oishii.com",
        aliases_search_terms=["Oishii Berry", "Omakase Berry"],
        candidate_sources=[
            source(
                source_type="official_website_feed", url="https://oishii.com/blogs/press.atom",
                region_language="United States, English", berry_relevance="strawberry",
                discovery_mechanism="article_rss adapter against the confirmed-live Shopify blog Atom feed", adapter_compatibility="article_rss (existing -- Atom is already handled by the same generic feed fetch/list)",
                maturity="discovery_mechanism_understood", robots_access_observation="robots.txt 200 (standard e-commerce Disallow: /admin, /cart/, /checkout only -- does not block the /blogs/press path); feed URL returned HTTP 200",
                cadence_expectation="inference: moderate-to-high (a well-funded, press-active startup with a dedicated press page and PR Newswire presence)",
                confidence="high", evidence_urls=["https://oishii.com/pages/press", "https://www.prnewswire.com/news/oishii/"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="PR Newswire's dedicated Oishii news page (prnewswire.com/news/oishii/) as a manual/redundant-corroboration check.",
        unresolved_questions=[],
        proposed_priority="wave_1_candidate",
    ),
    "Ozblu": entry(
        "Ozblu", official_domain="ozblu.com",
        aliases_search_terms=["OZblu", "United Exports", "Oz Varieties", "Nature Select"],
        candidate_sources=[
            source(
                source_type="official_website_feed", url="https://www.ozblu.com/news/feed/",
                region_language="Australia/South Africa/Peru/Mexico/multi-region, English", berry_relevance="blueberry",
                discovery_mechanism="article_rss adapter against the confirmed-live feed", adapter_compatibility="article_rss (existing)",
                maturity="discovery_mechanism_understood", robots_access_observation="robots.txt 200, fully permissive (Disallow: none), sitemap_index.xml declared; feed URL returned HTTP 200",
                cadence_expectation="inference: moderate (an active multi-region brand with a dedicated /news/ section)",
                confidence="high", evidence_urls=["https://www.ozblu.com/", "https://www.ozblu.com/news/world-development-finance-institutions-invest-in-a-united-exports-ozblu-blueberry-expansion/"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="United Exports' own site (united-exports.com) as a secondary manual check, since it is the brand owner behind Ozblu.",
        unresolved_questions=["Confirms the existing Company + Genetics Relationships V1 finding that brand-ozblu is a multi-party entity (United Exports owns the brand, Nature Select develops genetics, Oz Varieties licenses) -- this source would monitor the brand's own news, not resolve which party issued a given announcement; that attribution stays a human/analyst judgment at review time."],
        proposed_priority="wave_1_candidate",
    ),
    "Pairwise": entry(
        "Pairwise", official_domain="pairwise.com",
        aliases_search_terms=["Pairwise Plants"],
        candidate_sources=[
            source(
                source_type="official_website_page", url="https://www.pairwise.com/insights",
                region_language="United States, English", berry_relevance="unspecified (gene-editing platform; berry-specific work not confirmed in this pass)",
                discovery_mechanism="not yet determined -- robots.txt permissive but no feed/sitemap URL was confirmed live this mission; the /insights page itself is not confirmed to expose a machine-readable feed",
                adapter_compatibility="unknown -- needs a follow-up technical check", maturity="candidate_identified",
                robots_access_observation="robots.txt 200; homepage and /insights page load",
                cadence_expectation="inference: low-to-moderate (a well-funded biotech with periodic partnership announcements, e.g. the 2024 Corteva deal)",
                confidence="low", evidence_urls=["https://www.pairwise.com/insights", "https://www.corteva.com/resources/media-center/corteva-pairwise-join-forces-to-accelerate-gene-editing-advance-climate-resilience-in-agriculture.html"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="Corteva's own newsroom and GenEngNews/produce trade press already cover major Pairwise announcements as a manual-check alternative.",
        unresolved_questions=["Pairwise's public work is broader ag-biotech (CRISPR platform across multiple crops), not confirmed berry-specific in this pass -- berry relevance for this roster entry should be re-confirmed by whoever activates this source, not assumed from the company's general profile."],
        proposed_priority="wave_3_low_confidence",
    ),
    "Perfection Fresh": entry(
        "Perfection Fresh", official_domain="perfection.com.au",
        aliases_search_terms=["Perfection Fresh Australia"],
        candidate_sources=[
            source(
                source_type="official_website_feed", url="https://www.perfection.com.au/blog/rss.xml",
                region_language="Australia (Tasmania, Queensland), English", berry_relevance="strawberry, blueberry, raspberry, blackberry",
                discovery_mechanism="article_rss adapter against the confirmed-live blog RSS feed", adapter_compatibility="article_rss (existing)",
                maturity="discovery_mechanism_understood", robots_access_observation="robots.txt 200 (HubSpot-style Disallow rules for sample/preference pages only, not the blog); feed URL returned HTTP 200",
                cadence_expectation="inference: moderate (an active company blog)",
                confidence="high", evidence_urls=["https://www.perfection.com.au/perfection-berries", "https://berries.net.au/wp-content/uploads/2024/01/AUT-21-PROFILE-PERFECTION.pdf"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="Berries Australia's own grower-profile PDF on Perfection Fresh as a manual-check corroboration source.",
        unresolved_questions=[],
        proposed_priority="wave_2_candidate",
    ),
    "Planasa": entry(
        "Planasa", official_domain="planasa.com",
        aliases_search_terms=["Planasa"],
        candidate_sources=[],
        recommended_monitoring_state="source_configured_never_run",
        manual_fallback="n/a -- existing Source source-20260819-planasa-newsroom covers this",
        unresolved_questions=["See Company + Genetics Relationships V1's own flagged pre-existing possible identity duplication (company-planasa / company-planasa-2 / company-plantas-de-navarra) -- not investigated further in this source-strategy mission; out of scope."],
        proposed_priority="wave_1_already_configured",
    ),
    "Plant Sciences": entry(
        "Plant Sciences", official_domain="plantsciencesgenetics.com",
        aliases_search_terms=["Plant Sciences, Inc.", "Plant Sciences Genetics", "PSG"],
        candidate_sources=[
            source(
                source_type="official_website_sitemap", url="https://www.plantsciencesgenetics.com/sitemap.xml",
                region_language="United States (Watsonville, CA), English", berry_relevance="strawberry, raspberry, blackberry",
                discovery_mechanism="sitemap_xml adapter", adapter_compatibility="sitemap_xml (existing)",
                maturity="discovery_mechanism_understood", robots_access_observation="robots.txt on plantsciencesgenetics.com returned 404 (no robots.txt file present -- not a block, simply absent, so no crawl restriction is declared); sitemap.xml itself returned HTTP 200",
                cadence_expectation="inference: low (a breeding/IP company, not a frequent-news operation)",
                confidence="medium", evidence_urls=["https://finance.yahoo.com/news/plant-sciences-inc-unveils-restructuring-140000641.html"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="Trade/financial press coverage of the 2026 Plant Sciences -> Plant Sciences Genetics (PSG) restructuring as a manual-check reference.",
        unresolved_questions=["Company recently restructured into a new entity, Plant Sciences Genetics, Inc., consolidating several prior berry-breeding affiliates (Berry Genetics, Strawberry Sciences, Via Berry Breeding, Vitae Caneberry Breeding, Fragaria Plant Sciences) -- the existing canonical entity company-plant-sciences-genetics already carries this exact alias, so this finding corroborates rather than contradicts the prior mission's reconciliation."],
        proposed_priority="wave_2_candidate",
    ),
    "Royakkers": entry(
        "Royakkers", official_domain="softfruit.be",
        aliases_search_terms=["Royakkers Fruit & Planten", "Royakkers Planten & Fruit"],
        candidate_sources=[
            source(
                source_type="official_website", url="https://www.softfruit.be/en/",
                region_language="Belgium (near the Netherlands border), English/Dutch", berry_relevance="strawberry, raspberry, blackberry",
                discovery_mechanism="not yet determined -- /en/feed/ returned 404; a sitemap.xml was not probed this mission",
                adapter_compatibility="unknown -- needs a follow-up technical check", maturity="candidate_identified",
                robots_access_observation="homepage reachable", cadence_expectation="inference: low (a small family farm/nursery business)",
                confidence="medium", evidence_urls=["https://www.softfruit.be/over-ons/", "https://zakenblad.nl/2021/04/21/jan-en-gijs-royakkers-vader-en-zoon-in-een-gezond-familiebedrijf/"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="None beyond the official site itself for manual review.",
        unresolved_questions=[
            "Spreadsheet lists Royakkers under regions DOA_DANZ/DEMEA; search results place the company in Kinrooi, Belgium, not the Netherlands the company's own surname might suggest -- a geographic detail worth a human's attention, not corrected here (this mission does not modify regions).",
        ],
        proposed_priority="wave_3_low_confidence",
    ),
    "Smart Berries": entry(
        "Smart Berries", official_domain="smartberries.com.au",
        aliases_search_terms=["Smart Berries Pty Ltd", "Fresh Produce Group (FPG)", "Pascoes"],
        candidate_sources=[
            source(
                source_type="official_website_feed", url="https://www.smartberries.com.au/feed/",
                region_language="Australia/New Zealand, English", berry_relevance="blueberry, raspberry, blackberry",
                discovery_mechanism="article_rss adapter against the confirmed-live feed", adapter_compatibility="article_rss (existing)",
                maturity="discovery_mechanism_understood", robots_access_observation="robots.txt 200 (standard WordPress Disallow: /wp-admin/ only); feed URL returned HTTP 200",
                cadence_expectation="inference: low-to-moderate", confidence="high",
                evidence_urls=["https://www.smartberries.com.au/about-us/", "https://www.fruitnet.com/asiafruit/smart-berries-building-up/170931.article"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="Fruitnet Asiafruit coverage as a manual-check corroboration source.",
        unresolved_questions=[],
        proposed_priority="wave_2_candidate",
    ),
    "Splendor Produce": entry(
        "Splendor Produce", official_domain=None,
        aliases_search_terms=["Splendor Produce Mexico"],
        candidate_sources=[],
        recommended_monitoring_state="no_supported_source",
        manual_fallback="Mexican government trade profile (gob.mx/agricultura article) and Facebook page (facebook.com/splendorproducemx) as manual-check-only references; neither is a dated publishing source suitable for an adapter.",
        unresolved_questions=["No official company website was found in two search passes despite the company being real and described in a Mexican government trade article (450ha blackberries, 200ha raspberries, ~80% exported to the US). 'California Splendor, Inc.' (calsplendor.com) appeared in results but is a distinct entity (strawberries/blackberries, different profile) -- NOT treated as the same company."],
        proposed_priority="identity_search_strategy_pending",
    ),
    "SunBelle": entry(
        "SunBelle", official_domain="sun-belle.com",
        aliases_search_terms=["Sun Belle", "Sunbelle", "Sunbelle Berries"],
        candidate_sources=[
            source(
                source_type="official_website_feed", url="https://www.sun-belle.com/feed/",
                region_language="United States, English", berry_relevance="blueberry, raspberry, blackberry, golden berries, currants",
                discovery_mechanism="article_rss adapter against the confirmed-live feed", adapter_compatibility="article_rss (existing)",
                maturity="discovery_mechanism_understood", robots_access_observation="robots.txt 200 (standard WordPress Disallow: /wp-admin/ only), sitemap also declared (wp-sitemap.xml); feed URL returned HTTP 200",
                cadence_expectation="inference: low-to-moderate", confidence="high",
                evidence_urls=["https://www.sun-belle.com/", "https://www.thepacker.com/news/produce-crops/sun-belle-expands-berry-grower-relationships"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="The Packer's existing Sun Belle coverage as a manual-check corroboration source.",
        unresolved_questions=["Three related domains found (sun-belle.com, sunbelleberries.com, sunbelle.info) -- sun-belle.com's own confirmed-live feed is proposed as the single candidate; the other two are noted, not separately proposed, to avoid duplicate-content risk (see the duplicate-risk assessment)."],
        proposed_priority="wave_2_candidate",
    ),
    "The Berry Collective": entry(
        "The Berry Collective", official_domain="theberrycollective.com.au",
        aliases_search_terms=["The Berry Collective (Australia)"],
        candidate_sources=[
            source(
                source_type="official_website_feed", url="https://theberrycollective.com.au/feed/",
                region_language="Australia, English", berry_relevance="unspecified (a berry supply/retail partnership site, not confirmed variety/genetics content)",
                discovery_mechanism="article_rss adapter against the confirmed-live feed (technically ready)", adapter_compatibility="article_rss (existing)",
                maturity="identity_search_strategy_pending", robots_access_observation="robots.txt 200; feed URL returned HTTP 200",
                cadence_expectation="unknown", confidence="low",
                evidence_urls=["https://theberrycollective.com.au/", "https://theberrycollective.com.au/about/"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="None -- identity ambiguity should be resolved by a human before any fallback is relied upon.",
        unresolved_questions=[
            "Multiple, clearly distinct organizations share this exact name: a US/NYC wellness-and-community brand (theberrycollective.co), an events platform, a classical-music ensemble, and this Australian 'berry supply & fruit retailer' partnership (theberrycollective.com.au). The Australian one is the best fit for a berry-industry roster, but the spreadsheet's own Competitor Type for this row is 'University/Public,' which does not obviously match a growers-to-retailers supply partnership -- this mismatch is flagged, not resolved. Do not onboard this source until a human confirms which real-world organization the spreadsheet row actually means.",
        ],
        proposed_priority="wave_3_low_confidence",
    ),
    "UC Davis": entry(
        "UC Davis", official_domain="strawberry.ucdavis.edu",
        aliases_search_terms=["UC Davis Strawberry Breeding Program", "University of California, Davis Strawberry Breeding Program"],
        candidate_sources=[
            source(
                source_type="official_website_page", url="https://strawberry.ucdavis.edu/news-and-events-0",
                region_language="United States, English", berry_relevance="strawberry",
                discovery_mechanism="unresolved -- see robots_access_observation", adapter_compatibility="sitemap_xml or article_rss, if access is resolved",
                maturity="known_blocked", robots_access_observation="robots.txt returned HTTP 200 (standard Drupal Disallow rules, not obviously blocking /news-and-events-0), but the site's HOME PAGE returned HTTP 403 to this project's own User-Agent on two separate checks -- a real, observed access limitation, not a guess. Not investigated further to avoid any appearance of probing around the block.",
                cadence_expectation="inference: high-value but likely low-frequency (a public research program, not a daily news operation) -- real variety-release announcements (5 new Fusarium-resistant cultivars, international licensing deals) are exactly the kind of content this roster needs",
                confidence="medium", evidence_urls=["https://strawberry.ucdavis.edu/news-and-events-0", "https://www.ucdavis.edu/news/strawberry-breeding-program-backgrounder-frequently-asked-questions"],
            ),
        ],
        recommended_monitoring_state="source_blocked",
        manual_fallback="UC Davis's main university newsroom (ucdavis.edu/news, a different subdomain) carries the same major strawberry-program announcements (Fusarium-resistant variety release, international licensing) and returned no observed block in this pass -- worth a follow-up technical check as an alternative entry point before assuming the whole ucdavis.edu domain is inaccessible.",
        unresolved_questions=["Whether the 403 is specific to the strawberry.ucdavis.edu subdomain, this project's exact User-Agent string, or a broader ucdavis.edu WAF policy was not determined -- would need the same kind of A/B (curl vs. httpx) diagnostic this project has already applied to California Giant, which was out of this mission's time-bounded scope to repeat for every blocked candidate."],
        proposed_priority="wave_2_candidate_pending_access_resolution",
    ),
    "University of Arkansas": entry(
        "University of Arkansas", official_domain="aaes.uada.edu",
        aliases_search_terms=["University of Arkansas Division of Agriculture", "UADA", "Arkansas Agricultural Experiment Station"],
        candidate_sources=[],
        recommended_monitoring_state="source_configured_never_run",
        manual_fallback="n/a -- existing Source source-20260824-arkansas-aaes-news covers this",
        unresolved_questions=[],
        proposed_priority="wave_1_already_configured",
    ),
    "University of Florida": entry(
        "University of Florida", official_domain="blogs.ifas.ufl.edu",
        aliases_search_terms=["University of Florida IFAS", "UF/IFAS", "UF"],
        candidate_sources=[],
        recommended_monitoring_state="source_configured_never_run",
        manual_fallback="n/a -- existing Source source-20260824-uf-ifas-news covers this",
        unresolved_questions=[],
        proposed_priority="wave_1_already_configured",
    ),
    "Well-Pict": entry(
        "Well-Pict", official_domain="wellpict.com",
        aliases_search_terms=["Well Pict Berries", "Well•Pict Berries"],
        candidate_sources=[
            source(
                source_type="official_website", url="https://www.wellpict.com/",
                region_language="United States (Watsonville, CA), English", berry_relevance="strawberry, blueberry, blackberry, raspberry",
                discovery_mechanism="not confirmed this mission -- see robots_access_observation", adapter_compatibility="unknown, pending a successful connection",
                maturity="candidate_identified", robots_access_observation="Both the homepage and /feed/ path returned a connection failure (curl exit/HTTP code 000, not a 4xx/5xx) on repeated attempts from this environment -- inconclusive, NOT the same as a confirmed HTTP-level block (compare California Giant's clean 403). Needs a re-check from a different network path before any access conclusion is drawn.",
                cadence_expectation="inference: moderate (a real trade-press-covered relaunch of its site in 2013, with an active blog historically)",
                confidence="low", evidence_urls=["https://www.supermarketnews.com/fresh-produce/well-pict-berries-launches-new-website", "https://www.thepacker.com/news/industry/gem-pack-and-well-pict-berries-combine-companies"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="Trade press (Supermarket News, The Packer, Produce News) already covers Well-Pict as a manual-check alternative while the connection issue is investigated.",
        unresolved_questions=[
            "Connection to wellpict.com failed outright (not a 403/blocked response) during this mission's verification -- could be a transient network condition in this research environment, a DNS/hosting issue, or a genuine access restriction; not distinguishable without a retry from elsewhere.",
            "See Gem-Pack Berries entry: trade press reports Gem-Pack and Well-Pict Berries 'combining companies' -- a possible merger/affiliation between two separate roster entries, not investigated or acted on further (entity-identity scope, not this mission's).",
        ],
        proposed_priority="wave_2_candidate_pending_access_resolution",
    ),
    "Wish Farms": entry(
        "Wish Farms", official_domain="wishfarms.com",
        aliases_search_terms=["Wish Farms"],
        candidate_sources=[
            source(
                source_type="official_website_feed", url="https://wishfarms.com/newsroom/feed/",
                region_language="United States (Plant City, FL), English", berry_relevance="strawberry, blueberry, blackberry, raspberry",
                discovery_mechanism="article_rss adapter against the confirmed-live feed", adapter_compatibility="article_rss (existing)",
                maturity="discovery_mechanism_understood", robots_access_observation="robots.txt 200, fully permissive (Disallow: none), sitemap_index.xml also declared; feed URL returned HTTP 200",
                cadence_expectation="inference: moderate-to-high (an active, dedicated newsroom with recent leadership, event, and breeding-program posts)",
                confidence="high", evidence_urls=["https://wishfarms.com/newsroom/", "https://wishfarms.com/newsroom-item/wish-farms-refreshes-its-brand-reveals-app-and-website/"],
            ),
        ],
        recommended_monitoring_state="discovery_pending",
        manual_fallback="n/a -- source is strong enough that a manual fallback is not the priority recommendation.",
        unresolved_questions=[],
        proposed_priority="wave_1_candidate",
    ),
}

assert len(ENTRIES) == 33, len(ENTRIES)
print(f"OK: {len(ENTRIES)} entries constructed")

# ---------------------------------------------------------------------------
# Merge with the prior mission's reconciliation matrix -- canonical_entity_id,
# canonical_display_name, entity_type all come from there, never re-derived
# or guessed here, per this mission's explicit "do not modify competitor
# tiers, priorities, regions, identities, genetics, or aliases" rule. This
# script only READS that file.
# ---------------------------------------------------------------------------
reconciliation = json.loads(RECONCILIATION_PATH.read_text(encoding="utf-8"))
recon_by_label = {r["spreadsheet_label"]: r for r in reconciliation["rows"]}
assert set(recon_by_label) == set(ENTRIES), set(recon_by_label) ^ set(ENTRIES)

rows = []
for label, data in ENTRIES.items():
    recon = recon_by_label[label]
    rows.append(
        {
            "row_number": recon["row_number"],
            "spreadsheet_label": label,
            "canonical_entity_id": recon["canonical_entity_id"],
            "canonical_display_name": recon["canonical_display_name"],
            "entity_type": recon["entity_type"],
            **data,
        }
    )
rows.sort(key=lambda r: r["row_number"])
assert len(rows) == 33
assert len({r["canonical_entity_id"] for r in rows}) == 33, "duplicate canonical entity id in source strategy"
print(f"OK: {len(rows)} rows merged with reconciliation matrix; {len({r['canonical_entity_id'] for r in rows})} unique canonical ids")

FIRST_WAVE_TAGS = {"wave_1_already_configured", "wave_1_candidate"}
first_wave = [r for r in rows if r["proposed_priority_for_implementation"] in FIRST_WAVE_TAGS]
print(f"First activation wave size: {len(first_wave)}")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


contract = {
    "id": "competitor-source-strategy-v1",
    "verification_date": VERIFICATION_DATE,
    "base_commit": "4e54401da040be937cc68877f410b4da7b646d65",
    "scope": "Research and import-planning only. No live Source records created, no collection run, no canonical entity/relationship/tier/priority/region data changed.",
    "maturity_states": list(MATURITY_STATES),
    "monitoring_states": list(MONITORING_STATES),
    "row_count": len(rows),
    "rows": rows,
}
write_json(IMPORT_DIR / "competitor-source-strategy-v1.json", contract)
print("wrote competitor-source-strategy-v1.json")

# ---------------------------------------------------------------------------
# Noncanonical candidate-source import proposal: source-record-SHAPED
# entries (adapter/feed_url/label/etc., matching sources.json's own field
# names for a smooth human review diff) but explicitly namespaced and
# flagged as proposals, never written to data/configuration/sources.json.
# ---------------------------------------------------------------------------
proposals = []
for r in rows:
    for i, cs in enumerate(r["candidate_sources"]):
        adapter_guess = {
            "official_website_feed": "article_rss",
            "official_website_sitemap": "sitemap_xml",
        }.get(cs["source_type"])
        proposals.append(
            {
                "proposed_id": f"PROPOSAL-{r['canonical_entity_id']}-{i}".replace("company-", "").replace("brand-", "").replace("breeding_program-", ""),
                "NONCANONICAL": True,
                "note": "This is a research proposal, not a live Source record. Do not import into data/configuration/sources.json without human review.",
                "label": f"{r['canonical_display_name']} ({cs['source_type']})",
                "linked_competitor_ids": [r["canonical_entity_id"]],
                "proposed_discovery": {
                    "adapter": adapter_guess,
                    "feed_url": cs["url"] if adapter_guess else None,
                    "note_if_no_adapter_guess": None if adapter_guess else f"source_type={cs['source_type']!r} is not a direct feed/sitemap -- see candidate_sources.discovery_mechanism",
                },
                "maturity": cs["maturity"],
                "confidence": cs["confidence"],
                "evidence_urls": cs["evidence_urls"],
                "verification_date": cs["verification_date"],
            }
        )
write_json(IMPORT_DIR / "candidate-source-import-proposal.json", {
    "id": "competitor-source-strategy-v1-candidate-proposals",
    "NONCANONICAL": True,
    "note": "Every entry here is a research proposal keyed to an existing canonical_entity_id. None has been written to data/configuration/sources.json. A human must review and explicitly onboard through existing governance before any of these becomes a real Source.",
    "verification_date": VERIFICATION_DATE,
    "count": len(proposals),
    "proposals": proposals,
})
print(f"wrote candidate-source-import-proposal.json ({len(proposals)} proposals)")

# ---------------------------------------------------------------------------
# First activation wave
# ---------------------------------------------------------------------------
write_json(IMPORT_DIR / "first-activation-wave.json", {
    "id": "competitor-source-strategy-v1-first-activation-wave",
    "verification_date": VERIFICATION_DATE,
    "count": len(first_wave),
    "note": "Bounded first wave: the 8 already-configured-but-never-run Sources (zero new research needed, only an operator running collection) plus the highest-confidence newly-researched candidates (confirmed-live feed, permissive robots.txt, real trade-press corroboration).",
    "entries": [
        {
            "spreadsheet_label": r["spreadsheet_label"],
            "canonical_entity_id": r["canonical_entity_id"],
            "proposed_priority_for_implementation": r["proposed_priority_for_implementation"],
            "why": (
                "Already configured, discovery-eligible, never run -- zero new research or adapter work needed."
                if r["proposed_priority_for_implementation"] == "wave_1_already_configured"
                else f"Confirmed-live {r['candidate_sources'][0]['source_type']} ({r['candidate_sources'][0]['url']}), "
                     f"{r['candidate_sources'][0]['confidence']} confidence, existing adapter compatible."
            ),
        }
        for r in first_wave
    ],
})
print(f"wrote first-activation-wave.json ({len(first_wave)} entries)")

# ---------------------------------------------------------------------------
# Duplicate-risk / query-collision assessment
# ---------------------------------------------------------------------------
duplicate_risk_notes = [
    {
        "risk": "Multiple related domains for one company",
        "entities": ["SunBelle"],
        "detail": "sun-belle.com, sunbelleberries.com, and sunbelle.info all appear to be the same company. Only sun-belle.com's feed was proposed; the other two must not be independently onboarded without confirming they are not mirrors of the same content (would double-count every article).",
    },
    {
        "risk": "Possible corporate-family overlap",
        "entities": ["AgroBerries", "BerryWorld"],
        "detail": "Marketing copy found during research describes BerryWorld as part of an 'AgroBerries family of companies' alongside Berry Fresh. If true, their respective newsrooms could report overlapping/duplicate corporate news. Not confirmed or acted on -- flagged for the entity-identity workstream.",
    },
    {
        "risk": "Possible company merger/affiliation",
        "entities": ["Gem-Pack Berries", "Well-Pict"],
        "detail": "Trade press ('Gem-Pack and Well-Pict Berries combine companies' -- The Packer) suggests these two separate roster entries may now be one organization. If so, onboarding both as independent Sources risks duplicate coverage of what is actually one company's news. Flagged, not merged or resolved here.",
    },
    {
        "risk": "Aggregator/trade-press candidates need entity-targeted queries, not bare onboarding",
        "entities": ["Denning Blueberries", "Expoberries", "Splendor Produce", "Marionnet", "IQ Berries"],
        "detail": "Where no dedicated company website was found, the only available leads are trade associations, licensing partners, or general trade press (Fruitnet, FreshFruitPortal, Blueberries Consulting, aneberries.mx). These are broad, multi-company publishers -- if ever onboarded as a Source for one of these companies, it must be as a company-scoped news_search_rss query (the existing pattern already used for Costa: source-news-search-costa-group), never a bare full-feed subscription that would flood review with unrelated companies' news.",
    },
    {
        "risk": "Low-frequency official sources -- sparse, not broken",
        "entities": ["Australasian Plant Genetics", "Marionnet", "Royakkers", "IQ Berries"],
        "detail": "Small breeding/nursery operations with variety-catalog-style sites are expected to publish rarely. A future Source Health view should not flag these as 'quiet'/failing after a normal multi-month gap between real updates -- that would misrepresent expected low cadence as a collection problem.",
    },
    {
        "risk": "Candidates that should not be activated without a prior human decision",
        "entities": ["The Berry Collective"],
        "detail": "Technically ready (live feed, permissive robots.txt) but the underlying company identity is genuinely ambiguous (multiple unrelated organizations share the exact name, and the matched Australian site's business type does not obviously match the spreadsheet's 'University/Public' competitor type). Activating this source before identity confirmation risks importing an entirely unrelated organization's content under this roster entry's name.",
    },
]
write_json(IMPORT_DIR / "duplicate-risk-assessment.json", {
    "id": "competitor-source-strategy-v1-duplicate-risk-assessment",
    "verification_date": VERIFICATION_DATE,
    "count": len(duplicate_risk_notes),
    "notes": duplicate_risk_notes,
})
print("wrote duplicate-risk-assessment.json")

# ---------------------------------------------------------------------------
# Adapter-gap analysis
# ---------------------------------------------------------------------------
adapter_gap = {
    "id": "competitor-source-strategy-v1-adapter-gap-analysis",
    "verification_date": VERIFICATION_DATE,
    "existing_adapters_sufficient_for_this_roster": [
        "article_rss (RSS/Atom -- covers every confirmed-live feed candidate found this mission, including a Shopify .atom blog feed, which the existing generic feed fetch/list already handles)",
        "sitemap_xml (covers every confirmed sitemap candidate found this mission)",
        "news_search_rss (already proven for Costa; the right shape for any future company-scoped Google News query onboarded for a no-dedicated-website roster entry, e.g. Denning Blueberries or Splendor Produce, if ever attempted)",
    ],
    "no_new_adapter_type_required_by_this_research": (
        "Every technically-confirmed candidate this mission found (feed or sitemap) fits an adapter that already "
        "exists in app/services/media_discovery.py. This roster did not surface a need for, e.g., a new social/video "
        "adapter -- no roster entry's best available source was a social/video channel with no feed."
    ),
    "access_limitations_found_requiring_a_policy_or_client_decision_not_a_new_adapter": [
        {
            "entity": "California Giant",
            "issue": "TLS/HTTP-client fingerprint block (Cloudflare bot management) -- see dedicated assessment. Not an adapter gap; a client/policy question.",
        },
        {
            "entity": "UC Davis",
            "issue": "strawberry.ucdavis.edu returns HTTP 403 to this project's client on two checks, while robots.txt itself does not obviously disallow the relevant path. Not diagnosed further (no curl-vs-httpx A/B run) -- flagged as a candidate for the same diagnostic already applied to California Giant, not solved here.",
        },
        {
            "entity": "Mountain Blue",
            "issue": "robots.txt uses the newer IETF Content-Signal opt-out convention (search/ai-input/ai-train) rather than classic Disallow. This project has no documented policy yet for how to interpret an ai-input=no signal (if present) for a source it would use in an AI-assisted pipeline -- a governance question, not a technical adapter gap.",
        },
        {
            "entity": "Well-Pict",
            "issue": "Connection failed outright (not an HTTP-level response) from this research environment -- inconclusive; needs a retry from the production/collection environment before drawing any access conclusion.",
        },
    ],
}
write_json(IMPORT_DIR / "adapter-gap-analysis.json", adapter_gap)
print("wrote adapter-gap-analysis.json")

# ---------------------------------------------------------------------------
# Markdown 33-row matrix (human-readable companion to the JSON contract)
# ---------------------------------------------------------------------------
md_lines = [
    "# Competitor Source Strategy V1 — 33-row matrix",
    "",
    f"Verification date: {VERIFICATION_DATE}. Base commit: `4e54401da040be937cc68877f410b4da7b646d65`.",
    "Research/import-planning only — no live Source created, no collection run, no canonical data changed.",
    "",
    "| # | Label | Canonical entity | Domain | Best candidate | Adapter | Maturity | Monitoring state | Priority |",
    "|---|---|---|---|---|---|---|---|---|",
]
for r in rows:
    best = r["candidate_sources"][0] if r["candidate_sources"] else None
    domain = r["official_domain"] or "_none found_"
    best_url = best["url"] if best else ("_n/a — already configured_" if r["recommended_initial_monitoring_state"] == "source_configured_never_run" else "_none_")
    adapter = best["existing_adapter_compatibility"] if best else ("existing (see linked Source)" if r["recommended_initial_monitoring_state"] == "source_configured_never_run" else "—")
    maturity = best["maturity"] if best else ("known_runnable" if r["recommended_initial_monitoring_state"] == "linked_to_runnable_source" else ("configured_but_untested" if r["recommended_initial_monitoring_state"] == "source_configured_never_run" else "known_blocked"))
    md_lines.append(
        f"| {r['row_number']} | {r['spreadsheet_label']} | `{r['canonical_entity_id']}` | {domain} | "
        f"{best_url} | {adapter} | {maturity} | {r['recommended_initial_monitoring_state']} | {r['proposed_priority_for_implementation']} |"
    )
md_lines += [
    "",
    "## Unresolved questions (per row, where any exist)",
    "",
]
for r in rows:
    if r["unresolved_questions"]:
        md_lines.append(f"**{r['spreadsheet_label']}**")
        for q in r["unresolved_questions"]:
            md_lines.append(f"- {q}")
        md_lines.append("")
(IMPORT_DIR / "competitor-source-strategy-matrix.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
print("wrote competitor-source-strategy-matrix.md")

print("\nDONE.")
