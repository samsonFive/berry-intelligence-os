# Why the integrated published corpus contains zero readable article bodies

Branch: `fix/readable-acquisition-canary-v1`, base `85a157233674ee5cd3d2e358ea02924d3ac04790`
(`integration/competitor-intelligence-wave2`)

## Headline finding

**There is no code defect that prevents readable-body acquisition.** The
extraction pipeline (`app/services/article_acquisition.py` +
`app/services/article_refresh.py`) is correctly built, correctly wired into
every production entry point, and demonstrably produces real readable
article bodies today, live, from real Wave 1 Source URLs. The corpus has
zero readable bodies because **no readable draft this pipeline has ever
produced has been promoted through publication review** — a mandatory
human gate that has simply never been exercised on a body-bearing draft in
this project's history — combined with the fact that most of the
**existing 1,272-record trusted corpus predates this pipeline entirely**
and was captured through mechanisms that never fetch a full article body.
Separately, two of the five Wave 1 Sources have a **genuine, permanent,
external content-availability limitation** (confirmed below) that no
extraction improvement on our side could fix.

## Evidence trail

### 1. The trusted corpus really has zero readable bodies — confirmed directly

```
$ python -c "... scan data/evidence/*.json ..."
total evidence files: 1272
with article field populated: 0
with paragraphs: 0
statuses: {'published': 1269, 'in_review': 3}
```

`schemas/evidence.schema.json` already declares an `article` field capable
of carrying a full readable body (word count, paragraphs, extractor
provenance) — this is not a missing schema capability. Every one of the
1,272 trusted records simply never had that field populated, because every
one of them entered the corpus before the article-acquisition pipeline
existed, or through a path (legacy `source_polling_loop()`, manual
submission) that never calls it.

### 2. The pipeline is correctly wired everywhere that matters

- `scripts/run_collection.py` (the real recurring/production collector)
  routes every `media_format == "web_article"` item through
  `app.services.article_refresh.process_discovered_article()`.
- `scripts/run_recent_batch.py` and `scripts/process_discovered_media.py
  --relevance-gate` do the same.
- `process_discovered_article()` calls `article_acquisition.fetch_article()`
  (real HTTP fetch, wall/paywall/interstitial detection, trafilatura
  extraction, `MIN_BODY_CHARS` sanity floor), persists a structured,
  redacted outcome via `article_acquisition_outcomes.persist_outcome()`
  regardless of success or failure (this exact mechanism was built for
  TD-114, `docs/v2/TECHNICAL-DEBT-REGISTER.md`, during the prior
  `astra-repair` mission — "mitigated locally… production scheduling…
  remain open"), and Source Health (`/sources`, `app/main.py:7616`) already
  aggregates and displays these outcomes per source
  (`ARTICLE-BODY ACQUISITION — N sources attempted · N attempts · N
  readable · N blocked or unusable · N retryable`).
- There is no orphaned or bypassed code path for Wave 1 sources
  specifically — they flow through the exact same, single pipeline as
  every other web_article Source.

### 3. Readable extraction demonstrably works, live, for two of the three currently-runnable Wave 1 Sources

Independent diagnostic calls to the exact same `fetch_article()` function
(no discovery, no persistence — see `CANARY-RESULTS.md` for the
distinction from the capped canary itself):

| Source | URLs sampled | Readable | Example word counts |
|---|---:|---:|---|
| `source-20260901-blueberrybreeding-newsroom` (UF, updated Wave 1 record) | 3 | 2 | 61, 64 |
| `source-20260915-fruitist-newsroom` (new Wave 1 record) | 21 | 6 | 83, 319, 320, 362, 412, 495 |
| `source-20260915-oishii-press` (new Wave 1 record) | 8 | 0 | — |

This directly answers the mission's own bar: "at least one proven readable
acquisition or transcript path if the configured sources make that
technically possible" — it is possible, and proven, for two of the three
currently-runnable Wave 1 Sources.

### 4. Why the 5-item capped canary itself still shows 0/5 readable

`discover_source()` deliberately keeps only the `INITIAL_DISCOVERY_MAX_ITEMS`
most-recent items per source (an existing, preserved hard cap — see
`SOURCE-FUNNEL.md`). For all three runnable Wave 1 Sources, the
**most-recently-published items happen to be exactly the shape that fails**
(see §5) — this is real, honest bad luck in a 5-item sample, not evidence
that acquisition is broken. §3's diagnostic sweep (21 Fruitist URLs, not
just the newest 2) shows the underlying success rate is real, just not
uniformly distributed across recency.

### 5. Two concrete, external, permanent failure patterns — confirmed structurally, not inferred

