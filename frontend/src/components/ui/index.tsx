import {
  forwardRef,
  useId,
  useState,
  type AnchorHTMLAttributes,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactNode,
} from 'react';
import {
  autoUpdate,
  flip,
  FloatingFocusManager,
  FloatingPortal,
  offset,
  safePolygon,
  shift,
  useDismiss,
  useClick,
  useFloating,
  useFocus,
  useHover,
  useInteractions,
  useRole,
} from '@floating-ui/react';

function classes(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ');
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'small' | 'medium';
  busy?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'medium', busy = false, className, children, disabled, type = 'button', ...props },
  ref,
) {
  return (
    <button
      {...props}
      ref={ref}
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={classes('berry-button', `berry-button--${variant}`, `berry-button--${size}`, className)}
    >
      {busy && <span className="berry-spinner" aria-hidden="true" />}
      {children}
    </button>
  );
});

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: 'neutral' | 'sage' | 'berry' | 'warning' | 'danger' | 'info';
}

/** Tone is chosen by the domain presenter; color never determines trust. */
export function Badge({ tone = 'neutral', className, children, ...props }: BadgeProps) {
  return <span {...props} className={classes('berry-badge', `berry-badge--${tone}`, className)}>{children}</span>;
}

export interface EntityButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  name?: string;
  kind?: string;
  meta?: ReactNode;
  selected?: boolean;
  compact?: boolean;
}

/** Activation focuses/opens an entity. Pinning remains a separate control. */
export const EntityButton = forwardRef<HTMLButtonElement, EntityButtonProps>(function EntityButton(
  { name, kind, meta, selected = false, compact = false, className, children, type = 'button', ...props },
  ref,
) {
  return (
    <button
      {...props}
      ref={ref}
      type={type}
      aria-current={selected ? 'true' : undefined}
      data-selected={selected || undefined}
      className={classes('berry-entity-button', compact && 'berry-entity-button--compact', className)}
    >
      {kind && <span className="berry-entity-kind">{kind}</span>}
      <span className="berry-entity-name">{name ?? children}</span>
      {meta && <span className="berry-entity-meta">{meta}</span>}
    </button>
  );
});

export interface SourceLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  href: string;
  onOpen?: () => void;
  external?: boolean;
}

/** Retains a real link and modifier-key/new-tab behavior when opening shared detail. */
export const SourceLink = forwardRef<HTMLAnchorElement, SourceLinkProps>(function SourceLink(
  { href, onOpen, onClick, external = false, className, children, target, rel, ...props },
  ref,
) {
  return (
    <a
      {...props}
      ref={ref}
      href={href}
      target={external ? '_blank' : target}
      rel={external || target === '_blank' ? `${rel ? `${rel} ` : ''}noopener noreferrer` : rel}
      className={classes('berry-source-link', className)}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented && onOpen && !external && !target && event.button === 0
          && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      {children}
      {external && <span aria-hidden="true" className="berry-external-mark">↗</span>}
      {external && <span className="berry-sr-only"> (opens in a new tab)</span>}
    </a>
  );
});

export interface PreviewProps {
  /** Trigger label/content only: Preview supplies the accessible button. */
  children: ReactNode;
  content: ReactNode;
  /** Click, tap and Enter open the persistent, domain-owned detail area. */
  onOpenDetail?: () => void;
  label?: string;
  detailLabel?: string;
  className?: string;
  disabled?: boolean;
}

/** Enterable support popover. Opening it never dispatches an investigation action. */
export function Preview({ children, content, onOpenDetail, label = 'Supporting context', detailLabel = 'Open detail', className, disabled = false }: PreviewProps) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const { refs, floatingStyles, context } = useFloating({
    open: open && !disabled,
    onOpenChange: setOpen,
    placement: 'bottom-start',
    middleware: [offset(8), flip({ padding: 12 }), shift({ padding: 12 })],
    whileElementsMounted: autoUpdate,
  });
  const hover = useHover(context, {
    enabled: !disabled,
    mouseOnly: true,
    delay: { open: 160, close: 160 },
    handleClose: safePolygon({ buffer: 8 }),
  });
  const focus = useFocus(context, { enabled: !disabled });
  const click = useClick(context, { enabled: !disabled && !onOpenDetail });
  const dismiss = useDismiss(context, { escapeKey: true, outsidePress: true });
  const role = useRole(context, { role: 'dialog' });
  const { getReferenceProps, getFloatingProps } = useInteractions([hover, focus, click, dismiss, role]);
  const openDetail = () => {
    setOpen(false);
    onOpenDetail?.();
  };

  return (
    <>
      <button
        type="button"
        ref={refs.setReference}
        disabled={disabled}
        className={classes('berry-preview-trigger', className)}
        {...getReferenceProps(onOpenDetail ? { onClick: openDetail } : {})}
      >
        {children}
      </button>
      {open && !disabled && (
        <FloatingPortal>
          <FloatingFocusManager context={context} modal={false} initialFocus={-1} returnFocus>
            <div
              ref={refs.setFloating}
              style={floatingStyles}
              className="berry-app berry-preview"
              aria-labelledby={titleId}
              {...getFloatingProps()}
            >
              <div className="berry-preview-heading">
                <span id={titleId}>{label}</span>
                <button type="button" className="berry-icon-button" aria-label="Dismiss preview" onClick={() => setOpen(false)}>×</button>
              </div>
              <div className="berry-preview-content">{content}</div>
              {onOpenDetail && <Button size="small" variant="ghost" onClick={openDetail}>{detailLabel}<span aria-hidden="true"> →</span></Button>}
            </div>
          </FloatingFocusManager>
        </FloatingPortal>
      )}
    </>
  );
}

export interface EmptyStateProps {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
  className?: string;
}

export function EmptyState({ title, children, action, compact = false, className }: EmptyStateProps) {
  return (
    <div className={classes('berry-empty-state', compact && 'berry-empty-state--compact', className)}>
      <p className="berry-empty-title">{title}</p>
      {children && <div className="berry-empty-description">{children}</div>}
      {action && <div className="berry-empty-action">{action}</div>}
    </div>
  );
}
