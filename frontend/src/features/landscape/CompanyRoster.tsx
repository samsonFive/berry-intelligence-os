import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import { legacyHref } from '../../app/legacy';
import { SESSION_TRANSITION_EVENT } from '../../app/PrivateQueryProvider';
import { Button, EmptyState, EntityButton, SourceLink } from '../../components/ui';
import { hasBlockingIssues, serializeInvestigation, splitIds } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { useBrandMedia } from '../brand-media/useBrandMedia';
import { companyPageSwitchBlocked } from '../grids/company-pages';
import { isUserLayoutEvent } from '../grids/grid-state';
import { useAccountGridLayout } from '../grids/useAccountGridLayout';
import { workspaceGridTheme } from '../grids/workspace-grid-theme';
import { CompactCollection, CompactGenetics, CompactGeographies, CompactRoles } from './RosterCompactCells';
import { CompanyTierControl } from './CompanyTierControl';
import { monitoringContext } from './company-set-context';
import { COMPANY_ROSTER_COLUMNS, COMPANY_ROSTER_VIEW_KEY, TIER_HEADER_FILTER, companyRosterText, companyTierBucket, companyTierRows, isRosterTierHeader, orderCompanyTierNodes, rosterTextMatch } from './company-roster-data';
import type { CompanyRosterRow } from './company-roster-data';
import type { LandscapeEdge, LandscapeModel, LandscapeNode, MonitoringCompany, MonitoringModel } from './models';
import { useReadModel } from './useReadModel';
import { rosterGenetics } from './roster-genetics';
import '../grids/grid.css';
import './CompanyRoster.css';

ModuleRegistry.registerModules([AllCommunityModule]);

// AG Grid treats a new defaultColDef object as a column-definition change.
// Keep it stable across local Info/dialog renders so cells and tier drafts survive.
const ROSTER_COLUMN_DEFAULTS: ColDef<CompanyRosterRow> = {
  sortable: true, filter: 'agTextColumnFilter', filterParams: { maxNumConditions: 2,
    filterOptions: ['contains', 'notContains', 'equals', 'notEqual', 'startsWith', 'endsWith'], textMatcher: rosterTextMatch },
  cellDataType: false, resizable: true, wrapText: true, autoHeight: true, wrapHeaderText: true, autoHeaderHeight: true,
};

export interface CompanyRosterProps {
  model: LandscapeModel;
  onReady: (ready: boolean) => void;
  renderNode: (node: LandscapeNode) => ReactNode;
  renderEdge: (edge: LandscapeEdge) => ReactNode;
  renderGeographies: (geographies: MonitoringCompany['geographies']) => ReactNode;
}

function CompanySearch({ disabled }: { disabled: boolean }) {
  const { context, dispatch } = useInvestigation();
  const [draft, setDraft] = useState(context.q), [basis, setBasis] = useState(context.q_scope);
  return <form className="berry-company-search" aria-label="Search company roster" onSubmit={event => {
    event.preventDefault(); dispatch({ type: 'setSearch', q: draft, q_scope: basis, origin: 'direct' });
  }}><fieldset disabled={disabled}>
    <label>Company<input type="search" maxLength={200} placeholder="Name or authored alias" value={draft} onChange={event => setDraft(event.target.value)} /></label>
    <label>Search in<select value={basis} onChange={event => setBasis(event.target.value as typeof basis)}><option value="scope">Standing field</option><option value="catalog">Selected company set</option></select></label>
    <Button size="small" type="submit">Find</Button>{context.q && <Button size="small" variant="ghost" onClick={() => dispatch({ type: 'setSearch', q: '', origin: 'direct' })}>Clear search</Button>}
  </fieldset></form>;
}

