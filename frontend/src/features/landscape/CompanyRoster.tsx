import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import { legacyHref } from '../../app/legacy';
import { Button, EmptyState, EntityButton } from '../../components/ui';
import { hasBlockingIssues, serializeInvestigation, splitIds } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { BrandLogo } from '../brand-media/BrandMedia';
import { useBrandMedia } from '../brand-media/useBrandMedia';
import { companyPageSwitchBlocked } from '../grids/company-pages';
import { isUserLayoutEvent } from '../grids/grid-state';
import { useAccountGridLayout } from '../grids/useAccountGridLayout';
import { workspaceGridTheme } from '../grids/workspace-grid-theme';
import { CompactCollection, CompactGenetics, CompactRoles } from './RosterCompactCells';
import { CompanyTierControl } from './CompanyTierControl';
import { monitoringContext } from './company-set-context';
import { COMPANY_ROSTER_COLUMNS, COMPANY_ROSTER_VIEW_KEY, TIER_HEADER_FILTER, companyRosterText, companyTierBucket, companyTierRows, isRosterTierHeader, orderCompanyTierNodes, rosterTextMatch } from './company-roster-data';
import type { CompanyRosterRow } from './company-roster-data';
import type { LandscapeEdge, LandscapeModel, LandscapeNode, MonitoringCompany, MonitoringModel } from './models';
import { useReadModel } from './useReadModel';
import '../grids/grid.css';
import './CompanyRoster.css';

ModuleRegistry.registerModules([AllCommunityModule]);

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

