import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { legacyHref } from '../../app/legacy';
import { useSurfaceReady } from '../../app/SurfaceScroll';
import { Badge, Button, EmptyState } from '../../components/ui';
import { hasBlockingIssues, investigationHref } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { DevelopmentCard } from '../landscape/DevelopmentCard';
import { developmentsContext } from '../landscape/developments-context';
import { useReadModel } from '../landscape/useReadModel';
import type { DevelopmentsModel } from '../landscape/models';
import './briefing.css';

const advanced = [
  { label: 'Following', href: '/following', note: 'Your established subscriptions' },
  { label: 'Saved stories', href: '/saved', note: 'Retained personal selections' },
  { label: 'Reading queue', href: '/queues/reading', note: 'Your established reading priorities' },
  { label: 'Social listening', href: '/social', note: 'Existing listening and review workspace' },
  { label: 'Signals', href: '/signals', note: 'Governed analyst patterns and review' },
];
const basis = { scope: 'Applied scope', focus: 'Focused identity', comparison: 'Selected comparison cohort' };

/** A bounded read of retained developments; all sources use the shared Reader. */
export function BriefingPage() {
  const { context, issues } = useInvestigation();
  const blocked = hasBlockingIssues(issues);
  const subject = useMemo(() => developmentsContext(context), [context]);
  const query = useReadModel<DevelopmentsModel>('/developments', subject, !blocked);
  const data = query.data?.data;
  const cards = data?.cards.slice(0, 6) ?? [];
  useSurfaceReady(blocked || !query.isPending);
  const deeper = data?.briefing_href.startsWith('/') && !data.briefing_href.startsWith('//')
    ? legacyHref(data.briefing_href, '/app/briefing', context) : null;
  return <div className="berry-briefing-page">
    <header className="berry-page-heading"><div><p className="berry-eyebrow">Retained developments</p><h1>Briefing</h1><p className="berry-subtitle">Read the current investigation's retained sources, then return to its connections.</p></div>
      <Link className="berry-button berry-button--ghost" to={investigationHref('/app/landscape', context)}>Back to Landscape →</Link>
    </header>
    {blocked ? <EmptyState title="Resolve the investigation selectors">Some scope or URL values are unsupported. Correct them before loading; the investigation has not been broadened.</EmptyState>
      : query.isPending ? <p className="berry-loading" role="status">Loading retained developments for this investigation…</p>
        : query.isError ? <EmptyState title="This Briefing could not be loaded" action={<Button onClick={() => { void query.refetch(); }}>Try again</Button>}>{query.error instanceof Error ? query.error.message : 'The retained source service is unavailable.'}</EmptyState>
          : data && <>
            {!!query.data?.issues.length && <div className="berry-issue" role="status">{query.data.issues.map((issue, index) => <p key={index}>{issue.message}</p>)}</div>}
            <section className="berry-briefing-basis" aria-labelledby="briefing-subject-heading"><div>
              <Badge tone="neutral">{basis[data.basis]}</Badge><h2 id="briefing-subject-heading">{data.heading}</h2>
              <p>{cards.length} of {data.matching_count} matching retained developments. Source geography and publication dates apply; standing portfolio records are separate.</p>
              <p className="berry-scope-note">{context.news_from || context.news_to ? `Publication interval: ${context.news_from || 'No lower bound'} to ${context.news_to || 'No upper bound'}.` : 'No publication-date bounds.'} Source review does not approve every claim.</p>
              {(context.relationship_types || context.q) && <p className="berry-scope-note">Relationship-type filters and the analytical text search do not trim this developments view.</p>}
            </div>{deeper && <a className="berry-button berry-button--secondary" href={deeper}>Open full scoped News ↗</a>}</section>
            {cards.length ? <section className="berry-briefing-cards news-grid berry-legacy-news-grid" aria-label="Retained source developments">{cards.map(card => <DevelopmentCard key={card.id} card={card} newsHref={data.briefing_href} />)}</section>
              : <EmptyState title="No retained developments match this subject and scope">Missing captured news does not establish an absence of developments. Change the applied selectors deliberately to inspect another scope.</EmptyState>}
            {data.briefing_scope_note && <p className="berry-scope-note berry-briefing-deeper-note">{data.briefing_scope_note}</p>}
          </>}
    <section className="berry-briefing-boundaries" aria-labelledby="briefing-existing-heading"><h2 id="briefing-existing-heading">Existing personal and analyst views</h2><p>These established views keep their own controls and return to this investigation.</p>
      <nav aria-label="Existing briefing views">{advanced.map(view => <a key={view.href} href={legacyHref(view.href, '/app/briefing', context)}><strong>{view.label} ↗</strong><span>{view.note}</span></a>)}</nav>
    </section>
  </div>;
}

export default BriefingPage;
