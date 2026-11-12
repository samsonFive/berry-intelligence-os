import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getInvestigation } from '../../api/client';
import { currentDetail, detailPath, hasBlockingIssues, investigationHref, parseRef, refString, sameDetailIdentity, splitIds } from '../../contracts/investigation';
import type { DetailRef, DetailType } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { Badge, Button, EmptyState, Preview, SourceLink } from '../../components/ui';
import { BrandLogo, BrandMediaGallery } from '../brand-media/BrandMedia';
import { useBrandMedia } from '../brand-media/useBrandMedia';
import { VerifiedCompanyLogo } from '../brand-media/VerifiedCompanyLogo';
import { companyLogoBatch } from '../brand-media/company-logo-batches';
import { ProfileSheet } from './ProfileSheet';
import type { ProfileItem } from './ProfileSheet';
import { readerOrganizations } from './reader-companies';
import './detail.css';

interface SourceRef {
  id: string; title: string; url?: string; source_name?: string;
  status?: string; review?: string; published?: string; captured?: string;
}
interface DetailItem extends ProfileItem {}
interface ArticleBlock { text: string; heading?: boolean; level?: number }
interface DocumentBlock {
  kind: string; text?: string; level?: number; cells?: string[];
  spans?: { colspan?: number; rowspan?: number }[];
}
interface Transcript {
  status?: string; language?: string; source?: string; text?: string;
  segments?: { start_seconds: number; end_seconds?: number; text: string }[];
}
interface DetailModel {
  type: DetailType; id: string; title: string; kind_label: string; status?: string;
  summary?: string; outside_scope?: boolean; scope_note?: string; trust_note?: string;
  expand_href?: string; roles?: string[];
  sections: { title: string; items: DetailItem[] }[];
  sources: SourceRef[];
  article_text?: string[]; article_blocks?: ArticleBlock[]; document_blocks?: DocumentBlock[];
  card?: { headline?: string; source_name?: string; source_url?: string; image_url?: string; published_at?: string;
    entities?: Array<{ id: string; name: string; entity_type?: string }>;
    company_mentions?: Array<{ id: string; name: string }>;
    reference_image?: { url?: string; caption?: string; credit?: string; attribution?: string; source_url?: string; license?: string } };
  body_availability?: {
    available?: boolean; auto_acquisition?: boolean; state?: string;
    content_kind?: 'html' | 'pdf'; availability?: 'full_article' | 'excerpt_only' | 'metadata_only'; notice?: string;
  };
  media?: { spoken?: boolean; transcript?: Transcript; format?: string; url?: string; source_url?: string;
    transcript_read_error?: boolean; transcript_provenance?: { method?: string; created_by?: string; created_at?: string; language?: string } };
}
interface ReturnTarget { element: HTMLElement | null; token: string | null }

function visibleReturnTarget(target: ReturnTarget | null): HTMLElement | null {
  const usable = (element: HTMLElement | null): element is HTMLElement => Boolean(element?.isConnected
    && element.getClientRects().length && !element.closest('[inert], [aria-hidden="true"]')
    && !element.matches(':disabled') && getComputedStyle(element).visibility !== 'hidden');
  if (usable(target?.element ?? null)) return target!.element;
  const replacement = target?.token ? document.querySelector<HTMLElement>(`[data-detail-trigger="${CSS.escape(target.token)}"]`) : null;
  return usable(replacement) ? replacement : null;
}

function safeLink(value: string | undefined): string | undefined {
  if (!value) return undefined;
  if (value.startsWith('/') && !value.startsWith('//') && !value.includes('\\')) return value;
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? value : undefined;
  } catch { return undefined; }
}
function sourceFallback(id: string): string { return `/intelligence/${encodeURIComponent(id)}`; }

function ReaderBrandLogo({ id, name, ids }: { id: string; name: string; ids: string[] }) {
  const media = useBrandMedia(companyLogoBatch(id, ids));
  const entity = media?.[id];
  return entity?.entity_type === 'brand' && entity.logo
    ? <div className="berry-verified-company-logo berry-verified-company-logo--inspectable"><BrandLogo asset={entity.logo} name={name} /></div> : null;
}

