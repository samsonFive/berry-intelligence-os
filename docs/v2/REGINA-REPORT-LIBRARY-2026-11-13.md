# Regina report library — November 13, 2026

Regina is available in **Reports & Briefings → Reports → Research reports**, with an in-app reader and direct PDF download. The four-page profile retains its supporting image, 16 individually linked sources, and clickable field video.

- [Open the Regina report](https://intel.johnnyaceii.com/reports/library/regina-blackberry).
- [Download the PDF](https://intel.johnnyaceii.com/reports/library/regina-blackberry/download.pdf).

The [reusable variety-profile standard](../../reports/README.md) presents identity, characteristics, commercial context, comparisons, and open research questions. It uses an industry-neutral viewpoint; recommendations and decision gates are included only when requested. Finished downloads serve the approved artifact without regenerating research or creating trusted intelligence records. Working drafts remain available alongside the finished-report library.

## Verification

Live HTTPS checks using normal sign-in returned 200 for the reader and PDF download; anonymous access redirected to login with 302. The downloaded 399,470-byte PDF matched the approved file exactly. All 16 source URLs and the video link were retained. Desktop/mobile layout review was performed locally; live verification used authenticated HTTPS requests.

Preservation covered **30,261 runtime files** and **906 existing static assets**. The 32 environment values, mounts, application settings, and copilot image were retained; the collection timer was restored. The fresh 695,528,318-byte backup was verified, and all six copied SQLite databases passed checks.

## Release evidence

- [PR #574](https://github.com/samsonFive/berry-intelligence-os/pull/574), merged as `6f74665b9446d2215e357d22ccbcb230bd55eac1`.
- Tested head: `c707ae0cc3caa2594d1996f9ef7cc41bc6bcb91f`; all five checks passed in [CI run 43478045650](https://github.com/samsonFive/berry-intelligence-os/actions/runs/43478045650).
- Live image: `sha256:7c5263efd3cb9d2e0f48a1c9829bc84bbdf0938e9a2c4fbf39493da9d1b733df`, inheriting `sha256:7f1c1bd953c537c1fce6f002a6dcd4a714e506e9d8072a6eceef6e9d260bb2ff`. Eleven copied files matched committed bytes; existing client layers and image settings were retained.
- PDF SHA-256: `1af71baac792f7b5aa82f7428d46ac71091cfa86cc42ba88f3e74aab06dffe84`.
- Fresh backup SHA-256: `87f257f5a2c6aa890c520bedeef73566da790957f749a39b3ba119933f169026`.
- Live ledger SHA-256: `9df518c2e7ff4aaf5c025b8cbcf731d04b1ed48480d3bfe00c2ea48e734cd8e4`.
- Promotion receipt: `/opt/berry-platform-releases/regina-report-library-574-c707ae0c-20261113-retry1/cutover-20261113T203729Z-4d436c/report-library-promotion.json`.

## Recovery and preservation detail

The first attempt restored the prior healthy pair after a guard flagged restart bookkeeping. Independent comparison found identical workspace schema and every row. The reviewed correction permits only the exact workspace database’s two SQLite header-counter fields and cron-log ownership normalization, with every other content and metadata check retained. Raw backup comparisons remain exact.

The user explicitly approved retaining that attempt’s recovery archive locally. Its exact hash and all 30,223 archived files were verified before removing its duplicate server copy to make room for the fresh retry backup. Prior release archives and receipts were retained.
