# Monitoring roster and native News

The additive `company_set=all|watched` selector defaults to `all`. It is a
reference to a company universe, never an ID snapshot or an expanded comparison
cohort. `watched` resolves current company references from the existing shared
workspace Watch store. No GET seeds watches, marks them seen, collects content,
or changes trust. A Watch expresses interest; configured, never-run, blocked and
manual source states keep their existing distinct labels.

Comparison remains capped at five companies and four cultivars. Focus, pins,
standing scope and monitoring membership remain separate. Existing saved
investigations lacking `company_set` read as `all` without rewriting storage;
explicit invalid values remain invalid. Save/reopen resolves current membership.

## Read APIs

Both endpoints use the existing private investigation envelope and revision.
Transport extras are one decimal `limit` (1–100) and `offset` (0 through the
JavaScript safe-integer maximum); missing values default to 36/0 for News and
10/0 for monitoring. Duplicate, negative, fractional or excessive values fail.
Pagination bounds transport work and do not cap the stored monitoring universe.

`GET /api/investigations/v1/monitoring` returns `companies`, `total`,
`universe_count`, `matching_count`, `offset`, `limit`, `has_more`, `next_offset`,
`company_set`, `company_set_key`, `basis`, `watched_count`,
`unavailable_watch_count`, `search_basis` and `scope_note`.

Company rows contain canonical ID/label/type, identity status/note, authored
roles/berry IDs, `watched`, `in_scope`, existing monitoring state/detail and
scoped company-geography activity with exact relationship/source IDs, status,
review and material caveat. Source-health work runs only for the requested page.
Roster membership is not trimmed by berry, geography or publication dates;
`in_scope` describes the standing landscape. Nonempty `q` searches names/aliases
before pagination: `q_scope=scope` searches in-scope rows; `catalog` also finds
outside-scope rows. Empty search retains the entire selected company universe.

`GET /api/investigations/v1/news` returns the existing News card/source metadata
shape plus `company_set`, `company_set_key`, `basis`, `subject_count`,
`matching_count`/`total` and the same page fields. It uses the existing News
eligibility, publication-date order, review/trust labels, attribution and Reader.
Applied berry, source geography, actor roles and publication dates remain active.
Focus and comparison pins do not select this feed. Relationship predicates do
not filter News and are explicitly marked as not applied.

All-company mode applies no extra company filter, retaining eligible
unattributed industry News. Watched mode filters by the entire current Watch
company set before pagination. Empty, missing or wholly unavailable membership
returns an honest empty feed; there is no fallback to general News. A deeper
legacy News link explicitly does not carry the multi-company Watch filter.

The existing developments rail applies the watched universe first, then its
existing comparison-cohort/focus/scope precedence. Standing relationship
findings remain independent of monitoring membership and publication windows.

For `lens=news`, complete output uses `news_data(..., all_cards=True)` over that
same feed, including all pages and citations. Its `company_set_key` fingerprints
resolved membership, including unavailable Watch references, so changed Watch
membership invalidates the preview hash even when both feeds contain zero cards.
The key is output provenance, not a new store or saved member list.

## Real ten-company local model

The local modeling set reuses these active canonical identities. Only an
explicit isolated QA setup may add its Watch references; production is never
seeded automatically.

| Canonical company ID | Recorded company name |
| --- | --- |
| company-driscolls | Driscoll's, Inc. |
| company-fall-creek-farm-and-nursery | Fall Creek Farm & Nursery, Inc. |
| company-costa-group-holdings | Costa Group Holdings Pty Ltd |
| company-hortifrut | Hortifrut S.A. |
| company-planasa | Plantas de Navarra, S.A. |
| company-agrovision | Agrovision Corp. (Fruitist) |
| company-berryworld | BerryWorld Group |
| company-mountain-blue-orchards | Mountain Blue Orchards Pty Ltd |
| company-naturipe-farms | Naturipe Farms |
| company-wish-farms | Wish Farms |
