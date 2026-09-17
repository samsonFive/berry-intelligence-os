# Next agent — implement Daily Reading Loop V1

Work only from the merged, CI-validated integration base. Read the roadmap, current-state audit, trust state model, implementation sequence, and `AGENTS.md` first.

Implement Phase 3 as one bounded production slice using existing `/today`, `app/services/today.py`, the shared Reader/offcanvas, `/intelligence/{id}`, `/api/intelligence/{id}/reader`, chronology/content-honesty functions, and canonical entity/company/competitor links. Do not create a second feed repository, trust object, source adapter, or AI narrative engine.

Required: publication-date honesty with capture date separate; 0–30, 31–60, 61–90, historical, and unknown groups; reproducible URL filters/sort; readable article/transcript Reader with provenance and quality states; honest partial/consent/bot-wall/empty/shell/unsupported/external-only states; feed-position and filter preservation; Enter/o, Escape, j/k, focus restore, and mobile Reader; competitor/company/entity links; external source secondary.

Do not add thumbs in this slice. That is Phase 4.

Acceptance: focused Today/Reader/chronology/acquisition/content-honesty tests; new tests for all date and unusable states plus keyboard/mobile/focus; static leak safety; browser evidence for desktop, filtered, mobile, empty, readable, and blocked states; record validation; no Source/data changes; full deterministic CI suite.

Exclusions: live collection, model calls, automatic publication, new trust schema, source activation, blended scoring, full CSS rewrite, and infinite scroll before measured need.
