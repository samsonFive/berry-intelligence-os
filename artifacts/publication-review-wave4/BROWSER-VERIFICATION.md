# Browser verification

## Environment

- Isolated local server on `127.0.0.1:8791`.
- Canonical data mounted read-only by validation discipline.
- Empty temporary inbox/runtime.
- `BIOS_PUBLICATION_REVIEW_REHEARSAL_UI=1` for verification fixtures only.
- Playwright Chromium; desktop 1440×900, tablet 834×1112, mobile 390×844.

## Results

- All ten representative review states opened successfully.
- Readable body, transcript and limited-content distinctions rendered.
- Untrusted AI labeling rendered.
- Decision controls were visible, disabled and had no form action.
- No fake approval receipt appeared.
- Keyboard Tab moved focus to a real link rather than leaving focus on the document body.
- Today, Morning Brief, Reader offcanvas, Competitor Landscape, Company, Brand, Breeding Program and Source Health returned 200 and rendered substantive content.
- Reader opened through a rendered intelligence card and fetched its in-app reader fragment successfully.
- Console errors: 0.
- Failed browser responses: 0.
- POST/PUT/PATCH/DELETE browser requests: 0.
- Static private-content leaks: 0.

The native computer-use helper could not initialize on this host after its prescribed reset/retry, so the repository's existing Playwright path performed the browser verification. Results are in `browser-results.json`; screenshots are under `browser/`.
