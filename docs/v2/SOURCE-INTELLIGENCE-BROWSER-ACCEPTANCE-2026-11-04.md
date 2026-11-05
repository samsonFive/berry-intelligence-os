# Source intelligence browser checkpoint — November 4, 2026 Pacific

The user explicitly requested continued autonomous mission work and use of existing credentials to finish the browser checks, with review before recurring collection/transcription activation. Native Chrome verification now supplements the earlier [HTTP presentation checks](SOURCE-INTELLIGENCE-MANUAL-CANARY-2026-11-04.md). It does not close the complete source-intelligence mission.

## Native browser results

Normal sign-in used the existing configured account. Production credentials were kept out of tool output and plaintext files; the one-use encrypted handoff files were removed and the credential object cleared after submission. No password, account role, security setting or saved browser password was changed.

- The Podcasts view visibly renders both new October 22/30 Business of Blueberries drafts as **Unreviewed**, among ten matching cards. Their Reader panels correctly show **Description only · not a transcript**, original-source listening links and the appropriate description-save control.
- Reader Next moves between the episodes while retaining `media=podcast`. Wider/Narrower changes the panel from approximately 650 to 920 pixels, then was restored. No feedback, story-save, publication-edit, rejection or promotion action was performed.
- Source health retains the podcast scope and shows the actual successful manual check, weekly cadence, 202 retained discoveries, three active unreviewed publications and two matching publications. The temporary loaded-row filter was cleared after verification.
- The retained English Lucentlands Reader displays **1,212** timed segments through 2,663.86 seconds, language `en`, automatic generation and `faster-whisper:small` provenance. Browser reload reopens the same transcript and segment count.
- The Spanish Redagrícola video Reader displays **382** timed segments through 980 seconds, language `es`, automatic generation and `youtube-captions:auto:es` provenance. It remains unreviewed. These are structural/source-version checks, not audio word-accuracy certification.
- Both new podcasts are accessible in **All media** through the visible title filter. Native Enter and native Apply filters both submit correctly. A stalled automation click was not reproduced as a native product failure; no application patch was made on that assumption.
- The Luke Lindberg title query returns zero cards in the Trusted view. The BerrySmart query also displays a zero Trusted count. Source collection and playback metadata did not bypass the human trust gate.
- The original empty title search and Podcasts view were restored. The tested page has no captured console errors. Applying the filters can resubmit the same empty/all tag preference; no different tag selection was saved.

Private screenshot evidence remains outside Git/static output under `inbox/search-quality-evaluation/`:

- `source-mission-live-podcasts-20261104.png`
- `source-mission-live-podcast-reader-20261104.png`
- `source-mission-live-source-health-20261104.png`
- `source-mission-live-english-transcript-20261104.png`
- `source-mission-live-spanish-transcript-20261104.png`
- `source-mission-live-all-media-20261104.png`

The existing interrupted tag-classification notice remains visible, retaining prior assignments. Browser page loads and the checks did not explicitly refresh collection, acquire/transcribe recordings or invoke a research model. Existing independently authorized News collection continues on its own timer.

## Confirmed file ownership concern; explicit approval pending

The manual canary command used Docker's root default for its collection CLI. Its command has now been corrected locally to include `--user 1000:1000` for future runs. A read-only production report finds exactly two canary discoveries and two new drafts at UID 0 / GID 1000 / mode 0644. All four match their retained canary hashes and are readable, but `os.access(..., W_OK)` is false for app UID 1000. Their parent directories are app-writable.

The current discovery `_write_item` and legacy `main.save_draft` helpers use direct `Path.write_text`; parent atomic-replacement capability alone does not establish that these direct writers can update the files. No real review edit or rediscovery write was attempted to test permissions.

Automatic approval review rejected a proposed isolated writer probe, then separately rejected the narrower four-file owner correction because explicit authorization for this production file-access change was missing. Neither action ran. The human has been asked to approve only UID 0 → UID 1000 ownership for the four exact paths in private `sourcegap-ownership-readonly-plan.json`; file bytes, groups, modes, modification times and review decisions must remain unchanged. Both prepared operators require their own explicit approval receipt. No alternate delegation or indirect execution is authorized by this checkpoint. The isolated probe is not needed to perform the narrow correction and is not part of the pending owner-repair question.

## Remaining work

Continue local browser capture tests for actual variety/company/workspace/report destinations and restart reopening, then the accessible-page linked Reader and source coverage/evaluation gaps. The existing [local service/store capture proof](SOURCE-INTELLIGENCE-POST-508-CHECKPOINT-2026-11-04.md) does not substitute for every UI workflow. Current video production staging, audio accuracy, provider allowance and sealed analyst outcomes remain open. Existing failed benchmarks and human decisions stay intact.

Exa allowance remains unverified: its dashboard opened at sign-in, and its documented management usage API needs a separately enabled service-account credential; usage history alone is not the current credit balance. No provider key/account was created and no metered Exa search/content request was made. See [Exa billing documentation](https://exa.ai/docs/admin/billing) and [its usage API authentication requirements](https://exa.ai/docs/reference/team-management/get-api-key-usage).
