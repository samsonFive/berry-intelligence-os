import { useCallback, useEffect, useRef, useState } from 'react';
import type { GridApi } from 'ag-grid-community';
import { SESSION_TRANSITION_EVENT } from '../../app/PrivateQueryProvider';
import type { LayoutColumn } from './layout-codec';
import { PortfolioSessionLayouts } from './portfolio-session-layout';

const memory = new PortfolioSessionLayouts();
if (typeof window !== 'undefined') window.addEventListener(SESSION_TRANSITION_EVENT, () => memory.clear());

/** No account adapter, fetch, browser storage or selector dispatch exists here. */
export function usePortfolioSessionLayout<Row>(specs: readonly LayoutColumn[], viewKey: string) {
  const api = useRef<GridApi<Row> | null>(null), restoring = useRef(true), ended = useRef(false);
  const epoch = useRef(memory.epoch).current, cycle = useRef(0), query = useRef('');
  const [status, setStatus] = useState<{ phase: 'loading' | 'local' | 'error'; message: string; retainedUnknownColumns: number }>({ phase: 'loading', message: 'Restoring session layout…', retainedUnknownColumns: 0 });
  const [quickFilter, setQuickFilter] = useState(''), [visible, setVisible] = useState<Record<string, boolean>>({});
  const signature = JSON.stringify(specs), ids = specs.map(column => column.colId);
  const active = () => !ended.current && epoch === memory.epoch;
  const syncVisibility = useCallback(() => {
    if (!active() || !api.current || api.current.isDestroyed()) return;
    setVisible(Object.fromEntries(api.current.getColumnState().map(column => [column.colId, !column.hide])));
  // This grid instance has a fixed semantic membership and private-session epoch.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [epoch]);
  const restore = useCallback(() => {
    const grid = api.current;
    if (!active() || !grid || grid.isDestroyed()) return;
    const attempt = ++cycle.current;
    restoring.current = true;
    const saved = memory.load(viewKey, ids, epoch);
    const state = saved?.columns ?? specs.map(column => ({ colId: column.colId, width: column.defaultWidth ?? 160, hide: Boolean(column.defaultHidden) }));
    const byId = new Map(specs.map(column => [column.colId, column]));
    const locked = specs.filter(column => column.lockedVisible).map(column => column.colId);
    const order = [...locked, ...state.map(column => column.colId).filter(id => !locked.includes(id))];
    const accepted = grid.applyColumnState({ applyOrder: true, state: order.map(id => {
      const column = byId.get(id)!, value = state.find(item => item.colId === id)!;
      return { ...value, colId: id, width: Math.min(column.maxWidth ?? 1200, Math.max(column.minWidth ?? 48, value.width ?? column.defaultWidth ?? 160)),
        hide: column.lockedVisible ? false : Boolean(value.hide), pinned: column.lockedVisible ? 'left' as const : null, flex: null };
    }) });
    if (!accepted) {
      restoring.current = false;
      setStatus({ phase: 'error', message: 'These session columns could not be restored. Reload the session layout to try again.', retainedUnknownColumns: 0 });
      return;
    }
    grid.setFilterModel(saved?.filterModel ?? null);
    query.current = saved?.quickFilter ?? ''; setQuickFilter(query.current); grid.setGridOption('quickFilterText', query.current);
    syncVisibility();
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (!active() || cycle.current !== attempt || grid.isDestroyed()) return;
      restoring.current = false;
      setStatus({ phase: 'local', message: 'Session layout', retainedUnknownColumns: 0 });
    }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, viewKey, epoch, syncVisibility]);
  useEffect(() => {
    ended.current = epoch !== memory.epoch;
    if (!ended.current) restore();
    const clear = () => { ended.current = true; cycle.current++; api.current = null; setStatus({ phase: 'error', message: 'Session ended.', retainedUnknownColumns: 0 }); };
    window.addEventListener(SESSION_TRANSITION_EVENT, clear);
    return () => { ended.current = true; cycle.current++; window.removeEventListener(SESSION_TRANSITION_EVENT, clear); };
  }, [epoch, restore]);
  const changed = useCallback(() => {
    const grid = api.current;
    if (!active() || restoring.current || !grid || grid.isDestroyed()) return;
    syncVisibility();
    try {
      memory.save(viewKey, ids, { columns: grid.getColumnState(), filterModel: grid.getFilterModel(), quickFilter: query.current }, epoch);
      setStatus({ phase: 'local', message: 'Session layout', retainedUnknownColumns: 0 });
    } catch (error) { setStatus({ phase: 'error', message: error instanceof Error ? error.message : 'Session layout is unavailable.', retainedUnknownColumns: 0 }); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, viewKey, epoch, syncVisibility]);
  const onReady = useCallback((grid: GridApi<Row>) => { if (!active()) return; api.current = grid; restore(); }, [restore]);
  return { status, busy: status.phase === 'loading', quickFilter, visible, onReady, changed, syncVisibility,
    changeQuickFilter: (value: string) => { query.current = value; setQuickFilter(value); api.current?.setGridOption('quickFilterText', value); changed(); },
    changeVisibility: (id: string, show: boolean) => { if (specs.find(column => column.colId === id)?.lockedVisible || !active()) return; api.current?.setColumnsVisible([id], show); changed(); },
    reloadSavedLayout: () => { restore(); return undefined; }, view: 'grid' as const, changeView: (_value: 'grid' | 'cards') => {} };
}
