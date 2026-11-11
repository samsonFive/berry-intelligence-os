# Berry primitives and composition

Import `design/berry.css` once. Put `berry-app` on the application root; the
Floating UI preview applies that scope to its portal automatically. No font,
image, or runtime asset is fetched by these styles.

`components/ui` exports:

- `Button`: native button props and ref; `variant` is `primary`, `secondary`,
  `ghost`, or `danger`; `size` is `small` or `medium`; `busy` preserves its label
  while showing progress and disables repeat activation.
- `Badge`: native span props; `tone` is `neutral`, `sage`, `berry`, `warning`,
  `danger`, or `info`. Presenters choose the label and tone explicitly. A tone
  never assigns trust or changes record state.
- `EntityButton`: native button props/ref; `name`, `kind`, `meta`, `selected`,
  `compact`. Activation is entity focus/detail; use a separate pin control for
  comparison membership.
- `SourceLink`: native anchor props/ref, real `href`, optional `onOpen` for
  shared detail, and `external`. Modifier keys preserve normal new-tab behavior.
- `Preview`: `children` is the trigger's noninteractive label/content, `content`
  is supporting context, and `onOpenDetail` is the persistent-detail action.
  Optional `label`, `detailLabel`, `className`, `disabled`. It **owns the trigger
  button**: do not put another link/button inside `children`. Hover/focus opens
  the enterable preview; click, tap and Enter open persistent detail. Escape,
  an explicit dismiss button and outside press dismiss the preview. No state,
  URL, model, or query side effect occurs merely because the preview opens.
- `EmptyState`: `title`, optional explanatory `children`, `action`, `compact`,
  and `className`. Use one honest module-level state; missing cells use an
  accessible unknown label and an em dash.

Primary class vocabulary:

| Composition | Classes |
| --- | --- |
| Shell | `berry-shell`, `berry-topbar`, `berry-brand`, `berry-nav`, `berry-page`, `berry-page-heading`, `berry-eyebrow`, `berry-subtitle` |
| Scope/actions | `berry-scopebar`, `berry-commandbar`, `berry-commandbar-end`, `berry-segmented`, `berry-comparison-tray`, `berry-pin` |
| Applied-scope findings | `berry-readout`, `berry-readout-title`, `berry-findings`, `berry-finding` |
| Main/detail | `berry-workspace`, `berry-main`, `berry-detail`, `berry-detail-header`, `berry-detail-breadcrumbs`, `berry-detail-section`, `berry-detail-summary`, `berry-detail-actions` |
| Main renderer | `berry-analytical`, `berry-section-heading`, `berry-section-tools` |
| Relationships | `berry-relationship-header`, `berry-relationship-row`, `berry-relationship-actor`, `berry-relationship-path`, `berry-relationship-edge`, `berry-relationship-role`, `berry-relationship-target`, `berry-relationship-activity`, `berry-relationship-context` |
| News | `berry-developments`, `berry-news-grid`, `berry-news-card`, `berry-news-image`, `berry-news-body`, `berry-news-meta`, `berry-news-title`, `berry-news-excerpt`, `berry-news-actions`, `berry-news-match` |
| Reading | `berry-reader`, `berry-reader-meta`, `berry-reader-media`, `berry-reader-limit`, `berry-definition-list` |
| Analytical tables | `berry-grid`, `berry-table-wrap`, `berry-table`, `berry-frozen-identity` |
| Domain states | `berry-outside-scope`, `berry-issue`, `berry-error`, `berry-loading`, `berry-updating`, `berry-unknown` |
| Isolated demo | `berry-synthetic-label`, `berry-sensory-chart`, `berry-sensory-dot`, `berry-sensory-axis`, `berry-sensory-guide` |

Relationships use three aligned columns: actor, explicit role-bearing paths,
and geographic activity. An edge receives an arrow; an intermediate program
must be backed by a real record. `data-selected="true"` highlights a relationship
row without changing its scope. Keep source-named, planned, disputed and
outside-scope distinctions visible in content rather than relegating them to
previews. Findings remain editorial text separated by light rules.

The host lays out `berry-main` and an optional sibling `berry-detail`. Only
render the detail element when open. At 850px and below detail occupies the
viewport; the detail feature owner must provide focus containment, its explicit
return action, dialog semantics as appropriate, scroll locking, and focus/scroll
restoration. CSS does not implement those behaviors. The coordinated command
panel must use that same allocation rather than a third permanent drawer.

AG Grid CSS variables bridge existing theme use. The grid feature owner should
also map the Berry tokens through the pinned version's theming API when used.
Unknowns remain null and exports use domain data, independent of grid DOM.

V1 remains unreviewed until a populated mounted investigation is captured and
tested. Source completion or successful compilation is not visual acceptance.
