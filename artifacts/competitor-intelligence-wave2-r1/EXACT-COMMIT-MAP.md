# Exact commit map

| Role | Commit | Subject / disposition |
|---|---|---|
| R1 base | `85a157233674ee5cd3d2e358ea02924d3ac04790` | Reconcile competitor intelligence wave 2 |
| Static-link fix already in base | `fe46718116de764d1f02a49fdc8dfc1e42414d11` | Fix static links with query strings; direct parent of the R1 base |
| Claude profile base | `516f1ee74a369fb59e0563341a0b9d75da6edf9e` | Competitor Profile Data Service V1 |
| Claude frozen source | `25e109081992b47debf87d526afa45cd9d6a4a8c` | Refine competitor profile completeness into 7 separated concerns |
| Integrated Claude commit | `ad8a08ecd6a17715231e6838bacec5d9ce763a4f` | Clean cherry-pick of the exact Claude source commit onto Wave 2 |

The source-to-integrated patch is unchanged. The new Git SHA is expected because the parent changed from Claude's profile branch to the Wave 2 integration head.

Excluded by design:

- `origin/prototype/product-visual-system-v1` is not an ancestor of this branch and no commit from it was integrated.
- No Wave 3 branch or commit was integrated.
- No inbox, canary, generated, credential, or temporary readable-content fixture path is tracked.
