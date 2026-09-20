# Local feed-first run (human publishing)

Use this to run Berry OS on your machine, score statements, and thumbs-up
items. This is the Gate 3 / publishing path on the Monday branch.

Official-site **first-party news cards** still need a watched company host
to publish a public page that Google News can see. Running this app does
not publish onto Hortifrut.com or any other company site.

## Start

```bash
git fetch origin
git checkout cursor/monday-tracked-companies-80ac
./scripts/run_local.sh
```

Open http://127.0.0.1:8000/today

Python 3.12, `requirements-dev.txt`. The script creates `.venv` if needed.

## Optional live keys

Copy `.env.example` to `.env` and fill **only keys you already have**.
Canonical names: `PERPLEXITY_API_KEY`, `EXA_API_KEY`, `APITUBE_API_KEY`,
`NEWSCATCHER_API_KEY`. Do not invent Firecrawl/Jina/social keys.
`.env` is gitignored.

Without keys, Google News RSS + specialist RSS + the bounded official-site
`site:` lane still run.

## Publish / score on Today

1. Open `/today`. Click **Refresh live lanes** once if the disclosure looks stale.
2. Open a same-day (or Window=7d) card. Reader stays beside the feed.
3. **Thumbs-up** = this matters. Statements extract in the inspector. Edit,
   mark Important, or reject. Undo the thumb to clear the working set.
4. Open the company from the chip or `/entities/company/…`. Trusted
   statements land under **From Today thumbs-up**.
5. Landscapes / This week reuse those statements and live briefs.

`/review` is the old publication-review queue. It is not the thumbs-up path.

## Official-site lane

Research Ops (`/research-ops`) shows `polled N hosts · 0 first-party this
fetch` when watched hosts did not publish. That is a coverage gap, not a
missing watch. When a host does publish, the card is `company_website` on
the `official_site` lane.

## Stop

Ctrl+C the script. Leave `inbox/` alone — thumbs and statements live there
and are gitignored.