function DocumentBody({ blocks }: { blocks: DocumentBlock[] }) {
  const output = [];
  for (let index = 0; index < blocks.length; index++) {
    const block = blocks[index];
    if (block.kind === 'table_row') {
      const rows = [block];
      while (blocks[index + 1]?.kind === 'table_row') rows.push(blocks[++index]);
      output.push(<div className="berry-table-wrap" key={`table-${index}`}><table className="berry-table"><tbody>
        {rows.map((row, rowIndex) => <tr key={rowIndex}>{row.cells?.map((cell, cellIndex) => <td key={cellIndex}
          colSpan={Math.max(1, Math.min(20, row.spans?.[cellIndex]?.colspan ?? 1))}
          rowSpan={Math.max(1, Math.min(100, row.spans?.[cellIndex]?.rowspan ?? 1))}>{cell}</td>)}</tr>)}
      </tbody></table></div>);
    } else if (block.kind === 'list_item') {
      const items = [block];
      while (blocks[index + 1]?.kind === 'list_item') items.push(blocks[++index]);
      output.push(<ul key={`list-${index}`}>{items.map((item, itemIndex) => <li key={itemIndex}>{item.text}</li>)}</ul>);
    } else if (block.kind === 'heading') output.push(block.level === 4
      ? <h4 key={index}>{block.text}</h4> : <h3 key={index}>{block.text}</h3>);
    else if (block.text) output.push(<p key={index}>{block.text}</p>);
  }
  return <>{output}</>;
}
function ArticleBody({ model }: { model: DetailModel }) {
  if (model.document_blocks?.length) return <DocumentBody blocks={model.document_blocks} />;
  if (model.article_blocks?.length) return <>{model.article_blocks.map((block, index) => block.heading
    ? block.level === 4 ? <h4 key={index}>{block.text}</h4> : <h3 key={index}>{block.text}</h3>
    : <p key={index}>{block.text}</p>)}</>;
  return <>{model.article_text?.map((paragraph, index) => <p key={index}>{paragraph}</p>)}</>;
}
function timeLabel(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
}

