import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AllCommunityModule, ModuleRegistry, type ColDef, type GridApi, type GridOptions } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import { SheetToolbar } from './SheetToolbar';
import { useAccountGridLayout } from './useAccountGridLayout';
import { isUserLayoutEvent } from './grid-state';
import { workspaceGridTheme } from './workspace-grid-theme';
import { defaultSheetColumnState } from './sheet-layout';
import './grid.css';
import './workspace-sheet.css';

ModuleRegistry.registerModules([AllCommunityModule]);

export interface WorkspaceSheetColumn { id: string; label: string; header?: ReactNode; width: number; frozen?: boolean }
export interface WorkspaceSheetCell { text: string; content: ReactNode }
export interface WorkspaceSheetRow { id: string; cells: Record<string, WorkspaceSheetCell> }
const SHEET_ROW_ID: NonNullable<GridOptions<WorkspaceSheetRow>['getRowId']> = params => params.data.id;
const SHEET_COLUMN_DEFAULTS: ColDef<WorkspaceSheetRow> = {
  sortable: true, filter: 'agTextColumnFilter', filterParams: { maxNumConditions: 2 }, cellDataType: false,
  resizable: true, wrapText: true, autoHeight: true, wrapHeaderText: true, autoHeaderHeight: true,
};

/** Read-only intelligence uses the same grid, preference owner and toolbar as the roster. */
export function WorkspaceSheet({ label, viewKey, columns, rows, onReady }: {
  label: string; viewKey: string; columns: WorkspaceSheetColumn[]; rows: WorkspaceSheetRow[]; onReady?: (ready: boolean) => void;
}) {
  const specs = useMemo(() => columns.map(column => ({ colId: column.id, defaultWidth: column.width,
    minWidth: column.frozen ? 160 : 120, maxWidth: 1200, lockedVisible: column.frozen })), [columns]);
  const layout = useAccountGridLayout<WorkspaceSheetRow>(specs, viewKey, false, true);
  const grid = useRef<GridApi<WorkspaceSheetRow> | null>(null);
  const [mounted, setMounted] = useState(false), [count, setCount] = useState(rows.length);
  const blocked = layout.busy || layout.status.phase === 'conflict';
  useLayoutEffect(() => onReady?.(mounted && !layout.busy), [mounted, layout.busy, onReady]);
  const definitions = useMemo<ColDef<WorkspaceSheetRow>[]>(() => columns.map(column => ({
    colId: column.id, headerName: column.label, initialWidth: column.width, minWidth: column.frozen ? 160 : 120, maxWidth: 1200,
    pinned: column.frozen ? 'left' : undefined, lockPinned: true, lockVisible: column.frozen, suppressMovable: column.frozen,
    ...(column.header ? { headerComponentParams: { innerHeaderComponent: () => column.header } } : {}),
    valueGetter: params => params.data?.cells[column.id]?.text ?? '',
    cellRenderer: (params: { data?: WorkspaceSheetRow }) => <div className="berry-workspace-sheet-cell">{params.data?.cells[column.id]?.content ?? '—'}</div>,
  })), [columns]);
  const reset = () => {
    grid.current?.applyColumnState({ state: defaultSheetColumnState(specs), applyOrder: true });
    grid.current?.setFilterModel(null); layout.changeQuickFilter(''); layout.changed();
  };
  return <section className="berry-workspace-sheet" aria-label={label}>
    <SheetToolbar label={`${label} controls`} filter={{ label: 'Filter rows', value: layout.quickFilter, onChange: layout.changeQuickFilter,
      placeholder: 'Search this view', disabled: layout.busy }} count={`${count} / ${rows.length} rows`}
      columns={{ columns: columns.map(column => ({ id: column.id, label: column.label, locked: column.frozen })), visible: layout.visible,
        onChange: layout.changeVisibility, onReload: layout.reloadSavedLayout, busy: layout.busy, actionDisabled: blocked || !mounted,
        onFit: () => { grid.current?.sizeColumnsToFit(); layout.changed(); } }} reset={{ onClick: reset, disabled: blocked || !mounted }} />
    <div className="berry-grid-layout-status" data-phase={layout.status.phase} hidden={['ready', 'saved'].includes(layout.status.phase)}><p role="status">{layout.status.message}</p></div>
    <div className="berry-grid berry-workspace-data-grid" aria-busy={layout.busy} inert={layout.busy}>
      <AgGridReact<WorkspaceSheetRow> theme={workspaceGridTheme} rowData={rows} columnDefs={definitions} getRowId={SHEET_ROW_ID}
        maintainColumnOrder quickFilterText={layout.quickFilter} includeHiddenColumnsInQuickFilter
        processUnpinnedColumns={params => params.columns.filter(column => !columns.some(spec => spec.frozen && spec.id === column.getColId()))}
        defaultColDef={SHEET_COLUMN_DEFAULTS}
        rowHeight={42} headerHeight={34} animateRows={false}
        onGridReady={event => { grid.current = event.api; layout.onReady(event.api); setMounted(true); }}
        onModelUpdated={event => setCount(event.api.getDisplayedRowCount())}
        onColumnResized={event => { if (isUserLayoutEvent('resize', event.source, event.finished)) layout.changed(); }}
        onColumnMoved={event => { if (isUserLayoutEvent('move', event.source, event.finished)) layout.changed(); }}
        onColumnVisible={event => { layout.syncVisibility(); if (isUserLayoutEvent('visible', event.source)) layout.changed(); }}
        onSortChanged={event => { if (isUserLayoutEvent('sort', event.source)) layout.changed(); }}
        onFilterChanged={event => { if (isUserLayoutEvent('filter', event.source) && !event.afterDataChange) layout.changed(); }}
        overlayNoRowsTemplate="No rows match this filter." />
    </div>
  </section>;
}

/** Separate comparison memberships must never overwrite each other's column preferences. */
export function useComparisonSheetKey(kind: 'company' | 'variety', ids: string[]) {
  const membership = JSON.stringify([...ids].sort()), [resolved, setResolved] = useState({ membership: '', kind: '', key: '' });
  useEffect(() => {
    let active = true;
    void crypto.subtle.digest('SHA-256', new TextEncoder().encode(membership)).then(bytes => {
      if (active) setResolved({ membership, kind, key: `berry-compare-${kind}-${Array.from(new Uint8Array(bytes)).slice(0, 16).map(byte => byte.toString(16).padStart(2, '0')).join('')}` });
    });
    return () => { active = false; };
  }, [kind, membership]);
  return resolved.membership === membership && resolved.kind === kind ? resolved.key : '';
}
