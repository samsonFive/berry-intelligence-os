# Production Continuation Prompt — Product Visual System V1

Copy/paste for the next production agent.

---

You are continuing Berry Intelligence OS visual unification after the frozen prototype:

- Branch: `prototype/product-visual-system-v1`
- Base: `5113b22e5d1f8472f58a454958ac64d07c783cd5` (trust-controls)

## Do

1. Read `prototypes/product-visual-system-v1/docs/MIGRATION-MAP.md` and `tokens/tokens.css`.
2. Start Stage 1 only: Daily Briefing + in-app reader visual adoption.
3. Introduce a shared production token layer that aliases existing `--brief-*` / `--v2-*` during transition.
4. Keep behavior from Slice 1 Briefing and Trust contracts intact.
5. Pass accessibility checklist items for touched surfaces.
6. Do not rewrite Landscape/profiles/Source Health in the same slice.

## Do not

- Force-push, merge, or deploy unless explicitly requested.
- Create a fourth visual language.
- Hotlink arbitrary images or use generated images as article photos.
- Implement Sol trust persistence here.

## Success

`/today` and reader visually match the prototype tokens; production CSS is shared; no feature regressions; focused tests + browser checks green.