/** One allocation for selected entities, exact relationships and the Reader. */
export function DetailHost({ suspended = false }: { suspended?: boolean }) {
  const { context, revision, issues, dispatch } = useInvestigation();
  const selected = currentDetail(context);
  const media = useBrandMedia(selected?.type === 'company' && !suspended && !hasBlockingIssues(issues) ? [selected.id] : []);
  const path = context.detail_path;
  const ancestry = detailPath(context);
  const readerView = selected?.type === 'source' && selected.section === 'brief' ? 'brief' : 'article';
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 850px)').matches);
  const [panelWidth, setPanelWidth] = useState(440);
  const drag = useRef<{ start: number; width: number } | null>(null);
  const panel = useRef<HTMLElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const targets = useRef(new Map<string, ReturnTarget>());
  const scrollPositions = useRef(new Map<string, number>());
  const titles = useRef(new Map<string, string>());
  const profileExpansions = useRef(new Set<string>());
  const profileScroll = useRef(new Map<string, number>());
  const returnToMain = useRef(false);
  const wasSuspended = useRef(suspended);
  const previousPath = useRef('');
  const pendingReturn = useRef<ReturnTarget | null>(null);
  const openingTarget = useRef<ReturnTarget | null>(null);
  const focusApplied = useRef('');
  const endpoint = selected ? `/detail?type=${selected.type}&id=${encodeURIComponent(selected.id)}` : '';
  const query = useQuery({
    queryKey: ['investigation-detail', endpoint, context.berry, context.countries, context.geo_basis, context.actor_roles, context.relationship_types],
    queryFn: ({ signal }) => getInvestigation<DetailModel>(endpoint, context, revision, signal),
    enabled: !!selected && !hasBlockingIssues(issues),
    staleTime: 60_000,
  });

  useEffect(() => {
    const media = window.matchMedia('(max-width: 850px)');
    const update = () => setNarrow(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useLayoutEffect(() => {
    const workspace = panel.current?.parentElement;
    if (!workspace || narrow || suspended) return;
    const previous = workspace.style.getPropertyValue('--berry-detail-width');
    workspace.style.setProperty('--berry-detail-width', `${panelWidth}px`);
    return () => {
      if (previous) workspace.style.setProperty('--berry-detail-width', previous);
      else workspace.style.removeProperty('--berry-detail-width');
    };
  }, [!!selected, narrow, panelWidth, suspended]);
  useLayoutEffect(() => {
    const previous = previousPath.current;
    if (previous === path) return;
    const before = previous.split('~').filter(Boolean).map(parseRef);
    const after = path.split('~').filter(Boolean).map(parseRef);
    const sectionOnly = !!previous && !!path && before.length === after.length
      && before.every((item, index) => !!item && !!after[index] && sameDetailIdentity(item, after[index]!));
    if (sectionOnly) {
      const target = targets.current.get(previous);
      if (target) targets.current.set(path, target);
      openingTarget.current = null;
      previousPath.current = path;
      focusApplied.current = path;
      if (panel.current) panel.current.scrollTop = scrollPositions.current.get(path) ?? 0;
      return;
    }
    if (path && (!previous || path.startsWith(previous + '~'))) {
      const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      targets.current.set(path, openingTarget.current ?? { element: active, token: active?.getAttribute('data-detail-trigger') ?? null });
    } else if (previous) {
      // Dismissing the stack returns to the main-page opener. A one-level Back
      // instead restores the citation/record that opened the previous detail.
      pendingReturn.current = targets.current.get(path ? previous : previous.split('~')[0]) ?? null;
    }
    openingTarget.current = null;
    previousPath.current = path;
    focusApplied.current = '';
    if (path) heading.current?.focus({ preventScroll: true });
    if (!path) {
      returnToMain.current = !!previous;
    }
  }, [path]);
  useLayoutEffect(() => {
    if (!selected || !query.data || focusApplied.current === path) return;
    titles.current.set(`${selected.type}:${selected.id}`, query.data.data.title);
    focusApplied.current = path;
    if (panel.current) panel.current.scrollTop = scrollPositions.current.get(path) ?? 0;
    const target = pendingReturn.current;
    pendingReturn.current = null;
    const restored = visibleReturnTarget(target);
    (restored ?? heading.current)?.focus({ preventScroll: true });
  }, [path, query.data, selected]);
  useLayoutEffect(() => {
    const resuming = wasSuspended.current && !suspended;
    wasSuspended.current = suspended;
    if (resuming && selected && panel.current) {
      panel.current.scrollTop = scrollPositions.current.get(path) ?? 0;
      heading.current?.focus({ preventScroll: true });
    }
  }, [suspended, selected?.id, path]);
  useEffect(() => {
    if (!selected || !narrow || suspended) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const workspace = panel.current?.parentElement;
    const shell = workspace?.closest('.berry-app');
    // Mark sibling branches, never an ancestor containing this modal. The shared
    // Workspace frame can introduce sidebars between the panel and app shell.
    const backgroundElements = new Set<HTMLElement>();
    let branch: HTMLElement | null = panel.current;
    while (branch && branch !== shell) {
      const parentElement: HTMLElement | null = branch.parentElement;
      if (!parentElement) break;
      for (const element of parentElement.children) {
        if (element instanceof HTMLElement && element !== branch) backgroundElements.add(element);
      }
      branch = parentElement;
    }
    const background = [...backgroundElements]
      .map(element => ({ element, inert: element.inert, hidden: element.getAttribute('aria-hidden') }));
    for (const { element } of background) { element.inert = true; element.setAttribute('aria-hidden', 'true'); }
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !panel.current) return;
      // The shared informational/image Preview owns its enterable portal and
      // tab order while open; it must not be pulled back into the panel.
      if (document.querySelector('.berry-preview')) return;
      const controls = [...panel.current.querySelectorAll<HTMLElement>('a[href],button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),audio[controls],video[controls],summary,[contenteditable="true"],[tabindex]:not([tabindex="-1"])')]
        .filter(element => element.getClientRects().length > 0);
      const first = controls[0]; const last = controls.at(-1);
      if (!first) { event.preventDefault(); heading.current?.focus(); return; }
      if (!panel.current.contains(document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first)?.focus(); }
      else if (event.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) {
        event.preventDefault(); last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      for (const { element, inert, hidden } of background) {
        element.inert = inert;
        if (hidden === null) element.removeAttribute('aria-hidden'); else element.setAttribute('aria-hidden', hidden);
      }
      document.removeEventListener('keydown', onKey);
    };
  }, [selected?.id, narrow, suspended]);
  useEffect(() => {
    if (path || suspended || !returnToMain.current) return;
    returnToMain.current = false;
    const target = pendingReturn.current;
    pendingReturn.current = null;
    // Passive cleanup has now removed narrow-mode inert attributes. Focusing
    // during the layout phase would target the still-inert main investigation.
    const frame = requestAnimationFrame(() => {
      const restored = visibleReturnTarget(target);
      (restored ?? document.getElementById('investigation-main'))?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [path, suspended]);
  useEffect(() => {
    if (!selected || suspended) return;
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) {
        if (document.querySelector('.berry-preview')) return;
        event.preventDefault(); dispatch({ type: 'closeDetail', origin: 'direct' });
      }
    };
    document.addEventListener('keydown', onEscape);
    return () => document.removeEventListener('keydown', onEscape);
  }, [selected?.id, dispatch, suspended]);

  if (!selected || suspended) return null;
  const model = query.data?.data;
  const publisherImage = safeLink(model?.card?.image_url);
  const referenceImage = safeLink(model?.card?.reference_image?.url);
  const readerImage = publisherImage || referenceImage;
  const usingReferenceImage = !publisherImage && !!referenceImage;
  const sourceCompanies = selected.type === 'source' ? readerOrganizations(model?.card) : [];
  const sourceCompanyIds = sourceCompanies.map(company => company.id);
  const selectedSource = model?.sources.find(item => item.id === model.id);
  const chooseReaderView = (section: 'article' | 'brief') => dispatch({ type: 'setDetailSection', section, origin: 'direct' });
  const open = (detail: DetailRef) => {
    // Capture before React removes the selected profile's source/record link.
    // Capturing in the path layout effect is too late: activeElement is body.
    const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    openingTarget.current = sameDetailIdentity(selected, detail) ? null
      : { element: active, token: active?.getAttribute('data-detail-trigger') ?? null };
    dispatch({ type: 'openDetail', detail, origin: 'direct' });
  };
  const source = (item: SourceRef, trigger?: string) => <SourceLink key={item.id} href={sourceFallback(item.id)}
    data-detail-trigger={trigger ?? `source:${item.id}`} onOpen={() => open({ type: 'source', id: item.id })}>
    {item.title || item.source_name || item.id}{item.published ? ` · ${item.published}` : ' · Publication date not recorded'}
  </SourceLink>;
  const pinKind = selected.type === 'company' || selected.type === 'variety' ? selected.type : null;
  const pinned = pinKind ? splitIds(context[pinKind === 'company' ? 'cohort_companies' : 'cohort_varieties']).includes(selected.id) : false;
  const compactProfile = selected.type === 'company' || selected.type === 'relationship';
  const profileIdentity = `${selected.type}:${selected.id}`;
  const profileSectionOpen = (section: string, defaultOpen = false) => {
    const key = `${profileIdentity}:${section}`;
    return !profileExpansions.current.has(`${key}:closed`) && (defaultOpen || profileExpansions.current.has(key));
  };
  const rememberProfileSection = (section: string, expanded: boolean) => {
    const key = `${profileIdentity}:${section}`;
    profileExpansions.current.delete(expanded ? `${key}:closed` : key);
    profileExpansions.current.add(expanded ? key : `${key}:closed`);
  };
  const cited = new Set(model?.sections.flatMap(section => section.items.flatMap(item => [...(item.evidence_ids ?? []), ...(item.sources ?? []).map(source => source.id)])) ?? []);
  const additionalSources = model?.sources.filter(item => !cited.has(item.id)) ?? [];
  const materialStatus = model?.status && /historical|disputed|planned|validation|inactive|inferred/i.test(model.status);
  const expanded = safeLink(model?.expand_href);
  const expandHref = expanded && expanded.startsWith('/') ? expanded + (expanded.includes('?') ? '&' : '?')
    + new URLSearchParams({ return_to: investigationHref('/app/landscape', context) }) : expanded;
  const resize = (width: number) => setPanelWidth(Math.max(340, Math.min(720, window.innerWidth - 520, width)));
  return <aside ref={panel} className={`berry-detail${compactProfile ? ' berry-detail--sheet' : ''}`} role="dialog" aria-modal={narrow || undefined}
    aria-labelledby="berry-detail-heading" aria-busy={query.isFetching || undefined}
    onScroll={event => scrollPositions.current.set(path, event.currentTarget.scrollTop)}>
    {!narrow && <div className="berry-detail-resizer" role="separator" tabIndex={0} aria-label="Resize detail panel"
      aria-orientation="vertical" aria-valuemin={340} aria-valuemax={720} aria-valuenow={panelWidth}
      onKeyDown={event => {
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); resize(panelWidth + (event.key === 'ArrowLeft' ? 24 : -24)); }
      }}
      onPointerDown={event => { event.preventDefault(); drag.current = { start: event.clientX, width: panelWidth }; event.currentTarget.setPointerCapture(event.pointerId); }}
      onPointerMove={event => { if (drag.current) resize(drag.current.width + drag.current.start - event.clientX); }}
      onPointerUp={event => { drag.current = null; if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }}
      onLostPointerCapture={() => { drag.current = null; }} />}
    <div className="berry-detail-actions"><Button size="small" onClick={() => dispatch({ type: 'closeDetail', origin: 'direct' })}>
        {ancestry.length > 1 ? '← Back to previous detail' : '← Return to investigation'}
      </Button>{expandHref && <SourceLink href={expandHref}>{selected.type === 'company' ? 'Company profile ↗' : 'Expand ↗'}</SourceLink>}
        <button type="button" className="berry-icon-button berry-detail-close" aria-label={selected.type === 'source' ? 'Close Reader and all details' : 'Close all details'}
          title="Close all details" onClick={() => dispatch({ type: 'dismissDetails', origin: 'direct' })}>×</button></div>
    <header className="berry-detail-header">
      {ancestry.length > 1 && <nav className="berry-detail-breadcrumbs" aria-label="Detail ancestry">{ancestry.map((ref, index) =>
        <span key={refString(ref)}>{index > 0 && <span aria-hidden="true"> / </span>}{index < ancestry.length - 1
          ? <button type="button" onClick={() => open(ref)}>{titles.current.get(`${ref.type}:${ref.id}`) ?? ref.type.slice(0, 1).toUpperCase() + ref.type.slice(1)}</button>
          : <span aria-current="page">{ref.type}</span>}</span>)}</nav>}
      <p className="berry-eyebrow">{model?.kind_label ?? selected.type}</p>
      <div className="berry-detail-identity"><BrandLogo asset={selected.type === 'company' ? media?.[selected.id]?.logo : null} name={model?.title ?? selected.id} />
      <h2 id="berry-detail-heading" ref={heading} tabIndex={-1}>{model?.title ?? 'Loading selected detail…'}</h2></div>
      {model?.status && (!compactProfile || materialStatus) && <Badge>{model.status.replaceAll('_', ' ')}</Badge>}
      {model?.outside_scope && <div className="berry-outside-scope berry-scope-context"><Preview label="Outside the applied scope"
        className="berry-scope-info" content={<p>Outside the applied scope. Inspection keeps the landscape and developments unchanged.</p>}>
          <span aria-hidden="true">ⓘ</span><span className="berry-sr-only">Outside-scope information</span></Preview>
        {pinKind && <Button size="small" onClick={() => dispatch({ type: 'applyScope', origin: 'direct',
          scope: { berry: 'all', countries: '', actor_roles: '', relationship_types: '' } })}>All berries / countries</Button>}</div>}
      {model?.scope_note && !compactProfile && <p className="berry-subtitle">{model.scope_note}</p>}
      {pinKind && <Button size="small" aria-pressed={pinned}
        onClick={() => dispatch({ type: 'togglePin', entity: { type: pinKind, id: selected.id }, origin: 'direct' })}>
        {pinned ? 'Remove from comparison' : 'Add to comparison'}</Button>}
    </header>
    {query.isPending && <p className="berry-loading" role="status">Loading the selected record…</p>}
    {query.isError && <EmptyState title="This detail could not be loaded" action={<Button onClick={() => void query.refetch()}>Try again</Button>}>
      {query.error instanceof Error ? query.error.message : 'Return to the investigation or open the original record.'}
    </EmptyState>}
    {model && <>
      {compactProfile ? <>
        {!!model.roles?.length && <p className="berry-profile-roles">{model.roles.map(role => role.replaceAll('_', ' ')).join(' · ')}</p>}
        <details className={`berry-profile-basis${selected.type === 'company' ? ' berry-profile-overview' : ''}`} key={`${profileIdentity}:basis`}
          open={profileSectionOpen('basis', selected.type === 'company')} onToggle={event => rememberProfileSection('basis', event.currentTarget.open)}>
          <summary>Profile info</summary>{model.summary && <p>{model.summary}</p>}
          {selected.type === 'company' ? <details className="berry-profile-basis berry-profile-context" key={`${profileIdentity}:context`}
            open={profileSectionOpen('context')} onToggle={event => rememberProfileSection('context', event.currentTarget.open)}>
            <summary>Context</summary>{model.scope_note && <p>{model.scope_note}</p>}{model.status && <p>Status: {model.status.replaceAll('_', ' ')}</p>}
          </details> : <>{model.scope_note && <p>{model.scope_note}</p>}{model.status && <p>Status: {model.status.replaceAll('_', ' ')}</p>}</>}
        </details>
      </> : model.summary && selected.type !== 'source' && <p className="berry-detail-summary">{model.summary}</p>}
      {selected.type === 'company' && <details className="berry-profile-media" key={`${profileIdentity}:images`}
        open={profileSectionOpen('images', true)} onToggle={event => rememberProfileSection('images', event.currentTarget.open)}>
        <summary>Images</summary><BrandMediaGallery key={selected.id} model={media?.[selected.id]} /></details>}
      {selected.type === 'source' && <section className="berry-reader" aria-label="Source Reader">
        {sourceCompanies.length > 0 && <div className="berry-reader-companies" aria-label="Companies and brands associated with this source">{sourceCompanies.map(company => <div key={company.id}>
          {company.kind === 'company' ? <VerifiedCompanyLogo id={company.id} name={company.name} companyIds={sourceCompanyIds} inspectable />
            : <ReaderBrandLogo id={company.id} name={company.name} ids={sourceCompanyIds} />}
          <div>{company.kind === 'company' ? <button type="button" className="berry-text-button" data-detail-trigger={`company:${company.id}`}
            onClick={() => open({ type: 'company', id: company.id })}>{company.name}</button> : <span>{company.name}<small>Brand</small></span>}
            {company.association === 'mentioned' && <small>Mentioned in source · company link not reviewed</small>}</div>
        </div>)}</div>}
        <p className="berry-reader-meta">{selectedSource?.source_name || model.card?.source_name || 'Source publication'}
          {' · '}{selectedSource?.published || 'Publication date not recorded'}
          {safeLink(selectedSource?.url || model.card?.source_url) && <span> · <SourceLink external href={safeLink(selectedSource?.url || model.card?.source_url)!}>Original publisher</SourceLink></span>}</p>
        <div className="berry-segmented" role="group" aria-label="Source reading mode">
          <Button size="small" aria-pressed={readerView === 'article'} onClick={() => chooseReaderView('article')}>Article</Button>
          <Button size="small" aria-pressed={readerView === 'brief'} onClick={() => chooseReaderView('brief')}>Brief</Button>
        </div>
        {model.trust_note && <p className="berry-reader-limit">{model.trust_note}</p>}
        {readerImage && <figure><img src={readerImage} alt={usingReferenceImage ? model.card?.reference_image?.caption ?? 'Contextual reference image' : ''} loading="lazy" />
          {usingReferenceImage && model.card?.reference_image && <figcaption><span>Reference photo · contextual illustration. </span>{model.card.reference_image.caption}
            {(model.card.reference_image.credit || model.card.reference_image.attribution) && <span> {model.card.reference_image.credit || model.card.reference_image.attribution}</span>}
            {safeLink(model.card.reference_image.source_url) && <span> <SourceLink href={safeLink(model.card.reference_image.source_url)!} external>Image source</SourceLink></span>}
          </figcaption>}</figure>}
        {safeLink(model.media?.url) && (model.media?.format === 'podcast' || model.media?.format === 'audio')
          && <audio controls preload="none" src={safeLink(model.media.url)}>Audio playback is unavailable. <a href={safeLink(model.media.url)}>Open audio</a></audio>}
        {safeLink(model.media?.url) && model.media?.format === 'video'
          && <video controls playsInline preload="none" src={safeLink(model.media.url)}>Video playback is unavailable. <a href={safeLink(model.media.url)}>Open video</a></video>}
        {readerView === 'article' && <>
          {model.body_availability?.notice && <p className="berry-reader-limit" data-reader-body-notice>{model.body_availability.notice}</p>}
          {model.article_text?.length || model.article_blocks?.length || model.document_blocks?.length
          ? <div className="berry-reader-article"><ArticleBody model={model} /></div>
          : <EmptyState compact title="Article text is not available here">Use the publisher link below to inspect the source. Opening this Reader does not acquire new material.</EmptyState>}
        </>}
        {readerView === 'brief' && <div><p>{model.summary || 'No source summary is recorded.'}</p>
          <p className="berry-reader-limit">A source summary is distinct from a verified claim. Supporting statements retain their own status.</p></div>}
        {model.media?.transcript?.status === 'available' && <details className="berry-reader-transcript"><summary>Transcript{model.media.transcript.language ? ` · ${model.media.transcript.language}` : ''}</summary>
          {model.media.transcript.source && <p className="berry-subtitle">{model.media.transcript.source}</p>}
          {model.media.transcript.segments?.length ? model.media.transcript.segments.map((segment, index) => <p key={index}>
            <time>{timeLabel(segment.start_seconds)}</time> {segment.text}</p>) : <p>{model.media.transcript.text}</p>}
        </details>}
        {model.sources.map(item => safeLink(item.url) && <p key={item.id}><SourceLink href={safeLink(item.url)!} external>
          Open {item.source_name || 'original publisher'}</SourceLink></p>)}
      </section>}
      {selected.type === 'company' && <SourceLink className="berry-profile-catalog" href={`/entities/variety?${new URLSearchParams({ berry: '', return_to: investigationHref('/app/landscape', context) })}`}>Full cultivar catalog ↗</SourceLink>}
      {compactProfile ? <ProfileSheet key={profileIdentity} sections={model.sections} sources={model.sources} open={open} renderSource={source}
        expansions={profileExpansions.current} scrollPositions={profileScroll.current} identity={profileIdentity} /> : model.sections.map((section, index) => section.items.length > 0 && <section className="berry-detail-section" key={`${section.title}-${index}`}>
        <h3>{section.title}</h3><dl className="berry-definition-list">{section.items.map((item, itemIndex) => <div key={item.id ?? itemIndex}>
          <dt>{item.id && item.type && ['company', 'variety', 'geography', 'relationship', 'source', 'observation'].includes(item.type)
            ? <button type="button" data-detail-trigger={`${item.type}:${item.id}`} onClick={() => open({ type: item.type!, id: item.id! })}>{item.label || 'Inspect record'}</button>
            : item.label || 'Recorded observation'}</dt>
          <dd>{item.value ? <p>{item.value}</p> : null}{item.summary && <p>{item.summary}</p>}{item.status && <Badge>{item.status}</Badge>}
            {!!item.sources?.length && <div className="berry-citations">{item.sources.map(item => source(item))}</div>}</dd>
        </div>)}</dl>
      </section>)}
      {compactProfile ? additionalSources.length > 0 && <details className="berry-profile-basis" key={`${profileIdentity}:sources`} open={profileExpansions.current.has(`${profileIdentity}:sources`)}
        onToggle={event => { if (event.currentTarget.open) profileExpansions.current.add(`${profileIdentity}:sources`); else profileExpansions.current.delete(`${profileIdentity}:sources`); }}>
        <summary>Additional sources · {additionalSources.length}</summary><div className="berry-profile-sources">{additionalSources.map(item => source(item))}</div>
      </details> : selected.type !== 'source' && model.sources.length > 0 && <section className="berry-detail-section"><h3>Sources</h3>
        <div className="berry-citations">{model.sources.map(item => source(item))}</div></section>}
    </>}
  </aside>;
}

export default DetailHost;
