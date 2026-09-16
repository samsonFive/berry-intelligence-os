# Continue Berry Intelligence OS work — readable-body promotion & Ozblu/Wish Farms re-check

Work in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-readable-acquisition-canary-v1`,
branch `fix/readable-acquisition-canary-v1`. Read
`artifacts/readable-acquisition-canary-v1/CHECKPOINT.md`,
`ROOT-CAUSE-ANALYSIS.md`, and `SOURCE-FUNNEL.md` first.

## Settled facts — do not re-derive

1. The article-acquisition pipeline (`article_acquisition.py` +
   `article_refresh.py`) has no code defect. It is correctly wired into
   every production entry point and Source Health already surfaces its
   structured outcomes. Do not re-audit this from scratch.
2. Readable extraction is proven technically possible, live, for
   `source-20260901-blueberrybreeding-newsroom` (UF) and
   `source-20260915-fruitist-newsroom` — real word counts and URLs are in
   `SOURCE-FUNNEL.md`.
3. `source-20260915-oishii-press` is permanently, structurally unsupported
   — every sampled item (8/8) shares one bodyless page template with no
   body text anywhere in the static HTML. Do not re-diagnose this; a
   future re-check would only be worth doing if Oishii changes their site
   template.
4. The trusted corpus (`data/evidence/`) has zero readable bodies because
   no readable draft has ever been promoted through publication review —
   a process/adoption gap, not a code gap.

## Open items for a future mission

1. **Promote at least one real, human-reviewed readable draft.** This
   mission deliberately created only untrusted, in-review drafts (per its
   own scope: "Do not create trusted Evidence or publish automatically").
   A natural next mission is to have an actual operator review one of the
   readable UF/Fruitist items this mission proved feasible (or a fresh
   discovery run against those sources) through the real `/review`
   publication-review UI, and observe whether the `article` field survives
   promotion into `data/evidence/` correctly (schema already supports it;
   this has simply never been exercised end-to-end).
2. **Ozblu / Wish Farms discrepancy.** This mission's own diagnostic fetch
   returned HTTP 200 for both `https://www.ozblu.com/news/feed/` and
   `https://wishfarms.com/newsroom/feed/` today, contradicting the recorded
   403 from Wave 1's own verification. This was deliberately **not acted
   on** (no bypass of an `OPERATOR_ACTION_REQUIRED` lifecycle gate without
   explicit operator sign-off) — but it is worth a dedicated, careful
   re-verification (robots.txt + feed, from a clean environment, on a
   different day, ideally more than once) before deciding whether to
   transition either source back to `ACTIVE`.
3. **TD-114** (`docs/v2/TECHNICAL-DEBT-REGISTER.md`) says "production
   scheduling and Cal Giant coverage remain open." This mission did not
   touch production scheduling; that recommendation still stands.
4. If a future mission adds a headless-browser or PDF-extraction fallback
   for JS-rendered/CMS-empty pages, note that Oishii's press pages are
   **not** a JS-rendering case — the text is absent from the underlying
   page entirely, not merely hidden pre-render — so that specific source
   would not benefit from such a fallback; re-verify against real HTML
   before assuming otherwise.

## Runtime / housekeeping

Use `../berry-intelligence-os/.venv/Scripts/python.exe`. Git needs
`-c safe.directory=C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-readable-acquisition-canary-v1`
per command. The canary driver script used for this mission was
deliberately not committed (kept in the session scratchpad, matching this
codebase's own precedent from the prior Wave 1 activation canary) — a
future mission wanting to re-run a similar bounded canary should compose
`discover_source(..., max_persisted_items=N)` +
`process_discovered_article(...)` directly, exactly as
`scripts/run_recent_batch.py` already demonstrates, rather than inventing
a new orchestration layer.
