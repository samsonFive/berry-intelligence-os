import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useParams } from 'react-router-dom';
import { InvestigationApiError } from '../../api/client';
import { SESSION_TRANSITION_EVENT } from '../../app/PrivateQueryProvider';
import { useSurfaceReady } from '../../app/SurfaceScroll';
import { investigationHref } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { DEFAULT_LEARNING_SELECTION, getLearningCatalog, getLearningContent, legacyExpansionHref } from './api';
import type { LearningCatalog, LearningCollection, LearningContent, LearningItem, LearningKind, LearningSelection } from './models';
import { ConceptSections, LearningCitations, LessonMarkdown } from './Reading';
import { CaneCalendar, LearningFigure, TeachingDiagram, TeachingResources } from './Teaching';
import { groupCropNotes } from './crop-notes';
import './learn-page.css';

const UI_KEY = ['learning-ui-selection'];
const count = (value: number | null) => value === null ? 'Unknown' : String(value);
function errorMessage(error: unknown): string {
  return error instanceof InvestigationApiError ? error.message : 'The educational library could not be loaded. Try again.';
}
function EducationNotice() {
  return <p className="berry-learn-boundary">Educational knowledge explains how crops and production systems work. It is separate from competitive Evidence, Signals and Assessments.</p>;
}
function ItemStatus({ item }: { item: LearningItem }) {
  return <div className="berry-learn-labels"><span>{item.status_label}</span><span>{item.knowledge_class_label}</span>
    {item.partial && <span className="berry-learn-warning-label">Partial research</span>}
    {item.is_stale && <span className="berry-learn-warning-label">Past review date</span>}
  </div>;
}
function ReadingError({ error, retry, back }: { error: unknown; retry: () => void; back: string }) {
  const session = error instanceof InvestigationApiError && error.requiresSession;
  return <section className="berry-learn-message" role="status"><h2>{session ? 'Sign in to read Learn' : 'This learning view is unavailable'}</h2>
    <p>{errorMessage(error)}</p>{session ? <a href={`/login?next=${encodeURIComponent(back)}`}>Sign in</a>
      : <button type="button" className="berry-button" onClick={retry}>Try again</button>}</section>;
}

/** Zero-prop slot: nested routes and the library share the persistent shell. */
export default function LearnPage() {
  const { learningId } = useParams();
  const { pathname } = useLocation();
  const kind: LearningKind | undefined = pathname.startsWith('/app/learn/concept/') ? 'concept'
    : pathname.startsWith('/app/learn/lesson/') ? 'lesson' : undefined;
  return kind && learningId ? <SelectedLearning key={`${kind}:${learningId}`} kind={kind} id={learningId} /> : <LearningLibrary />;
}

