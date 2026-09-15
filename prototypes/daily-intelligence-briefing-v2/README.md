# Daily Intelligence Briefing V2 — standalone prototype

Stakeholder-facing prototype for the next product concept after Competitor Landscape V1.

## Open locally

```bash
cd prototypes/daily-intelligence-briefing-v2
python3 -m http.server 18181 --bind 127.0.0.1
# then visit http://127.0.0.1:18181/
```

## Contents

| Path | Purpose |
|---|---|
| `index.html` | Interactive briefing prototype |
| `landscape-handoff.html` | Query-param landscape handoff stub |
| `fixtures/briefing-v2.json` | Prototype fixture |
| `fixtures/briefing-v2.js` | Same fixture for browser load |
| `docs/VIEW-MODEL-CONTRACT.md` | Future view-model contract |
| `docs/UX-DECISION-LOG.md` | UX decisions |
| `docs/IMPLEMENTATION-SLICE-PLAN.md` | Cherry-pickable implementation slices |
| `docs/ACCESSIBILITY-CHECKLIST.md` | A11y checklist |
| `docs/CHECKPOINT.md` | Checkpoint record |
| `docs/CONTINUATION-PROMPT.md` | Prompt for production implementation later |
| `verification/` | Screenshots / video evidence |

## Isolation guarantees

- No production routes modified
- No production templates modified
- No `app/main.py` changes
- No live inbox reads or writes
- No acquisition / Source Health behavior changes
- Competitor Landscape V1 branch untouched
