import { useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { autoUpdate, flip, FloatingFocusManager, FloatingPortal, offset, shift, size, useFloating } from '@floating-ui/react';
import { Button } from '../../components/ui';
import './sheet-toolbar.css';

export interface SheetColumn { id: string; label: string; locked?: boolean }
export interface ColumnControlsProps {
  columns: readonly SheetColumn[];
  visible: Readonly<Record<string, boolean>>;
  onChange: (id: string, visible: boolean) => void;
  onReload: () => void;
  onFit?: () => void;
  busy?: boolean;
  actionDisabled?: boolean;
  reloadLabel?: string;
}

/** One enterable, viewport-contained column menu for every native sheet. */
export function ColumnControls({ columns, visible, onChange, onReload, onFit, busy = false,
  actionDisabled = false, reloadLabel = 'Reload saved layout' }: ColumnControlsProps) {
  const menu = useRef<HTMLDetailsElement>(null);
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const { refs, floatingStyles, context } = useFloating({
    open, onOpenChange: setOpen, placement: 'bottom-end', strategy: 'fixed', whileElementsMounted: autoUpdate,
    middleware: [offset(4), flip({ padding: 8 }), shift({ padding: 8 }),
      size({ padding: 8, apply({ availableHeight, elements }) {
        elements.floating.style.maxHeight = `${Math.max(0, Math.min(360, availableHeight))}px`;
      } })],
  });
  const close = (restoreFocus = false) => {
    if (menu.current) menu.current.open = false;
    setOpen(false);
    if (restoreFocus) menu.current?.querySelector('summary')?.focus({ preventScroll: true });
  };
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Node && !menu.current?.contains(target) && !refs.floating.current?.contains(target)) close();
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault(); event.stopPropagation(); close(true);
    };
    const ended = () => close();
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape, true);
    window.addEventListener('berry:session-transition', ended);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape, true);
      window.removeEventListener('berry:session-transition', ended);
    };
  }, [open, refs.floating]);
  const portalRoot = menu.current?.closest('.berry-app') as HTMLElement | null;
  return <details className="berry-grid-columns berry-sheet-columns" ref={menu} open={open}
    onToggle={event => setOpen(event.currentTarget.open)}>
    <summary ref={refs.setReference} aria-controls={panelId} aria-expanded={open}>Columns</summary>
    {open && <FloatingPortal root={portalRoot}><FloatingFocusManager context={context} modal={false}
      initialFocus={-1} returnFocus={false} closeOnFocusOut={false}>
      <div id={panelId} ref={refs.setFloating} style={floatingStyles}
        className="berry-grid-column-options berry-sheet-column-panel" role="group" aria-label="Column display controls">
        {columns.map(column => <label key={column.id}><input type="checkbox" checked={visible[column.id] ?? true}
          disabled={busy || column.locked} aria-label={`Show ${column.label} column`}
          onChange={event => onChange(column.id, event.target.checked)} />
          <span>{column.label}{column.locked && <small>Fixed identity</small>}</span></label>)}
        <div className="berry-sheet-column-actions">
          {onFit && <Button size="small" variant="ghost" aria-label="Fit columns" disabled={actionDisabled || busy}
            onClick={() => { onFit(); close(true); }}>Fit columns</Button>}
          <Button size="small" variant="ghost" disabled={busy} aria-label={reloadLabel}
            onClick={() => { onReload(); close(true); }}>{reloadLabel}</Button>
        </div>
      </div>
    </FloatingFocusManager></FloatingPortal>}
  </details>;
}

export interface SheetToolbarProps {
  label: string;
  filter?: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; disabled?: boolean };
  display?: { value: 'grid' | 'cards'; onChange: (value: 'grid' | 'cards') => void; label?: string; disabled?: boolean };
  count?: ReactNode;
  columns?: ColumnControlsProps;
  reset?: { onClick: () => void; disabled?: boolean };
  children?: ReactNode;
  className?: string;
}

/** The established Workspaces display/filter/layout strip, without another grid controller. */
export function SheetToolbar({ label, filter, display, count, columns, reset, children, className = '' }: SheetToolbarProps) {
  return <div className={`lw-view-tools berry-sheet-toolbar ${className}`} role="group" aria-label={label}>
    {display && <div className="berry-sheet-display" role="group" aria-label={display.label ?? 'Page display'}>
      {(['grid', 'cards'] as const).map(view => <Button key={view} size="small" disabled={display.disabled}
        aria-pressed={display.value === view} onClick={() => display.onChange(view)}>{view === 'grid' ? 'Grid' : 'Cards'}</Button>)}
    </div>}
    {filter && <label className="berry-sheet-filter">{filter.label}<input type="search" maxLength={200}
      disabled={filter.disabled} value={filter.value} placeholder={filter.placeholder}
      onChange={event => filter.onChange(event.target.value)} /></label>}
    {count && <span className="berry-sheet-count">{count}</span>}
    {children}
    <div className="berry-sheet-layout-actions">
      {columns && <ColumnControls {...columns} />}
      {reset && <Button size="small" variant="ghost" disabled={reset.disabled} onClick={reset.onClick}>Reset layout</Button>}
    </div>
  </div>;
}
