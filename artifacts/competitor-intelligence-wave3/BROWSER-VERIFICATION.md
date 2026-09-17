# Browser verification

## Matrix

Playwright Chromium verified eight surfaces at desktop (1440×1000), tablet (900×1100), and mobile (390×844):

- `/today`
- a deterministic readable reader state from an isolated external data copy
- a real limited/unavailable reader state
- default Blueberry Competitor Landscape
- California Giant company profile
- OZblu brand profile
- UC Davis breeding-program profile
- Source Health

Result: **24/24 page checks passed**. Every page returned HTTP 200. There were no browser console errors, failed local requests, local responses at 400+, or missing Slice 1 CSS/JS.

## Reader interaction

At all three viewports, the deterministic item:

1. opened within `/today` on the same origin;
2. moved focus into the dialog;
3. closed with Escape;
4. returned focus to the exact opening item.

Result: **3/3 interaction checks passed**. Appropriate reader flows did not force external navigation. The limited state displayed `Body unavailable` and kept the original-source action explicit. Trust status remained display-only; no feedback mutation control exists.

## Scope isolation

`pvs_tokens.css`, `daily_briefing.css`, and `daily_briefing.js` loaded on Today and reader checks only. They did not load on Landscape, representative profiles, or Source Health. This confirms Product Visual System Slice 1 is limited to Daily Briefing and its reader.

The deterministic readable record exists only in `C:\Users\Johnny\AppData\Local\Temp\berry-wave3-reader-fixture-20260915-a`, outside the repository and production data. It was never imported or published.

Evidence: `browser-verification.json` and the `screenshots/` directory.