**Oishii Press Feed (`source-20260915-oishii-press`) — every sampled item
is a permanently bodyless page template.** Fetched HTML for 8 distinct
Oishii press URLs (200 OK every time, real page content) contains a hero
image, an `<h1>` title, a publish-date/byline block, and social-share
icons — and literally no body-text element anywhere in the page, no hidden
div, no outbound link to the original third-party coverage this "Press"
page is nominally aggregating. This is not a bot wall (no 403, no wall
signal), not a JS-rendering gap our static fetcher could ever resolve with
a headless browser (the text genuinely is not in the page at all, static
or dynamic), and not a defect in `trafilatura`/our extraction config — it
is a real content decision on the publisher's own site. Correctly
classified `empty_body` → `navigation_only_shell`, non-retryable,
`manual_acquisition_required`.

**Fruitist Newsroom (`source-20260915-fruitist-newsroom`) — roughly
two-thirds of "news" CMS items have an empty body field.** Fetched HTML
for a failing item shows `<article class="news-text w-dyn-bind-empty
w-richtext"></article>` — `w-dyn-bind-empty` is a real Webflow CMS marker
meaning the bound rich-text field for this specific collection item is
empty in Fruitist's own CMS, while the identical class on a *succeeding*
item (e.g. `dc-united-sells-out-m-t-bank-stadium`) is populated. This is a
genuine, real, per-item content-population inconsistency on the
publisher's own site — some "news" entries are fully-written pieces
(sponsorship announcements), others are bare headline stubs pointing at
press mentions elsewhere with no body ever entered. Correctly classified
`empty_body` → `navigation_only_shell`, non-retryable.

Both patterns are now covered by dedicated regression fixtures in
`tests/test_article_acquisition.py` (`test_headline_only_press_template_with_no_body_element_is_empty_body`,
`test_cms_bound_empty_rich_text_article_is_empty_body`), matching this
codebase's existing convention (see `test_recaptcha_script_tag_does_not_false_positive_as_blocked`)
of turning a real, live-observed pattern into a permanent, deterministic
fixture test.

### 6. A real, previously-uncovered gap: no fetch-level interstitial/cookie-consent test existed

`article_acquisition.py`'s own `_looks_like_interstitial()`/
`_INTERSTITIAL_SIGNALS` wall-detection logic (and `source_body.py`'s
separate, independently-tested `looks_like_interstitial()` used at
*read time* for already-stored records) had **no test exercising a real
cookie/consent HTML page through `fetch_article()` itself** — only a
synthetic `ArticleAcquisitionError(category="interstitial")` was tested at
the outcome-persistence layer (`tests/test_article_acquisition_outcomes.py`).
Added `test_cookie_consent_gate_is_an_interstitial_failure_not_a_readable_body`
to close that gap at the source.

### 7. A real, previously-uncovered gap: no test proved a readable draft never reaches trusted Evidence

Every existing test that exercises a successful readable-body draft
(`test_relevant_article_produces_a_review_ready_draft_with_real_body`)
checks the *draft's own shape*, but nothing explicitly asserted that the
canonical, trusted evidence store stays empty afterward. Added
`test_readable_article_never_reaches_trusted_evidence_or_publication_review_approval`,
which asserts both `repositories.evidence.list() == []` and the trusted
`<data_dir>/evidence/` directory has zero files after a fully successful
acquisition — the mission's own "no automatic trusted publication or
Evidence creation" requirement, proven directly rather than by inference.

## What was NOT found

- No bug in adapter dispatch (`ADAPTER_TYPES` keys off `discovery.adapter`,
  never `type`, so `"reference"`-typed Wave 1 sources with a real
  `discovery.adapter` block are processed identically to `"rss"`-typed
  ones — confirmed for `source-20260901-blueberrybreeding-newsroom`).
- No network-access limitation in this environment — all five Wave 1
  Source URLs (including the two `OPERATOR_ACTION_REQUIRED` ones,
  diagnostically only, never acted on) return real HTTP responses from
  this worktree.
- No regression introduced by "Reconcile competitor intelligence wave 2"
  (`85a1572`) — that commit is documentation/screenshots only, zero
  application-code changes.
- No missing hard-cap/lifecycle enforcement — `source_lifecycle.is_collection_eligible()`
  already correctly excludes both `OPERATOR_ACTION_REQUIRED` Wave 1
  sources (Ozblu, Wish Farms) from any `--all`/eligible-source iteration.

## Conclusion

The "repair" this mission makes is: (a) two new fetch-level regression
tests closing real coverage gaps (interstitial detection, no-auto-trust
proof) that existed before this mission touched anything, (b) two new
fixture tests permanently encoding the two real failure shapes discovered
against live Wave 1 sources, and (c) a fresh, honestly-reported capped
canary plus independent diagnostic verification proving the pipeline is
functional today for Wave 1. No change was made to
`article_acquisition.py`, `article_refresh.py`, `media_discovery.py`, or
any other pipeline module, because none of them exhibited a defect —
every failure observed was a correct, honest classification of a genuine
external content-availability fact.
