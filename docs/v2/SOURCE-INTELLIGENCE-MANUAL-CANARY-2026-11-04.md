# Source intelligence production canary — November 4, 2026 Pacific

The standing source-intelligence mission authorizes bounded real-source tests, with separate review before new recurring activation. After #507 handed back its window, the root release owner reserved a short window for this manual canary. No implementation was deployed and no recurring selector/cadence was changed.

## Verified baseline and recovery

The current live release was `8f510b5383274f218e4e1eb714b4c28dc5413da7`, tested #507 head `6940405f`, image `sha256:7cb55cc6995f7e9ca044f846882142c3efa432de88beba1559a8a72588e6c2eb`. It retained #508's bounded selection/relevance implementation. The existing News timer selected exactly `--pipeline news_workspace_refresh`.

The retained photo-inclusive full backup was hash-verified and its contents streamed against its manifest. A fresh small delta included all later runtime changes, including the four saved landscape seeds from #507. Before collection, both root and UID 1000 independently traversed and hash-checked all **26,306** selected runtime files with exact path, size, mode, ownership and modification-time agreement; all four databases were readable and their logical contents matched. Traversal failures, links, invisible/deleted paths and unexpected private-binary changes fail the checks. Standard backup credential exclusions and the transient collection lease are excluded explicitly, not by a broad filename wildcard.

The first preparation attempt stopped before any collection call: a read-only SQLite connection touched only a shared-memory file's modification time. Independent inspection found unchanged bytes, unchanged logical database contents, no new/deleted files and a restored active timer. The retry completed database reads before taking the strict file inventory. No metadata or hash check was weakened, no fixture was restored over production, and the stopped attempt's artifacts remain retained.

The existing timer was paused only for the bounded window, protected by a one-shot restoration watchdog, then restored active. Shared review locking, the pipeline lease and the unchanged 2 GiB RAM / 10 GiB disk reserve remained enforced. No cleanup was performed.

## Actual collection and repeat

At approximately **3:27 p.m. Pacific**, the allowlisted Business of Blueberries Source was due. Each of two explicit manual cycles capped persisted discoveries and processed items at two, skipped transcription with budget zero, disabled model enrichment and explicitly disabled extraction in the process environment.

| Result | First cycle | Repeat |
| --- | --- | --- |
| Public feed entries observed | 200 | 200 |
| New discoveries persisted | 2 | 0 |
| Known capped discoveries | 0 | 2 |
| New publication drafts | 2 | 0 |
| Historical backlog processed as suppressed | 0 | 2 |
| STT/model/extraction calls | 0 | 0 |

The two new production drafts are:

- `ev-media-1837305cb2be073109c2`: **BerrySmart Field Insights: Automated Blueberry Harvest Technology**, published October 30, 2026.
- `ev-media-46d31540b87c69767c56`: **From the USDA to the United Nations: Luke Lindberg on Trade, Policy and Feeding the World**, published October 22, 2026.

Both remain awaiting human publication review and have publisher-description/metadata evidence, not new transcripts. This is actual production staging, unlike the earlier local-only canaries. Distinct publisher GUIDs preserve their separate identities despite the shared show-homepage link; exact episode-page binding remains a separate open case. A repeated successful feed read is not complete recall. The repeat selected two retained historical recordings and suppressed them rather than creating review drafts; that suppression is not new content acquisition.

## Preservation and handoff

After collection, exact root/app-UID coverage passed for **26,314** files. All **4,552 canonical data files**, **1,754 existing draft files**, private media, account/review state and **four logical databases** were preserved. Eight files were added: two discoveries, two unreviewed drafts, two per-item operational states and two run receipts. Only three existing files changed: this Source's discovery state and two historical-backlog operational item states. No existing file was deleted. No canonical Source/data row, trust decision, alias, trait, right or footprint was added.

The live image/current pointer and News selector remained unchanged. The timer was restored active; no credits were purchased and no paid routing, transcription or recurring media lane was activated. A final full-plus-delta recovery point verifies all 26,314 selected files without constructing another full runtime copy. Free disk at completion was **10,910,543,872 bytes**, about 173 MB above the unchanged 10 GiB floor; future work must recheck capacity.

Server receipt: `/opt/berry-platform-releases/sourcegap-manual-canary-20261104T232659Z/completed.json`. Local receipt: private `inbox/search-quality-evaluation/sourcegap-post507-manual-canary.json`. The shared-host window was handed back to the root release owner immediately after the two cycles and preservation. No further host work remains active in this task.

Recovery assets, all retained:

- Full: `/var/backups/berry-intelligence-os/sourcegap508-release/berry-runtime-20261104T225436Z.tar.gz`, SHA-256 `2c4e4c6003e7b1445244027d64a34523ca3e0c3aa58012e4994424967958b72e`.
- Current delta: `after-delta.tar.gz` in the canary stage, SHA-256 `91f22c7bd0e72bef13761a811e7e6dcd28906179abe632f8e4775ba8feb31952`, 6,317,011 bytes / 29 changed-or-new files relative to the full backup.
- Final inventory: `after-manifest.json` in the same stage, SHA-256 `1dfd70a97676322eda6c6875105bbacbe4152db09e3a444aa5215389fdb50e6c`. `after-recovery.json` records the recipe; `after.json` retains root/app-UID coverage and logical database hashes. Restore only into a fresh destination, select only final-manifest paths, overlay delta members, apply final file metadata, then verify the complete inventory. No recovery was executed against live data.

## Review boundary and next work

The manual production prerequisite now passes for this Source. It does not authorize recurring activation. A future proposal must name only this Source, cap discovery/processing at two each, retain zero transcription and no model enrichment/extraction, preserve the existing News lane and provide rollback. The daily dispatcher and this Source's weekly collection cadence are separate; a daily freshness expectation would require an explicitly reviewed Source-cadence change.

Presentation verification for these two new production drafts, actual browser/entity-profile/report capture, exact episode links, current video staging, audio word accuracy, Exa allowance, linked-page Reader behavior, sealed analyst outcomes and broader coverage remain open. Continue presentation work locally while root owns the next preservation window; repin current live state before any further production canary. Existing failed benchmarks and all human review gates remain unchanged. See also the [local transcript/destination checkpoint](SOURCE-INTELLIGENCE-POST-508-CHECKPOINT-2026-11-04.md).
