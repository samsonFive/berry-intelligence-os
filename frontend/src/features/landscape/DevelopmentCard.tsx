import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { InvestigationApiError } from '../../api/client';
import { clearPrivateSession } from '../../app/PrivateQueryProvider';
import { legacyHref } from '../../app/legacy';
import { SourceLink } from '../../components/ui';
import { useInvestigation } from '../../state/InvestigationProvider';
import { safeHref, type NewsCard } from './models';
import { Citation } from './Citation';
import { retainedSourceLinks, RETAINED_LINK_LIMITATION } from './retained-source-links';
import { newsTagEditorHref, saveNewsAction, updateNewsDecision, type NewsAction } from './news-actions';
import './legacy-news.css';

function publicationDate(value?: string | null) {
  if (!value) return 'Date unavailable';
  // Same display-only transformation as the established us_date template filter.
  const date = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return date ? `${Number(date[2])}/${Number(date[3])}/${date[1]}` : value;
}

/** Exact symbols from the established _personal_icons.html macro. */
function ActionIcon({ name }: { name: 'up' | 'down' | 'save' | 'newspaper' }) {
  return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === 'up' && <><path d="M7 10h3l3-7c3 0 3 3 2 6h4a2 2 0 0 1 2 2l-2 8a2 2 0 0 1-2 2H7z" /><path d="M3 10h4v11H3z" /></>}
    {name === 'down' && <><path d="M7 14h3l3 7c3 0 3-3 2-6h4a2 2 0 0 0-2-2l-2-8a2 2 0 0 0-2-2H7z" /><path d="M3 3h4v11H3z" /></>}
    {name === 'save' && <><path d="M4 3h14l3 3v15H3V3z" /><path d="M7 3v6h10V3M7 21v-8h10v8" /></>}
    {name === 'newspaper' && <><path d="M4 4h16v16H4zM4 8H2v12a2 2 0 0 0 2 2h16" /><path d="M7 7h5v5H7zM15 7h2M15 11h2M7 15h10M7 18h10" /></>}
  </svg>;
}

/** _article_visual.html/article_visuals.js behavior, without global legacy scripts. */
function ArticleVisual({ card }: { card: NewsCard }) {
  const publisher = safeHref(card.image_url, ''), reference = card.reference_image;
  const referenceImage = safeHref(reference?.url, '');
  const [publisherFailed, setPublisherFailed] = useState(false), [referenceFailed, setReferenceFailed] = useState(false);
  useEffect(() => setPublisherFailed(false), [publisher]); useEffect(() => setReferenceFailed(false), [referenceImage]);
  const hasPublisher = Boolean(publisher && !publisherFailed), hasReference = Boolean(referenceImage && reference && !referenceFailed);
  return <figure className="article-visual" data-article-visual>
    {hasPublisher && <img className="digest-image" src={publisher} alt={`Article image from ${card.source_name ?? 'source publication'}`} loading="lazy" decoding="async" referrerPolicy="no-referrer" data-publisher-image onError={() => setPublisherFailed(true)} />}
    {!hasPublisher && <div data-image-fallback>{hasReference && reference && <><img className="digest-image" src={referenceImage} alt={[reference.alt ?? reference.title ?? 'Reference photo', reference.note].filter(Boolean).join('. ')} loading="lazy" decoding="async" referrerPolicy="no-referrer" data-reference-image onError={() => setReferenceFailed(true)} /><figcaption data-reference-credit><a href={safeHref(reference.source_url)} target="_blank" rel="noopener noreferrer" title={[reference.credit ?? reference.creator, reference.license, reference.note].filter(Boolean).join(' · ')}>Reference photo</a></figcaption></>}
      {!hasReference && <div data-last-resort className="article-visual-placeholder"><span>{card.source_name || 'Source article'}</span><small>Article photo unavailable</small></div>}
    </div>}
  </figure>;
}

