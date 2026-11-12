import { useState } from 'react';
import { Badge, Button, SourceLink } from '../../components/ui';
import { useInvestigation } from '../../state/InvestigationProvider';
import { safeHref, type NewsCard } from './models';
import { Citation } from './Citation';
import { retainedSourceLinks, RETAINED_LINK_LIMITATION } from './retained-source-links';

function publicationDate(value?: string | null) {
  const day = value?.slice(0, 10);
  if (!day || !/^\d{4}-\d{2}-\d{2}$/.test(day)) return 'Publication date unavailable';
  const parsed = new Date(`${day}T00:00:00Z`);
  return Number.isNaN(parsed.valueOf()) ? 'Publication date unavailable' : parsed.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
}

export function DevelopmentCard({ card, summaryOpen = false }: { card: NewsCard; summaryOpen?: boolean }) {
  const { dispatch } = useInvestigation();
  const [imageFailed, setImageFailed] = useState(false);
  const publisherImage = safeHref(card.image_url, '');
  const reference = card.reference_image;
  const image = publisherImage || safeHref(reference?.url, '');
  const additionalLinks = retainedSourceLinks(card.retained_source_links);
  const openSource = () => dispatch({ type: 'openDetail', detail: { type: 'source', id: card.id }, origin: 'direct' });
  return <article className="berry-news-card">
    {image && !imageFailed && <figure className="berry-news-figure"><img className="berry-news-image" src={image} alt="" loading="lazy" onError={() => setImageFailed(true)} />
      {!publisherImage && reference && <figcaption><span>{reference.label ?? 'Reference photo'}</span><details><summary>Photo credit</summary>{reference.note && <span>{reference.note}</span>}<span>{reference.credit ?? reference.creator}{reference.license ? ` · ${reference.license}` : ''}{reference.source_url && <> · <SourceLink external href={safeHref(reference.source_url)}>Photo source</SourceLink></>}</span></details></figcaption>}
    </figure>}
    <div className="berry-news-body"><p className="berry-news-meta"><span>{card.source_name ?? 'Source name not recorded'}</span><time dateTime={card.published_at ?? undefined}>{publicationDate(card.published_at)}</time></p>
      <a className="berry-news-title" title={card.headline} href={card.full_reader_href ?? `/intelligence/${encodeURIComponent(card.id)}?personal=1`} onClick={event => {
        if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); openSource(); }
      }}>{card.headline}</a>
      <div className="berry-news-labels"><Badge tone={card.trusted ? 'sage' : card.source_reviewed ? 'neutral' : 'warning'}>{card.trusted ? 'Escalated' : card.source_reviewed ? 'Source reviewed' : 'Unreviewed'}</Badge>{card.crop_labels?.map(crop => <span key={crop}>{crop}</span>)}</div>
      {card.scope_match?.kind === 'related_context' && <p className="berry-news-scope-match">{card.scope_match.primary_label && <>About {card.scope_match.primary_label} · </>}Context for {card.scope_match.subject_labels.join(' · ')}</p>}
      {card.translated && <p className="berry-news-match">Auto-translated to English</p>}{card.translation_pending && <p className="berry-news-match">English translation pending · original source available</p>}
      {card.media_label && <p className="berry-news-match"><strong>{card.media_label}</strong>{card.media_note ? ` · ${card.media_note}` : ''}</p>}
      {card.deck && <details className="berry-news-summary" open={summaryOpen}><summary>Summary</summary><p className="berry-news-excerpt">{card.deck}</p></details>}
      {!!card.company_mentions?.length && <p className="berry-news-match">Mentioned in source: {card.company_mentions.map(company => company.name).join(' · ')} · company link not reviewed</p>}
      {!!card.coverage_sources?.length && <details className="berry-news-coverage"><summary>{card.coverage_sources.length} retained sources</summary><p>{card.independence}</p>{card.coverage_sources.map(source => <p key={source.id}><Citation id={source.id} /> · Published {source.published_date || 'Unknown'} · Captured {source.captured_at || source.captured_date || 'Unknown'}</p>)}</details>}
      {!!additionalLinks.length && <details className="berry-news-coverage" data-retained-source-links><summary>{additionalLinks.length} additional collected link{additionalLinks.length === 1 ? '' : 's'}</summary>
        <p>{RETAINED_LINK_LIMITATION}</p>{additionalLinks.map((link, index) => <p key={`${link.url}-${index}`}><SourceLink external href={link.url}>{link.label}</SourceLink> · {link.kind}</p>)}
      </details>}
      <footer className="berry-news-actions"><Button variant="ghost" size="small" onClick={openSource}>Read source →</Button>{(card.source_link_url || card.source_url) && <SourceLink external aria-label={card.source_link_label ?? 'Original publisher'} href={safeHref(card.source_link_url || card.source_url)}>{card.source_link_label?.startsWith('Listen') ? 'Listen at source' : card.source_link_label?.startsWith('Watch') ? 'Watch at source' : 'Publisher'}</SourceLink>}</footer>
    </div>
  </article>;
}
