# Claude Code Build Guide

## Milestone 0 — Repository foundation

Deliverables:

- repository structure;
- product docs;
- schemas;
- sample data;
- validation command;
- minimal read-only app.

Acceptance:

- app starts locally;
- sample feed renders;
- schema validator passes;
- no company-specific privileged entity is hard-coded.

## Milestone 1 — Read-only intelligence platform

Build:

- navigation shell matching the approved visual language;
- newsfeed;
- evidence detail page;
- company page;
- variety page;
- basic search and filters;
- reading/testing/commercial/monitoring chips.

Acceptance:

- adding a valid JSON evidence record and rebuilding makes it appear in the feed;
- linked evidence appears on company and variety pages;
- filters combine correctly.

## Milestone 2 — Local intake

Build:

- Add Intelligence modal/page;
- article/URL, note, upload-report, and standalone-fact pathways;
- draft files;
- attachments;
- local-only write controls.

Acceptance:

- a user can create a draft without editing JSON;
- original input is preserved;
- drafts never appear in the published feed.

## Milestone 3 — Review and structure

Build:

- split-pane review interface;
- metadata editing;
- entity match/create;
- proposed facts and relationships;
- duplicate warnings;
- priority rationale;
- publish action.

Acceptance:

- one evidence item can publish linked facts and relationships;
- publish updates feed and entity pages;
- every fact links back to evidence.

## Milestone 4 — Analyst workflow

Build:

- work queue;
- reading queue;
- testing queue;
- commercial-position queue;
- monitoring queue;
- strategic-question pages;
- signal pages.

## Milestone 5 — Static publication

Build:

- reproducible static-site generator;
- read-only deployment documentation;
- relative asset paths;
- validation that unpublished drafts are excluded.

## Milestone 6 — AI-assisted enrichment

Only after the manual workflow is stable:

- suggested summaries;
- entity extraction;
- fact proposals;
- duplicate suggestions;
- priority recommendations;
- signal clustering.

All AI output remains proposed until human approval.
