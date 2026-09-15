# Prototype → Production decision log (Slice 1)

1. **Canonical route:** Replace `/today` news edition with the briefing; keep archive UX at `/news`.
2. **No third feed:** Morning Brief (`/brief`) remains analyst ops; Today is the daily intelligence reader.
3. **Data boundary:** Production adapter reads published evidence + entities + sources + landscape completeness only. Prototype `fixtures/briefing-v2.json` is never loaded.
4. **Recency:** Publication date only. Capture date is displayed secondarily and cannot promote old items into What Changed.
5. **What Changed gate:** trusted published + usable_in_app + publication date ≤ 90 days.
6. **Implications:** Show only explicit `why_it_matters`; otherwise “Analyst implication not yet added.”
7. **Reader:** In-app drawer via `?reader=<id>`; sanitized text only; original source is secondary `rel=noopener` link.
8. **Landscape handoff:** Real `/competitors` query contract with `from=today`.
9. **Non-company entities:** Profile URLs use `/entities/{type}/{id}` (brand, breeding_program, etc.).
10. **Deferred:** thumbs mutations, saved searches, read/unread, personalized ranking, AI implications, source activation scoring.