function RosterDisplay({ model, roster, onReady, changePage, renderNode, renderEdge, renderGeographies }: CompanyRosterProps & {
  roster: MonitoringModel; changePage: (offset: number) => void;
}) {
  const { context, dispatch } = useInvestigation();
  const media = useBrandMedia(roster.companies.map(company => company.id));
  const layout = useAccountGridLayout<CompanyRosterRow>(COMPANY_ROSTER_COLUMNS, COMPANY_ROSTER_VIEW_KEY, true);
  const grid = useRef<GridApi<CompanyRosterRow> | null>(null), columns = useRef<HTMLDetailsElement>(null);
  const [gridMounted, setGridMounted] = useState(false), [cards, setCards] = useState(roster.companies);
  const [cardOrder, setCardOrder] = useState(COMPANY_ROSTER_COLUMNS.map(column => column.colId));
  const [tierReceipt, setTierReceipt] = useState('');
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
    <div className="berry-roster-identity"><BrandLogo asset={media?.[company.id]?.logo} name={company.label} /><EntityButton compact name={company.label} selected={context.focus === company.id}
      onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'company', id: company.id }, origin: 'grid' })} /></div>
    <Button size="small" variant="ghost" aria-pressed={pins.includes(company.id)} disabled={!pins.includes(company.id) && pins.length >= 5}
      title={!pins.includes(company.id) && pins.length >= 5 ? 'Remove a comparison pin before adding another; the company roster is uncapped.' : undefined}
      onClick={() => dispatch({ type: 'togglePin', entity: { type: 'company', id: company.id }, origin: 'grid' })}>{pins.includes(company.id) ? 'Unpin' : 'Compare +'}</Button>
    <CompanyTierControl company={company} disabled={blocked} saved={setTierReceipt} />
    <div className="berry-roster-marks">{company.identity_note && <span className="berry-material-caveat">{company.identity_note}</span>}
      {!company.in_scope && <span>No standing links in this scope</span>}{context.company_set === 'all' && company.watched && <span>Shared watch</span>}</div>
    {layout.visible['company.collection'] !== true && <details className="berry-roster-monitoring"><summary>Monitoring details</summary><CompactCollection monitoring={company.monitoring} /></details>}
  </div>;
  const cells = (company: MonitoringCompany): Record<string, ReactNode> => ({
    'company.identity': identity(company),
    'company.genetics': <CompactGenetics id={company.id} model={model} renderNode={renderNode} renderEdge={renderEdge} />,
    'company.roles': <CompactRoles roles={company.roles} berryIds={company.berry_ids} />,
    'company.geography': renderGeographies(company.geographies),
    'company.collection': <CompactCollection monitoring={company.monitoring} />,
  });
  const definitions = useMemo<ColDef<CompanyRosterRow>[]>(() => COMPANY_ROSTER_COLUMNS.map(column => ({
    colId: column.colId, headerName: column.label, initialWidth: column.defaultWidth, minWidth: column.minWidth, maxWidth: column.maxWidth,
    pinned: column.lockedVisible ? 'left' : undefined, lockPinned: true, lockVisible: Boolean(column.lockedVisible),
    initialHide: Boolean(column.defaultHidden),
    lockPosition: column.lockedVisible ? 'left' : undefined, suppressMovable: Boolean(column.lockedVisible),
    valueGetter: params => isRosterTierHeader(params.data) ? TIER_HEADER_FILTER : params.data ? text.get(params.data.id)?.[column.colId] ?? '' : '',
    cellRenderer: (params: ICellRendererParams<CompanyRosterRow>) => params.data && !isRosterTierHeader(params.data) && <div className="berry-roster-cell">{cells(params.data)[column.colId]}</div>,
  })), [text, model, context.focus, context.company_set, dispatch, pins.join(','), media, renderNode, renderEdge, renderGeographies, blocked, layout.visible]);
  const resetLayout = () => {
    grid.current?.applyColumnState({ state: COMPANY_ROSTER_COLUMNS.map(column => ({ colId: column.colId, width: column.defaultWidth,
      hide: Boolean(column.defaultHidden) && !column.lockedVisible, sort: null, pinned: column.lockedVisible ? 'left' : null })), applyOrder: true });
    grid.current?.setFilterModel(null); layout.changeQuickFilter(''); layout.changed();
  };
  const pages = <nav className="berry-roster-pages" aria-label="Company roster pages"><span aria-live="polite">{roster.companies.length ? `${roster.offset + 1}–${roster.offset + roster.companies.length} of ${roster.total}` : `${roster.total} results · no rows on this page`}</span>
    <Button size="small" variant="ghost" disabled={blocked || roster.offset === 0} onClick={() => changePage(Math.max(0, roster.offset - roster.limit))}>Previous</Button>
    <Button size="small" variant="ghost" disabled={blocked || !roster.has_more || roster.next_offset === null} onClick={() => { if (roster.next_offset !== null) changePage(roster.next_offset); }}>Next</Button></nav>;
  return <section className="berry-company-roster" aria-label="Company roster">
    <div className="berry-roster-title"><h2>Company roster</h2>{pages}</div>
    <CompanySearch key={`${context.q}\u0000${context.q_scope}`} disabled={blocked} />
    <div className="berry-roster-tier-summary" aria-label="Tiers across the selected company set">{roster.tier_groups?.map(group => <span key={group.tier}><strong>{group.label}</strong> {group.count}{context.q && <small> · {group.matching_count} search matches</small>}</span>)}</div>
    <div className="lw-view-tools berry-roster-view-tools">
      <div role="group" aria-label="Company roster display"><Button size="small" aria-pressed={layout.view === 'grid'} disabled={blocked} onClick={() => layout.changeView('grid')}>Grid</Button><Button size="small" aria-pressed={layout.view === 'cards'} disabled={blocked} onClick={() => layout.changeView('cards')}>Cards</Button></div>
      <label>Filter loaded companies<input type="search" maxLength={200} disabled={layout.busy} value={layout.quickFilter} onChange={event => layout.changeQuickFilter(event.target.value)} placeholder="This ten-company page" /></label>
      <span className="berry-roster-row-count">{cards.length} / {roster.companies.length} loaded companies</span>
      <details className="berry-grid-columns" ref={columns} onKeyDown={event => { if (event.key === 'Escape') { columns.current!.open = false; columns.current?.querySelector('summary')?.focus(); } }}><summary>Columns</summary>
        <div className="berry-grid-column-options">{COMPANY_ROSTER_COLUMNS.map(column => <label key={column.colId}><input type="checkbox" checked={layout.visible[column.colId] ?? true} disabled={layout.busy || column.lockedVisible}
          onChange={event => layout.changeVisibility(column.colId, event.target.checked)} />{column.label}{column.lockedVisible && <small>Frozen identity</small>}</label>)}</div>
      </details><Button size="small" variant="ghost" disabled={blocked} onClick={resetLayout}>Reset layout</Button>
    </div>
    <div className="berry-grid-layout-status berry-roster-layout-status" data-phase={layout.status.phase}><p role="status">{layout.status.message}</p><Button size="small" variant="ghost" disabled={layout.busy} onClick={layout.reloadSavedLayout}>Reload saved layout</Button></div>
    {!!roster.unavailable_watch_count && <p className="berry-issue">{roster.unavailable_watch_count} shared watched identities are unavailable; no replacement identity has been selected.</p>}
    {tierReceipt && <p className="berry-roster-tier-receipt" role="status">{tierReceipt}</p>}
    <>
      <div className="berry-roster-grid lw-research-grid" hidden={layout.view === 'cards'} aria-busy={layout.busy} inert={layout.busy}>
        <AgGridReact<CompanyRosterRow> theme={workspaceGridTheme} rowData={rowData} columnDefs={definitions} getRowId={params => params.data.id} maintainColumnOrder
          defaultColDef={{ sortable: true, filter: 'agTextColumnFilter', filterParams: { maxNumConditions: 2,
            filterOptions: ['contains', 'notContains', 'equals', 'notEqual', 'startsWith', 'endsWith'], textMatcher: rosterTextMatch }, cellDataType: false, resizable: true, wrapText: true, autoHeight: true, wrapHeaderText: true, autoHeaderHeight: true }}
          includeHiddenColumnsInQuickFilter quickFilterText={layout.quickFilter} rowHeight={64} headerHeight={34} animateRows={false}
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
        <header>{identity(company)}</header>{cardOrder.flatMap(id => COMPANY_ROSTER_COLUMNS.filter(column => column.colId === id && !column.lockedVisible && layout.visible[id] !== false)).map(column => <section key={column.colId}><h3>{column.label}</h3>{cells(company)[column.colId]}</section>)}
      </article>)}</div></section>)}</div>}
      {layout.view === 'cards' && !cards.length && <EmptyState compact title="No loaded companies match this page filter">Clear or change the loaded-page filter; the server-wide roster search remains separate.</EmptyState>}
    </>
    {!roster.companies.length && <EmptyState compact title={context.q ? 'No company names or aliases match' : 'No companies are available in this set'}>Change the roster search or company set explicitly. No companies have been substituted.</EmptyState>}
    <details className="berry-roster-explanation"><summary>{roster.universe_count} companies in this set{context.q ? ` · ${roster.matching_count} matches · ${roster.search_basis}` : ''} · Roster basis</summary><p>{roster.scope_note} Comparison is limited to five pins; the roster is not.</p>{roster.tier_basis && <p>{roster.tier_basis}</p>}<p>Genetics follow recorded paths; roles do not transfer. Location-only records do not specify activity or cultivar growing. Unrecorded activity remains unknown. Grid filters and sorting apply only to this loaded company page. Cards use that same filtered and sorted page.</p><a href={legacyHref('/queues/monitoring', '/app/landscape', context)}>Manage shared watches ↗</a></details>
  </section>;
}

export default CompanyRoster;
