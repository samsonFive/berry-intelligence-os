import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode, RefObject } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
import type { ColDef, GridApi, GridOptions, ICellRendererParams } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import { legacyHref } from '../../app/legacy';
import { Button, EmptyState, EntityButton } from '../../components/ui';
import { hasBlockingIssues, serializeInvestigation, splitIds } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { VerifiedCompanyLogo } from '../brand-media/VerifiedCompanyLogo';
import { loadCompleteMonitoring } from './complete-monitoring';
import { RosterLayoutBusy } from './roster-layout-context';
import { rosterDisplayPage, type RosterPageSize } from './roster-display';
import { companyPageSwitchBlocked } from '../grids/company-pages';
import { isUserLayoutEvent } from '../grids/grid-state';
import { useAccountGridLayout } from '../grids/useAccountGridLayout';
import { workspaceGridTheme } from '../grids/workspace-grid-theme';
import { SheetToolbar } from '../grids/SheetToolbar';
import { defaultSheetColumnState } from '../grids/sheet-layout';
import { CompactCollection, CompactGenetics, CompactGeographies, CompactRoles } from './RosterCompactCells';
import { CompanyTierControl } from './CompanyTierControl';
import { CompanyRosterDetails } from './CompanyRosterDetails';
import type { CompanyRosterDetailsHandle } from './CompanyRosterDetails';
import { monitoringContext } from './company-set-context';
import { COMPANY_ROSTER_COLUMNS, COMPANY_ROSTER_VIEW_KEY, companyRosterText, companyTierBucket, companyTierRows, isRosterTierHeader, orderCompanyTierNodes, rosterTextMatch } from './company-roster-data';
import type { CompanyRosterRow } from './company-roster-data';
import type { LandscapeEdge, LandscapeModel, LandscapeNode, MonitoringCompany, MonitoringModel } from './models';
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
const ROSTER_ROW_ID: NonNullable<GridOptions<CompanyRosterRow>['getRowId']> = params => params.data.id;
const ROSTER_SORT: NonNullable<GridOptions<CompanyRosterRow>['postSortRows']> = params => {
  const ordered = orderCompanyTierNodes(params.nodes); params.nodes.splice(0, params.nodes.length, ...ordered);
};
const ROSTER_UNPIN: NonNullable<GridOptions<CompanyRosterRow>['processUnpinnedColumns']> = params => params.columns.filter(column => column.getColId() !== 'company.identity');

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

/** One complete read model; all display pages share global AG filtering/sorting. */
export function CompanyRoster(props: CompanyRosterProps) {
  const { context, revision, issues } = useInvestigation();
  const rosterContext = monitoringContext(context), key = serializeInvestigation(rosterContext);
  const query = useQuery({ queryKey: ['investigation', '/monitoring?complete=1', key],
    queryFn: ({ signal }) => loadCompleteMonitoring(rosterContext, revision, signal), enabled: !hasBlockingIssues(issues) });
  const roster = query.data?.data;
  const [display, setDisplay] = useState({ key: '', ready: false });
  const displayReady = useCallback((ready: boolean) => setDisplay(previous => previous.key === key && previous.ready === ready ? previous : { key, ready }), [key]);
  useLayoutEffect(() => props.onReady(!query.isPending && (query.isError || Boolean(roster && display.key === key && display.ready))),
    [props.onReady, query.isPending, query.isError, roster, display, key]);
  if (query.isPending) return <p className="berry-loading" role="status">Loading the complete company roster…</p>;
  if (query.isError) return <EmptyState compact title="Company roster unavailable" action={<Button size="small" onClick={() => void query.refetch()}>Try again</Button>}>{query.error instanceof Error ? query.error.message : 'The roster could not be loaded.'}</EmptyState>;
  if (!roster) return null;
  return <RosterDisplay {...props} roster={roster} onReady={displayReady} />;
}

