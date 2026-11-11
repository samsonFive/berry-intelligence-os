import { useEffect, useMemo, useRef } from 'react';
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef, type ICellRendererParams } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import { Button, EmptyState, EntityButton } from '../../components/ui';
import { useInvestigation } from '../../state/InvestigationProvider';
import { splitIds } from '../../contracts/investigation';
import type { LandscapeEdge, LandscapeModel, LandscapeNode } from '../landscape/models';
import type { LayoutColumn } from './layout-codec';
import { isUserLayoutEvent } from './grid-state';
import { useAccountGridLayout } from './useAccountGridLayout';
import './grid.css';

ModuleRegistry.registerModules([AllCommunityModule]);

const berryGridTheme = themeQuartz.withParams({
  fontFamily: 'var(--berry-font-ui)',
  fontSize: 12,
  backgroundColor: 'var(--berry-surface)',
  foregroundColor: 'var(--berry-ink)',
  headerBackgroundColor: 'var(--berry-surface-subtle)',
  accentColor: 'var(--berry-forest)',
  borderColor: 'var(--berry-line-strong)',
  rowBorder: true,
  columnBorder: true,
  headerHeight: 44,
  spacing: 7,
  wrapperBorderRadius: 5,
});

interface PortfolioRow {
  id: string;
  variety: LandscapeNode;
  byCompany: Record<string, LandscapeEdge[]>;
}

/** A real Community grid. Canonical identity and comparison membership stay separate. */
export function BerryDataGrid({ model }: { model: LandscapeModel }) {
  const companies = useMemo(() => model.portfolios.map(row => row.actor), [model.portfolios]);
  const rows = useMemo(() => {
    const result = new Map<string, PortfolioRow>();
    for (const portrait of model.portfolios) {
      for (const edge of portrait.portfolio_edges) {
        const variety = [model.nodes[edge.subject_id], model.nodes[edge.object_id]].find(node => node?.type === 'variety');
        if (!variety) continue;
        const row = result.get(variety.id) ?? { id: variety.id, variety, byCompany: {} };
        const edges = row.byCompany[portrait.actor.id] ?? [];
        if (!edges.some(item => item.id === edge.id)) edges.push(edge);
        row.byCompany[portrait.actor.id] = edges;
        result.set(variety.id, row);
      }
    }
    return [...result.values()].sort((a, b) => a.variety.label.localeCompare(b.variety.label));
  }, [model]);
  if (companies.length > 38) return <EmptyState title="This portfolio exceeds the grid's 40-column limit">There are {companies.length} company columns plus the fixed cultivar and pin columns. Apply a narrower scope to use the saved-layout grid. No companies have been omitted from the records.</EmptyState>;
  if (!rows.length) return <EmptyState title="No cultivar portfolio relationships in this scope">Recorded geographic connections can still be inspected in Connections. Missing portfolio records do not establish an absence of commercial access.</EmptyState>;
  return <PortfolioGrid key={companies.map(company => company.id).join('|')} model={model} companies={companies} rows={rows} />;
}

