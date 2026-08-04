# Berry Intelligence OS

A local-first, evidence-based competitive intelligence platform for the global berry industry.

## Current status

This repository is the V1 foundation. It includes:

- canonical product vision and PRD draft;
- design-language specification derived from the approved platform mockup;
- evidence-first information architecture;
- JSON schemas and example records;
- a minimal FastAPI read-only prototype;
- a phased Claude Code build plan;
- initial Architecture Decision Records.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

To build the read-only static site (see `docs/07-static-deployment/STATIC-DEPLOYMENT.md`):

```bash
python scripts/build_static.py
python -m http.server 8080 --directory generated   # smoke test
```

## V1 operating model

1. Capture locally through the app or by dropping Markdown/JSON into an inbox.
2. Review and structure submissions.
3. Publish trusted JSON records.
4. Generate the newsfeed, entity pages, priority queues, and static web build.
5. Later add a secure hosted submission pathway without changing the trusted data model.

## Repository map

- `WELCOME.md` — product philosophy
- `docs/01-prd/PRD.md` — canonical product requirements
- `docs/04-technical-architecture/ARCHITECTURE.md` — implementation direction
- `docs/05-development-roadmap/BUILD-GUIDE.md` — Claude Code milestone plan
- `docs/06-claude-prompts/CLAUDE-CODE-STARTER.md` — first prompt to use
- `schemas/` — authoritative JSON schemas
- `data/` — versioned, trusted, published intelligence records
- `inbox/` — untrusted drafts and attachments captured through intake, created at runtime; excluded from the published feed and from schema validation until reviewed
- `app/` — local web application
- `scripts/build_static.py` — generates a deployable read-only static site into `generated/`
- `docs/07-static-deployment/STATIC-DEPLOYMENT.md` — how to build and deploy the static site
