# Wave 2 contract matrix

| Contract group | Gate coverage | Focused sources |
|---|---|---|
| Roster and identity | 33/33 rows, no drops/duplicates, company/brand/breeding-program routes, provisional and unknown states, aliases, redirects, duplicate audit, no canonical writes | `test_competitor_registry_v1.py`, `test_competitor_profile_v1.py`, `test_competitor_intelligence_integration_v1.py`, `test_entity_identity_integrity.py`, `test_entity_alias_recall.py` |
| Landscape | Blueberry default 33, filters, valid links, incomplete monitoring visibility | `test_competitor_landscape_v1.py`, `test_landscape_v2.py` |
| Daily Briefing | Date/content honesty, stale exclusion, empty/limited states, no draft/prototype leakage | `test_daily_intelligence_briefing_slice1.py`, `test_morning_brief.py` |
| Reader | In-app readable content, limited/missing-content labels, no fabricated full article | `test_astra_news_reader.py`, `test_intelligence_feed.py` |
| Trust | Backend repository contracts, feedback isolation, promotion/trust safeguards | `test_trust_feedback.py`, `test_sync_trusted_data.py`, `test_repository_backends.py` |
| Build integrity | Record schemas, static output safety, Pagefind in full mode | `validate_records.py`, `test_build_static.py`, `build_static.py` |

Quick mode runs all groups except static build/Pagefind. Full mode runs every
group and requires Pagefind to be installed; missing Pagefind is a failure.
