import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { AllCommunityModule, ModuleRegistry, type ColDef, type ICellRendererParams } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import { Button, EmptyState, EntityButton, Preview } from '../../components/ui';
import { useInvestigation } from '../../state/InvestigationProvider';
import { splitIds } from '../../contracts/investigation';
import type { LandscapeEdge, LandscapeModel, LandscapeNode } from '../landscape/models';
import { Citation } from '../landscape/Citation';
import type { LayoutColumn } from './layout-codec';
import { isUserLayoutEvent } from './grid-state';
import { useAccountGridLayout } from './useAccountGridLayout';
import { COMPANY_COLUMN_SIZES, companyPage, companyPageSwitchBlocked, companyPageViewKey } from './company-pages';
import type { CompanyPage } from './company-pages';
import type { CompanyColumnSize } from './company-pages';
import { portfolioData, type PortfolioRow } from './portfolio-data';
import { useCompanyPageMemory } from './useCompanyPageMemory';
import { usePortfolioSessionLayout } from './usePortfolioSessionLayout';
import { VerifiedCompanyLogo } from '../brand-media/VerifiedCompanyLogo';
import './grid.css';
import { workspaceGridTheme } from './workspace-grid-theme';

ModuleRegistry.registerModules([AllCommunityModule]);

const berryGridTheme = workspaceGridTheme;

/** A directed role and compact qualifier; the complete source basis stays on demand. */
function PortfolioRelationship({ edge, model, open }: {
  edge: LandscapeEdge; model: LandscapeModel; open: () => void;
}) {
  const subject = model.nodes[edge.subject_id];
  const object = model.nodes[edge.object_id];
  const path = `${subject?.label ?? 'Unresolved recorded subject'} → ${object?.label ?? 'Unresolved recorded target'}`;
  const identityNotes = [...new Set([subject?.identity_note, object?.identity_note].filter((note): note is string => !!note))];
  return <article className="berry-portfolio-edge" data-edge-status={edge.status}>
    <Preview className="berry-grid-role berry-portfolio-edge-trigger" label="Recorded portfolio relationship" detailLabel="Inspect relationship"
      onOpenDetail={open} content={<div className="berry-portfolio-edge-preview"><strong>{edge.role}</strong><p>{path}</p>
        <dl><div><dt>Recorded status</dt><dd>{edge.status_label}</dd></div><div><dt>Source review</dt><dd>{edge.review}</dd></div></dl>
        {identityNotes.map(note => <p key={note}>{note}</p>)}{edge.caveat && <p>{edge.caveat}</p>}{edge.notes && <p>{edge.notes}</p>}
        {!!edge.evidence_ids.length && <div className="berry-portfolio-edge-sources"><span>Sources</span><div>{edge.evidence_ids.map(id => <Citation key={id} id={id} source={model.sources.find(source => source.id === id)} parent={{ type: 'relationship', id: edge.id }} />)}</div></div>}
      </div>}>
      <strong className="berry-portfolio-edge-role">{edge.role}</strong>
      {edge.status !== 'active' && <span className="berry-portfolio-edge-status">{edge.status_label}</span>}
      <span className="berry-portfolio-edge-path">{path}</span>
    </Preview>
  </article>;
}

