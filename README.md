# Berry Intelligence OS

A local-first, evidence-based competitive intelligence platform for the global
berry industry. Berry Intelligence is the first Domain Pack and reference
implementation of the broader Intelligence OS direction (see `docs/v2/`).

## Current status

The application is the working V2 reference implementation: an evidence-first
FastAPI app plus a recurring collection pipeline (source discovery, media
acquisition, transcription, and human-reviewed transcript→Atomic Evidence
extraction). Trust gates are always human: external sources → discovery →
publication review → trusted publication → AI *proposals* → Atomic Evidence
review → trusted Atomic Evidence.

## Requirements

- Python 3.12
- No credentials are required for ordinary development, tests, status, or the
  static build. External AI is optional and off by default (see below).

## Quick start (development)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt  # runtime deps + pytest
uvicorn app.main:app --reload        # http://127.0.0.1:8000
```

`requirements-dev.txt` installs everything needed to run the app and the test
suite. On Debian/Ubuntu, creating a virtualenv may require `python3-venv`.

## Testing

```bash
pytest
```

## Static site build

The read-only static site is generated into `generated/`:

```bash
pip install pagefind pagefind_bin    # required for the client-side search index
python scripts/build_static.py
python -m http.server 8080 --directory generated   # optional smoke test
```

`pagefind`/`pagefind_bin` are what CI installs for the full build; without them
the build still runs but skips the search index. See
`docs/07-static-deployment/STATIC-DEPLOYMENT.md`.

## Collection pipeline (read-only status first)

`collection_status.py` is a safe, read-only operator view — it never
discovers, downloads, transcribes, calls a model, or writes data:

```bash
python scripts/collection_status.py           # human-readable
python scripts/collection_status.py --json     # machine-readable
```

`scripts/run_collection.py` advances the pipeline one bounded step; `/review`
is where humans make publication and Atomic Evidence decisions;
`scripts/qualify_extraction_model.py` explicitly qualifies an extraction model.
See `docs/v2/COLLECTION-OPERATIONS-STATUS.md` and
`docs/v2/RECURRING-COLLECTION-RUNNER.md`.

## External AI (optional, off by default)

Semantic extraction is disabled unless explicitly enabled *and* backed by an
explicitly qualified model; nothing turns it on implicitly. Extraction only
ever creates *untrusted* proposals that still require human review.

High-level configuration (all optional environment variables):

- `BIOS_MODE` — `authoring` (default) enables local write/review; `readonly`
  disables write endpoints.
- `BIOS_RUNTIME_DIR` — optional runtime root containing `data/` and `inbox/`
  (used by the remote interactive demo container).
- `BIOS_REMOTE_INTERACTIVE` — when `true`, require HTTP Basic Auth
  (`BIOS_REVIEW_USERNAME` / `BIOS_REVIEW_PASSWORD`, no defaults) for the
  interactive app. `/healthz` stays public. See
  `docs/07-static-deployment/REMOTE-INTERACTIVE-DEMO.md`.
- `ENABLE_SOURCE_POLLING` — opt-in background source polling (off by default).
- `BIOS_EXTRACT_BASE_URL` / `BIOS_EXTRACT_MODEL` / `BIOS_EXTRACT_RESPONSE_FORMAT`
  — OpenAI-compatible (e.g. local LM Studio) extraction settings.
- `BIOS_EXTRACT_API_KEY` — optional key env var name for the local/compatible
  extraction endpoint.

An optional external-AI gateway (`app/services/ai_gateway/`) can route
extraction through Perplexity. It is provider-neutral to domain code and stays
off unless explicitly selected. Three distinct provider identities exist:

- `openai-compatible` — the local/LM Studio path (default; unchanged).
- `perplexity-agent` — Perplexity's Agent API (`POST /v1/agent`), the
  multi-provider path: one `PERPLEXITY_API_KEY` selects an exact frontier model
  from OpenAI, Anthropic, Google, xAI, Perplexity, etc. This is the intended
  first external qualification path. Extraction is closed-book: no tools, no
  model fallback array.
- `perplexity-router` — Perplexity's Router API for Perplexity-hosted
  open-weight models. Router is currently a **private preview**: an ordinary
  Perplexity key does not necessarily have Router access, and a `403` from
  Router usually means the account lacks preview access (not that the key is
  invalid). Router is optional and never the default.

Select a Perplexity provider explicitly, e.g.
`python scripts/qualify_extraction_model.py probe --provider perplexity-agent --model <id>`.
Discover current Agent model ids with `python scripts/ai_models.py --provider perplexity-agent`
(read-only `GET /v1/models`; nothing is persisted). Qualification is per exact
routed model — switching the model invalidates it.

Perplexity configuration (all optional):

- `BIOS_PERPLEXITY_MODEL` — the exact routed model id to use.
- `BIOS_PERPLEXITY_AGENT_BASE_URL` / `BIOS_PERPLEXITY_BASE_URL` — Agent / Router
  base URLs (defaults point at the official endpoints).
- `BIOS_PERPLEXITY_MAX_OUTPUT_TOKENS` — Agent output cap (default 8192; the
  Agent API requires a positive value for `anthropic/*` models).
- `PERPLEXITY_API_KEY` — read from the environment at call time only. It is a
  runtime secret: never written to a file, provenance, status, review, or the
  static build. The Search and grounded-research clients are dormant
  infrastructure seams, separate from extraction and not wired into collection.

## Runtime state and ignored directories

Runtime, untrusted, or disposable state is created on demand and kept out of
Git (see `.gitignore`): `inbox/` (drafts, discovered media, transcripts,
operations, qualifications), `generated/` (static build), and `review/*`
(review exports, except the one committed backlog snapshot). A fresh clone
starts with empty runtime state; the app and status commands handle that
safely.

## Repository map

- `WELCOME.md` — product philosophy
- `docs/v2/00-README.md` — V2 / Intelligence OS documentation entry point
- `docs/01-prd/PRD.md` — canonical product requirements
- `docs/04-technical-architecture/ARCHITECTURE.md` — implementation direction
- `docs/07-static-deployment/STATIC-DEPLOYMENT.md` — static build and deploy
- `schemas/` — authoritative JSON schemas
- `data/` — versioned, trusted, published intelligence records
- `app/` — local web application and services
- `scripts/` — operational CLIs (`collection_status.py`, `run_collection.py`,
  `qualify_extraction_model.py`, `build_static.py`, `export_for_review.py`, …)
