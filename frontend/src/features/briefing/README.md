# Native bounded Briefing

`BriefingPage.tsx` exports named/default `BriefingPage` for the root FeatureSlots
integration. It reads the same current `/developments` model as the Landscape
rail and displays at most six cards, the exact matching count and the server's
scope/focus/typed-comparison basis. The server determines valid-subject precedence;
the client never substitutes an unfiltered cohort result. Source geography and
publication-date applicability remain visible. Unsupported selectors stop loading.

Shared `DevelopmentCard`, `Citation`, `useReadModel` and the pure
`developmentsContext` normalization were extracted from the already accepted
Landscape implementation. Existing roles/trust/translation/media/date/reference
photo and related-context labels remain on the same component. Briefing starts
the existing retained summary open. Selecting a source dispatches the shared
Reader action; no separate modal, body fetch workflow, collection or model exists.

Landscape's Open scoped Briefing now uses `/app/briefing` with the complete
canonical context. Briefing's Back to Landscape does the same. Full scoped News
uses the actual API-provided compatibility link plus `legacyHref`'s exact native
return. Following, Saved stories, Reading queue, Social listening and Signals are
explicit links to their established views, with their own controls and native
return; nothing new follows, saves, collects or approves on navigation.

The page calls `useSurfaceReady` after data/final empty/error DOM. Its dedicated
CSS coordinates three/two/one-column visual cards and the one shared detail area.
No manifest or shared shell change is included here. Three normalization cases
cover scope/date/role preservation, invalid-cohort focal fallback, dormant typed
pins, and independence from detail/demo/save presentation state. Mounted route,
Reader/return/history, narrow visuals and no-provider checks passed on the root's
`index-Cp5PKdjN.js` hardening build. The actual legacy News expansion also proved
zero automatic classification POST while its explicit Recheck control remained
wired through an intercepted-only response. See
`docs/experience-consolidation/acceptance/BRIEFING-QA.md` for current artifacts and
scope; final G2 manual acceptance belongs to the root reviewer.
