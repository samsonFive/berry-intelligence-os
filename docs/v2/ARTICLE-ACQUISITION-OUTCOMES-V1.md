# Article acquisition outcomes V1

Every attempted article-body request writes a compact immutable JSON record under:

`<inbox>/operations/article_acquisition_outcomes/<source-id>/<item-id>/<attempt>.json`

The staged discovery item also receives `article_acquisition_attempt_count` and `latest_article_acquisition` for direct operational inspection. These records do not change publication trust and never contain fetched HTML, cookie walls, bot-wall bodies, credentials, or full response payloads.

Each attempt records the source and item identifiers, any publication or draft identifier, a query-redacted attempted URL, attempt and recording timestamps, acquisition stage, normalized outcome, HTTP status when available, retryability, manual-action requirement, content-quality result, extractor and acquisition versions, article publication date when a readable body supplied one, and a short scrubbed diagnostic.

Normalized outcomes are `readable_article_body`, `cookie_or_consent_page`, `access_denied`, `bot_wall`, `empty_page`, `navigation_only_shell`, `http_failure`, `network_failure`, `parser_failure`, `unsupported_source`, `retryable_failure`, and `manual_acquisition_required`.

Discovery success and article-body success are independent. A feed can run successfully while every body request is blocked. Source Health and the recurring collection summary therefore report discovery execution, body attempts, readable results, blocked or unusable results, and retryable failures as separate measures. Bounded historical reacquisition uses the same ledger with the `historical_reacquisition` stage and does not create a synthetic discovery item.

Unusable acquisition results remain discovery records for diagnosis. They do not become readable evidence, summaries, current company coverage, report evidence, or Today content. Existing source-completeness and source-body gates remain the downstream enforcement layer.
