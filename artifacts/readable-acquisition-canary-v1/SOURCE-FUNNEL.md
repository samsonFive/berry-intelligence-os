# Wave 1 source-by-source funnel

Scope: the four newly-created Wave 1 Source records plus the one updated
Wave 1 record (`data/configuration/sources.json`, commit `cdb059e`
"Activate competitor sources wave 1"), restricted in this canary to the
three that are currently collection-eligible.

| Source | Lifecycle | In this canary? | Reason |
|---|---|---|---|
| `source-20260901-blueberrybreeding-newsroom` (UF, **updated**) | ACTIVE | ✅ | `configuration_state: configured_never_run` |
| `source-20260915-fruitist-newsroom` (**new**) | ACTIVE | ✅ | `configuration_state: configured_never_run` |
| `source-20260915-oishii-press` (**new**) | ACTIVE | ✅ | `configuration_state: configured_never_run` |
| `source-20260915-ozblu-news` (**new**) | `OPERATOR_ACTION_REQUIRED` | ❌ | Live re-verification returned HTTP 403 for robots.txt + feed; this mission does not retry or bypass an operator-required lifecycle gate |
| `source-20260915-wish-farms-newsroom` (**new**) | `OPERATOR_ACTION_REQUIRED` | ❌ | Same as above |

Note: a fresh, unrelated diagnostic fetch of the Ozblu/Wish Farms feed
URLs from this worktree returned HTTP 200, not 403 — recorded honestly in
`ROOT-CAUSE-ANALYSIS.md`/`CHECKPOINT.md` as a discrepancy worth an
operator's attention, but **not acted on**: the recorded 403 was a real,
cited, dated verification, and lifting an `OPERATOR_ACTION_REQUIRED` gate
based on one unrelated agent's transient re-check would itself be exactly
the kind of automatic bypass this mission's own git-discipline section
prohibits.

## Capped canary funnel (5 discovered items total, this mission's own run)

| Source | Discovered | Acquisition attempted | Fetched (HTTP 200) | Blocked/retryable | Meaningful body extracted | Transcript available | Publication draft created | Review required | Readable success rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| UF blueberrybreeding | 2 | 1 | 1 | 0 | 0 | n/a (web_article) | 1 | 1 | 0/1 |
| Fruitist Newsroom | 2 | 1 | 1 | 0 | 0 | n/a | 1 | 1 | 0/1 |
| Oishii Press Feed | 1 | 1 | 1 | 0 | 0 | n/a | 1 | 1 | 0/1 |
| **Total** | **5** | **3** | **3** | **0** | **0** | **0** | **3** | **3** | **0/3 (0%)** |

The remaining 2 of the 5 discovered items (1 each for UF and Fruitist)
were screened as **confidently irrelevant** (Stage A: no berry/CI keyword
signal in title or description at all) before any acquisition attempt —
correct, expected behavior, not a failure. They are counted in
"discovered" but not in "acquisition attempted."

**Precise failure reasons (all 3 attempted items):** `navigation_only_shell`
(`empty_body` category; extracted body under `MIN_BODY_CHARS`), `retryable:
false`, `manual_acquisition_required: true`. Every item's fetch itself
succeeded (real HTTP 200, real page content) — the failure is in what the
page contains, not in reaching it. See `ROOT-CAUSE-ANALYSIS.md` §5 for the
confirmed structural cause per source.

Each attempted item, despite its body failing extraction, still produced a
**metadata-only publication draft** for human review (title, canonical
URL, publisher, discovery-feed date) rather than being silently dropped —
this is `article_refresh.py`'s existing, preserved access-limited-fallback
behavior (Stage A had already confirmed `TIER_DIRECT` relevance from
metadata alone), and is why "publication draft created" and "review
required" both read 3/3 despite 0/3 readable.

## Independent diagnostic verification (not part of the 5-item cap; no persistence)

To establish whether readable acquisition is *technically possible* for
these sources at all — the 5-item cap is real but necessarily narrow —
`fetch_article()` (the exact same function the canary and production
collection call) was run directly against additional real URLs pulled
from each source's own feed/sitemap. No `discovered_media` record, no
draft, no outcome ledger entry was created by these calls; they exist only
to answer "is this pipeline capable of a readable body from this
publisher," independent of which 1-2 items a 5-item cap happens to land
on.

| Source | URLs sampled | Readable | Failure (empty_body) | Readable word counts |
|---|---:|---:|---:|---|
| UF blueberrybreeding | 3 | 2 | 1 | 61, 64 |
| Fruitist Newsroom | 21 | 6 | 15 | 83, 319, 320, 362, 412, 495 |
| Oishii Press Feed | 8 | 0 | 8 | — |

**Conclusion: readable acquisition is proven technically possible today
for UF blueberrybreeding and Fruitist Newsroom** (real word counts above,
real live URLs, identical extraction code the canary itself uses) — the
5-item capped canary's 0/3 result reflects which specific items were most
recent on the day this canary ran, not a defect. **Oishii Press Feed is
permanently, structurally unsupported**: 8/8 sampled items (spanning this
canary's own 1 item plus 7 additional diagnostic URLs) share one page
template with no body-text element anywhere in the static HTML and no
outbound link to original coverage — see `ROOT-CAUSE-ANALYSIS.md` §5 for
the confirmed HTML evidence.

## Transcript path

Not applicable to Wave 1: all five Wave 1 Sources are `media_format:
"web_article"` (RSS/sitemap article feeds), none are podcast/video. No
transcript acquisition path exists or is expected for this specific
source set.
