import { forwardRef, useCallback, useEffect, useId, useImperativeHandle, useLayoutEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { SESSION_TRANSITION_EVENT } from '../../app/PrivateQueryProvider';
import { Button, SourceLink } from '../../components/ui';
import { serializeInvestigation } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import type { EntityBrandMedia } from '../brand-media/api';
import { CompactCollection, CompactGenetics, CompactRoles } from './RosterCompactCells';
import type { LandscapeEdge, LandscapeModel, LandscapeNode, MonitoringCompany } from './models';
import { rosterGenetics } from './roster-genetics';

export interface CompanyRosterDetailsHandle { open(companyId: string, trigger: HTMLElement): void }
interface Props {
  model: LandscapeModel;
  companies: MonitoringCompany[];
  media: Record<string, EntityBrandMedia> | undefined;
  rosterRoot: RefObject<HTMLElement | null>;
}

// Local modal state must never update the AG Grid owner: AG refresh can remount
// framework cell renderers, including an analyst's still-unsaved tier control.
export const CompanyRosterDetails = forwardRef<CompanyRosterDetailsHandle, Props>(function CompanyRosterDetails({ model, companies, media, rosterRoot }, ref) {
  const { context, dispatch } = useInvestigation();
  const dialog = useRef<HTMLDialogElement>(null), dialogClose = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLElement | null>(null), restoreDetailsFocus = useRef(true), openedCompany = useRef('');
  const detailsActive = useRef(false), detailsClosing = useRef(false), detailsCycle = useRef(0);
  const [detailsId, setDetailsId] = useState<string | null>(null);
  const detailsCompany = companies.find(company => company.id === detailsId);
  const dialogHeading = useId();
  const finishDetails = useCallback(() => {
    if (!detailsActive.current || dialog.current?.open) return;
    detailsActive.current = false;
    const target = opener.current, companyId = openedCompany.current, restore = restoreDetailsFocus.current;
    const cycle = detailsCycle.current;
    opener.current = null; setDetailsId(null);
    if (restore) requestAnimationFrame(() => requestAnimationFrame(() => {
      if (!restoreDetailsFocus.current || cycle !== detailsCycle.current || detailsActive.current || !rosterRoot.current?.isConnected) return;
      if (document.activeElement instanceof Element && document.activeElement.closest('.berry-detail, .berry-command')) return;
      const replacement = [...(rosterRoot.current?.querySelectorAll<HTMLElement>('[data-roster-details-for]') ?? [])]
        .find(button => button.dataset.rosterDetailsFor === companyId && button.getClientRects().length > 0);
      (replacement ?? (target?.isConnected && target.getClientRects().length ? target : rosterRoot.current))?.focus({ preventScroll: true });
    }));
  }, []);
  const closeDetails = useCallback((restore = true) => {
    // A reference action's no-restore choice remains sticky through repeated
    // context effects and the eventual native close event for this dialog.
    if (!restore) restoreDetailsFocus.current = false;
    if (!detailsActive.current || detailsClosing.current) return;
    detailsClosing.current = true;
    if (dialog.current?.open) dialog.current.close(); else finishDetails();
  }, [finishDetails]);
  useLayoutEffect(() => {
    if (detailsCompany && detailsActive.current && !detailsClosing.current && dialog.current && !dialog.current.open) {
      dialog.current.showModal(); dialogClose.current?.focus({ preventScroll: true });
    } else if (detailsId && !detailsCompany) closeDetails(false);
  }, [detailsId, detailsCompany, closeDetails]);
  const contextKey = serializeInvestigation(context), previousContext = useRef(contextKey);
  useLayoutEffect(() => {
    if (previousContext.current !== contextKey && detailsId) closeDetails(false);
    previousContext.current = contextKey;
  }, [contextKey, detailsId, closeDetails]);
  useEffect(() => {
    const clear = () => closeDetails(false);
    window.addEventListener(SESSION_TRANSITION_EVENT, clear);
    return () => { window.removeEventListener(SESSION_TRANSITION_EVENT, clear); restoreDetailsFocus.current = false; detailsActive.current = false; dialog.current?.close(); };
  }, [closeDetails]);
  useImperativeHandle(ref, () => ({ open(companyId, trigger) {
    opener.current = trigger; openedCompany.current = companyId; restoreDetailsFocus.current = true;
    detailsActive.current = true; detailsClosing.current = false; detailsCycle.current++; setDetailsId(companyId);
  } }), []);
  const logo = detailsCompany ? media?.[detailsCompany.id]?.logo : null;
  const detailsSources = detailsCompany ? [...new Set([
    ...rosterGenetics(model, detailsCompany.id).edges.flatMap(edge => edge.evidence_ids),
    ...detailsCompany.geographies.flatMap(geo => geo.evidence_ids),
    ...(model.nodes[detailsCompany.id]?.evidence_ids ?? []),
  ])] : [];
  const detailNodes = new Map([...Object.values(model.nodes), ...[...model.portfolios, ...model.market_rows]
    .flatMap(portrait => [portrait.actor, ...portrait.programs, ...portrait.varieties])].map(node => [node.id, node]));
  const sourceButton = (id: string) => <button key={id} type="button" className="berry-text-button"
    onClick={() => dispatch({ type: 'openDetail', detail: { type: 'source', id }, origin: 'grid' })}>{model.sources.find(source => source.id === id)?.title || 'Open retained source'}</button>;
  const detailNode = (node: LandscapeNode) => node.type === 'breeding_program'
    ? <span>{node.label}<span className="berry-roster-compact-type"> · Breeding program</span></span>
    : <button type="button" className="berry-text-button" onClick={() => {
    if (node.type === 'company' || node.type === 'variety') dispatch({ type: 'focusEntity', entity: { type: node.type, id: node.id }, origin: 'grid' });
    else if (node.type === 'geography') dispatch({ type: 'openDetail', detail: { type: 'geography', id: node.id }, origin: 'grid' });
  }}>{node.label}</button>;
  const detailEdge = (edge: LandscapeEdge) => <div className="berry-roster-dialog-edge">
    <button type="button" className="berry-text-button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: edge.id }, origin: 'grid' })}><strong>{edge.role}</strong></button>
    <div className="berry-roster-dialog-path">{detailNodes.has(edge.subject_id) ? detailNode(detailNodes.get(edge.subject_id)!) : 'Unavailable recorded subject'}<span> → </span>{detailNodes.has(edge.object_id) ? detailNode(detailNodes.get(edge.object_id)!) : 'Unavailable recorded object'}</div>
    <p>{edge.status_label}</p>{edge.caveat && <p className="berry-material-caveat">{edge.caveat}</p>}{edge.scope_kind && <p>{edge.scope_kind}</p>}
    {!!edge.evidence_ids.length && <div className="berry-roster-dialog-evidence">{edge.evidence_ids.map(sourceButton)}</div>}
  </div>;
  return (
    <dialog ref={dialog} className="berry-roster-dialog" aria-labelledby={dialogHeading} onClose={finishDetails}
      onKeyDownCapture={event => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeDetails(); } }}
      onCancel={event => { event.preventDefault(); closeDetails(); }}>
      {detailsCompany && <><header><h2 id={dialogHeading}>{detailsCompany.label}</h2><Button ref={dialogClose} size="small" onClick={() => closeDetails()} aria-label={`Close details for ${detailsCompany.label}`}>Close</Button></header>
        <div className="berry-roster-dialog-body" onClickCapture={event => {
          // Native modal inertness must end before the existing Reader/focus action.
          if (event.target instanceof Element && event.target.closest('button,a')) closeDetails(false);
        }}>
          <section><h3>Company context</h3><dl className="berry-roster-context-list">
            <div><dt>Identity</dt><dd>{detailsCompany.identity_status}{detailsCompany.identity_note && <p>{detailsCompany.identity_note}</p>}</dd></div>
            <div><dt>Standing scope</dt><dd>{detailsCompany.in_scope ? 'Recorded standing links in this scope' : 'No standing links in this scope'}</dd></div>
            <div><dt>Shared watch</dt><dd>{detailsCompany.watched ? 'On the shared Watch list' : 'Not on the shared Watch list'}</dd></div>
            <div><dt>Assigned tier</dt><dd>{detailsCompany.assigned_tier_label}</dd></div>
          </dl><Button size="small" variant="ghost" onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'company', id: detailsCompany.id }, origin: 'grid' })}>Open company profile</Button></section>
          <section><h3>Genetics and exact recorded paths</h3><CompactGenetics expanded id={detailsCompany.id} model={model} renderNode={detailNode} renderEdge={detailEdge} /></section>
          <section><h3>Authored roles and berries</h3><CompactRoles expanded roles={detailsCompany.roles} berryIds={detailsCompany.berry_ids} /></section>
          <section><h3>Geographic activity and sources</h3>{detailsCompany.geographies.length ? <div className="berry-roster-full-geographies">{detailsCompany.geographies.map((geo, index) => <article key={`${geo.relationship_id}-${index}`}>
            <button type="button" className="berry-text-button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: geo.relationship_id }, origin: 'grid' })}><strong>{geo.label}</strong> · {geo.activity}</button>
            <p>{geo.status}</p>{geo.caveat && <p className="berry-material-caveat">{geo.caveat}</p>}{geo.review && <p>Review: {geo.review}</p>}
            {!!geo.evidence_ids.length && <div className="berry-roster-dialog-evidence">{geo.evidence_ids.map(sourceButton)}</div>}
          </article>)}</div> : <p>No geographic activity is recorded in scope.</p>}</section>
          {!!detailsSources.length && <section><h3>Retained sources</h3><ul className="berry-roster-dialog-sources">{detailsSources.map(id => {
            const source = model.sources.find(row => row.id === id);
            return <li key={id}><button type="button" className="berry-text-button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'source', id }, origin: 'grid' })}>{source?.title || 'Open retained source'}</button>
              {source?.source_name && <span>{source.source_name}</span>}{source?.published && <span>Published {source.published}</span>}
            </li>;
          })}</ul></section>}
          <section><h3>Monitoring and collection</h3><CompactCollection expanded monitoring={detailsCompany.monitoring} /></section>
          {logo && <section><h3>Logo and source credit</h3><figure className="berry-roster-logo-credit"><img src={logo.image_url} data-background={logo.background ?? 'light'} alt={`${detailsCompany.label} logo`} width="100" height="64" referrerPolicy="no-referrer" />
            <figcaption>{logo.caption && <p>{logo.caption}</p>}<p>{logo.kind_label}{logo.source_kind && ` · ${logo.source_kind}`}</p>{logo.attribution && <p>{logo.attribution}</p>}
              {logo.match_basis && <p>{logo.match_basis}</p>}{logo.historical_status && <p>{logo.historical_status.replaceAll('_', ' ')}</p>}
              {logo.source_account && <p>{logo.source_account}</p>}{logo.published_at && <p>Published {logo.published_at}</p>}
              {logo.inspection_href && <SourceLink external href={logo.inspection_href}>Inspect retained source</SourceLink>}{logo.source_page_url && <SourceLink external href={logo.source_page_url}>Original source</SourceLink>}
            </figcaption></figure></section>}
        </div></>}
    </dialog>
  );
});
