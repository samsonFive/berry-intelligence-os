# Mission 18 — Company tracking and manual logo acceptance

Continues from draft #290 final head `aa76992cc08aae7e1f40f1d25c0483d19bf17b93`. All four required checks passed, run `37066747850`: 3,602 passed / 11 skipped / two warnings in 289.55 seconds. The initial authoring caption failure remains documented in Mission 17. This is another bounded acceptance slice, not combined canonical release approval.

## Tier assignments

Directory and company profile tier controls offer Untiered, Tier 1, Tier 2 and Tier 3. Old watch classifications no longer appear as choices for an organization without that existing value. A stored Legacy watch or Muted value remains selected and explicitly labeled existing, alongside the four current choices. An unrecognized stored value remains selected with a correction hint; the existing backend rejects unsupported values rather than implicitly assigning Untiered. Users must explicitly select a current tier to replace it.

Legacy tier filters and existing POST compatibility remain intact across Directory, News, Map and Personal Digest. No migration, automatic tier assignment, favorite/list/watch change or canonical data write occurs. The display catalog derives choices without modifying the personal state. Favorites, tiers, lists and subject watches remain independent.

Phone tracking buttons/selects and the list disclosure now have at least 44px target dimensions. Desktop row density remains. All existing users of the shared company stylesheet use its new cache version.

## Manual logos

The existing Profile & links panel supports a public image URL and PNG/JPEG/GIF/WebP upload up to 2 MB. Browser review in the isolated loopback workspace saved the already-collected public Planasa logo URL as a manual override, verified the success status and reset control, then used Use collected logo. The exact original image URL returned, the reset control disappeared and unrelated profile links remained. No canonical record, company identity or human intelligence decision changed.

The browser file chooser stalled for approximately 161 minutes and exposed a fake-path value without any selected file. No save was attempted for that file selection; reloading cleared it. Do not treat this as browser-upload success or repeat the stalled picker as acceptance evidence. Multipart upload is independently verified by route integration tests with a tiny raster fixture, including private asset delivery, both new company views, unchanged canonical file bytes, reset behavior and retention of the original upload for recovery.

## Verification

Final company, logo, Personal Digest, News and Map test run: **71 passed / one existing reportlab warning in 22.12 seconds**. Seven new tracking cases cover current choices, both legacy states, an unknown legacy value, selected rendered markup, independent favorite/list state and retained change history. One new logo integration case checks the canonical company and new directory/profile. A first test fixture accidentally depended on an unavailable HTML parser package; it now uses the Python standard library. One intermediate command named a nonexistent test file and ran no tests; the final run above uses the actual Map workspace suite.

Canonical validation passed. Static build wrote **1,755 pages** with no unpublished IDs or titles. Exact-head draft CI remains required. Browser verified the four tier options on Directory and Profile, manual URL/reset, restored original logo and mobile containment. At 390px the page measured 375px; tracking targets were 44px high. Save/list widths were slightly smaller initially and have been increased to 44px; the star needed its more-specific width rule retained. Final measurements are recorded after review. Screenshots: `company-tracking-four-tiers-live.png`, `company-tracking-mobile-live.png`, `company-logo-manual-url-live.png`, `company-logo-restored-live.png`. Temporary viewport overrides are reset.

## Still open

Draft #291 exact head `2d3218736d37cecd99da4b583d40294dd5471834` passed all four required checks, run `37081601872`: 3,610 passed / 11 skipped / two warnings in 341.97 seconds. This verifies the slice, not the combined canonical release.

Final phone measurement after the width corrections: page 375px at a 390px viewport; star, Save and Lists targets 44×44px, tier select 83×44px. The final mobile screenshot reflects those measurements.

Browser file upload remains unverified because of the picker failure. This does not establish production persistence, per-account isolation, logo-history recovery UI or protected source-assisted profile/contact enrichment. Wider learning visuals, market statistics, geographic suggestions, source/body/media acquisition, fresh packet/receiving compatibility, specialist/static consistency and canonical integration remain in the durable requirements ledger. Prepare the tested release/rollback review; no merge/deployment without final approval.