/** A real Community grid. Canonical identity and comparison membership stay separate. */
export function BerryDataGrid({ model, onReady }: { model: LandscapeModel; onReady?: (ready: boolean) => void }) {
  const { companies, rows } = useMemo(() => portfolioData(model), [model]);
  const pagination = useCompanyPageMemory(companies);
  const pageIndex = pagination.index;
  const plan = useMemo(() => {
    try { return { page: companyPage(companies, pageIndex, pagination.size), error: '' }; }
    catch (error) { return { page: null, error: error instanceof Error ? error.message : 'Company columns are unavailable.' }; }
  }, [companies, pageIndex, pagination.size]);
  const page = plan.page;
  const pageIdentity = JSON.stringify([page?.membershipBound, page?.companies.map(company => company.id)]);
  const [resolvedLayout, setResolvedLayout] = useState<{ identity: string; key: string; error: string } | null>(null);
  useEffect(() => {
    let active = true;
    if (page && pagination.ready) void companyPageViewKey(page.companies.map(company => company.id), page.membershipBound)
      .then(key => { if (active) setResolvedLayout({ identity: pageIdentity, key, error: '' }); })
      .catch(() => { if (active) setResolvedLayout({ identity: pageIdentity, key: '', error: 'The display layout for these company columns could not be identified. Reopen the portfolio to try again.' }); });
    return () => { active = false; };
  }, [pageIdentity, pagination.ready]);
  const displayGrid = Boolean(pagination.ready && page && rows.length && resolvedLayout?.identity === pageIdentity && !resolvedLayout.error);
  const finalMessage = pagination.ready && (!page || !rows.length || resolvedLayout?.identity === pageIdentity && Boolean(resolvedLayout.error));
  useLayoutEffect(() => { if (!displayGrid) onReady?.(finalMessage); }, [onReady, displayGrid, finalMessage]);
  if (!pagination.ready) return <p role="status" className="berry-loading">Restoring company columns…</p>;
  if (!page) return <EmptyState title="Company columns could not be displayed">{plan.error}</EmptyState>;
  if (!rows.length) return <EmptyState title="No cultivar portfolio relationships in this scope">Recorded geographic connections can still be inspected in Connections. Missing portfolio records do not establish an absence of commercial access.</EmptyState>;
  if (!resolvedLayout || resolvedLayout.identity !== pageIdentity) return <p role="status" className="berry-loading">Preparing company columns {page.start + 1}–{page.end} of {page.total}…</p>;
  if (resolvedLayout.error) return <EmptyState title="Company display preferences are unavailable">{resolvedLayout.error}</EmptyState>;
  return <PortfolioGrid key={`${resolvedLayout.key}:${pageIdentity}`} model={model} companies={page.companies} rows={rows}
    viewKey={resolvedLayout.key} page={page} changePage={pagination.setIndex} changeSize={pagination.setSize} onReady={onReady} />;
}

function ColumnVisibility({ columns, visible, busy, change, reload, sessionOnly = false }: {
  columns: Array<{ id: string; label: string; locked?: boolean }>; visible: Record<string, boolean>; busy: boolean;
  change: (id: string, show: boolean) => void; reload: () => void; sessionOnly?: boolean;
}) {
  const popup = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const outside = (event: PointerEvent) => {
      if (popup.current?.open && event.target instanceof Node && !popup.current.contains(event.target)) popup.current.open = false;
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || !popup.current?.open) return;
      event.preventDefault(); popup.current.open = false; popup.current.querySelector('summary')?.focus();
    };
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, []);
  return <details className="berry-grid-columns" ref={popup}>
    <summary className="berry-button berry-button--quiet">Columns</summary>
    <div className="berry-grid-column-options">
      {columns.map(column => <label key={column.id}><input type="checkbox" checked={visible[column.id] ?? true} disabled={busy || column.locked}
        aria-label={`Show ${column.label} column`} onChange={event => change(column.id, event.target.checked)} />
        <span>{column.label}{column.locked && <small>Fixed</small>}</span></label>)}
      <Button size="small" variant="ghost" disabled={busy} onClick={reload}>{sessionOnly ? 'Reload session layout' : 'Reload saved layout'}</Button>
    </div>
  </details>;
}

