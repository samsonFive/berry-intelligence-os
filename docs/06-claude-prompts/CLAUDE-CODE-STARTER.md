# Claude Code Starter Prompt

You are working inside the `berry-intelligence-os` repository.

Before changing code, read these files in order:

1. `WELCOME.md`
2. `docs/00-product-vision/VISION.md`
3. `docs/01-prd/PRD.md`
4. `docs/02-design-system/DESIGN-SYSTEM.md`
5. `docs/03-information-architecture/DOMAIN-MODEL.md`
6. `docs/04-technical-architecture/ARCHITECTURE.md`
7. `docs/05-development-roadmap/BUILD-GUIDE.md`
8. all files in `docs/decisions/`

Then inspect the current repository and complete **Milestone 1 only**.

Constraints:

- Keep JSON files authoritative.
- Do not introduce Airtable, Supabase, Firebase, Notion, or another proprietary data dependency.
- Do not introduce a graph database.
- Do not hard-code any employer or privileged market entity.
- Preserve the evidence-first model.
- Keep the application runnable locally.
- Generated indexes must remain disposable.
- Match the visual language in `assets/platform-visual-language.png` without copying unreadable text from the mockup.
- Use accessible semantic HTML and do not rely on color alone.
- Do not implement AI enrichment yet.

Required output:

1. Explain the proposed implementation plan.
2. Identify files you will add or modify.
3. Implement the read-only newsfeed, evidence page, company page, variety page, and basic filters.
4. Add or update tests.
5. Run tests and report results.
6. Update documentation only where implementation creates a new confirmed decision.

Stop after Milestone 1 is complete and tested.
