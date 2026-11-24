# Version 1 file contracts

All packages use UTF-8 JSON, `schema_version: 1`, and a `kind`. See the complete working files in `samples/`. File import is local only. Dates use `YYYY-MM-DD`; IDs must be stable strings containing letters, numbers, periods, underscores, hyphens, or colons, starting with a letter or number. Unknown fields are not carried into the normalized workspace.

## Directory package

```json
{
  "schema_version": 1,
  "kind": "directory",
  "exported_at": "2026-11-18T09:00:00-08:00",
  "title": "Company and variety directory",
  "companies": [{
    "id": "company-001", "name": "Example company", "country": "Spain",
    "aliases": [], "roles": ["Grower"], "berries": ["blueberry"],
    "description": "Company description", "activity_geographies": ["Morocco"], "tags": ["Fresh market"], "website": ""
  }],
  "varieties": [{
    "id": "variety-001", "name": "Example variety", "berry": "blueberry",
    "company_ids": ["company-001"], "aliases": [],
    "description": "Variety description", "activity_geographies": ["Morocco"], "traits": [], "tags": []
  }]
}
```

Directory imports replace the directory. Every linked company must exist in the same package. Existing real tasting sessions may not be orphaned: the replacement must retain their varieties. Fictional sample scores are cleared when the first directory is imported. `berry_ids` is accepted as a company alternative to `berries`, removing a `berry-` prefix. Geography is supplied explicitly; the app does not infer countries from text. `country` means company headquarters; optional `activity_geographies` lists recorded operating markets or variety activity locations. Missing activity arrays default to empty for older version 1 packages. The Either/HQ/Activity filter never treats an associated company's headquarters as a variety growing location. Traits and associations should carry only information suitable for distribution.

## Newsletter package

```json
{
  "schema_version": 1,
  "kind": "digest",
  "issue": {
    "id": "digest-2026-11-18", "date": "2026-11-18",
    "title": "This week in berries", "editor": "Intelligence desk",
    "intro": "The stories selected for this edition.",
    "items": [{
      "id": "article-001", "title": "Selected article headline",
      "summary": "A distribution-ready summary.", "source": "Publisher",
      "source_url": "https://example.com/story", "published_date": "2026-11-17",
      "category": "Genetics", "berries": ["blueberry"],
      "company_ids": ["company-001"], "tags": ["Breeding"],
      "editor_note": "Context intended for the company newsletter.",
      "status": "Curated selection"
    }]
  }
}
```

One file represents one complete edition, preserving its supplied story order. A matching issue ID replaces the edition; a new ID adds it. An empty `items` array is valid. Item IDs must be unique within an issue. Stories without IDs receive position-based IDs; exporters should supply stable source IDs. The first real issue replaces the fictional demo newsletter. Sources and dates remain visible; missing dates are not inferred. Source URLs must be HTTP(S), with no embedded credentials.

The `issue` wrapper is optional if the issue fields are at the top level. `cards` is accepted as an alternative to `items`, and a card can wrap source fields in `record`. Field aliases include `source_name`, `url`, `excerpt`, `why_it_matters`, and `berry_ids`. These conveniences are **not** a full personal-digest exporter; the export must still supply issue ID, title, and date. It must include all selected stories, not just a paginated UI page.

## Flavor package

```json
{
  "schema_version": 1,
  "kind": "flavor",
  "scores": [{
    "id": "session-001", "variety_id": "variety-001", "panel": "panel-1", "date": "2026-11-18",
    "sample": "Lot A, 3 days after harvest", "panel_size": 12,
    "scale_min": 1, "scale_max": 9,
    "overall_liking": 7.4, "taste": 7.2, "texture": 7.8, "appearance": 7.1,
    "brix": 14.2, "acidity": 0.65, "acidity_unit": "% titratable acidity",
    "notes": "Optional sampling and storage notes."
  }]
}
```

Flavor CSV uses those same columns with a header row. The sensory categories are **Overall liking** (`overall_liking`), **Taste** (`taste`), **Texture** (`texture`), and **Appearance** (`appearance`). **Brix** (`brix`) and **Acidity** (`acidity`, with `acidity_unit`) are separate measurements. `panel` is required and must be `panel-1`, `panel-2`, `panel-3`, or `panel-4`. The labels are provisional until the real panel names are supplied; `Panel 1` and equivalent forms are normalized. CSV headers with spaces are normalized to underscores.

Quoted commas, double quotes, and multiline notes are supported. `id` and `sample` are recommended. `variety_id`, panel, date, and overall liking score are required. Panel size and other measurements can be blank. If supplied, panel size must be a positive integer. Sensory scale defaults to 1–9 when omitted; set it explicitly for production data. Sensory scores must fit that scale. Brix is stored in degrees Brix, from 0–100; acidity is nonnegative and retains the supplied unit without conversion. The earlier `overall` key is accepted as an alias for `overall_liking`, and `bricks` is accepted as an input alias for `brix`. No acidity method is assumed when its unit is missing.