function CompanyIdentity({ company, ids, details, tier }: { company: MonitoringCompany; ids: string[];
  details: RefObject<CompanyRosterDetailsHandle | null>; tier?: { label: string; count: number } }) {
  const { context, dispatch } = useInvestigation();
  return <div className="berry-roster-company" data-company-id={company.id}>
    {tier && <div className="berry-roster-tier-boundary"><strong>{tier.label}</strong><span>{tier.count} in company set</span></div>}
    <div className="berry-roster-identity"><VerifiedCompanyLogo id={company.id} name={company.label} companyIds={ids} />
      <EntityButton compact name={company.label} selected={context.focus === company.id}
        onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'company', id: company.id }, origin: 'grid' })} />
      <Button size="small" variant="ghost" className="berry-roster-info" aria-label={`Details for ${company.label}`} data-roster-details-for={company.id}
        onClick={event => details.current?.open(company.id, event.currentTarget)}>Info</Button>
    </div>
  </div>;
}
function CompanyCompare({ company }: { company: MonitoringCompany }) {
  const { context, dispatch } = useInvestigation(), pins = splitIds(context.cohort_companies);
  return <input type="checkbox" className="berry-roster-compare" aria-label={`Compare ${company.label}`}
    checked={pins.includes(company.id)} disabled={!pins.includes(company.id) && pins.length >= 5}
    title={!pins.includes(company.id) && pins.length >= 5 ? 'Remove a comparison pin before adding another; the company roster is uncapped.' : undefined}
    onChange={() => dispatch({ type: 'togglePin', entity: { type: 'company', id: company.id }, origin: 'grid' })} />;
}

