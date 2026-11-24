# HTML-only corporate viewer export

Implemented in feature/export-to-viewer-20261123, based on the canonical platform. Source changes are not merged or deployed. Corporate SharePoint hosting is not configured.

## Delivery decision

The current delivery is a complete multi-page HTML folder with inline CSS and local assets. There is no browser JavaScript, API access, external stylesheet, browser storage or JSON/CSV processing in the corporate page. The earlier JavaScript single-page viewer is a legacy prototype, not the current publishing target.

Native HTML/CSS supports tier/berry/geography/initial filtering, A–Z/Z–A sorting, sticky grid headers/names, ordinary profile links, collapsible sections, recent/archive views, and temporary checkbox interaction. Text search uses browser Find. Script-based column resizing, in-browser imports and persistent browser editing are not offered. CSS relational selectors (:has) need support in the corporate browser/page wrapper; if unsupported, all data remains readable and page links still work. Actual SharePoint acceptance remains outstanding.

## Corporate ownership

Company tiers, project pages and flavor records stay entirely corporate. They are not fields uploaded to the research platform. Weekly research files cannot overwrite those authoritative corporate files.

- `corporate-site.json`: schema_version 1, kind corporate_site, tiers keyed by stable company ID and a projects list. Accepted tiers: tier-1, tier-2, tier-3, unassigned. The default is Unassigned; no platform/watchlist tier is copied. Variety lists, profile headings and associated-company/portfolio cards use the tiers of their associated companies, without creating an independent variety tier.
- Each project has a stable ID/title, summary, status, owner and tasks (title/owner/due/done), with optional HTML content. `html_file` can name a confined .html file within the corporate settings folder. The publisher retains passive HTML and safe inline element styles; active embeds, scripts, remote images and global imported styles are removed. Native details and checkboxes work without JavaScript. Checkbox changes are temporary visual marks. Shared saved progress requires updating corporate source files and republishing.
- `corporate-flavor.json`: the existing version 1 flavor supplement. Each supplied row and panel remains separate. It is displayed only when supplied. Unknown company or flavor-variety IDs block the build rather than silently discarding assignments or records. Flavor data is not averaged and never goes to the platform.

## Weekly workflow

1. Open **Export to viewer** from Digest, Companies or Varieties. Reuse the previous research export. Any uploaded baseline must be research-only, without flavor scores.
2. Choose directory coverage. Company and variety profiles include eligible stored public-source activity independently of newsletter selections. Profiles default to the 90 days ending the snapshot date; older and undated records remain in the full archive.
3. Select newsletter stories and edition metadata, or omit a new edition. Existing editions are retained and repeated IDs revise an edition.
4. Under **Expose reports internally**, select the reports intended for company readers. Selections are remembered for the next export. Finished library reports include a passive HTML view and their available PDF/XLSX downloads. Saved report drafts export stored section prose with draft/AI-assisted labels; no research is regenerated, provider metadata or raw caches are copied. Missing/unavailable report selections block rather than silently substituting other content. Deselecting a report removes it from the next site release.
5. Preview counts, selected reports, changes and asset omissions. Download the complete package.
6. On corporate systems, combine the incoming research snapshot with the corporate files using the included publisher:

```
python publisher/static_site.py --workspace content/workspace.json --corporate corporate-site.json --flavor corporate-flavor.json --output new-staged-site
```

Omit --flavor when absent. Use a new empty staging directory. Preserve corporate source files outside this directory. The published page uses no Python runtime; Python is only the offline build tool and does not make network calls.

7. Validate the new folder, keep a rollback copy, publish the complete tree through the approved SharePoint process, and retire files absent from the new manifest. Do not overlay files indefinitely: that could leave deselected reports accessible. Confirm relative links, assets/downloads, inline CSS and native filtering on the actual corporate site.
8. Only after verification, confirm the generated release as published in the platform. That becomes the next change baseline. This confirmation does not deploy anything.

## Package version 3 / viewer 2.0

```
site/index.html               company directory with corporate tier filters
site/varieties.html           variety directory with associated-company tier filters
site/company-<stable-hash>.html
site/variety-<stable-hash>.html
site/newsletter.html
site/projects.html
site/project-template.html
site/reports.html
site/report-<stable-hash>.html selected reports only
site/report-files/            selected report PDF/XLSX files
site/assets/                  verified local raster/PDF bytes and brand logo
content/workspace.json        complete research-only snapshot, scores empty
content/directory.json
content/activity.json
content/assets.json
content/reports.json
content/digest.json            when adding/revising an edition
manifest.json                 package versions, counts and SHA-256 file hashes
changes.json / CHANGELOG.md
asset-omissions.json
publisher/static_site.py       standard-library corporate build tool
publisher/driscolls-logo.png
corporate-site.example.json    first-publication example, never a replacement for corporate settings
corporate-company-ids.csv      stable ID/name lookup for corporate tier assignment
PROJECTS-AND-TIERS.md
START-HERE.md / COPILOT-HANDOFF.md / DATA-FORMATS.md
```

Publish the complete folder, not index.html alone. Selected report downloads and company/variety profile pages use safe stable filenames. Every generated HTML page contains its CSS inline; no scripts are included. No corporate tiers/projects/flavor file is included in a research-platform release. Corporate-only project and flavor pages are generated by the corporate publisher when those inputs exist.

## Data and change rules

Source/review/confidence labels and original publication/capture dates remain distinct. News, social posts, job listings, public communications and other records have separate profile sections. Unknown source types remain Other. A captured job is not proof of a current vacancy; absence is not proof company activity ceased. Older missing source records may be retained as labeled archive snapshots; explicit private/inactive/source-deletion exclusions win over retention.

Recorded public logo/image/document URLs may be retrieved during platform export preview. Existing media policy and source restrictions are respected. Non-logo discovery images are not presented as company logos; obvious social UI icons are excluded. Unavailable, unsupported and over-budget assets are reported individually. No source-body scraping, logo discovery, AI generation or canonical evidence mutation occurs.

Change comparison uses the last confirmed published research snapshot, otherwise the previous generated one with an honest label. Additions, updated fields, no-longer-exported items, scope changes and unavailable assets are separate. Generation timestamps/list-order noise do not count as content changes; newsletter ordering does. Reports participate in comparison. Corporate tier/project/flavor changes are administered in the corporate repository and are not tracked back on the research platform.

## Limits, privacy and verification

Current research workspace limit: 10 MB; upload request: 22 MB. Raster/PDF assets: 2 MB per file, 5 MB total. Selected report files: 10 MB each, still subject to the overall workspace limit. These are explicit portable limits, not a claim every recorded asset fits. Assets/report downloads use local files; only deliberate source links leave the viewer.

All platform export controls require existing authentication, authoring mode, same-origin forms and account-scoped private/no-store snapshots. Personal subscriptions, reading activity, private annotations, raw article/transcript bodies, credentials and prompts do not enter the release. Selected report prose is intentionally shared by the operator; it is not treated as reviewed evidence. Protect all files through corporate hosting access controls.

Tests cover report opt-in/removal and real downloads, stored prose and metadata exclusion, HTML sanitization, CSS/native-controls markup, corporate tier inheritance, corporate flavor isolation, orphan blocking, account isolation, stale previews, publication confirmation, archive/deletion behavior and package integrity. Browser checks exercised native berry/geography filtering and the project template. Final PR-head CI and actual SharePoint testing remain required before deployment.