/** One server-paged company universe; Grid and Cards share its actual grid model. */
export function CompanyRoster(props: CompanyRosterProps) {
  const { context, issues } = useInvestigation();
  const rosterContext = monitoringContext(context), key = serializeInvestigation(rosterContext);
  const [page, setPage] = useState({ key: '', offset: 0 });
  const offset = page.key === key ? page.offset : 0;
  const query = useReadModel<MonitoringModel>(`/monitoring?offset=${offset}&limit=10`, rosterContext, !hasBlockingIssues(issues));
  const roster = query.data?.data;
  const readyKey = `${key}\u0000${offset}`;
  const [display, setDisplay] = useState({ key: '', ready: false });
  const displayReady = useCallback((ready: boolean) => setDisplay(previous => previous.key === readyKey && previous.ready === ready ? previous : { key: readyKey, ready }), [readyKey]);
  useLayoutEffect(() => props.onReady(!query.isPending && (query.isError || Boolean(roster && display.key === readyKey && display.ready))),
    [props.onReady, query.isPending, query.isError, roster?.companies.length, display, readyKey]);
  if (query.isPending) return <p className="berry-loading" role="status">Loading company roster…</p>;
  if (query.isError) return <EmptyState compact title="Company roster unavailable" action={<Button size="small" onClick={() => void query.refetch()}>Try again</Button>}>{query.error instanceof Error ? query.error.message : 'The roster could not be loaded.'}</EmptyState>;
  if (!roster) return null;
  return <RosterDisplay {...props} roster={roster} onReady={displayReady} changePage={value => setPage({ key, offset: value })} />;
}