function ColumnVisibility({ columns, visible, busy, change }: {
  columns: Array<{ id: string; label: string; locked?: boolean }>; visible: Record<string, boolean>; busy: boolean;
  change: (id: string, show: boolean) => void;
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
    <div className="berry-grid-column-options"><p>Show or hide company columns. Cultivar identity and its separate comparison pin stay visible.</p>
      {columns.map(column => <label key={column.id}><input type="checkbox" checked={visible[column.id] ?? true} disabled={busy || column.locked}
        aria-label={`Show ${column.label} column`} onChange={event => change(column.id, event.target.checked)} />
        <span>{column.label}{column.locked && <small>Fixed identity / comparison control</small>}</span></label>)}
    </div>
  </details>;
}

function PortfolioGrid({ model, companies, rows }: { model: LandscapeModel; companies: LandscapeNode[]; rows: PortfolioRow[] }) {
  const { context, dispatch } = useInvestigation();
  const selectedCompanies = splitIds(context.cohort_companies);
  const selectedVarieties = splitIds(context.cohort_varieties);
  const specs = useMemo<LayoutColumn[]>(() => [
    { colId: 'cultivar.identity', defaultWidth: 220, minWidth: 150, maxWidth: 1200, lockedVisible: true },
    { colId: 'cultivar.comparison-pin', defaultWidth: 75, minWidth: 65, maxWidth: 90, lockedVisible: true },
    ...companies.map(company => ({ colId: `company.${company.id}.recorded-role`, defaultWidth: 260, minWidth: 220, maxWidth: 1200 })),
  ], [companies]);
  const layout = useAccountGridLayout<PortfolioRow>(specs);
  const columnChoices = [{ id: 'cultivar.identity', label: 'Cultivar', locked: true }, { id: 'cultivar.comparison-pin', label: 'Comparison pin', locked: true },
    ...companies.map(company => ({ id: `company.${company.id}.recorded-role`, label: company.label }))];
  const columnDefs = useMemo<ColDef<PortfolioRow>[]>(() => [
    {
      colId: 'cultivar.identity', headerName: 'Cultivar', pinned: 'left', initialWidth: 220, minWidth: 150, maxWidth: 1200,
      lockPinned: true, lockVisible: true, lockPosition: 'left', suppressMovable: true,
      valueGetter: params => params.data?.variety.label ?? '',
      cellRenderer: (params: ICellRendererParams<PortfolioRow>) => params.data && <EntityButton compact name={params.data.variety.label}
        selected={context.focus === params.data.id}
        onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'variety', id: params.data!.id }, origin: 'grid' })} />,
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
      wrapText: true, autoHeight: true,
      valueGetter: (params: { data?: PortfolioRow }) => (params.data?.byCompany[company.id] ?? []).map(edge => edge.label).join('; '),
      cellRenderer: (params: ICellRendererParams<PortfolioRow>) => {
        const edges = params.data?.byCompany[company.id] ?? [];
        return edges.length ? <div className="berry-grid-role-list">{edges.map(edge => <button key={edge.id} type="button"
          className="berry-grid-role" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: edge.id }, origin: 'grid' })}>
          <strong>{edge.role}</strong><span>{model.nodes[edge.subject_id]?.label} → {model.nodes[edge.object_id]?.label}</span>
          {edge.status !== 'active' && <span>{edge.status_label}</span>}
        </button>)}</div> : <span className="berry-unknown" aria-label="Unknown: no recorded portfolio relationship">—</span>;
      },
    })),
  ], [companies, context.focus, dispatch, model.nodes, selectedVarieties.join(',')]);

  return <section aria-label="Recorded company and cultivar portfolio">
    <div className="berry-grid-company-controls" aria-label="Company focus and comparison pins">{companies.map(company => <div key={company.id}>
      <EntityButton compact name={company.label} selected={context.focus === company.id} onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'company', id: company.id }, origin: 'grid' })} />
      <Button size="small" variant="ghost" aria-pressed={selectedCompanies.includes(company.id)} onClick={() => dispatch({ type: 'togglePin', entity: { type: 'company', id: company.id }, origin: 'grid' })}>{selectedCompanies.includes(company.id) ? 'Unpin' : 'Pin'}</Button>
    </div>)}</div>
    <div className="berry-grid-preferences"><label className="berry-field-label">Filter loaded rows<input className="berry-input" type="search" maxLength={200} disabled={layout.busy} value={layout.quickFilter} onChange={event => layout.changeQuickFilter(event.target.value)} placeholder="Cultivar, role or company" /></label>
      <ColumnVisibility columns={columnChoices} visible={layout.visible} busy={layout.busy} change={layout.changeVisibility} />
    </div>
    <div className="berry-grid-layout-status" data-phase={layout.status.phase}>
      <p role="status" aria-live="polite">{layout.status.message}{layout.status.retainedUnknownColumns > 0 && <small>Preferences for {layout.status.retainedUnknownColumns} columns outside this scope remain saved.</small>}</p>
      <Button size="small" variant="ghost" disabled={layout.busy} onClick={layout.reloadSavedLayout} title="Replace this tab's display settings with the last saved layout.">Reload saved layout</Button>
    </div>
    <p className="berry-scope-note">Standing portfolio records · {rows.length} loaded cultivars · roles retain their recorded direction. Company columns include actual program links where recorded.</p>
    <div className="berry-grid berry-portfolio-grid" data-grid-edition="community" aria-busy={layout.busy} inert={layout.busy}>
      <AgGridReact<PortfolioRow> theme={berryGridTheme} rowData={rows} columnDefs={columnDefs}
        getRowId={params => params.data.id} quickFilterText={layout.quickFilter} maintainColumnOrder
        processUnpinnedColumns={params => params.columns.filter(column => !['cultivar.identity', 'cultivar.comparison-pin'].includes(column.getColId()))}
        defaultColDef={{ sortable: true, filter: 'agTextColumnFilter', filterParams: { maxNumConditions: 2 }, cellDataType: false, resizable: true, wrapHeaderText: true, autoHeaderHeight: true }}
        onGridReady={event => layout.onReady(event.api)}
        onColumnResized={event => { if (isUserLayoutEvent('resize', event.source, event.finished)) layout.changed(); }}
        onColumnMoved={event => { if (isUserLayoutEvent('move', event.source, event.finished)) layout.changed(); }}
        onColumnVisible={event => { layout.syncVisibility(); if (isUserLayoutEvent('visible', event.source)) layout.changed(); }}
        onSortChanged={event => { if (isUserLayoutEvent('sort', event.source)) layout.changed(); }}
        onFilterChanged={event => { if (isUserLayoutEvent('filter', event.source) && !event.afterDataChange) layout.changed(); }}
        rowHeight={70} headerHeight={48} animateRows={false} suppressCellFocus={false}
        getRowClass={params => params.data?.id === context.focus ? 'berry-grid-row-focused' : ''}
        overlayNoRowsTemplate="No loaded cultivar rows match this filter." />
    </div>
    <p className="berry-scope-note berry-grid-caption">Select a name to inspect. Use the explicit pins to build company or variety comparisons. The filter searches loaded rows; the investigation's scope stays unchanged.</p>
  </section>;
}

export default BerryDataGrid;
