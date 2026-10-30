# Captured-news feed integration checklist

Stage 1 code inspection only. All Stage 2 implementation, desktop, narrow-screen and keyboard verification cells remain pending. This is not an acceptance receipt. Reconcile this list with the actual route map again before final delivery.

| Existing route / mode | Current code / behavior inspected | Required Stage 2 work | Browser verification |
| --- | --- | --- | --- |
| `/entities/company` | `app/main.py` delegates to `app/company_routes.py` / Company Directory | Directly accessible scoped captured-feed panel/tab alongside directory/selected companies | Pending |
| `/entities/company/{entity_id}` | Generic entity route / company dossier and recent intelligence | Reuse reader and existing evidence; expose complete scoped archive, date/tags, people/assessment links | Pending |
| `/entities/brand/{entity_id}` and `/entities/breeding_program/{entity_id}` | Generic entity route, separate canonical identities | Feed preserves brand/program scope and explicit operating-company links; no automatic parent inheritance | Pending |
| `/entities/company/compare` | `company_compare.html#compare-recent`: at most five recent trusted cards per company, with shared-reader links | Unified full-archive ANY-company feed; one-company/shared focus; explicit crop/destination/origin/market-context semantics | Pending |
| `/entities/company/{entity_id}/portfolio` | `company_portfolio.html`: recent moves and source mix | Shared scoped captured feed alongside portfolio; retain named variety relationships and claim status | Pending |
| `/competitors` with selected-company detail | `competitor_landscape.html`: registry, monitoring/current-coverage counts and selected detail | Accessible feed panel using actual selected cohort and crop/market scope; counts alone are not the feed | Pending |
| `/landscapes` default | `landscape_routes.py` / `landscape_workspace.html`: captured dated sources and external News handoff; handoff carries only one explicit company | Reusable in-view feed with multi-company semantics; do not depend on an external Today-only or live lane | Pending |
| `/landscapes?view=legacy` | `landscape_all.html`: recent moves links | Full scoped feed with all required filtering/actions/empty states | Pending |
| `/landscapes?view=feed` | Separate live tracked-company brief mode in `app/main.py` | Keep live lane labeled; add captured-archive access within the view | Pending |
| `/landscapes/berries/{berry_slug}` | `landscape.html`: recent-development region tables and recent-movement cards; region UI hides rows after five | Full archive filtering/pagination, company/destination distinctions, shared reader/state preservation | Pending |
| `/landscapes/explorer` | `landscape_explorer_routes.py` / `landscape_explorer.html`: graph and source panel/export | Shared contextual archive feed alongside graph, selected actors/crop/destination and enabling relationship explanation | Pending |
| `/landscapes/explorer?topic=gene-editing` | Same route branches to `gene_editing_landscape.html` | Shared feed preserving technology/program/crop applicability and verification distinctions | Pending |
| `/pulse/company/{company_id}` | Live Competitor Pulse plane | Captured-archive panel distinct from live research; opening comparison must not trigger paid research | Pending |
| `/whitespace` | Existing analytical landscape handoff target | Shared captured-feed scope consistent with chosen axes/crop/market | Pending |
| `/workspaces/{page_id}` with linked saved landscape/comparison | `living_workspace_routes.py`, shared feed endpoint and `workspace_landscapes.py` panel | Reuse feed/state/capture and SQLite revision checks; saved cited matrix snapshot does not silently rewrite on refresh | Pending |
| `/landscapes/explorer/briefing` and `/landscapes/explorer/export/{format}` | Snapshot/export views, not interactive archive browsing | Keep scope, assessment dates, statuses, rubric versions and citations in exports; return link to interactive scoped feed | Pending |

For each interactive route verify full-archive filtering before pagination; ANY selected company and separate Tags All/Any; one-company and shared-coverage focus; market context without named company; explicit enabling/relationship connections; origins distinct from destinations; honest global/unspecified scope; actual publication dates and independent event/first-seen dates; source-family dedup; original-source/read/save/capture actions; reading-position and filter retention; normal ingestion refresh; no silent override of reviewed assessments. Verify no matches, incomplete index and retrieval failure separately. A route with a live research widget or a recent-five table has not yet satisfied this contract.