function RosterDisplay({ model, roster, onReady, changePage, renderNode, renderEdge }: CompanyRosterProps & {
  roster: MonitoringModel; changePage: (offset: number) => void;
}) {
  const { context, dispatch } = useInvestigation();
  const media = useBrandMedia(roster.companies.map(company => company.id));
  const layout = useAccountGridLayout<CompanyRosterRow>(COMPANY_ROSTER_COLUMNS, COMPANY_ROSTER_VIEW_KEY, true, true);
  const grid = useRef<GridApi<CompanyRosterRow> | null>(null), columns = useRef<HTMLDetailsElement>(null);
  const [gridMounted, setGridMounted] = useState(false), [cards, setCards] = useState(roster.companies);
  const [cardOrder, setCardOrder] = useState(COMPANY_ROSTER_COLUMNS.map(column => column.colId));
  const [tierReceipt, setTierReceipt] = useState('');
  const root = useRef<HTMLElement>(null), dialog = useRef<HTMLDialogElement>(null), dialogClose = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLElement | null>(null), restoreDetailsFocus = useRef(true), openedCompany = useRef('');
  const detailsActive = useRef(false), detailsClosing = useRef(false), detailsCycle = useRef(0);
  const [detailsId, setDetailsId] = useState<string | null>(null);
  const detailsCompany = roster.companies.find(company => company.id === detailsId);
  const dialogHeading = useId();
  const finishDetails = useCallback(() => {
    if (!detailsActive.current || dialog.current?.open) return;
    detailsActive.current = false;
    const target = opener.current, companyId = openedCompany.current, restore = restoreDetailsFocus.current;
    const cycle = detailsCycle.current;
    opener.current = null; setDetailsId(null);
    if (restore) requestAnimationFrame(() => requestAnimationFrame(() => {
      if (!restoreDetailsFocus.current || cycle !== detailsCycle.current || detailsActive.current || !root.current?.isConnected) return;
      if (document.activeElement instanceof Element && document.activeElement.closest('.berry-detail, .berry-command')) return;
      const replacement = [...(root.current?.querySelectorAll<HTMLElement>('[data-roster-details-for]') ?? [])]
        .find(button => button.dataset.rosterDetailsFor === companyId && button.getClientRects().length > 0);
      (replacement ?? (target?.isConnected && target.getClientRects().length ? target : root.current))?.focus({ preventScroll: true });
    }));
  }, []);
  const closeDetails = useCallback((restore = true) => {
    // A reference action's no-restore choice remains sticky through repeated
    // context effects and the eventual native close event for this dialog.
    if (!restore) restoreDetailsFocus.current = false;
    if (!detailsActive.current || detailsClosing.current) return;
    detailsClosing.current = true;
    if (dialog.current?.open) dialog.current.close(); else finishDetails();
  }, [finishDetails]);
  useLayoutEffect(() => {
    if (detailsCompany && detailsActive.current && !detailsClosing.current && dialog.current && !dialog.current.open) {
      dialog.current.showModal(); dialogClose.current?.focus({ preventScroll: true });
    } else if (detailsId && !detailsCompany) closeDetails(false);
  }, [detailsId, detailsCompany, closeDetails]);
  const contextKey = serializeInvestigation(context), previousContext = useRef(contextKey);
  useLayoutEffect(() => {
    if (previousContext.current !== contextKey && detailsId) closeDetails(false);
    previousContext.current = contextKey;
  }, [contextKey, detailsId, closeDetails]);
  useEffect(() => {
    const clear = () => closeDetails(false);
    window.addEventListener(SESSION_TRANSITION_EVENT, clear);
    return () => { window.removeEventListener(SESSION_TRANSITION_EVENT, clear); restoreDetailsFocus.current = false; detailsActive.current = false; dialog.current?.close(); };
  }, [closeDetails]);
  const rowData = useMemo(() => companyTierRows(roster.companies, roster.tier_groups ?? []), [roster.companies, roster.tier_groups]);
  const tierHeaders = rowData.filter(isRosterTierHeader);
  const pins = splitIds(context.cohort_companies), blocked = companyPageSwitchBlocked(layout.status.phase);
  const text = useMemo(() => new Map(roster.companies.map(company => [company.id, companyRosterText(company, model)])), [roster.companies, model]);
  const syncCards = useCallback(() => {
    if (!grid.current || grid.current.isDestroyed()) return;
    const next: MonitoringCompany[] = [];
    grid.current.forEachNodeAfterFilterAndSort(node => { if (node.data && !isRosterTierHeader(node.data)) next.push(node.data); });
    setCards(previous => previous.length === next.length && previous.every((row, index) => row === next[index]) ? previous : next);
    const order = grid.current.getColumnState().map(column => column.colId);
    setCardOrder(previous => previous.join('\u0000') === order.join('\u0000') ? previous : order);
  }, []);
  useLayoutEffect(() => onReady(gridMounted && !layout.busy), [onReady, gridMounted, layout.busy]);
  useEffect(() => {
    const outside = (event: PointerEvent) => { if (columns.current?.open && event.target instanceof Node && !columns.current.contains(event.target)) columns.current.open = false; };
    document.addEventListener('pointerdown', outside); return () => document.removeEventListener('pointerdown', outside);
  }, []);
  const identity = (company: MonitoringCompany) => <div className="berry-roster-company" data-company-id={company.id}>
    <div className="berry-roster-identity">{media?.[company.id]?.logo && <img className="berry-roster-logo" src={media[company.id].logo!.image_url}
      data-background={media[company.id].logo!.background ?? 'light'} alt="" width="24" height="24" decoding="async" referrerPolicy="no-referrer" onError={event => { event.currentTarget.hidden = true; }} />}
      <EntityButton compact name={company.label} selected={context.focus === company.id}
        onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'company', id: company.id }, origin: 'grid' })} />
      <Button size="small" variant="ghost" className="berry-roster-info" aria-label={`Details for ${company.label}`} data-roster-details-for={company.id}
        onClick={event => {
          opener.current = event.currentTarget; openedCompany.current = company.id; restoreDetailsFocus.current = true;
          detailsActive.current = true; detailsClosing.current = false; detailsCycle.current++; setDetailsId(company.id);
        }}>Info</Button>
    </div>
  </div>;
  const comparison = (company: MonitoringCompany) => <input type="checkbox" className="berry-roster-compare" aria-label={`Compare ${company.label}`}
      checked={pins.includes(company.id)} disabled={!pins.includes(company.id) && pins.length >= 5}
      title={!pins.includes(company.id) && pins.length >= 5 ? 'Remove a comparison pin before adding another; the company roster is uncapped.' : undefined}
      onChange={() => dispatch({ type: 'togglePin', entity: { type: 'company', id: company.id }, origin: 'grid' })} />;
  const cells = (company: MonitoringCompany): Record<string, ReactNode> => ({
    'company.identity': identity(company),
    'company.tier': <CompanyTierControl company={company} disabled={blocked} saved={setTierReceipt} />,
    'company.compare': comparison(company),
    'company.genetics': <CompactGenetics id={company.id} model={model} renderNode={renderNode} renderEdge={renderEdge} />,
    'company.roles': <CompactRoles roles={company.roles} berryIds={company.berry_ids} />,
    'company.geography': <CompactGeographies geographies={company.geographies} open={id => dispatch({ type: 'openDetail', detail: { type: 'relationship', id }, origin: 'grid' })} />,
    'company.collection': <CompactCollection monitoring={company.monitoring} />,
  });
  const definitions = useMemo<ColDef<CompanyRosterRow>[]>(() => COMPANY_ROSTER_COLUMNS.map(column => ({
    colId: column.colId, headerName: column.label, initialWidth: column.defaultWidth, minWidth: column.minWidth, maxWidth: column.maxWidth,
    suppressSizeToFit: ['company.tier', 'company.compare'].includes(column.colId),
    sortable: !['company.tier', 'company.compare'].includes(column.colId),
    filter: ['company.tier', 'company.compare'].includes(column.colId) ? false : 'agTextColumnFilter',
    suppressHeaderMenuButton: ['company.tier', 'company.compare'].includes(column.colId),
    pinned: column.lockedVisible ? 'left' : undefined, lockPinned: true, lockVisible: Boolean(column.lockedVisible),
    initialHide: Boolean(column.defaultHidden),
    lockPosition: column.lockedVisible ? 'left' : undefined, suppressMovable: Boolean(column.lockedVisible),
    valueGetter: params => isRosterTierHeader(params.data) ? TIER_HEADER_FILTER : params.data
      ? column.colId === 'company.compare' ? pins.includes(params.data.id) ? 'Selected' : 'Not selected' : text.get(params.data.id)?.[column.colId] ?? '' : '',
    cellRenderer: (params: ICellRendererParams<CompanyRosterRow>) => params.data && !isRosterTierHeader(params.data) && <div className="berry-roster-cell">{cells(params.data)[column.colId]}</div>,
  })), [text, model, context.focus, context.company_set, dispatch, pins.join(','), media, renderNode, renderEdge, blocked, layout.visible]);
  const resetLayout = () => {
    grid.current?.applyColumnState({ state: COMPANY_ROSTER_COLUMNS.map(column => ({ colId: column.colId, width: column.defaultWidth,
      hide: Boolean(column.defaultHidden) && !column.lockedVisible, sort: null, pinned: column.lockedVisible ? 'left' : null })), applyOrder: true });
    grid.current?.setFilterModel(null); layout.changeQuickFilter(''); layout.changed();
  };
  const pages = <nav className="berry-roster-pages" aria-label="Company roster pages"><span aria-live="polite">{roster.companies.length ? `${roster.offset + 1}–${roster.offset + roster.companies.length} of ${roster.total}` : `${roster.total} results · no rows on this page`}</span>
    <Button size="small" variant="ghost" disabled={blocked || roster.offset === 0} onClick={() => changePage(Math.max(0, roster.offset - roster.limit))}>Previous</Button>
    <Button size="small" variant="ghost" disabled={blocked || !roster.has_more || roster.next_offset === null} onClick={() => { if (roster.next_offset !== null) changePage(roster.next_offset); }}>Next</Button></nav>;
  const showLayoutStatus = !['ready', 'saved'].includes(layout.status.phase);
  const hasCardContent = (company: MonitoringCompany, id: string) => {
    if (id === 'company.roles') return company.roles.length > 0 || company.berry_ids.length > 0;
    if (id === 'company.geography') return company.geographies.length > 0;
    if (id === 'company.genetics') { const genetics = rosterGenetics(model, company.id); return genetics.programs.length > 0 || genetics.varieties.length > 0 || genetics.edges.length > 0; }
    return id === 'company.collection';
  };
  const logo = detailsCompany ? media?.[detailsCompany.id]?.logo : null;
  const detailsSources = detailsCompany ? [...new Set([
    ...rosterGenetics(model, detailsCompany.id).edges.flatMap(edge => edge.evidence_ids),
    ...detailsCompany.geographies.flatMap(geo => geo.evidence_ids),
    ...(model.nodes[detailsCompany.id]?.evidence_ids ?? []),
  ])] : [];
  const detailNodes = new Map([...Object.values(model.nodes), ...[...model.portfolios, ...model.market_rows]
    .flatMap(portrait => [portrait.actor, ...portrait.programs, ...portrait.varieties])].map(node => [node.id, node]));
  const sourceButton = (id: string) => <button key={id} type="button" className="berry-text-button"
    onClick={() => dispatch({ type: 'openDetail', detail: { type: 'source', id }, origin: 'grid' })}>{model.sources.find(source => source.id === id)?.title || 'Open retained source'}</button>;
  const detailNode = (node: LandscapeNode) => node.type === 'breeding_program'
    ? <span>{node.label}<span className="berry-roster-compact-type"> · Breeding program</span></span>
    : <button type="button" className="berry-text-button" onClick={() => {
    if (node.type === 'company' || node.type === 'variety') dispatch({ type: 'focusEntity', entity: { type: node.type, id: node.id }, origin: 'grid' });
    else if (node.type === 'geography') dispatch({ type: 'openDetail', detail: { type: 'geography', id: node.id }, origin: 'grid' });
  }}>{node.label}</button>;
  const detailEdge = (edge: LandscapeEdge) => <div className="berry-roster-dialog-edge">
    <button type="button" className="berry-text-button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: edge.id }, origin: 'grid' })}><strong>{edge.role}</strong></button>
    <div className="berry-roster-dialog-path">{detailNodes.has(edge.subject_id) ? detailNode(detailNodes.get(edge.subject_id)!) : 'Unavailable recorded subject'}<span> → </span>{detailNodes.has(edge.object_id) ? detailNode(detailNodes.get(edge.object_id)!) : 'Unavailable recorded object'}</div>
    <p>{edge.status_label}</p>{edge.caveat && <p className="berry-material-caveat">{edge.caveat}</p>}{edge.scope_kind && <p>{edge.scope_kind}</p>}
    {!!edge.evidence_ids.length && <div className="berry-roster-dialog-evidence">{edge.evidence_ids.map(sourceButton)}</div>}
  </div>;
  return <section ref={root} tabIndex={-1} className="berry-company-roster" aria-label="Company roster">
    <div className="berry-roster-title"><h2>Company roster</h2>{pages}</div>
    <CompanySearch key={`${context.q}\u0000${context.q_scope}`} disabled={blocked} />
    <div className="berry-roster-tier-summary" aria-label="Tiers across the selected company set">{roster.tier_groups?.map(group => <span key={group.tier}><strong>{group.label}</strong> {group.count}{context.q && <small> · {group.matching_count} search matches</small>}</span>)}</div>
    <div className="lw-view-tools berry-roster-view-tools">
      <div role="group" aria-label="Company roster display"><Button size="small" aria-pressed={layout.view === 'grid'} disabled={blocked} onClick={() => layout.changeView('grid')}>Grid</Button><Button size="small" aria-pressed={layout.view === 'cards'} disabled={blocked} onClick={() => layout.changeView('cards')}>Cards</Button></div>
      <label>Filter loaded companies<input type="search" maxLength={200} disabled={layout.busy} value={layout.quickFilter} onChange={event => layout.changeQuickFilter(event.target.value)} placeholder="This ten-company page" /></label>
      <span className="berry-roster-row-count">{cards.length} / {roster.companies.length} loaded companies</span>
      <details className="berry-grid-columns" ref={columns} onKeyDown={event => { if (event.key === 'Escape') { columns.current!.open = false; columns.current?.querySelector('summary')?.focus(); } }}><summary>Columns</summary>
        <div className="berry-grid-column-options">{COMPANY_ROSTER_COLUMNS.map(column => <label key={column.colId}><input type="checkbox" checked={layout.visible[column.colId] ?? true} disabled={layout.busy || column.lockedVisible}
          onChange={event => layout.changeVisibility(column.colId, event.target.checked)} />{column.label}{column.lockedVisible && <small>Frozen identity</small>}</label>)}
          <Button size="small" variant="ghost" aria-label="Fit columns" disabled={blocked || !gridMounted} onClick={() => {
            grid.current?.sizeColumnsToFit(); layout.changed(); if (columns.current) columns.current.open = false;
          }}>Fit columns</Button>
          <Button size="small" variant="ghost" aria-label="Reload saved layout" disabled={layout.busy} onClick={layout.reloadSavedLayout}>Reload saved layout</Button></div>
      </details><Button size="small" variant="ghost" disabled={blocked} onClick={resetLayout}>Reset layout</Button>
    </div>
    <div className="berry-grid-layout-status berry-roster-layout-status" data-phase={layout.status.phase} hidden={!showLayoutStatus}><p role="status">{showLayoutStatus ? layout.status.message : ''}</p></div>
    {!!roster.unavailable_watch_count && <p className="berry-issue">{roster.unavailable_watch_count} shared watched identities are unavailable; no replacement identity has been selected.</p>}
    {tierReceipt && <p className="berry-roster-tier-receipt" role="status">{tierReceipt}</p>}
    <>
      <div className="berry-roster-grid lw-research-grid" hidden={layout.view === 'cards'} aria-busy={layout.busy} inert={layout.busy}>
        <AgGridReact<CompanyRosterRow> theme={workspaceGridTheme} rowData={rowData} columnDefs={definitions} getRowId={params => params.data.id} maintainColumnOrder
          defaultColDef={ROSTER_COLUMN_DEFAULTS}
          includeHiddenColumnsInQuickFilter quickFilterText={layout.quickFilter} rowHeight={54} headerHeight={34} animateRows={false}
          quickFilterMatcher={(parts, aggregate) => aggregate.includes(TIER_HEADER_FILTER.toUpperCase()) || parts.every(part => aggregate.includes(part))}
          postSortRows={params => { const ordered = orderCompanyTierNodes(params.nodes); params.nodes.splice(0, params.nodes.length, ...ordered); }}
          isFullWidthRow={params => isRosterTierHeader(params.rowNode.data)}
          getRowHeight={params => isRosterTierHeader(params.data) ? 30 : undefined}
          fullWidthCellRenderer={(params: ICellRendererParams<CompanyRosterRow>) => isRosterTierHeader(params.data) && <div className="berry-roster-tier-heading" role="rowheader"><strong>{params.data.label}</strong><span>{params.data.count === null ? 'Universe count unavailable' : `${params.data.count} in company set`} · {params.data.loaded_count} loaded on this page</span></div>}
          processUnpinnedColumns={params => params.columns.filter(column => column.getColId() !== 'company.identity')}
          onGridReady={event => { grid.current = event.api; layout.onReady(event.api); setGridMounted(true); syncCards(); }} onModelUpdated={syncCards}
          onColumnResized={event => { if (isUserLayoutEvent('resize', event.source, event.finished)) layout.changed(); }}
          onColumnMoved={event => { syncCards(); if (isUserLayoutEvent('move', event.source, event.finished)) layout.changed(); }}
          onColumnVisible={event => { layout.syncVisibility(); if (isUserLayoutEvent('visible', event.source)) layout.changed(); }}
          onSortChanged={event => { syncCards(); if (isUserLayoutEvent('sort', event.source)) layout.changed(); }}
          onFilterChanged={event => { syncCards(); if (isUserLayoutEvent('filter', event.source) && !event.afterDataChange) layout.changed(); }}
          getRowClass={params => params.data?.id === context.focus ? 'berry-grid-row-focused' : ''}
          overlayNoRowsTemplate="No loaded companies match this page filter." />
      </div>
      {layout.view === 'cards' && <div className="berry-roster-card-groups" aria-label="Company roster cards">{tierHeaders.filter(group => cards.some(company => companyTierBucket(company.assigned_tier) === group.tier)).map(group => <section className="berry-roster-tier-cards" key={group.tier} aria-label={group.label}><h3 className="berry-roster-tier-heading">{group.label}<span>{group.count === null ? 'Universe count unavailable' : `${group.count} in company set`} · {cards.filter(company => companyTierBucket(company.assigned_tier) === group.tier).length} shown on this page</span></h3><div className="berry-roster-cards">{cards.filter(company => companyTierBucket(company.assigned_tier) === group.tier).map(company => <article className="berry-roster-card" key={company.id} data-company-id={company.id}>
        <header>{identity(company)}</header><div className="berry-roster-card-selectors">
          {layout.visible['company.tier'] !== false && <div><span>Tier</span>{cells(company)['company.tier']}</div>}
          {layout.visible['company.compare'] !== false && <label>Compare{comparison(company)}</label>}
        </div>{cardOrder.flatMap(id => COMPANY_ROSTER_COLUMNS.filter(column => column.colId === id && !column.lockedVisible
          && !['company.tier', 'company.compare'].includes(id) && layout.visible[id] !== false && hasCardContent(company, id)))
          .map(column => <section key={column.colId}><h3>{column.label}</h3>{cells(company)[column.colId]}</section>)}
      </article>)}</div></section>)}</div>}
      {layout.view === 'cards' && !cards.length && <EmptyState compact title="No loaded companies match this page filter">Clear or change the loaded-page filter; the server-wide roster search remains separate.</EmptyState>}
    </>
    {!roster.companies.length && <EmptyState compact title={context.q ? 'No company names or aliases match' : 'No companies are available in this set'}>Change the roster search or company set explicitly. No companies have been substituted.</EmptyState>}
    <details className="berry-roster-explanation"><summary>{roster.universe_count} companies in this set{context.q ? ` · ${roster.matching_count} matches · ${roster.search_basis}` : ''} · Roster basis</summary><p>{roster.scope_note} Comparison is limited to five pins; the roster is not.</p>{roster.tier_basis && <p>{roster.tier_basis}</p>}<p>Genetics follow recorded paths; roles do not transfer. Location-only records do not specify activity or cultivar growing. Unrecorded activity remains unknown. Grid filters and sorting apply only to this loaded company page. Cards use that same filtered and sorted page.</p><a href={legacyHref('/queues/monitoring', '/app/landscape', context)}>Manage shared watches ↗</a></details>
    <dialog ref={dialog} className="berry-roster-dialog" aria-labelledby={dialogHeading} onClose={finishDetails}
      onKeyDownCapture={event => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeDetails(); } }}
      onCancel={event => { event.preventDefault(); closeDetails(); }}>
      {detailsCompany && <><header><h2 id={dialogHeading}>{detailsCompany.label}</h2><Button ref={dialogClose} size="small" onClick={() => closeDetails()} aria-label={`Close details for ${detailsCompany.label}`}>Close</Button></header>
        <div className="berry-roster-dialog-body" onClickCapture={event => {
          // Native modal inertness must end before the existing Reader/focus action.
          if (event.target instanceof Element && event.target.closest('button,a')) closeDetails(false);
        }}>
          <section><h3>Company context</h3><dl className="berry-roster-context-list">
            <div><dt>Identity</dt><dd>{detailsCompany.identity_status}{detailsCompany.identity_note && <p>{detailsCompany.identity_note}</p>}</dd></div>
            <div><dt>Standing scope</dt><dd>{detailsCompany.in_scope ? 'Recorded standing links in this scope' : 'No standing links in this scope'}</dd></div>
            <div><dt>Shared watch</dt><dd>{detailsCompany.watched ? 'On the shared Watch list' : 'Not on the shared Watch list'}</dd></div>
            <div><dt>Assigned tier</dt><dd>{detailsCompany.assigned_tier_label}</dd></div>
          </dl><Button size="small" variant="ghost" onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'company', id: detailsCompany.id }, origin: 'grid' })}>Open company profile</Button></section>
          <section><h3>Genetics and exact recorded paths</h3><CompactGenetics expanded id={detailsCompany.id} model={model} renderNode={detailNode} renderEdge={detailEdge} /></section>
          <section><h3>Authored roles and berries</h3><CompactRoles expanded roles={detailsCompany.roles} berryIds={detailsCompany.berry_ids} /></section>
          <section><h3>Geographic activity and sources</h3>{detailsCompany.geographies.length ? <div className="berry-roster-full-geographies">{detailsCompany.geographies.map((geo, index) => <article key={`${geo.relationship_id}-${index}`}>
            <button type="button" className="berry-text-button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: geo.relationship_id }, origin: 'grid' })}><strong>{geo.label}</strong> · {geo.activity}</button>
            <p>{geo.status}</p>{geo.caveat && <p className="berry-material-caveat">{geo.caveat}</p>}{geo.review && <p>Review: {geo.review}</p>}
            {!!geo.evidence_ids.length && <div className="berry-roster-dialog-evidence">{geo.evidence_ids.map(sourceButton)}</div>}
          </article>)}</div> : <p>No geographic activity is recorded in scope.</p>}</section>
          {!!detailsSources.length && <section><h3>Retained sources</h3><ul className="berry-roster-dialog-sources">{detailsSources.map(id => {
            const source = model.sources.find(row => row.id === id);
            return <li key={id}><button type="button" className="berry-text-button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'source', id }, origin: 'grid' })}>{source?.title || 'Open retained source'}</button>
              {source?.source_name && <span>{source.source_name}</span>}{source?.published && <span>Published {source.published}</span>}
            </li>;
          })}</ul></section>}
          <section><h3>Monitoring and collection</h3><CompactCollection expanded monitoring={detailsCompany.monitoring} /></section>
          {logo && <section><h3>Logo and source credit</h3><figure className="berry-roster-logo-credit"><img src={logo.image_url} data-background={logo.background ?? 'light'} alt={`${detailsCompany.label} logo`} width="100" height="64" referrerPolicy="no-referrer" />
            <figcaption>{logo.caption && <p>{logo.caption}</p>}<p>{logo.kind_label}{logo.source_kind && ` · ${logo.source_kind}`}</p>{logo.attribution && <p>{logo.attribution}</p>}
              {logo.match_basis && <p>{logo.match_basis}</p>}{logo.historical_status && <p>{logo.historical_status.replaceAll('_', ' ')}</p>}
              {logo.source_account && <p>{logo.source_account}</p>}{logo.published_at && <p>Published {logo.published_at}</p>}
              {logo.inspection_href && <SourceLink external href={logo.inspection_href}>Inspect retained source</SourceLink>}{logo.source_page_url && <SourceLink external href={logo.source_page_url}>Original source</SourceLink>}
            </figcaption></figure></section>}
        </div></>}
    </dialog>
  </section>;
}

export default CompanyRoster;