function RosterDisplay({ model, roster, onReady, renderNode, renderEdge }: CompanyRosterProps & { roster: MonitoringModel }) {
  const { context, dispatch } = useInvestigation();
  const companyIds = useMemo(() => roster.companies.map(company => company.id), [roster.companies]);
  const [pageSize, setPageSize] = useState<RosterPageSize>(50);
  const sizeRef = useRef(pageSize); sizeRef.current = pageSize;
  const [pageState, setPageState] = useState({ index: 0, count: 1, start: 0, end: Math.min(50, roster.companies.length), total: roster.companies.length });
  const layout = useAccountGridLayout<CompanyRosterRow>(COMPANY_ROSTER_COLUMNS, COMPANY_ROSTER_VIEW_KEY, true, true);
  const grid = useRef<GridApi<CompanyRosterRow> | null>(null);
  const focus = useRef(context.focus); focus.current = context.focus;
  const rowClass = useCallback<NonNullable<GridOptions<CompanyRosterRow>['getRowClass']>>(params => params.data?.id === focus.current ? 'berry-grid-row-focused' : '', []);
  const identityRefreshPending = useRef(false);
  const refreshIdentities = useCallback(() => {
    if (identityRefreshPending.current) return;
    identityRefreshPending.current = true;
    queueMicrotask(() => {
      identityRefreshPending.current = false;
      if (grid.current && !grid.current.isDestroyed()) grid.current.refreshCells({ columns: ['company.identity'], force: true });
    });
  }, []);
  const [gridMounted, setGridMounted] = useState(false), [cards, setCards] = useState(roster.companies.slice(0, 50));
  const [cardOrder, setCardOrder] = useState(COMPANY_ROSTER_COLUMNS.map(column => column.colId));
  const [tierReceipt, setTierReceipt] = useState('');
  const root = useRef<HTMLElement>(null), companyDetails = useRef<CompanyRosterDetailsHandle>(null);
  const rowData = roster.companies;
  const tierHeaders = useMemo(() => companyTierRows(roster.companies, roster.tier_groups ?? []).filter(isRosterTierHeader), [roster.companies, roster.tier_groups]);
  const pins = splitIds(context.cohort_companies), blocked = companyPageSwitchBlocked(layout.status.phase);
  const text = useMemo(() => new Map(roster.companies.map(company => [company.id, companyRosterText(company, model)])), [roster.companies, model]);
  const syncCards = useCallback(() => {
    if (!grid.current || grid.current.isDestroyed()) return;
    const next: MonitoringCompany[] = [];
    grid.current.forEachNodeAfterFilterAndSort(node => { if (node.data && !isRosterTierHeader(node.data)) next.push(node.data); });
    const page = rosterDisplayPage(next, sizeRef.current, grid.current.paginationGetCurrentPage());
    setCards(previous => previous.length === page.rows.length && previous.every((row, index) => row === page.rows[index]) ? previous : page.rows);
    const { rows: ignored, ...state } = page;
    setPageState(previous => JSON.stringify(previous) === JSON.stringify(state) ? previous : state);
    const order = grid.current.getColumnState().map(column => column.colId);
    setCardOrder(previous => previous.join('\u0000') === order.join('\u0000') ? previous : order);
  }, []);
  useLayoutEffect(() => onReady(gridMounted && !layout.busy), [onReady, gridMounted, layout.busy]);
  const identity = (company: MonitoringCompany, tier?: { label: string; count: number }) => <CompanyIdentity company={company} ids={companyIds} details={companyDetails} tier={tier} />;
  const comparison = (company: MonitoringCompany) => <CompanyCompare company={company} />;
  const cells = (company: MonitoringCompany): Record<string, ReactNode> => ({
    'company.identity': identity(company),
    'company.tier': <CompanyTierControl company={company} disabled={false} saved={setTierReceipt} />,
    'company.compare': comparison(company),
    'company.genetics': <CompactGenetics id={company.id} model={model} renderNode={renderNode} renderEdge={renderEdge} />,
    'company.roles': <CompactRoles roles={company.roles} berryIds={company.berry_ids} />,
    'company.geography': <CompactGeographies geographies={company.geographies} open={id => dispatch({ type: 'openDetail', detail: { type: 'relationship', id }, origin: 'grid' })} />,
    'company.collection': <CompactCollection monitoring={company.monitoring} />,
  });
  const live = useRef({ cells, text, pins, roster }); live.current = { cells, text, pins, roster };
  // AG columns/framework renderer identities never depend on focus, pins, imagery,
  // layout visibility or owner render slots. Child hooks update those controls.
  const definitions = useMemo<ColDef<CompanyRosterRow>[]>(() => COMPANY_ROSTER_COLUMNS.map(column => ({
    colId: column.colId, headerName: column.label, initialWidth: column.defaultWidth, minWidth: column.minWidth, maxWidth: column.maxWidth,
    suppressSizeToFit: ['company.tier', 'company.compare'].includes(column.colId),
    sortable: !['company.tier', 'company.compare'].includes(column.colId),
    filter: ['company.tier', 'company.compare'].includes(column.colId) ? false : 'agTextColumnFilter',
    suppressHeaderMenuButton: ['company.tier', 'company.compare'].includes(column.colId),
    pinned: column.lockedVisible ? 'left' : undefined, lockPinned: true, lockVisible: Boolean(column.lockedVisible),
    initialHide: Boolean(column.defaultHidden),
    lockPosition: column.lockedVisible ? 'left' : undefined, suppressMovable: Boolean(column.lockedVisible),
    valueGetter: params => params.data && !isRosterTierHeader(params.data)
      ? column.colId === 'company.compare' ? live.current.pins.includes(params.data.id) ? 'Selected' : 'Not selected' : live.current.text.get(params.data.id)?.[column.colId] ?? '' : '',
    cellRenderer: (params: ICellRendererParams<CompanyRosterRow>) => {
      if (!params.data || isRosterTierHeader(params.data)) return null;
      if (column.colId === 'company.identity') {
        const company = params.data;
        const index = params.node.rowIndex ?? 0, previous = params.api.getDisplayedRowAtIndex(index - 1)?.data;
        const boundary = index === params.api.paginationGetCurrentPage() * params.api.paginationGetPageSize()
          || !previous || isRosterTierHeader(previous) || companyTierBucket(previous.assigned_tier) !== companyTierBucket(params.data.assigned_tier);
        const group = boundary ? live.current.roster.tier_groups.find(group => group.tier === companyTierBucket(company.assigned_tier)) : undefined;
        return <CompanyIdentity company={params.data} ids={live.current.roster.companies.map(company => company.id)} details={companyDetails} tier={group} />;
      }
      return <div className="berry-roster-cell">{live.current.cells(params.data)[column.colId]}</div>;
    },
  })), []);
  useEffect(() => {
    if (!grid.current || grid.current.isDestroyed()) return;
    // Update affected display cells without remounting an unsaved tier editor.
    grid.current.refreshCells({ columns: ['company.identity', 'company.compare', 'company.genetics', 'company.roles', 'company.geography', 'company.collection'] });
  }, [text, model, context.focus, context.cohort_companies]);
  const resetLayout = () => {
    grid.current?.applyColumnState({ state: defaultSheetColumnState(COMPANY_ROSTER_COLUMNS), applyOrder: true });
    grid.current?.setFilterModel(null); layout.changeQuickFilter(''); layout.changed();
  };
  const pages = <nav className="berry-roster-pages" aria-label="Company roster pages"><span aria-live="polite">{pageState.total ? `${pageState.start + 1}–${pageState.end} of ${pageState.total} companies` : 'No companies match'}</span>
    <label>Companies per view<select aria-label="Companies per view" value={pageSize} disabled={blocked} onChange={event => { setPageSize(event.target.value === 'all' ? 'all' : Number(event.target.value) as RosterPageSize); grid.current?.paginationGoToFirstPage(); }}>
      {[25, 50, 100, 'all'].map(size => <option key={size} value={size}>{size === 'all' ? 'All' : size}</option>)}</select></label>
    <Button size="small" variant="ghost" disabled={blocked || pageState.index === 0} onClick={() => grid.current?.paginationGoToPreviousPage()}>Previous</Button>
    <Button size="small" variant="ghost" disabled={blocked || pageState.index >= pageState.count - 1} onClick={() => grid.current?.paginationGoToNextPage()}>Next</Button></nav>;
  const showLayoutStatus = !['ready', 'saved'].includes(layout.status.phase);
  const hasCardContent = (company: MonitoringCompany, id: string) => {
    if (id === 'company.roles') return company.roles.length > 0 || company.berry_ids.length > 0;
    if (id === 'company.geography') return company.geographies.length > 0;
    if (id === 'company.genetics') { const genetics = rosterGenetics(model, company.id); return genetics.programs.length > 0 || genetics.varieties.length > 0 || genetics.edges.length > 0; }
    return id === 'company.collection';
  };
  return <RosterLayoutBusy.Provider value={blocked}><section ref={root} tabIndex={-1} className="berry-company-roster" aria-label="Company roster">
    <div className="berry-roster-title"><h2>Company roster</h2>{pages}</div>
    <CompanySearch key={`${context.q}\u0000${context.q_scope}`} disabled={blocked} />
    <div className="berry-roster-tier-summary" aria-label="Tiers across the selected company set">{roster.tier_groups?.map(group => <span key={group.tier}><strong>{group.label}</strong> {group.count}{context.q && <small> · {group.matching_count} search matches</small>}</span>)}</div>
    <SheetToolbar label="Company roster tools" className="berry-roster-view-tools"
      display={{ value: layout.view, onChange: layout.changeView, label: 'Company roster display', disabled: blocked }}
      filter={{ label: 'Filter companies', value: layout.quickFilter, onChange: layout.changeQuickFilter,
        placeholder: 'All companies in this result', disabled: layout.busy }}
      count={<span className="berry-roster-row-count">{cards.length} / {pageState.total} companies shown</span>}
      columns={{ columns: COMPANY_ROSTER_COLUMNS.map(column => ({ id: column.colId, label: column.label, locked: column.lockedVisible })),
        visible: layout.visible, busy: layout.busy, onChange: layout.changeVisibility, onReload: layout.reloadSavedLayout,
        actionDisabled: blocked || !gridMounted, onFit: () => { grid.current?.sizeColumnsToFit(); layout.changed(); } }}
      reset={{ onClick: resetLayout, disabled: blocked || !gridMounted }} />
    <div className="berry-grid-layout-status berry-roster-layout-status" data-phase={layout.status.phase} hidden={!showLayoutStatus}><p role="status">{showLayoutStatus ? layout.status.message : ''}</p></div>
    {!!roster.unavailable_watch_count && <p className="berry-issue">{roster.unavailable_watch_count} shared watched identities are unavailable; no replacement identity has been selected.</p>}
    {tierReceipt && <p className="berry-roster-tier-receipt" role="status">{tierReceipt}</p>}
    <>
      <div className="berry-roster-grid lw-research-grid" hidden={layout.view === 'cards'} aria-busy={layout.busy} inert={layout.busy}>
        <AgGridReact<CompanyRosterRow> theme={workspaceGridTheme} rowData={rowData} columnDefs={definitions} getRowId={ROSTER_ROW_ID} maintainColumnOrder
          defaultColDef={ROSTER_COLUMN_DEFAULTS}
          includeHiddenColumnsInQuickFilter quickFilterText={layout.quickFilter} rowHeight={54} headerHeight={34} animateRows={false}
          pagination paginationPageSize={pageSize === 'all' ? Math.max(1, roster.companies.length) : pageSize} paginationPageSizeSelector={false} suppressPaginationPanel
          onPaginationChanged={event => { syncCards(); if (event.newPage || event.newPageSize) refreshIdentities(); }}
          postSortRows={ROSTER_SORT}
          processUnpinnedColumns={ROSTER_UNPIN}
          onGridReady={event => { grid.current = event.api; layout.onReady(event.api); setGridMounted(true); syncCards(); }} onModelUpdated={() => { syncCards(); refreshIdentities(); }}
          onColumnResized={event => { if (isUserLayoutEvent('resize', event.source, event.finished)) layout.changed(); }}
          onColumnMoved={event => { syncCards(); if (isUserLayoutEvent('move', event.source, event.finished)) layout.changed(); }}
          onColumnVisible={event => { layout.syncVisibility(); if (isUserLayoutEvent('visible', event.source)) layout.changed(); }}
          onSortChanged={event => { syncCards(); if (isUserLayoutEvent('sort', event.source)) layout.changed(); }}
          onFilterChanged={event => { syncCards(); if (isUserLayoutEvent('filter', event.source) && !event.afterDataChange) layout.changed(); }}
          getRowClass={rowClass}
          overlayNoRowsTemplate="No companies match this filter." />
      </div>
      {layout.view === 'cards' && <div className="berry-roster-card-groups" aria-label="Company roster cards">{tierHeaders.filter(group => cards.some(company => companyTierBucket(company.assigned_tier) === group.tier)).map(group => <section className="berry-roster-tier-cards" key={group.tier} aria-label={group.label}><h3 className="berry-roster-tier-heading">{group.label}<span>{group.count === null ? 'Universe count unavailable' : `${group.count} in company set`} · {cards.filter(company => companyTierBucket(company.assigned_tier) === group.tier).length} shown on this page</span></h3><div className="berry-roster-cards">{cards.filter(company => companyTierBucket(company.assigned_tier) === group.tier).map(company => <article className="berry-roster-card" key={company.id} data-company-id={company.id}>
        <header>{identity(company)}</header><div className="berry-roster-card-selectors">
          {layout.visible['company.tier'] !== false && <div><span>Tier</span>{cells(company)['company.tier']}</div>}
          {layout.visible['company.compare'] !== false && <label>Compare{comparison(company)}</label>}
        </div>{cardOrder.flatMap(id => COMPANY_ROSTER_COLUMNS.filter(column => column.colId === id && !column.lockedVisible
          && !['company.tier', 'company.compare'].includes(id) && layout.visible[id] !== false && hasCardContent(company, id)))
          .map(column => <section key={column.colId}><h3>{column.label}</h3>{cells(company)[column.colId]}</section>)}
      </article>)}</div></section>)}</div>}
      {layout.view === 'cards' && !cards.length && <EmptyState compact title="No companies match this filter">Clear or change the company filter; the name-and-alias search remains separate.</EmptyState>}
    </>
    {!roster.companies.length && <EmptyState compact title={context.q ? 'No company names or aliases match' : 'No companies are available in this set'}>Change the roster search or company set explicitly. No companies have been substituted.</EmptyState>}
    <details className="berry-roster-explanation"><summary>{roster.universe_count} companies in this set{context.q ? ` · ${roster.matching_count} matches · ${roster.search_basis}` : ''} · Roster basis</summary><p>{roster.scope_note} Comparison is limited to five pins; the roster is not.</p>{roster.tier_basis && <p>{roster.tier_basis}</p>}<p>Genetics follow recorded paths; roles do not transfer. Location-only records do not specify activity or cultivar growing. Unrecorded activity remains unknown. Grid filters and sorting apply to the complete loaded company result before display pagination. Cards use the same filtered, sorted and paginated company identities.</p><a href={legacyHref('/queues/monitoring', '/app/landscape', context)}>Manage shared watches ↗</a></details>
    <CompanyRosterDetails ref={companyDetails} model={model} companies={roster.companies} rosterRoot={root} />
  </section></RosterLayoutBusy.Provider>;
}

export default CompanyRoster;
