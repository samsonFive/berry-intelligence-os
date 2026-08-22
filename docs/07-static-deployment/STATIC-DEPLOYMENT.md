# Static Publication (Milestone 5)

## What it is

`scripts/build_static.py` renders a self-contained, read-only copy of the
published intelligence into `generated/`. It reuses the exact same Jinja
templates as the live app, so the static build looks and reads identically
to the live app's read-only pages — it just has no server behind it.

## Building

```bash
python scripts/build_static.py
```

This wipes and recreates `generated/`, then:

- reads only `data/` (trusted, published records) — it never opens `inbox/`;
- writes one HTML page per published evidence record, entity, entity-type
  listing, priority queue, strategic question, and signal;
- copies `app/static/app.css` and any evidence attachments under `data/attachments/`;
- rewrites every internal link to be relative to the file that contains it;
- builds a client-side search index over the generated pages (see
  "Search" below) if Pagefind is installed;
- runs an automated check that no draft id or draft title from `inbox/`
  appears anywhere in the generated HTML, and fails the build (non-zero exit,
  printed diagnostics) if it finds one.

### Search

The static build ships with real search, not just browsing. It's built with
[Pagefind](https://pagefind.app) — a client-side search engine: it indexes
the generated HTML at build time and runs entirely in the visitor's browser
afterward, no server or external service involved. That keeps it consistent
with this project's avoid-proprietary-SaaS-dependency stance (ADR-0001) and
means it costs nothing to run.

Enable it locally:

```bash
pip install pagefind pagefind_bin
python scripts/build_static.py
```

If Pagefind isn't installed, the build still succeeds — it just prints a
note and skips the index, so a working (searchless) site is still the
default with zero extra setup. The GitHub Actions deploy workflow always
installs it, so the deployed site always has search; a Pagefind failure
*there* fails the build, since search is expected to work on the real
deployment.

Re-run the command any time published data changes — the output is fully
reproducible from `data/` and disposable; deleting `generated/` never loses
any knowledge, matching the "Rebuild guarantee" in `ARCHITECTURE.md`.

## Deploying anywhere, at any subpath, with zero configuration

Every link in the output is relative (e.g. `../../evidence/ev-123/index.html`),
computed from how deep the containing file is nested. There is no absolute
`/`-rooted path anywhere in the generated HTML. That means the `generated/`
folder can be:

- served from the domain root of any static host, or
- served from a subpath (e.g. a GitHub Pages project site at
  `https://user.github.io/berry-intelligence-os/`), or
- opened straight off the local filesystem with `file://`,

— all without changing the build command or any configuration. Just copy the
folder wherever it needs to live.

### Smoke-testing locally

```bash
python -m http.server 8080 --directory generated
```

Then open `http://localhost:8080/`.

### Common hosts

- **GitHub Pages / Netlify / Vercel (static)**: point the deploy at the
  `generated/` folder (or its contents) as the publish directory.
- **S3 + CloudFront (or any object storage)**: upload the contents of
  `generated/` as-is; no rewrite rules are required because every page is
  `.../index.html` and every link is relative.

## What's intentionally excluded

Per the architecture's runtime modes, a static build is read-only: it never
includes intake, review, or signal-creation pages, since those require a
server to accept writes. Concretely:

- `/intake`, `/review`, and `/signals/new` are not generated.
- The "Add Intelligence" button renders disabled, and the "Review Queue" nav
  item is omitted, exactly as they already do in the live app when
  `BIOS_MODE=readonly`.
- The newsfeed's *filter form* (`?berry=`/`?region=`/etc.) is omitted, with
  a note pointing back to the local app — there's no server to interpret
  those query params on a static host, so a form that silently did nothing
  would be misleading. Free-text *search* is not in that category: it's
  replaced with the Pagefind search box described above, which is fully
  functional on a static host because it runs client-side. Browsing every
  published evidence, entity, queue, strategic question, and signal page
  still works fully either way.

## Validating draft exclusion

`scripts/build_static.py` calls `validate_no_drafts_leaked()` after every
build, which scans every generated HTML file for any id or title belonging
to a record still sitting in `inbox/`. This is exercised directly in
`tests/test_build_static.py`, including a test that deliberately injects a
leaked draft reference to confirm the check actually catches it (not just
that it returns an empty list by construction).
