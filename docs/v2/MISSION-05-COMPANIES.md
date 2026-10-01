# Mission 5 — Company directory and profile workspace

October 1, 2026. Review checkpoint on `feature/company-workspace-consolidation`, stacked on Map Mission 4. Not merged or deployed.

## Analyst jobs

**Find → organize → inspect → read or edit.** `/entities/company` is a full-width alphabetical table in the approved bright Glasshouse shell. Search aliases/names, use A–Z (accent folded), select multiple berries, organization type, personal tier, favorite status or an existing company list. Focus directory moves the table into view without changing scope. The review corpus contains 240 organizations, including provisional identities, brands, breeding programs and source systems; this is not a count of verified competitors. Existing explicit seed-to-catalog mappings are reused, without fuzzy identity merges or silent prototype-state imports.

Favorites, assigned Tier 1/2/3/Untiered and list membership are independent. Legacy watch/muted values remain compatible. An absent assignment stays Untiered, including in the retained Following view; the seed's monitoring classification is retained separately rather than shown as an analyst assignment. Directory and profiles edit the same existing personal state used by News, Map and Digest filtering. Multiple company lists are supported; creation, rename, archive and explicit Digest subscription reuse the existing list service. Renaming preserves pre-existing registry members, including people, without permitting unknown additions. Membership does not subscribe, trigger alerts, change reading priority or approve news.

Company profiles use Overview, News, Intelligence, Varieties, Regions, People and Profile & links tabs. The first sentence of the catalog description leads; longer descriptions/identity notes are collapsed. Coverage counts describe recorded news/locations/relationships, not market scale or verified absence. News uses the shared metadata selector, publication dates newest first, safe previews and existing personal icon actions. The shared `#v2ReaderOffcanvas` opens Article/Brief and restores focus on close; missing article text remains explicit. Company tabs show up to 36 selected stories, with Full news filters reaching the paginated News workspace.

Intelligence retains the existing dossier backbone, reviewed statements, relationship roles, sources and research controls. The previous dossier remains at `?view=dossier`, the catalog profile at `?view=legacy`, and the previous directory at `?view=legacy`. Retired identities redirect before rendering and preserve tab/query context. Existing non-company catalogs remain reachable; People is a profile tab, not a new top-level news surface. Varieties are displayed from actual stored portfolio roles; photo associations remain separate candidates. Regions use the shared Mission 4 annotations/editor, not a second geography store. Provisional identities still require review before canonical region/portfolio editing.

## User-editable metadata

Collected logo, website, LinkedIn and social links are shown when available. Analysts can upload a PNG/JPEG/GIF/WebP logo up to 2 MB or supply a public URL. Resetting a logo preserves previous upload files for recovery. Logo writes now require the same authoring/same-origin safeguards and atomic serialized storage; corrupt existing history is not silently overwritten. Read-only runtimes do not serve private uploaded logo overrides.

Website, LinkedIn and social links/handles can be edited or reset to collected values. These overrides take precedence only for presentation. People contacts support name, role, LinkedIn, social handles and highlighting; hide/restore preserves their history. Existing named people and explicit relationships retain their basis. A manually added contact does not create a canonical Person, employment relationship, reviewed Fact or verified identity.

Profile changes live in ignored `inbox/company_profile_overrides.json`, with company-scoped revisions, reviewer/time and before/after history. Stale forms fail visibly instead of overwriting a newer revision. Public URL validation rejects local/private/credentialed URLs. Corrupt state fails closed. Favorites/tiers/list actions use the existing feed state; reading continues to use `analyst_queue_state.json`. GET performs no writes, collection, paid research or full-capture hydration. No domain schema, Variety backbone, Trade, Weather or CPVO backend changes are made.

Private notes, contacts, marks and logos are excluded from read-only runtime presentation and public static output. This is local shared analyst state, not account-isolated storage or a distributed transaction system. New automatic AI profile enrichment is not implemented: future collectors must propose sourced changes and preserve manual overrides and review gates.

## Verification

- 178 focused Company, News, Map, Digest, seed, dossier, logo and compatibility checks pass. Coverage includes independent marks/subscriptions, concurrent saves, corrupt-state preservation, stale edits, safe URLs, contact hide/restore, retained person list members, per-story Digest filtering and read-only boundaries.
- Browser review in the isolated local workspace: directory alphabet navigation; favorite/tier persistence into a profile; custom list join and Digest subscription; profile link save; highlighted contact add/hide/restore; Map favorite/tier/list scope; shared Reader content and focus return. Sample contact remains hidden and sample list/state is labeled as review-only.
- Directory Focus shows eight complete rows in the normal desktop viewport. At 390px, directory and profile remain within the viewport; wide table columns scroll inside their container. Keyboard labels, visible focus and delayed icon tooltips remain available.
- Records validation passes. Static build produces 1,755 pages with no unpublished draft ids/titles. Full-suite exact-head CI is recorded in the draft PR after push.
- Review images: [Directory](../../artifacts/design-sprint/company-directory-live.png), [Company profile](../../artifacts/design-sprint/company-profile-live.png).

## Next missions and limits

Complete Varieties candidate reconciliation and geographic depth without treating photo associations as reviewed roles. Build the consolidated Reports & Briefings / Meeting Prep workspace, then configurable Landscape and detailed visual Learn with explicit deep-research jobs, followed by Monitor/Operations and the final visual workflow guide. Existing tools remain reachable until replacement workflows are demonstrated.

Remaining platform work includes safe prototype mark migration, per-account isolation, multi-worker transactions, sourced AI contact/profile proposals, recovery UI for previous logos and broader geography/statistics acquisition. Company marks are available as filters in the migrated Directory, News, Map and Digest; old specialist screens are retained, not all redesigned in this checkpoint. No coverage counts, maturity ratings, recall claims, canonical Evidence or approved identities change.
