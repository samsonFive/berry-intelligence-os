# Google News Publisher URL Resolution V1

Closes TD-014. Relieves the TD-059 blocker without using an undocumented Google endpoint.

## Problem

`news_search_rss` item `<link>` values are `news.google.com/rss/articles/<token>` wrappers. `fetch_article()` follows HTTP redirects, but Google typically returns HTTP 200 with a JavaScript shell. Extracting that shell as an article caused the historic repeated-body incident. Borderline items (the ones this source class exists to catch) could not run Stage B and sat unconfirmed.

TD-014 hoped a plain HEAD/GET redirect would resolve the publisher URL. TD-059 later showed that redirect usually does not happen.

## What this does

`app/services/google_news_url.py::resolve_google_news_url()` locally decodes the token already present on the RSS link (base64url payload, nested tokens, `google.com/url?q=` unwrap). When a publisher **article** URL is present, `fetch_article()` fetches that URL instead of the wrapper.

Rules:

- No extra Google internal API request.
- No User-Agent spoofing to walk around a wall.
- No paywall bypass.
- Wrapper / consent HTML is still `script_rendered` / `interstitial`.
- Publisher homepages and Google tracking hosts are not accepted as article URLs.
- Discovery `canonical_url` stays the wrapper (stable identity). `ArticleBody.final_url` is the publisher page.

## What this does not do

- Does not onboard The Packer or any new Source.
- Does not change Story Thread matching, Today ranking, or freshness windows.
- Does not rewrite canonical Evidence.
- Does not re-measure live production yield.

## Tests

Mocked HTTP only. See `tests/test_google_news_url.py`, `tests/test_article_acquisition.py`, and `tests/test_article_refresh.py`.
