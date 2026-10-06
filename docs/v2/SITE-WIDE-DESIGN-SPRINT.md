# Site-wide design sprint

The current scope and implementation sequence are in [Berry Intelligence immersive design mission](IMMERSIVE-DESIGN-MISSION.md). The user has superseded the navy-led direction with bright green, berry color, translucent materials, compact top navigation and a full-width workspace. The requirements below are retained as the initial audit checklist; the current mission governs visual choices.

Follow-up scope approved after the Global Intelligence Explorer mission. The demonstrated Glasshouse UI direction was accepted September 30, 2026. See [Design review audit](DESIGN-REVIEW-AUDIT.md) for request coverage, remaining representative page reviews and known prototype gaps.

## Objective
Apply a bright, immersive agricultural visual language consistently across all application pages, with a tight, dense workspace and unmistakable information hierarchy.

## Work
- Inventory every route and shared shell, including Today, Reader, entities, evidence, review queues, reports, settings, forms, tables and dialogs.
- Establish shared typography roles: page title, article headline, section heading, lead summary, body, metadata and provenance. Distinguish roles through size, weight, contrast and spacing. Reader hierarchy is a priority.
- Establish compact spacing tokens and remove excessive empty padding, oversized headers and sparse panels. Preserve readable line lengths and accessible touch targets.
- Migrate shells and controls to the selected design system, with consistent navigation, selected states, source imagery and trust labels.
- Treat dense tables and feeds as primary workflows. Use progressive disclosure for secondary details rather than reserving empty panels.
- Preserve print and PDF styles independently of screen themes.

## Acceptance
Review every surface at desktop, tablet and mobile widths. Verify headline/summary/metadata are visibly distinct, useful content appears early, no horizontal overflow occurs, keyboard focus remains visible, and zoom does not lose controls. Capture before/after views of representative dense feeds, Reader, detail pages and report composition. Trust, review and publishing behavior must remain unchanged.

Explorer and snapshot adopt the newer shell now; the site-wide migration is a separate bounded mission.