function LearningLibrary() {
  const { context, revision } = useInvestigation();
  const client = useQueryClient();
  const [selection, setSelection] = useState<LearningSelection>(() => client.getQueryData<LearningSelection>(UI_KEY) ?? { ...DEFAULT_LEARNING_SELECTION });
  const [draft, setDraft] = useState(selection);
  useEffect(() => { client.setQueryDefaults(UI_KEY, { gcTime: Infinity }); client.setQueryData(UI_KEY, selection); }, [client, selection]);
  useEffect(() => {
    const clear = () => { setSelection({ ...DEFAULT_LEARNING_SELECTION }); setDraft({ ...DEFAULT_LEARNING_SELECTION }); };
    const restore = (event: PageTransitionEvent) => { if (event.persisted) clear(); };
    window.addEventListener(SESSION_TRANSITION_EVENT, clear); window.addEventListener('pageshow', restore);
    return () => { window.removeEventListener(SESSION_TRANSITION_EVENT, clear); window.removeEventListener('pageshow', restore); };
  }, []);
  const query = useQuery({ queryKey: ['learning', 'catalog', selection],
    queryFn: ({ signal }) => getLearningCatalog(context, revision, selection, signal), staleTime: 30_000 });
  useSurfaceReady(!!query.data || query.isError);
  const data = query.data?.data;
  const issues = query.data?.issues ?? [];
  const href = investigationHref('/app/learn', context);
  const apply = (event: FormEvent) => { event.preventDefault(); setSelection({ ...draft, q: draft.q.trim(), offset: 0 }); };
  const reset = () => { setDraft({ ...DEFAULT_LEARNING_SELECTION }); setSelection({ ...DEFAULT_LEARNING_SELECTION }); };
  const changePage = (kind: LearningKind, offset: number) => {
    const next = { ...selection, kind, offset };
    setSelection(next); setDraft(next);
  };
  return <div className="berry-learn-page" data-native-learn="library"><header className="berry-learn-heading"><div>
    <p className="berry-eyebrow">Learn</p><h1>Understand the crop.</h1><p>Existing lessons on crop biology, production systems, harvest technology and sensory science.</p>
  </div><a className="berry-button" href={`/learn/research/new?${new URLSearchParams({ return_to: href })}`}>Research a lesson ↗</a></header>
    <EducationNotice />
    <p className="berry-learn-applicability">Library filters apply here. Investigation geography, companies, cohorts and news dates remain navigation context and do not narrow educational coverage.</p>
    <form className="berry-learn-filters" aria-label="Learning library filters" onSubmit={apply}>
      <label>Search lessons<input type="search" value={draft.q} maxLength={200} placeholder="A concept or production question" onChange={event => setDraft({ ...draft, q: event.target.value })}/></label>
      <label>Topic area<select value={draft.pillar} onChange={event => setDraft({ ...draft, pillar: event.target.value })}><option value="">All topic areas</option>
        {data?.facets.pillars.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
      <label>Knowledge class<select value={draft.knowledge_class} onChange={event => setDraft({ ...draft, knowledge_class: event.target.value })}><option value="">All knowledge classes</option>
        {data?.facets.knowledge_classes.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
      <label>Library<select value={draft.kind} onChange={event => setDraft({ ...draft, kind: event.target.value as LearningSelection['kind'] })}><option value="all">All learning</option><option value="concept">Concepts</option><option value="lesson">Saved lessons</option></select></label>
      <button type="submit" className="berry-button berry-button--primary">Apply filters</button><button type="button" className="berry-button berry-button--ghost" onClick={reset}>Clear filters</button>
    </form>
    {query.isPending && <p className="berry-loading" role="status">Loading the existing educational library…</p>}
    {query.isError && <ReadingError error={query.error} retry={() => void query.refetch()} back={href}/>}
    {data && <>
      <div className="berry-learn-counts" aria-label="Learning library coverage"><span>{count(data.counts.concepts)} concepts</span><span>{count(data.counts.lessons)} saved lessons</span>
        {data.counts.stale !== null && data.counts.stale > 0 && <span>{data.counts.stale} past review date</span>}
        {data.counts.partial !== null && data.counts.partial > 0 && <span>{data.counts.partial} partial drafts</span>}</div>
      {issues.length > 0 && <ul className="berry-learn-warning" role="status">{issues.map((issue, index) => <li key={index}>{issue.message}</li>)}</ul>}
      {selection.kind !== 'lesson' && <LibraryCollection title="Concept library" kind="concept" collection={data.collections.concepts} selection={selection} facets={data.facets} page={changePage}/>}
      {selection.kind !== 'concept' && <LibraryCollection title="Your saved lessons" kind="lesson" collection={data.collections.lessons} selection={selection} facets={data.facets} page={changePage}/>}
    </>}
  </div>;
}

function LibraryCollection({ title, kind, collection, selection, facets, page }: {
  title: string; kind: LearningKind; collection: LearningCollection; selection: LearningSelection;
  facets: LearningCatalog['facets']; page: (kind: LearningKind, offset: number) => void;
}) {
  const { context } = useInvestigation();
  const card = (item: LearningItem) => <article className="berry-learn-entry" key={item.id}>
    <ItemStatus item={item}/><h3><Link to={investigationHref(item.href, context)}>{item.title}</Link></h3>
    {item.summary && <p>{item.summary}</p>}<p className="berry-learn-entry-meta">{item.source_count} captured source links
      {item.scope.berry_label && <> · {item.scope.berry_label}</>}{item.scope.geography_label && <> · {item.scope.geography_label}</>}
      {item.review_by && <> · Review by {item.review_by}</>}</p>
    <Link to={investigationHref(item.href, context)}>Read lesson →</Link>
  </article>;
  return <section className="berry-learn-collection" aria-label={title}><header><h2>{title}</h2>
    <p>{count(collection.matched_count)} matching · {count(collection.total)} recorded</p></header>
    {collection.status === 'unavailable' ? <p className="berry-learn-message">This library cannot be read right now. Existing records have been left unchanged.</p>
      : collection.status === 'empty' ? <p className="berry-learn-message">{kind === 'lesson' ? 'No saved research lessons are present in this environment. Choose Concepts in the library filter to read the existing educational library.' : 'No concept records are available in this environment.'}</p>
      : !collection.items.length ? <p className="berry-learn-message">No lessons match these library filters.</p>
      : kind === 'concept' ? facets.pillars.map(pillar => {
        const rows = collection.items.filter(item => item.pillar === pillar.id);
        return rows.length ? <section className="berry-learn-pillar" key={pillar.id}><h3>{pillar.label}</h3><div className="berry-learn-entry-grid">{rows.map(card)}</div></section> : null;
      }) : <div className="berry-learn-entry-grid">{collection.items.map(card)}</div>}
    {(selection.offset > 0 || collection.has_more) && <nav className="berry-learn-pagination" aria-label={`${title} pages`}>
      {selection.offset > 0 && <button className="berry-button" type="button" onClick={() => page(kind, Math.max(0, selection.offset - selection.limit))}>Previous {kind === 'concept' ? 'concepts' : 'saved lessons'}</button>}
      {collection.has_more && <button className="berry-button" type="button" onClick={() => page(kind, selection.offset + selection.limit)}>More {kind === 'concept' ? 'concepts' : 'saved lessons'}</button>}
    </nav>}
  </section>;
}

function SelectedLearning({ kind, id }: { kind: LearningKind; id: string }) {
  const { context, revision } = useInvestigation();
  const nativeHref = investigationHref(`/app/learn/${kind}/${id}`, context);
  const query = useQuery({ queryKey: ['learning', kind, id],
    queryFn: ({ signal }) => getLearningContent(kind, id, context, revision, nativeHref, signal), staleTime: 30_000 });
  useSurfaceReady(!!query.data || query.isError);
  const data = query.data?.data;
  const libraryHref = investigationHref('/app/learn', context);
  return <div className="berry-learn-page" data-native-learn="selected"><Link className="berry-learn-back" to={libraryHref}>← Back to Learn</Link>
    {query.isPending && <p className="berry-loading" role="status">Loading the selected lesson…</p>}
    {query.isError && <ReadingError error={query.error} retry={() => void query.refetch()} back={nativeHref}/>}
    {data && <LearningReading data={data} nativeHref={nativeHref}/>}
  </div>;
}

function LearningReading({ data, nativeHref }: { data: LearningContent; nativeHref: string }) {
  const { context } = useInvestigation();
  const item = data.item;
  const expansion = legacyExpansionHref(data.expand_href, nativeHref);
  const teaching = data.teaching;
  const cropNotes = groupCropNotes(data.berry_notes, context.berry);
  return <article><header className="berry-learn-heading"><div><p className="berry-eyebrow">Learn / {item.pillar_label}</p><h1>{item.title}</h1><ItemStatus item={item}/></div>
    {expansion && <a className="berry-button" href={expansion}>{item.kind === 'lesson' ? 'Edit / versions ↗' : 'Research & expand ↗'}</a>}</header>
    <EducationNotice />
    {(item.scope.berry_label || item.scope.geography_label) && <p className="berry-learn-context">Recorded learning context: {[item.scope.berry_label, item.scope.geography_label].filter(Boolean).join(' · ')}. Regional practice is not universal guidance.</p>}
    {item.is_stale && <p className="berry-learn-warning" role="status">This lesson is past its review date. Check current sources before using technical guidance.</p>}
    {item.partial && <p className="berry-learn-warning" role="status">Research stopped before finishing. This is a partial educational draft.</p>}
    {!data.citations.length && <p className="berry-learn-warning" role="status">No source citations were captured. This draft needs source checking.</p>}
    {item.summary && <p className="berry-learn-answer">{item.summary}</p>}
    <nav className="berry-learn-jumps" aria-label="Lesson sections">{data.sections.map(section => <a key={section.id} href={`#learn-${section.id}`}>{section.title}</a>)}
      {teaching && <a href="#learning-visual">Visual explanation</a>}<a href="#learning-sources">Sources</a></nav>
    {teaching && <div id="learning-visual" className="berry-learn-visual">
      {teaching.cane_diagram ? <CaneCalendar sourceLink={teaching.companion ? <Link to={`${investigationHref(teaching.companion.href, context)}#learning-sources`}>See companion sources</Link> : undefined}/>
        : teaching.diagram && <TeachingDiagram diagram={teaching.diagram} slug={item.slug}/>}
      {teaching.note && <p className="berry-learn-applicability">{teaching.note}</p>}
      {teaching.companion && <p><Link to={investigationHref(teaching.companion.href, context)}>Read the companion concept: {teaching.companion.title} →</Link></p>}
    </div>}
    <div className="berry-learn-reading-grid"><div>
      {item.kind === 'lesson' ? data.content_markdown?.trim() ? <LessonMarkdown text={data.content_markdown} citations={data.citations} title={item.title}/>
        : <p className="berry-learn-message">This saved lesson has no current text. Its original research and earlier versions remain in the existing lesson tools.</p>
        : <ConceptSections sections={data.sections}/>}
      {data.clarification && <details className="berry-learn-original"><summary>Retained original wording</summary><p>The existing presentation clarifies this concept; the original record is retained.</p>
        <p>{data.clarification.retained_original.summary}</p><p>{data.clarification.retained_original.what_is_it}</p></details>}
    </div><aside className="berry-learn-companion" aria-label="Crop notes and teaching resources">
      {teaching?.figure && <LearningFigure figure={teaching.figure}/>}
      {data.berry_notes.length > 0 && <section aria-label="Crop notes"><h2>{cropNotes.isGlobal ? 'By crop' : `In ${cropNotes.berryLabel} context`}</h2>
        {cropNotes.inContext.map((note, index) => <article key={`${note.berry_id}-${index}`}><h3>{note.berry_label}</h3><p>{note.note}</p></article>)}
        {!cropNotes.isGlobal && !cropNotes.inContext.length && <p className="berry-learn-applicability">No {cropNotes.berryLabel}-specific crop note is recorded.</p>}
        {cropNotes.alsoGlobal.length > 0 && <><h2>Also in other berries</h2>{cropNotes.alsoGlobal.map((note, index) => <article key={`${note.berry_id}-${index}`}><h3>{note.berry_label}</h3><p>{note.note}</p></article>)}</>}
      </section>}
      {data.media.length > 0 && <TeachingResources resources={data.media}/>}
      {data.related.length > 0 && <section><h2>Related concepts</h2><ul>{data.related.map(row => <li key={row.id}><Link to={investigationHref(row.href, context)}>{row.title}</Link></li>)}</ul></section>}
    </aside></div>
    <LearningCitations sources={data.citations}/>
    <p className="berry-learn-applicability">{data.provenance.knowledge_class_note}</p>
    <div className="berry-learn-dates">{item.reviewed_at && <span>Last reviewed {item.reviewed_at}</span>}{item.review_by && <span>Review by {item.review_by}</span>}
      {item.updated_at && <span>Saved {item.updated_at.slice(0, 10)}</span>}{item.revision && <span>Revision {item.revision}</span>}</div>
    {item.needs_review_cadence && !item.review_by && <p className="berry-learn-applicability">This knowledge class needs current, contextual sources. No review-by date is recorded.</p>}
    {expansion && <p className="berry-learn-tools-note">Research, editing and version history use the existing governed workspace. <a href={expansion}>Open lesson tools ↗</a></p>}
  </article>;
}
