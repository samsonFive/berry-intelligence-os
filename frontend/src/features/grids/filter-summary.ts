export interface ActiveSheetFilter { id: string; label: string; detail: string; hidden?: boolean }
interface FilterValue { type?: string; filter?: unknown; operator?: string; conditions?: FilterValue[] }
const OPERATORS: Record<string, string> = { contains: 'contains', notContains: 'excludes', equals: 'is', notEqual: 'is not', startsWith: 'starts with', endsWith: 'ends with', blank: 'is blank', notBlank: 'is not blank' };
function describe(value: FilterValue): string {
  if (value.conditions?.length) return value.conditions.map(describe).join(` ${value.operator === 'OR' ? 'or' : 'and'} `);
  return [OPERATORS[value.type ?? ''] ?? value.type ?? 'filtered', typeof value.filter === 'string' ? `“${value.filter}”` : ''].filter(Boolean).join(' ');
}
/** Hidden-column filters stay visible in the active-filter strip. */
export function sheetFilterSummary(quickFilter: string, filterModel: Record<string, unknown>, columns: readonly { id: string; label: string }[], visible: Readonly<Record<string, boolean>>): ActiveSheetFilter[] {
  return [
    ...(quickFilter ? [{ id: '$quick', label: 'Search', detail: `“${quickFilter}”` }] : []),
    ...Object.entries(filterModel).filter(([, value]) => value && typeof value === 'object').map(([id, value]) => ({
      id, label: columns.find(column => column.id === id)?.label ?? id, detail: describe(value as FilterValue), hidden: visible[id] === false,
    })),
  ];
}

/** Clearing filters never changes display columns, ordering, sorting or view. */
export function clearSheetFilters(api: { setFilterModel: (model: null) => void; paginationGoToFirstPage: () => void }, changeQuickFilter: (value: string) => void) {
  api.setFilterModel(null); changeQuickFilter(''); api.paginationGoToFirstPage();
}

interface ResetGrid {
  isDestroyed: () => boolean; getFilterModel: () => Record<string, unknown>;
  setFilterModel: (model: null) => void; paginationGoToFirstPage: () => void;
}
/** A reset requested during account loading waits for restoration and runs once. */
export class SheetFilterReset {
  private appliedToken = 0;
  apply(token: number, ready: boolean, grid: ResetGrid | null, quickFilter: string,
    changeQuickFilter: (value: string) => void, acknowledge?: (token: number) => void): boolean {
    if (!token || token === this.appliedToken || !ready || !grid || grid.isDestroyed()) return false;
    this.appliedToken = token;
    if (quickFilter || Object.keys(grid.getFilterModel()).length) clearSheetFilters(grid, changeQuickFilter);
    else grid.paginationGoToFirstPage();
    acknowledge?.(token); return true;
  }
}
