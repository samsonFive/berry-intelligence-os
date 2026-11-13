import type { ColumnState } from 'ag-grid-community';
import type { LayoutColumn } from './layout-codec';

/** Explicit display reset only; canonical row identities and comparison pins are untouched. */
export function defaultSheetColumnState(columns: readonly LayoutColumn[]): ColumnState[] {
  return columns.map(column => ({ colId: column.colId, width: column.defaultWidth,
    hide: Boolean(column.defaultHidden) && !column.lockedVisible,
    sort: null, sortIndex: null, pinned: column.lockedVisible ? 'left' : null }));
}
