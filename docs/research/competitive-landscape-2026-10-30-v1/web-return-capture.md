# Perplexity web return capture

The user authorized web-UI execution and the specific combined public-only pack upload. Browser actions remain manual UI automation; these local helpers do not access browser profiles, hidden APIs, credentials or remote services.

1. Download each completed answer's original PDF and every accessible table as CSV. A completed research phase can precede answer generation: wait for the completed answer controls and absence of Stop response. Never reload an unfinished answer.
2. Run `python scripts/capture_competitive_web_returns.py`. It copies only the observed export filename families after the first known export into private `inbox/competitive_landscape/web-research-2026-10-30/raw/`. Hashes make repeated capture idempotent. Unrecognized/ambiguous batch identities remain unresolved. For PDFs with generic names, explicitly preserve the observed download under its batch and register its original hash in the capture manifest; do not infer a batch from download order.
3. Run `python scripts/assemble_competitive_research_returns.py`. It verifies raw hashes, reconstructs readable Markdown, and creates untrusted candidate records. Uniform empty trailing export columns are excluded only from the candidate mapping; original bytes remain intact. Malformed rows, conflicts and missing references stay visible. Source passages, Unknown values, numeric precision and units are preserved.
4. Review the original answer, metadata and resolution queue. Prose metadata and split or additional tables require inspection. Candidate counts are not verified source coverage. Inspect original cited pages before source validation or any application assessment.

Wide Perplexity PDF exports can physically clip columns. PDFs are archival originals; use complete CSV tables for reconstruction. All raw returns and candidate records remain gitignored. These helpers neither publish evidence nor produce ratings, and they are not the Stage 2 application importer. Analyst decisions and runtime application state are untouched.

The October 30 run captured B01–B15 before the service's monthly Deep Research limit. B16 returned no findings; B16–B46 and the two follow-ups remain queued. See the [status receipt](../../v2/COMPETITIVE-LANDSCAPE-EVALUATION-STATUS.md) and private `run.json` for continuation state.
