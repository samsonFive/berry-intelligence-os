# All-berry Social Listening rollout — October 7, 2026

The user approved the blueberry workspace and explicitly authorized strawberries, raspberries and blackberries. This extends the same private Social Listening workspace on draft PR314, not Landscape Explorer's separate rollout. No merge, deployment, paid activation, external applications or vendor messages.

## What changed

A shareable Berry selector scopes posts, phrases, attribute counts, map/gallery, Momentum, coverage, briefing and exports. Reset preserves berry, view and data mode. All berries use the approved compact author column, English-only display, carousel/lightbox and newest-first presentation. Mixed-berry posts retain one source identity and may appear in multiple selections; counts cannot be added across selections. Unassigned mixed-berry sentiment is uncertain in a selected berry heatmap. Canonical entity/variety and Landscape contracts are unchanged.

Regional vocabulary includes Spanish frutilla/frutillas and plural frambuesas/zarzamoras, Portuguese plural framboesas/amoras-pretas, traditional Chinese 樹莓 and Japanese 苺. This is a bounded five-language pack, not worldwide recall. Explicit BlackBerry-phone and Raspberry Pi/perfume/tasting-note controls remain conservative. Latin names adjacent to Chinese/Japanese text now retain evidence spans; localized sentence boundaries separate retailer sightings from wishes. Literal rule proposals still require review, especially botanical homonyms, metaphor, negation and mixed-food targets.

Optional author identity and role-basis fields use the existing schema-version-1 payload. The checked-in intake schema now includes them; older records remain valid. The reader exposes supplied author and classification basis. Native @driscollsberry matching supports proposed company ownership; it is not inferred from query text. Assistant-inspected recipe/consumer captions are draft categories, never independent qualification.

## Measured source trial

Six predeclared, one-page probes: X known-company search and Reddit newest/month discovery for each new berry. All six returned HTTP200; each consumed one existing free credit, cash spend $0. X returned 20 items per query and retained 10; Reddit returned/retained seven per query. Normalization reported no mapping errors. There were 46 unique additions, bringing the private raw corpus from 197 to 243. This raw corpus contains unrelated results and unreadable/pending-language posts; raw counts are not relevant consumer coverage.

Thirty X records supplied English metadata. Reddit did not supply language metadata: only complete captions actually inspected by the assistant can receive a hash-bound English assessment. Other records remain hidden until English is verified or a translation is available. Neither title indexing nor a successful request proves relevance, freshness, consumer sentiment, country coverage or independent accuracy. Corporate searches can return historical posts; genuine posting dates remain visible.

The account used 38 of its initial 50 free credits; 12 remain, preserving the original 10-credit reserve. These are finite signup credits, not a free ongoing monitoring service. No retries, pagination, media downloads, AI calls, subscription, recharge or recurring collection. The runner now uses the established private collection lease. Future --live invocations hit the cumulative attempt ceiling; no additional test calls are authorized by this report.

Current per-berry readable counts, sources and role proposals are in `artifacts/social-all-berries/trial-summary.json`. The source-access matrix still marks other platform methods and rights requirements honestly. Official documentation checked October7: [X search](https://docs.sociavault.com/api-reference/twitter/search), [Reddit search](https://docs.sociavault.com/api-reference/reddit/search), [pricing](https://sociavault.com/pricing). Documented request costs were checked against actual balance deltas; no paid pricing is used to justify a purchase.

## Evaluation and limitations

`benchmarks/social-all-berries-fixtures.json` contains 33 developer-authored synthetic cases for the three additional berries, five languages, mixed sentiment, retailer relations, unknown geography, mixed berries and phone exclusion. `artifacts/social-all-berries/evaluation.json` reports measured exact-field checks by language. The existing blueberry dataset/report remains separate. Synthetic handles and translations are invented and isolated by mode. Small authored fixtures are optimistic; they are neither independent native-language review nor a representative population.

Independent live accuracy: zero graded cases; precision and recall unavailable. No regional discovery score, five-language live qualification, comment/media retrieval comparison for this six-call extension, rights/deletion refresh qualification or unattended monitoring approval. Long Reddit texts, perfume/wine metaphors and recipe-versus-fruit relevance remain review candidates; successful mapping does not make them relevant. Proposed corporate and consumer categories remain distinct from unclassified records.

The shared dossier/briefing/market-snapshot hooks remain available, but automatic downstream assembly/publication retraction and durable analyst watch-profile management are still incomplete. Network/footprint views remain honest design previews. These limitations are not resolved by accepting the blueberry layout.

## Reproduce and operate

- Offline evaluation: `python scripts/evaluate_social_all_berries.py` and `python scripts/evaluate_social_blueberry.py`.
- Offline private replay: `python scripts/social_all_berries_trial.py` requires the retained private ledger/raw files and cannot collect by default.
- Private preview: `python scripts/preview_social_sociavault.py`, localhost port18345. Select berry and live collection; existing private data is required. Reading a page never collects.
- Synthetic review: use `scripts/social_intelligence.py fixture --file benchmarks/social-all-berries-fixtures.json` against an isolated BIOS_INBOX_DIR and choose Sample posts. It never counts as live collection.
- Real-post review packet and screenshots remain in the local outputs directory; raw text, private assessments and keys are excluded from Git/static publication.

## Migration, rollback and next review

No canonical registry or SQL-table migration. Reanalysis applies the new version only to unreviewed private records and preserves source payload/provenance; ordinary Store ingestion preserves reviewed analysis and removal tombstones. Synthetic records remain separate. Back up the private SQLite database and assessments before operational migration. Rollback the code commit, restore private runtime backup if old extraction proposals are required, restart the preview. No production data or deployment is touched.

Five-minute review: switch among all four berries; compare corporate/consumer/unclassified posts; inspect authors and real dates; cycle/enlarge attachments; drill a phrase/attribute into matching posts; check unknown geography and source coverage; export the same filtered selection.

Continuation order: independent relevance/role/language review; curate corporate and consumer reference/watch scope; improve contextual berry/aspect extraction and translation workflow; close retention/deletion rights; persist reviewed watch profiles and bounded ongoing collection; complete dossier/briefing/snapshot assembly; then implement shared Landscape-compatible network/footprint views and in-app alerts. External notifications, paid collection, merge and deployment require separate authorization.

## Validation receipt

Focused social suite: 90 passed, one dependency deprecation warning (93.20 seconds). After adding English-translation search, the four affected berry-route tests passed (89.46 seconds); 91 distinct focused tests are covered. Added synthetic evaluation: 246/246 exact-field checks across 33 cases; original blueberry evaluation: 202/207, with five unresolved negation/sentiment cases. Offline replay adds zero duplicates. Browser inspection confirmed strawberry, raspberry and blackberry selection, corporate filtering and newest-first ordering; screenshots are retained privately. Required GitHub checks must be read on the final pushed head.
