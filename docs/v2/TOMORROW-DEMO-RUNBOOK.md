# Tomorrow morning demo runbook

5–7 minute live demo of Berry Intelligence OS using **real persisted records**.
Do not invent data. Do not auto-approve. Do not present untrusted AI as accepted intelligence.

Tracked copy of this file: `docs/v2/TOMORROW-DEMO-RUNBOOK.md`.
Runtime copy (gitignored): `inbox/operations/TOMORROW-DEMO-RUNBOOK.md`.

## BEFORE DEMO CHECKLIST

- Branch: `cursor/tomorrow-demo-readiness-bd27` (do not demo from canonical `v2/intelligence-os` until this is merged).
- Start server: `uvicorn app.main:app --reload` from the repo root (venv activated).
- URL: http://127.0.0.1:8000
- Runtime artifacts needed (local `inbox/`, gitignored):
  - 16 publication drafts in `inbox/evidence/`
  - 19 screened discovered items in `inbox/discovered_media/`
  - Ready staged transcript for the Peru El Niño episode under `inbox/discovered_media/_normalized_transcripts/`
- API dependency: **none** for Scanner, triage, publication review, newsfeed, or landscape.
- Perplexity/Haiku is **not** required during the demo. Do not call extraction.
- Safest first record: `ev-media-cfc3cc9f97414c09c483` — *How Peru is Preparing for the Next El Niño*
- Backup record: `ev-media-6b00e9da4ab8b0740ec7` — *Click to Cart: Capturing the Modern Blueberry Shopper With Dana Concepcion*
- Third backup: `ev-media-5f3abbf5a900546806a4` — *The Florida Perspective: Managing Operations With Fletcher Simmons*
- Transcript target status: **ready** (local Whisper `small`, RSS audio, ~43:49, 447 segments). Still **unbound** until a human publishes the parent. That is correct.

## Product story (say this once)

The system watches. AI finds what matters. A human reviews it. Accepted information becomes trusted intelligence.

## SCENE 1 — SCANNER (~60s)

- Screen: http://127.0.0.1:8000/work-queue
- Record: none yet; this is the entry summary.
- Clicks: open **Scanner** in the left nav (formerly Work Queue). The first review card should be Peru El Niño (High relevance + transcript ready).
- Johnny says: “Here is what the system found. Nineteen recent items were processed. Sixteen are important. Sixteen are ready for a human to review. Transcripts are not required to review a publication.”
- Success: tiles show FOUND / IMPORTANT / NEEDS REVIEW / ACCEPTED / ATTENTION. The caution line must **not** say “0 failures.” It should say transcripts are not a batch failure.
- Fallback: if Scanner counts are empty, this runtime lost `inbox/`. Open `/review?kind=publication` and use the persisted 16-item queue.

Expected counts in this runtime:

- FOUND 19
- IMPORTANT 16
- NEEDS REVIEW 16
- ACCEPTED 1 (the already-trusted Lucentlands Ep. 102 publication)
- ATTENTION 0 transcript blockers in operational state
- 3 skipped as irrelevant
- 1 transcript-ready (Peru El Niño)
- remaining review-ready without transcript

## SCENE 2 — TRIAGE (~75s)

- Screen: http://127.0.0.1:8000/review?kind=publication
- Record: lead with Peru El Niño; if the sort order moved it, search visually for that title.
- Clicks: from Scanner, **Open review queue** or **View all items that need review**. Stay on publication cards. Do not switch Item type to Atomic Evidence yet.
- Johnny says: “AI tells me what deserves attention and why. These suggestions are untrusted until I accept them.”
- Success: cards lead with title, source, date, relevance, Why it matters, concise summary, berry/geography suggestions, transcript status, AI-assisted/untrusted, and a primary **Review** action. No model hashes or schema labels as the first thing a new user sees.
- Fallback: `/review/ev-media-cfc3cc9f97414c09c483` directly. Second-best card is Click to Cart.

## SCENE 3 — HUMAN PUBLICATION REVIEW (~90s)

