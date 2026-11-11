import type { ColumnState, FilterModel } from 'ag-grid-community';
import { GridLayoutError } from './layout-codec.ts';
import type { ColumnCatalog, GridLayoutSnapshot } from './layout-codec.ts';

/** Only display state crosses this boundary; row selection and cohort pins do not. */
export function captureGridLayout(columns: ColumnState[], filterModel: FilterModel, quickFilter: string, catalog: ColumnCatalog): GridLayoutSnapshot {
  const current = columns.filter(column => catalog.byId.has(column.colId));
  if (current.length !== catalog.columns.length) throw new GridLayoutError('The complete grid columns are not ready to save. Reload the saved layout.');
  return {
    columns: current.map(column => ({ colId: column.colId, width: column.width ?? catalog.byId.get(column.colId)!.defaultWidth,
      hide: catalog.byId.get(column.colId)!.lockedVisible ? false : Boolean(column.hide) })),
    sort: current.filter(column => column.sort === 'asc' || column.sort === 'desc')
      .sort((a, b) => (a.sortIndex ?? 0) - (b.sortIndex ?? 0))
      .map(column => ({ colId: column.colId, sort: column.sort as 'asc' | 'desc' })),
    filterModel: structuredClone(filterModel), quickFilter,
  };
}

export function restoredColumnState(snapshot: GridLayoutSnapshot, catalog: ColumnCatalog): ColumnState[] {
  return snapshot.columns.map(column => {
    const sortIndex = snapshot.sort.findIndex(item => item.colId === column.colId);
    const locked = catalog.byId.get(column.colId)?.lockedVisible;
    return { ...column, hide: locked ? false : column.hide, pinned: locked ? 'left' : null,
      sort: sortIndex < 0 ? null : snapshot.sort[sortIndex].sort, sortIndex: sortIndex < 0 ? null : sortIndex };
  });
}

/** AG Grid emits API/data/viewport changes too; only actual display gestures autosave. */
export function isUserLayoutEvent(kind: 'move' | 'resize' | 'visible' | 'sort' | 'filter', source?: string, finished = true): boolean {
  if (!finished) return false;
  if (kind === 'move') return source === 'uiColumnMoved' || source === 'uiColumnDragged';
  if (kind === 'resize') return source === 'uiColumnResized';
  if (kind === 'sort') return source === 'uiColumnSorted';
  if (kind === 'filter') return source === 'columnFilter';
  return source === 'columnMenu' || source === 'contextMenu' || source === 'toolPanelUi';
}
