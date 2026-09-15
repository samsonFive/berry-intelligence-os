# Wave 1 bounded canary — plan and results

Date: 2026-09-15

## Safety envelope

- Five Sources, run one at a time.
- `--max-discoveries 5` applies before discovery persistence.
- `--max-items 4` bounds downstream processing for each run.
- Maximum possible: 25 discoveries and 20 body attempts.
- No known-blocked Source included.
- Extraction disabled; no publication or approval action.
- Runtime target: this worktree's gitignored `inbox/` only.

## Sources and measured results

| Source | Adapter | Role in canary | Observed | Persisted | Body attempts | Readable | Unusable | Drafts |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Advanced Berry Breeding News | article_rss | Existing configured-never-run official RSS | 10 | 5 | 4 | 4 | 0 | 4 |
| BerryWorld Newsroom | sitemap_xml | Existing official sitemap | 83 | 5 | 2 | 2 | 0 | 2 |
| Arkansas Agricultural Experiment Station News | article_rss | Public/university Source | 10 | 5 | 1 | 1 | 0 | 0 |
| Oishii Press Feed | article_rss | Newly configured official Atom feed | 30 | 5 | 3 | 0 | 3 | 3 |
| Fruitist Newsroom | sitemap_xml | Newly configured official sitemap | 42 | 5 | 1 | 1 | 0 | 1 |
| **Total** |  |  | **175** | **25** | **11** | **8** | **3** | **10** |

The three Oishii attempts were `navigation_only_shell`, non-retryable, and marked for manual acquisition. Their private drafts have no usable body. Successful discovery therefore leaves Oishii at maturity level 3, not readable or current.

All ten drafts remain `in_review`. Published or approved: **0**. Detailed per-attempt fields are in `canary-results.json`.