- Screen: http://127.0.0.1:8000/review/ev-media-cfc3cc9f97414c09c483
- Record ID: `ev-media-cfc3cc9f97414c09c483`
- Title: How Peru is Preparing for the Next El Niño
- Source: The Business of Blueberries (USHBC / NABC)
- Clicks:
  1. Confirm title / source / date.
  2. Read **Why this matters** and **Concise summary**.
  3. Glance at Suggested berries / geography.
  4. Confirm transcript status is **Transcript ready**.
  5. Optionally expand Original submission / publisher description. Do not linger on RSS text.
  6. Optionally expand AI provenance and point at **untrusted**.
  7. If demonstrating the trust loop live: enter reviewer name, click **Approve**. Do **not** skip the human gate. Do **not** hand-edit trusted JSON.
- Johnny says: “I decide what becomes trusted. The AI drafted the brief. I am the gate.”
- Success: a 30–60 second decision is possible. Approve / Save / Reject + Next are visible. Expected conflicts render as an HTML banner, never raw JSON.
- Fallback: Click to Cart `ev-media-6b00e9da4ab8b0740ec7`. If review buttons are disabled, the server is in read-only mode (`BIOS_MODE`); restart without that override.

**Johnny should approve this exact record** when you want the end-to-end trusted path. Do not auto-approve it in advance.

## SCENE 4 — ATOMIC EVIDENCE (~60s)

- Screen: http://127.0.0.1:8000/review?kind=atomic
- Record: **none pending**. There is no trusted Atomic Evidence proposal from this sprint.
- Clicks: open Atomic Evidence only. Read the empty state. Do not run extraction live.
- Johnny says: “After a publication is trusted and a transcript is ready, AI can extract claims tied to exact source spans. Those proposals still require item-by-item human review. Haiku is not qualified for that job, so we will not pretend.”
- Success: the audience understands the loop without seeing fake accepted claims.
- Fallback: stay on this empty workbench. If a previous environment has pending atomic cards, they are untrusted proposals — say so. Never show Haiku output as accepted intelligence.

Qualification status at demo time:

- Model: `anthropic/claude-haiku-4-5`
- Probe: PASS (prior)
- Atomic benchmark: NOT RUN against a newly trusted parent in this sprint
- MODEL QUALIFIED: **NO**
- Do not click `scripts/qualify_extraction_model.py approve`

## SCENE 5 — INTELLIGENCE MODEL (~60s)

- Screen: http://127.0.0.1:8000/landscapes/berries/blueberry then http://127.0.0.1:8000/evidence/ev-lucentlands-scaling-blueberry-industry-2025
- Record: `ev-lucentlands-scaling-blueberry-industry-2025` — *Scaling the Blueberry Industry – Opportunities for Africa and Beyond | Ep. 102*
- Status: already **human-reviewed / trusted publication**. Transcript: `not_available`. That is honest.
- Clicks: Blueberry Landscape → open the Lucentlands trusted publication → optionally Newsfeed at `/` for accepted articles.
- Johnny says: “Accepted publications become reusable structured intelligence — competitors, geographies, and the blueberry landscape.”
- Success: the trusted record is visibly published, not a draft.
- Fallback: Newsfeed `/` always has real published items even if landscape navigation is slow.

## After a live Approve of Peru El Niño

If Johnny approves `ev-media-cfc3cc9f97414c09c483` during or before the demo:

1. The trusted publication appears at `/evidence/ev-media-cfc3cc9f97414c09c483`.
2. The staged Whisper transcript still needs a later `process_discovered_media` bind. Do not do that live unless rehearsed.
3. Do **not** run Haiku extraction. Model is not qualified.

## What not to show

- YouTube Blueberries TV / Redagrícola videos as if they have transcripts (anti-bot / no captions).
- Lucentlands Ep. 148–151 as highly berry-specific (enrichment already caveats this).
- Collection status CLI internals, model hashes, extraction versions.
- `inbox/*.json` files.
- Qualification approve.
- Any screen that dumps raw JSON or a traceback.

## Timing

1. Scanner — 60s
2. Triage — 75s
3. Publication review — 90s
4. Atomic Evidence honesty — 60s
5. Landscape / trusted publication — 60s