Import the associated directory first. Tasting rows merge by ID: corrections replace the matching record, and new IDs add records. Reimporting a file does not double-count it. If ID is missing, one is derived from variety ID, panel, date, and sample; distinct records on the same day within one panel therefore need distinct sample labels or explicit IDs. A shared ID cannot overwrite a different panel's record. Duplicate IDs within one upload are rejected. The first real score import replaces fictional sample records.

The chart shows each recorded score separately, labeled with panel, variety, date, and scale. **No panel averages, pooled scores, or shared summary values are calculated.** The table can show all four panels together or filter to one panel; variety history groups panel records separately. This is a container for supplied values, not a sensory-processing pipeline. More detailed processing, panel definitions, and scorecard protocols can be added later. Physical measurements never enter sensory score fields or share their scale validation.

## Workspace backup

Use **Export workspace** to create a `kind: workspace` JSON file with directory, scores, newsletter issues, demo markers, and import history. Restoring this file replaces the complete workspace after validation. A publisher can embed this export in a standalone HTML release using `package.cjs`. The backup may contain all imported content; distribute it only to the intended internal audience.

## Failure and replacement behavior

Validation happens before persistence. Unsupported versions, malformed JSON/CSV, broken flavor links, duplicate IDs, and out-of-range scores leave the existing workspace unchanged. Directory replacement is deliberate and documented; export a backup before replacing it. Files exceeding 10 MB are rejected. Storage quota failures preserve the previous workspace and display an error. If browser storage is unavailable from startup, a visible temporary-session warning appears.

## Weekly public research extension (viewer 1.2 / package 2)

Schema version 1 workspaces may also include `as_of` (snapshot YYYY-MM-DD), `activity`, `assets`, `asset_omissions`, and `changes`. Older workspaces default to empty containers. Company records may include `socials: [{platform, url}]`.

Activity records have stable `id`, title/summary, source/source_url, category (`news`, `social`, `jobs`, `communications`, `other`), source_type, published_date/captured_date, company_ids/variety_ids/berries, review status, confidence label, caveats, optional job_status, and availability (`stored_current` or `retained_archive`). Missing dates are not replaced by the export date. The 90-day view uses publication date when present, otherwise capture date; undated records remain in the archive.

Assets have stable `id`, entity_ids, kind/title, source_url/attribution, MIME, SHA-256, a safe content-derived relative path, and embedded raster/PDF bytes as a validated base64 data URL. Limits are 2 MB per file and 5 MB total portable asset bytes. HTML and SVG are excluded. Omissions record entity/asset ID, title, source URL and reason. Local asset bytes and their separate ZIP file copies permit future hosting adaptations without live image requests.

Changes record the baseline ID/basis, scope-change flag and items with container, stable ID/title, change kind and changed field names. No-longer-exported, outside-scope and unavailable assets are distinct; none asserts a job closure.

`content/research.json` has `kind: research` and the same public workspace fields, with scores empty. Importing it replaces research and preserves real corporate scores, rejecting orphaned variety references. `content/workspace.json` remains a complete research-only backup for the platform/publisher, with scores empty. A corporate workspace with scores must never be uploaded to the platform; export the research-only backup instead. The corporate supplement is the existing `kind: flavor` JSON and is merged solely by the corporate publisher.

## HTML-only delivery update (package 3 / viewer 2.0)

The current corporate page is generated HTML, not a JSON/CSV importer. Legacy JavaScript import contracts above remain data reference only. The standard-library Python publisher reads research workspace JSON and optional corporate settings/flavor JSON. Publish the complete folder.

Research workspaces may contain `reports`: records with id/title/date/summary/status, passive sanitized html, and files with name/extension/base64 (PDF/XLSX only). Report selection is explicit and remembered in the platform export settings; changing it controls which report pages/downloads are generated.

Corporate settings are separate: `{"schema_version":1,"kind":"corporate_site","tiers":{},"projects":[]}`. Tiers map known company IDs to tier-1/tier-2/tier-3/unassigned. Variety filtering matches associated-company tiers. Projects have id/title/summary/status/owner/tasks and optional html/html_file. Task rows have title/owner/due/done. html_file must be a bounded .html file inside the corporate settings folder. Active embeds/scripts and imported global styles are stripped; only embedded raster images are retained inside imported snippets. These corporate fields are never part of research-platform inputs or exports.

No browser uploads, storage, persistent edits or scripts are required or offered. Native CSS radio filters, details and checkboxes provide temporary view interaction. Shared project edits and tier changes are saved by updating corporate source files and regenerating/publishing. Use a fresh staging folder so deselected reports cannot linger.