/** Faithful legacy News markup, with native Reader and existing personal-state bridges. */
export function DevelopmentCard({ card, newsHref = '/today' }: { card: NewsCard; summaryOpen?: boolean; newsHref?: string }) {
  const { context, dispatch } = useInvestigation(); const { pathname } = useLocation(); const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false), [status, setStatus] = useState(''); const active = useRef<AbortController | null>(null);
  useEffect(() => () => { active.current?.abort(); }, []);
  const additionalLinks = retainedSourceLinks(card.retained_source_links);
  const openSource = () => dispatch({ type: 'openDetail', detail: { type: 'source', id: card.id }, origin: 'direct' });
  const readerHref = safeHref(card.full_reader_href, `/intelligence/${encodeURIComponent(card.id)}?personal=1`);
  const manageTags = newsTagEditorHref(legacyHref(newsHref, pathname, context), card.id);
  const read = (event: MouseEvent<HTMLAnchorElement>) => { if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); openSource(); } };
  const act = async (action: NewsAction) => {
    if (busy || active.current || !card.decision) return;
    const controller = new AbortController(); active.current = controller; setBusy(true); setStatus('');
    try { const decision = await saveNewsAction(card.id, action, controller.signal); if (controller.signal.aborted) return;
      queryClient.setQueriesData({ queryKey: ['investigation'] }, cached => updateNewsDecision(cached, card.id, decision)); setStatus('Saved your change.');
    } catch (error) { if (controller.signal.aborted) return; if (error instanceof InvestigationApiError && error.requiresSession) clearPrivateSession(); setStatus('Could not save this change. Try again.');
    } finally { if (!controller.signal.aborted) setBusy(false); if (active.current === controller) active.current = null; }
  };
  const actionButton = (symbol: 'up' | 'down' | 'save', label: string, action: NewsAction, selected?: boolean) => <button type="button" className={`icon-action${selected ? ' selected' : ''}`} data-personal-action={action} data-item-id={card.id} aria-label={label} aria-pressed={selected} disabled={busy || !card.decision} title={!card.decision ? 'Personal story state is unavailable' : undefined} onClick={() => void act(action)}><ActionIcon name={symbol} /><span className="action-tooltip" role="tooltip">{label}</span></button>;
  return <article className="digest-card news-card berry-news-card berry-legacy-news-card" tabIndex={-1} data-intel-card data-item-id={card.id} data-pending="false">
    <ArticleVisual key={card.id} card={card} />
    <div className="digest-card-body"><p className="card-meta"><span>{card.source_name ?? 'Source name not recorded'}</span><time dateTime={card.published_at ?? undefined}>{publicationDate(card.published_at)}</time></p>
      <h2><a data-open-reader href={readerHref} onClick={read}>{card.headline}</a></h2>
      {card.translated ? <p className="card-meta">Auto-translated to English</p> : card.translation_pending && <p className="card-meta">English translation pending · original source available</p>}
      {card.media_label && <p className="card-meta"><b>{card.media_label}</b>{card.media_note ? ` · ${card.media_note}` : ''}</p>}
      <div className="card-labels"><span className={`trust-label${card.trusted ? ' trusted' : ''}`}>{card.trusted ? 'Escalated' : card.source_reviewed ? 'Source reviewed' : 'Unreviewed'}</span>{card.crop_labels?.map(crop => <span key={crop}>{crop}</span>)}
        {!!card.assigned_tags?.length && <span className="news-article-tags" aria-label="Article tags">{card.assigned_tags.slice(0, 3).map(tag => <a className="news-tag-label" key={tag.id} href={manageTags} title={tag.description} aria-label={`Manage ${tag.name} in News`}>{tag.name}</a>)}{card.assigned_tags.length > 3 && <a className="news-tag-label" href={manageTags} aria-label="Manage all article tags in News">+{card.assigned_tags.length - 3}</a>}</span>}
        <a className="news-tag-label news-tag-add" href={manageTags} aria-label="Manage tags in News" title="Open the established News tag tools">+</a>
      </div>
      <p className="card-deck">{card.deck || 'No preview text is available. Open the story or read at the publisher.'}</p>
      {card.scope_match?.kind === 'related_context' && <p className="card-meta card-scope-match">{card.scope_match.primary_label && <>About {card.scope_match.primary_label} · </>}Context for {card.scope_match.subject_labels.join(' · ')}</p>}
      {!!card.company_mentions?.length && <p className="card-meta">Mentioned in source: {card.company_mentions.map(company => company.name).join(' · ')} · company link not reviewed</p>}
      {!!(card.entities?.length || card.geography_chips?.length) && <div className="news-context">{card.entities?.slice(0, 3).map(entity => <a key={entity.id} href={safeHref(entity.profile_url)} onClick={event => {
        if (['company', 'variety'].includes(entity.entity_type ?? '') && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); dispatch({ type: 'focusEntity', entity: { type: entity.entity_type as 'company' | 'variety', id: entity.id }, origin: 'direct' }); }
      }}>{entity.name}</a>)}{card.geography_chips?.slice(0, 2).map(place => <span key={place.id}>{place.name}</span>)}</div>}
      {!!card.coverage_sources?.length && <details className="news-coverage"><summary>{card.coverage_sources.length} retained source{card.coverage_sources.length !== 1 ? 's' : ''}</summary><p>{card.independence}</p>{card.coverage_sources.map(source => <p key={source.id}><Citation id={source.id} /> · Published {source.published_date || 'Unknown'} · Captured {source.captured_at || source.captured_date || 'Unknown'}</p>)}</details>}
      {!!additionalLinks.length && <details className="news-coverage" data-retained-source-links><summary>{additionalLinks.length} additional collected link{additionalLinks.length !== 1 ? 's' : ''}</summary><p>{RETAINED_LINK_LIMITATION}</p>{additionalLinks.map((link, index) => <p key={`${link.url}-${index}`}><SourceLink external href={link.url}>{link.label}</SourceLink> · {link.kind}</p>)}</details>}
      <footer className="card-actions">{actionButton('up', 'Useful', card.decision?.reaction === 'up' ? 'clear_feedback' : 'useful', card.decision ? card.decision.reaction === 'up' : undefined)}{actionButton('down', 'Not relevant', card.decision?.reaction === 'down' ? 'clear_feedback' : 'not_relevant', card.decision ? card.decision.reaction === 'down' : undefined)}{actionButton('save', card.decision?.saved ? 'Remove saved mark' : 'Save story', card.decision?.saved ? 'unsave' : 'save', card.decision?.saved)}
        {(card.source_link_url || card.source_url) && <a className="icon-action" href={safeHref(card.source_link_url || card.source_url)} target="_blank" rel="noopener noreferrer" aria-label={`${card.source_link_label ?? 'Original publisher'} (new tab)`}><ActionIcon name="newspaper" /><span className="action-tooltip" role="tooltip">{card.source_link_label ?? 'Original publisher'}</span></a>}
        <a data-open-reader className="read-link" href={readerHref} onClick={read}>Read story ↗</a>
      </footer>{status && <p className="reader-action-status" role="status">{status}</p>}
    </div>
  </article>;
}
