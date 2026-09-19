# Berry breeding seed — 2026-09-18

High-recall research seed (151 records). **Not** a trusted competitor master.

The app loads `berry_breeding_entities.json` through `app.services.seed_roster`.
Repairs happen at read time:

- `monitoring_status` URLs are never imported as status
- `resolved_website` is not promoted to an official domain
- Candidate-review rows stay visibly unverified
- The six registry/source-system rows stay queryable and out of competitor counts
- Existing trusted `data/entities/companies/` records are matched, never overwritten
- Logo URLs stay discovery metadata (monogram in product)

Do not copy these rows into trusted `data/entities/` without a human Gate 4 review.
