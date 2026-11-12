import { useCallback, useEffect, useRef, useState } from 'react';
import type { GridApi } from 'ag-grid-community';
import { AccountGridLayouts } from './account-layout';
import { createColumnCatalog, GridLayoutError } from './layout-codec';
import type { ColumnCatalog, LayoutColumn, LoadedGridLayout } from './layout-codec';
import { captureGridLayout, restoredColumnState } from './grid-state';

type Phase = 'loading' | 'ready' | 'pending' | 'saving' | 'saved' | 'local' | 'conflict' | 'error';
interface LayoutStatus { phase: Phase; message: string; retainedUnknownColumns: number }
const initial: LayoutStatus = { phase: 'loading', message: 'Loading your saved grid layout…', retainedUnknownColumns: 0 };

/** Account preferences are independent of investigation state and never dispatch it. */
export function useAccountGridLayout<Row>(specs: readonly LayoutColumn[], viewKey = 'berry-portfolio-v1') {
  const [status, setStatus] = useState<LayoutStatus>(initial);
  const [quickFilter, setQuickFilter] = useState('');
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const api = useRef<GridApi<Row> | null>(null);
  const controller = useRef<AccountGridLayouts | null>(null);
  const catalog = useRef<ColumnCatalog | null>(null);
  const pending = useRef<LoadedGridLayout | null>(null);
  const active = useRef(0);
  const loadSerial = useRef(0);
  const restoring = useRef(true);
  const writable = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const query = useRef('');
  const edit = useRef(0);
  const retained = useRef(0);
  const reload = useRef<() => Promise<void>>(async () => {});
  const signature = JSON.stringify(specs);
  const cancelSave = useCallback(() => { clearTimeout(timer.current); timer.current = undefined; }, []);
  const syncVisibility = useCallback(() => {
    if (api.current && !api.current.isDestroyed()) setVisible(Object.fromEntries(api.current.getColumnState().map(column => [column.colId, !column.hide])));
  }, []);

  const applyPending = useCallback(async () => {
    const grid = api.current, columns = catalog.current, loaded = pending.current;
    if (!grid || grid.isDestroyed() || !columns || !loaded) return;
    pending.current = null;
    const generation = active.current;
    const attempt = loadSerial.current;
    restoring.current = true;
    const accepted = grid.applyColumnState({ state: restoredColumnState(loaded.snapshot, columns), applyOrder: true });
    if (!accepted) {
      writable.current = false; restoring.current = false;
      setStatus({ phase: 'error', message: 'The saved columns could not be restored. Changes stay in this tab; reload the saved layout to try again.', retainedUnknownColumns: loaded.retainedUnknownColumns });
      return;
    }
    grid.setFilterModel(loaded.snapshot.filterModel);
    query.current = loaded.snapshot.quickFilter;
    setQuickFilter(query.current);
    grid.setGridOption('quickFilterText', query.current);
    syncVisibility();
    // API filter/column events can finish after applyColumnState returns.
    await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    if (active.current !== generation || loadSerial.current !== attempt || api.current !== grid || grid.isDestroyed()) return;
    restoring.current = false; writable.current = loaded.writable; retained.current = loaded.retainedUnknownColumns;
    setStatus({ phase: loaded.writable ? 'ready' : 'local', retainedUnknownColumns: loaded.retainedUnknownColumns,
      message: loaded.status === 'legacy-unmapped'
        ? 'An earlier layout cannot be matched safely. It remains saved. Showing default columns; changes stay in this tab.'
        : loaded.status === 'restored' ? 'Saved grid layout restored.' : 'Default grid layout. Display changes save automatically.' });
  }, [syncVisibility]);

  useEffect(() => {
    const generation = ++active.current;
    restoring.current = true; writable.current = false; pending.current = null;
    setStatus(initial); cancelSave();
    let owned: AccountGridLayouts | undefined;
    const ended = () => {
      active.current++; cancelSave(); writable.current = false; pending.current = null;
      setStatus({ phase: 'error', message: 'Sign in to restore or save your grid layout.', retainedUnknownColumns: 0 });
    };
    window.addEventListener('berry:session-transition', ended);
    void (async () => {
      try {
        const columns = await createColumnCatalog(specs);
        if (active.current !== generation) return;
        catalog.current = columns;
        owned = new AccountGridLayouts({ viewKey, catalog: columns });
        controller.current = owned;
        const load = async () => {
          const attempt = ++loadSerial.current;
          cancelSave(); writable.current = false; restoring.current = true;
          setStatus(current => ({ ...current, phase: 'loading', message: 'Loading your saved grid layout…' }));
          try {
            const loaded = await owned!.load();
            if (active.current !== generation || loadSerial.current !== attempt) return;
            pending.current = loaded;
            await applyPending();
          } catch (error) {
            if (active.current !== generation || loadSerial.current !== attempt) return;
            restoring.current = false;
            setStatus({ phase: owned!.getState().conflict ? 'conflict' : 'error', retainedUnknownColumns: retained.current,
              message: error instanceof GridLayoutError && error.kind === 'session' ? error.message
                : 'The saved layout could not be loaded. Changes stay in this tab; reload it to enable saving.' });
          }
        };
        reload.current = load;
        await load();
      } catch (error) {
        if (active.current !== generation) return;
        restoring.current = false;
        setStatus({ phase: 'error', retainedUnknownColumns: 0, message: error instanceof Error ? error.message : 'Saved grid layout is unavailable. Changes stay in this tab.' });
      }
    })();
    return () => {
      active.current++; cancelSave(); owned?.dispose(); controller.current = null; catalog.current = null; pending.current = null;
      writable.current = false; reload.current = async () => {};
      window.removeEventListener('berry:session-transition', ended);
    };
    // Semantic specs define this controller's lifetime; labels/focus/pins do not.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, viewKey, applyPending, cancelSave]);

  const changed = useCallback(() => {
    syncVisibility();
    if (restoring.current || !writable.current || !api.current || !controller.current || !catalog.current) return;
    const grid = api.current, owner = controller.current, columns = catalog.current, generation = active.current;
    const attempt = loadSerial.current;
    const serial = ++edit.current;
    cancelSave();
    setStatus({ phase: 'pending', message: 'Saving display changes…', retainedUnknownColumns: retained.current });
    timer.current = setTimeout(() => {
      timer.current = undefined;
      if (active.current !== generation || loadSerial.current !== attempt || grid.isDestroyed() || !writable.current) return;
      void (async () => {
        try {
          const snapshot = captureGridLayout(grid.getColumnState(), grid.getFilterModel(), query.current, columns);
          setStatus({ phase: 'saving', message: 'Saving display changes…', retainedUnknownColumns: retained.current });
          const loaded = await owner.save(snapshot);
          if (active.current !== generation || loadSerial.current !== attempt) return;
          retained.current = loaded.retainedUnknownColumns;
          if (serial === edit.current) setStatus({ phase: 'saved', message: 'Grid layout saved.', retainedUnknownColumns: retained.current });
        } catch (error) {
          if (active.current !== generation || loadSerial.current !== attempt) return;
          if (owner.getState().conflict) {
            writable.current = false; cancelSave();
            setStatus({ phase: 'conflict', message: 'This layout changed in another tab. Your display stays here. Reload the saved layout before saving again.', retainedUnknownColumns: retained.current });
          } else setStatus({ phase: 'error', message: error instanceof Error ? error.message : 'The layout could not be saved. Changes stay in this tab.', retainedUnknownColumns: retained.current });
        }
      })();
    }, 550);
  }, [cancelSave, syncVisibility]);

  const onReady = useCallback((grid: GridApi<Row>) => { api.current = grid; syncVisibility(); void applyPending(); }, [applyPending, syncVisibility]);
  const changeQuickFilter = useCallback((value: string) => {
    query.current = value; setQuickFilter(value);
    api.current?.setGridOption('quickFilterText', value); changed();
  }, [changed]);
  const changeVisibility = useCallback((colId: string, show: boolean) => {
    if (catalog.current?.byId.get(colId)?.lockedVisible) return;
    api.current?.setColumnsVisible([colId], show); changed();
  }, [changed]);
  return { status, busy: status.phase === 'loading', quickFilter, visible, onReady, changed, syncVisibility,
    changeQuickFilter, changeVisibility, reloadSavedLayout: () => void reload.current() };
}
