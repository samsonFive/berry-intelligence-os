# Combined release rehearsal

The approved redesign stack now starts as an authenticated Docker application on the existing trusted host, with separate persistent review data and no public port. Restart, verified backup, empty-target recovery and the previous production image were exercised on isolated copies. The live application was not replaced or restarted. This is preparation for release review, not deployment approval.

## Evidence from October 5, 2026

| Check | Actual result | Scope |
| --- | --- | --- |
| Tested application commit | `8be0d39614f3c867f8a93dbcf2da216c191de617` | #311: all four required checks; 3,893 passed / 11 skipped / two existing warnings, run 37338997850 |
| Canonical reconciliation | `916b8f09f9ce2a1847335d7990ea80ff921f1cec` is an ancestor; expansion guide unchanged | No historical draft was merged or closed |
| Package identity | 3,470 files matched committed Git blob bytes | SHA-256 `83b52c2a946b64b1e54086ee3a4ef35e398ebfd67b291cdaaae79d9c4bb782ae` |
| Application authentication | Unauthenticated News redirected to login; existing host-local session settings authenticated successfully | Credentials stayed on the trusted host; no new public access |
| Consolidated pages | News, Map, Companies, Varieties, Learn, Digest, Briefings, Landscape, Monitor, Operations, Guide and news packets returned authenticated HTTP 200 | Route smoke, not proof of every interaction |
| Operator state | Favorites, Tier 2 and a custom company list saved through real authenticated endpoints | Isolated rehearsal state only |
| Persistent restart | Candidate became healthy again; operator marks/list and an edited existing company record remained byte-identical | Additive startup did not replace existing record content |
| Backup and recovery | Verified archive restored into a new empty target; all 2,798 restored files matched the manifest hashes | Separate review runtime; no production restore |
| Previous-image rollback | Existing production image started on a restored review copy; login gate and health worked, operator records preserved | Previous image exercised without touching live mounts |
| Live preservation | Container ID, image, start time and exact mount settings remained unchanged | Mounts compared by destination because Docker list order varies |
| Visual guide | Actual desktop sections, workflow diagram and five report/export explanations inspected; 390-pixel phone contained, viewport reset | Current isolated browser preview, screenshots below |
| Manual logo upload | Native chooser selected a PNG; Save showed “Uploaded logo saved” and the company image; reset showed “Logo override cleared” | Test brand icon used only in the isolated profile, then removed |

The first package failed to start because Git's Windows `core.autocrlf` setting converted archived shell-script bytes. The corrected package explicitly disables that conversion and verifies every file and executable bit against the commit. `scripts/package_release_candidate.py` makes this repeatable; its regression test uses a Windows-style Git configuration and an uncommitted edit, checks committed Linux bytes, excludes even a committed private inbox fixture, and preserves any existing output package.

Final focused package/backup/guide validation: **17 passed**, one existing ReportLab warning, 15.15 seconds. The new packager was also run against the actual application commit and reproduced the byte-verified 3,470-file package/hash above. Fresh required CI on this release-review head remains necessary.

Recovery initially compared the Docker mount array in its unstable presentation order. The final comparison uses exact destination/source/options independent of order. A second byte comparison after starting the old application was too broad: startup writes its own synchronization metadata. A new empty restore was verified before any startup, and operator records were separately checked after rollback. These are distinct checks; backup integrity does not imply that all generated runtime metadata is immutable.

![Analyst workflow](../../artifacts/design-sprint/release-guide-workflow.png)

![Reporting capabilities](../../artifacts/design-sprint/release-guide-reporting.png)

The upload screenshot uses a test icon, not a researched company logo: [native upload proof](../../artifacts/design-sprint/release-native-logo-upload.png). [Phone guide](../../artifacts/design-sprint/release-guide-phone.png). The previously reviewed [refined five-page report](../../artifacts/design-sprint/report-export-refined.png) remains the report-design evidence; these guide images do not replace it.

## Release sequence after the remaining acceptance checks

1. Finish the combined native Map/snapshot and packet fresh-capture/review-mode/receipt checks, and audit the remaining requirement rows against current evidence. Keep sparse statistics, unavailable article text/media and unresolved photo identities explicit.
2. Fetch canonical again. Preserve the governing guide, reconcile any new changes, push the final candidate and require successful Change scope, Repository integrity, Static public safety and Python tests on that exact head. Do not substitute earlier slice results for final-head checks.
3. Produce the final committed package with `python scripts/package_release_candidate.py --ref <verified-head> --output <new-private-package-path>`. Record its returned head and hash, verify the transferred hash and build a separate versioned image. Keep runtime, credentials and private data out of the package and PR.
4. Before approved production change, create and verify a fresh consistent backup of the actual deployed data and inbox under the shared pipeline lock. Record the previous image, code SHA, configuration and mount identities privately. The review backup above is not the production backup.
5. Present the tested release, capability limits, final-head CI and rollback evidence for the user's final merge/deploy approval. This mission does not grant that approval.
6. Only after approval, keep the existing persistent production mounts, login configuration and one application worker. Code deployment must not copy a local inbox or replace operator data. Additive seed synchronization preserves existing records; do not silently promote proposed records or replace changed canonical/runtime files.
7. Verify login, core routes, selected operator state, human review gates and provider configuration after the approved deployment. Restore the previous image if application health/regressions fail. Restore data only for an actual data regression using the verified predeployment backup and an explicit safe recovery procedure; never overwrite a live runtime casually.

## Still required before declaring the full goal complete

The combined native Map/snapshot and packet fresh-capture/receipt checks, final requirement-by-requirement release audit, and exact-head final candidate CI remain. The supported runtime remains one shared analyst workspace and one worker. Human source/publication/statement/identity/market-figure decisions are retained, not automatically completed. No provider keys were enabled or paid research started in this container rehearsal. Additional licensed visuals and geographic source coverage remain ongoing content work with honest empty states. Nothing has been merged or deployed.