interface PortfolioGridProps {
  model: LandscapeModel; companies: LandscapeNode[]; rows: PortfolioRow[];
  viewKey: string; page: CompanyPage<LandscapeNode>; changePage: (index: number) => void;
  changeSize: (size: CompanyColumnSize) => void; onReady?: (ready: boolean) => void;
}
function PortfolioGrid(props: PortfolioGridProps) {
  const { companies } = props;
  const specs = useMemo<LayoutColumn[]>(() => [
    { colId: 'cultivar.identity', defaultWidth: 220, minWidth: 150, maxWidth: 1200, lockedVisible: true },
    { colId: 'cultivar.comparison-pin', defaultWidth: 75, minWidth: 65, maxWidth: 90, lockedVisible: true },
    ...companies.map(company => ({ colId: `company.${company.id}.recorded-role`, defaultWidth: 260, minWidth: 220, maxWidth: 1200 })),
  ], [companies]);
  return specs.length > 40 ? <SessionPortfolioGrid {...props} specs={specs} /> : <AccountPortfolioGrid {...props} specs={specs} />;
}
function AccountPortfolioGrid(props: PortfolioGridProps & { specs: LayoutColumn[] }) {
  const layout = useAccountGridLayout<PortfolioRow>(props.specs, props.viewKey);
  return <PortfolioDisplay {...props} layout={layout} sessionOnly={false} />;
}
function SessionPortfolioGrid(props: PortfolioGridProps & { specs: LayoutColumn[] }) {
  const layout = usePortfolioSessionLayout<PortfolioRow>(props.specs, props.viewKey);
  return <PortfolioDisplay {...props} layout={layout} sessionOnly />;
}
function PortfolioDisplay({ model, companies, rows, page, changePage, changeSize, onReady, layout, sessionOnly }: PortfolioGridProps & {
  layout: ReturnType<typeof useAccountGridLayout<PortfolioRow>>; sessionOnly: boolean;
}) {
  const { context, dispatch } = useInvestigation();
  const selectedCompanies = splitIds(context.cohort_companies);
  const selectedVarieties = splitIds(context.cohort_varieties);
  const [gridMounted, setGridMounted] = useState(false);
  useLayoutEffect(() => onReady?.(gridMounted && !layout.busy), [onReady, gridMounted, layout.busy]);
  const pageBlocked = companyPageSwitchBlocked(layout.status.phase);
  const columnChoices = [{ id: 'cultivar.identity', label: 'Cultivar', locked: true }, { id: 'cultivar.comparison-pin', label: 'Comparison pin', locked: true },
    ...companies.map(company => ({ id: `company.${company.id}.recorded-role`, label: company.label }))];
  const columnDefs = useMemo<ColDef<PortfolioRow>[]>(() => [
    {
      colId: 'cultivar.identity', headerName: 'Cultivar', pinned: 'left', initialWidth: 220, minWidth: 150, maxWidth: 1200,
      lockPinned: true, lockVisible: true, lockPosition: 'left', suppressMovable: true,
      wrapText: true, autoHeight: true,
      valueGetter: params => params.data?.variety.label ?? '',
      cellRenderer: (params: ICellRendererParams<PortfolioRow>) => params.data && <div className="berry-portfolio-identity"><EntityButton compact name={params.data.variety.label}
        selected={context.focus === params.data.id}
        onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'variety', id: params.data!.id }, origin: 'grid' })} /></div>,
    },
    {
      colId: 'cultivar.comparison-pin', headerName: 'Pin', pinned: 'left', initialWidth: 75, minWidth: 65, maxWidth: 90,
      sortable: false, filter: false, suppressMovable: true, lockPinned: true, lockVisible: true, lockPosition: 'left',
      cellRenderer: (params: ICellRendererParams<PortfolioRow>) => params.data && <input type="checkbox"
        aria-label={`Pin ${params.data.variety.label} for variety comparison`} checked={selectedVarieties.includes(params.data.id)}
        onChange={() => dispatch({ type: 'togglePin', entity: { type: 'variety', id: params.data!.id }, origin: 'grid' })} />,
    },
    ...companies.map(company => ({
      colId: `company.${company.id}.recorded-role`, headerName: company.label, minWidth: 220, maxWidth: 1200, initialWidth: 260, lockPinned: true,
      headerComponentParams: { innerHeaderComponent: () => <span><VerifiedCompanyLogo id={company.id} name={company.label} companyIds={companies.map(row => row.id)} /><span>{company.label}</span></span> },
      wrapText: true, autoHeight: true,
      valueGetter: (params: { data?: PortfolioRow }) => (params.data?.byCompany[company.id] ?? []).map(edge => edge.label).join('; '),
      cellRenderer: (params: ICellRendererParams<PortfolioRow>) => {
        const edges = params.data?.byCompany[company.id] ?? [];
        return edges.length ? <div className="berry-grid-role-list berry-portfolio-cell">{edges.map(edge => <PortfolioRelationship key={edge.id}
          edge={edge} model={model} open={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: edge.id }, origin: 'grid' })} />)}</div>
          : <span className="berry-unknown" aria-label="Unknown: no recorded portfolio relationship">—</span>;
      },
    })),
  ], [companies, context.focus, dispatch, model.nodes, model.sources, selectedVarieties.join(',')]);

  return <section aria-label="Recorded company and cultivar portfolio">
    <nav className="berry-portfolio-pages" aria-label="Portfolio company pages">
      <p aria-live="polite"><strong>Companies {page.start + 1}–{page.end} of {page.total}</strong><span> · {rows.length} cultivars</span>{page.paged && <span> · Page {page.index + 1} of {page.count}</span>}</p>
      <label>Company columns<select value={page.choice} disabled={pageBlocked} onChange={event => changeSize(event.target.value === 'all' ? 'all' : Number(event.target.value) as CompanyColumnSize)}>
        {COMPANY_COLUMN_SIZES.map(size => <option key={size} value={size}>{size === 'all' ? 'All' : size}</option>)}
      </select></label>
      {page.paged && <div><Button size="small" variant="secondary" disabled={pageBlocked || page.index === 0} onClick={() => changePage(page.index - 1)}>Previous companies</Button>
        <label>Company page<select value={page.index} disabled={pageBlocked} onChange={event => changePage(Number(event.target.value))}>
          {Array.from({ length: page.count }, (_, index) => <option key={index} value={index}>{index + 1} · {index * page.size + 1}–{Math.min((index + 1) * page.size, page.total)}</option>)}
        </select></label>
        <Button size="small" variant="secondary" disabled={pageBlocked || page.index === page.count - 1} onClick={() => changePage(page.index + 1)}>Next companies</Button></div>}
    </nav>
    {page.paged && pageBlocked && <p className="berry-scope-note" role="status">{layout.status.phase === 'conflict' ? 'Reload the saved layout before changing company page.' : 'Wait for the current layout to finish loading or saving before changing company page.'}</p>}
    <div className="berry-grid-company-controls" aria-label="Company focus and comparison pins">{companies.map(company => <div key={company.id}>
      <EntityButton compact name={company.label} selected={context.focus === company.id} onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'company', id: company.id }, origin: 'grid' })} />
      <Button size="small" variant="ghost" aria-pressed={selectedCompanies.includes(company.id)} onClick={() => dispatch({ type: 'togglePin', entity: { type: 'company', id: company.id }, origin: 'grid' })}>{selectedCompanies.includes(company.id) ? 'Unpin' : 'Pin'}</Button>
    </div>)}</div>
    <div className="berry-grid-preferences"><label className="berry-field-label">Filter this company group<input className="berry-input" type="search" maxLength={200} disabled={layout.busy} value={layout.quickFilter} onChange={event => layout.changeQuickFilter(event.target.value)} placeholder="Cultivar, role or company in this group" /></label>
      <ColumnVisibility columns={columnChoices} visible={layout.visible} busy={layout.busy} change={layout.changeVisibility} reload={layout.reloadSavedLayout} sessionOnly={sessionOnly} />
    </div>
    {sessionOnly ? <div className="berry-grid-layout-status" data-phase={layout.status.phase}><Preview label="Session layout" content={<p>Windows with more than forty columns keep resize, order, visibility and filter preferences in this session. Account layouts remain unchanged. Return to 10 or 25 company columns to restore their saved account layout.</p>}>Session layout</Preview>
      {layout.status.phase === 'error' && <span role="status">{layout.status.message}</span>}</div> : <div className="berry-grid-layout-status" data-phase={layout.status.phase} hidden={['ready', 'saved'].includes(layout.status.phase)}>
      <p role="status" aria-live="polite">{layout.status.message}</p>
      {['error', 'conflict', 'local'].includes(layout.status.phase) && <Button size="small" variant="ghost" disabled={layout.busy} onClick={layout.reloadSavedLayout}>Reload saved layout</Button>}
    </div>}
    <div className="berry-grid berry-portfolio-grid" data-grid-edition="community" aria-busy={layout.busy} inert={layout.busy}>
      <AgGridReact<PortfolioRow> theme={berryGridTheme} rowData={rows} columnDefs={columnDefs}
        getRowId={params => params.data.id} quickFilterText={layout.quickFilter} maintainColumnOrder
        processUnpinnedColumns={params => params.columns.filter(column => !['cultivar.identity', 'cultivar.comparison-pin'].includes(column.getColId()))}
        defaultColDef={{ sortable: true, filter: 'agTextColumnFilter', filterParams: { maxNumConditions: 2 }, cellDataType: false, resizable: true, wrapHeaderText: true, autoHeaderHeight: true }}
        onGridReady={event => { layout.onReady(event.api); setGridMounted(true); }}
        onColumnResized={event => { if (isUserLayoutEvent('resize', event.source, event.finished)) layout.changed(); }}
        onColumnMoved={event => { if (isUserLayoutEvent('move', event.source, event.finished)) layout.changed(); }}
        onColumnVisible={event => { layout.syncVisibility(); if (isUserLayoutEvent('visible', event.source)) layout.changed(); }}
        onSortChanged={event => { if (isUserLayoutEvent('sort', event.source)) layout.changed(); }}
        onFilterChanged={event => { if (isUserLayoutEvent('filter', event.source) && !event.afterDataChange) layout.changed(); }}
        rowHeight={42} headerHeight={34} animateRows={false} suppressCellFocus={false}
        getRowClass={params => params.data?.id === context.focus ? 'berry-grid-row-focused' : ''}
        overlayNoRowsTemplate="No loaded cultivar rows match this filter." />
    </div>
  </section>;
}

export default BerryDataGrid;
