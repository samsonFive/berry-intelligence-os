import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { getInvestigation } from '../../api/client';
import { clearPrivateSession, SESSION_TRANSITION_EVENT } from '../../app/PrivateQueryProvider';
import { useSurfaceReady } from '../../app/SurfaceScroll';
import { legacyHref } from '../../app/legacy';
import { Badge, Button, EmptyState, SourceLink } from '../../components/ui';
import { EMPTY_CONTEXT, hasBlockingIssues, investigationHref, splitIds } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { downloadOutput, getSaved, listSaved, OUTPUT_SECTIONS, previewOutput, saveInvestigation, WorkspaceRequestError } from './api';
import type { OutputPreview, OutputSection, OutputSelection, SavedInvestigation } from './api';
import { BERRY_LABELS, captureSave, capturedOutput, GEOGRAPHY_LABELS, LENS_LABELS, nativeSavedHref, outputKey, previewScopeLabel, responseStillCurrent } from './state';
import './workspaces.css';

interface Country { id: string; name?: string; label?: string }
interface ReviewedOutput { preview: OutputPreview; selection: OutputSelection; key: string; revision: number }
const SAVED_KEY = ['saved-investigations'] as const;
const errorText = (error: unknown) => error instanceof Error ? error.message : 'This action could not be completed. Try again.';
function displayDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.valueOf()) ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date) : 'Date unavailable';
}
function geographyLabels(ids: string[], countries: Country[]): string {
  if (!ids.length) return 'All geographies';
  return ids.map(id => { const country = countries.find(row => row.id === id); return country?.name ?? country?.label ?? 'Unavailable selected geography'; }).join(' · ');
}
function SavedDestination({ row, pathname }: { row: SavedInvestigation; pathname: string }) {
  const { context } = useInvestigation();
  if (!row.is_investigation) return <a href={legacyHref(row.href, pathname, context)}>Open existing saved view →</a>;
  try { return <Link to={nativeSavedHref(row)}>Reopen investigation →</Link>; }
  catch { return <span className="berry-scope-note">This saved destination needs review in its existing workspace.</span>; }
}

/** Live selectors and explicit current-data output; authored documents keep their existing editors. */
export function WorkspacesPage() {
  const { context, revision, getRevision, dispatch, issues } = useInvestigation();
  const { pathname } = useLocation();
  const navigate = useNavigate(), queryClient = useQueryClient();
  const [sessionEnded, setSessionEnded] = useState(false);
  const saved = useQuery({ queryKey: SAVED_KEY, queryFn: ({ signal }) => listSaved(signal), enabled: !sessionEnded });
  const options = useQuery({ queryKey: ['investigation-options'], enabled: !sessionEnded,
    queryFn: ({ signal }) => getInvestigation<{ countries: Country[] }>('/options', EMPTY_CONTEXT, 0, signal), staleTime: 5 * 60_000 });
  const countries = options.data?.data.countries ?? [];
  const rows = saved.data ?? [], investigations = rows.filter(row => row.is_investigation);
  const [mode, setMode] = useState<'new' | 'update'>('new');
  const [targetId, setTargetId] = useState(context.saved_view_id);
  const [name, setName] = useState('');
  const target = investigations.find(row => row.id === targetId);
  const [saving, setSaving] = useState(false), [reloading, setReloading] = useState(false);
  const [saveError, setSaveError] = useState(''), [saveMessage, setSaveMessage] = useState('');
  const [conflict, setConflict] = useState<SavedInvestigation | null>(null);
  const [savedReceipt, setSavedReceipt] = useState<SavedInvestigation | null>(null);
  const [sectionIds, setSectionIds] = useState<OutputSection[]>(OUTPUT_SECTIONS.map(([id]) => id));
  const [includeDemo, setIncludeDemo] = useState(false), [previewing, setPreviewing] = useState(false), [downloading, setDownloading] = useState(false);
  const [outputError, setOutputError] = useState(''), [outputMessage, setOutputMessage] = useState('');
  const [reviewed, setReviewed] = useState<ReviewedOutput | null>(null);
  const saveGeneration = useRef(0), previewGeneration = useRef(0), downloadGeneration = useRef(0);
  const alive = useRef(true), objectUrls = useRef(new Set<string>());
  const selection = useMemo(() => capturedOutput(context, sectionIds, includeDemo), [context, sectionIds, includeDemo]);
  const selectionKey = outputKey(selection), latestKey = useRef(selectionKey);
  latestKey.current = selectionKey;
  const blocked = hasBlockingIssues(issues);
  const currentReview = reviewed && responseStillCurrent(reviewed.revision, revision, reviewed.key, selectionKey) ? reviewed : null;
  const outputScope = currentReview?.preview.scope as (OutputPreview['scope'] & { actor_roles?: string[]; relationship_types?: string[]; standing_geographic_basis?: string }) | undefined;
  useSurfaceReady(sessionEnded || !saved.isPending && !options.isPending);

  useEffect(() => {
    alive.current = true;
    const clear = () => {
      ++saveGeneration.current; ++previewGeneration.current; ++downloadGeneration.current;
      setReviewed(null); setSavedReceipt(null); setName(''); setConflict(null); setSessionEnded(true);
      for (const url of objectUrls.current) URL.revokeObjectURL(url); objectUrls.current.clear();
    };
    window.addEventListener(SESSION_TRANSITION_EVENT, clear);
    return () => {
      alive.current = false; ++saveGeneration.current; ++previewGeneration.current; ++downloadGeneration.current;
      window.removeEventListener(SESSION_TRANSITION_EVENT, clear);
      for (const url of objectUrls.current) URL.revokeObjectURL(url); objectUrls.current.clear();
    };
  }, []);
  useEffect(() => { ++previewGeneration.current; setPreviewing(false); setReviewed(null); setOutputError(''); setOutputMessage(''); }, [selectionKey]);
  const handleSession = (error: unknown) => { if (error instanceof WorkspaceRequestError && error.requiresSession) clearPrivateSession(); };
  const rememberRow = async (row: SavedInvestigation, generation: number) => {
    // A list request opened before the save must not replace its newer receipt.
    await queryClient.cancelQueries({ queryKey: SAVED_KEY });
    if (!alive.current || generation !== saveGeneration.current) return false;
    queryClient.setQueryData<SavedInvestigation[]>(SAVED_KEY, previous => [row, ...(previous ?? []).filter(item => item.id !== row.id)]);
    void queryClient.invalidateQueries({ queryKey: SAVED_KEY }); return true;
  };

  const save = async (event: FormEvent) => {
    event.preventDefault(); if (saving || reloading || sessionEnded) return;
    setSaveError(''); setSaveMessage(''); setSavedReceipt(null);
    let payload: ReturnType<typeof captureSave>;
    try { payload = captureSave(context, name, mode, target); } catch (error) { setSaveError(errorText(error)); return; }
    const openedRevision = getRevision(), generation = ++saveGeneration.current;
    setSaving(true);
    try {
      const row = await saveInvestigation(payload);
      if (!alive.current || generation !== saveGeneration.current) return;
      if (!await rememberRow(row, generation)) return;
      setSavedReceipt(row); setConflict(null);
      if (getRevision() === openedRevision) {
        dispatch({ type: 'replaceContext', context: { ...payload.context, saved_view_id: row.id, saved_revision: String(row.revision) }, origin: 'direct', expectedRevision: openedRevision });
        setTargetId(row.id); setMode('update'); setName(row.name);
        setSaveMessage(`${payload.save_as_new ? 'Saved a new investigation' : 'Updated the saved investigation'} · version ${row.revision}.`);
      } else setSaveMessage('Saved the selection captured when you pressed Save. Your newer investigation remains open.');
    } catch (error) {
      if (!alive.current || generation !== saveGeneration.current) return;
      handleSession(error); setSaveError(errorText(error));
      if (error instanceof WorkspaceRequestError && error.status === 409 && target) setConflict(target);
    } finally { if (alive.current && generation === saveGeneration.current) setSaving(false); }
  };
  const reloadSaved = async () => {
    if (!conflict || reloading || saving) return;
    const openedRevision = getRevision(), generation = ++saveGeneration.current;
    setReloading(true); setSaveError('');
    try {
      const row = await getSaved(conflict.id);
      if (!alive.current || generation !== saveGeneration.current) return;
      if (!await rememberRow(row, generation)) return;
      if (getRevision() === openedRevision) { setConflict(null); void navigate(nativeSavedHref(row)); }
      else { setSavedReceipt(row); setSaveMessage('The latest saved version is ready below. Your newer investigation has been kept.'); }
    } catch (error) { if (alive.current && generation === saveGeneration.current) { handleSession(error); setSaveError(errorText(error)); } }
    finally { if (alive.current && generation === saveGeneration.current) setReloading(false); }
  };
  const makePreview = async () => {
    if (previewing || !sectionIds.length || blocked || sessionEnded) return;
    const capture = { selection: structuredClone(selection), key: selectionKey, revision: getRevision() }, generation = ++previewGeneration.current;
    setPreviewing(true); setReviewed(null); setOutputError(''); setOutputMessage('');
    try {
      const preview = await previewOutput(capture.selection);
      if (!alive.current || generation !== previewGeneration.current) return;
      if (!responseStillCurrent(capture.revision, getRevision(), capture.key, latestKey.current)) { setOutputMessage('The selection changed. Review a fresh preview.'); return; }
      setReviewed({ ...capture, preview });
    } catch (error) { if (alive.current && generation === previewGeneration.current) { handleSession(error); setOutputError(errorText(error)); } }
    finally { if (alive.current && generation === previewGeneration.current) setPreviewing(false); }
  };
  const download = async () => {
    if (!currentReview || downloading || sessionEnded) return;
    const capture = currentReview, generation = ++downloadGeneration.current;
    setDownloading(true); setOutputError(''); setOutputMessage('');
    try {
      const blob = await downloadOutput(capture.selection, capture.preview.content_hash);
      if (!alive.current || generation !== downloadGeneration.current) return;
      if (!responseStillCurrent(capture.revision, getRevision(), capture.key, latestKey.current)) { setOutputMessage('The selection changed. Review a fresh preview before downloading.'); return; }
      const url = URL.createObjectURL(blob); objectUrls.current.add(url);
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `berry-investigation-${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.append(anchor); anchor.click(); anchor.remove();
      setTimeout(() => { URL.revokeObjectURL(url); objectUrls.current.delete(url); }, 1000);
      setOutputMessage('Your reviewed investigation PDF has been downloaded.');
    } catch (error) {
      if (!alive.current || generation !== downloadGeneration.current) return;
      handleSession(error); setOutputError(errorText(error));
      if (error instanceof WorkspaceRequestError && error.status === 409) setReviewed(null);
    } finally { if (alive.current && generation === downloadGeneration.current) setDownloading(false); }
  };
  const chooseMode = (next: 'new' | 'update') => {
    setMode(next); setConflict(null); setSaveError('');
    if (next === 'new') setName('');
    else { const row = investigations.find(item => item.id === targetId); setName(row?.name ?? ''); }
  };
  if (sessionEnded) return <EmptyState title="Sign in to continue"><a href={`/login?next=${encodeURIComponent(investigationHref('/app/workspaces', context))}`}>Open sign in</a></EmptyState>;
  return <div className="berry-workspaces-page">
    <header className="berry-page-heading"><p className="berry-eyebrow">Workspaces</p><h1>Keep an investigation. Share its evidence.</h1><p className="berry-subtitle">Save a live selection, reopen its current records, or review a dated PDF.</p></header>
    <section className="berry-workspace-current" aria-labelledby="current-selection-heading"><div><p className="berry-eyebrow">Current investigation</p><h2 id="current-selection-heading">{BERRY_LABELS[context.berry] ?? 'Selected berry'} · {geographyLabels(splitIds(context.countries), countries)}</h2>
      <p>{LENS_LABELS[context.lens]} · {splitIds(context.cohort_companies).length} company pins · {splitIds(context.cohort_varieties).length} cultivar pins</p></div><Link className="berry-button berry-button--secondary" to={investigationHref('/app/landscape', context)}>Return to Landscape</Link></section>
    <div className="berry-workspaces-columns">
      <section className="berry-workspace-card" aria-labelledby="save-investigation-heading"><h2 id="save-investigation-heading">Save this investigation</h2><p>Retains scope, both comparison cohorts, view, nested Reader section and demo selection. Reopening resolves current records.</p>
        <form onSubmit={save} className="berry-investigation-save">
          <fieldset disabled={saving || reloading}><legend>Save destination</legend>
            <label><input type="radio" name="save-mode" checked={mode === 'new'} onChange={() => chooseMode('new')} />Save as a new investigation</label>
            <label><input type="radio" name="save-mode" checked={mode === 'update'} disabled={!investigations.length} onChange={() => chooseMode('update')} />Update a saved investigation</label>
            {mode === 'update' && <label>Saved investigation to update<select aria-label="Saved investigation to update" value={targetId} onChange={event => { const row = investigations.find(item => item.id === event.target.value); setTargetId(event.target.value); setName(row?.name ?? ''); setConflict(null); setSaveError(''); }}><option value="">Choose an investigation</option>{investigations.map(row => <option key={row.id} value={row.id}>{row.name} · version {row.revision}</option>)}</select></label>}
            <label>Investigation name<input value={name} maxLength={80} onChange={event => setName(event.target.value)} placeholder="Name this investigation" required /></label>
          </fieldset>
          {mode === 'update' && target && <p className="berry-scope-note">Updates “{target.name}” from version {target.revision}. Earlier versions keep their existing history.</p>}
          <Button type="submit" variant="primary" busy={saving} disabled={blocked || reloading || !!conflict || !name.trim() || mode === 'update' && !target}>{mode === 'new' ? 'Save new investigation' : 'Update investigation'}</Button>
        </form>
        {saveError && <p className="berry-workspace-error" role="alert">{saveError}</p>}
        {conflict && <div className="berry-workspace-conflict"><p>Reload the saved version before updating it, or name a new investigation with your current selection.</p><Button busy={reloading} onClick={() => void reloadSaved()}>Reload saved investigation</Button><Button onClick={() => chooseMode('new')}>Save current selection as new</Button></div>}
        {saveMessage && <p role="status">{saveMessage}</p>}{savedReceipt && <p><SavedDestination row={savedReceipt} pathname={pathname} /></p>}
      </section>
      <section className="berry-workspace-card" aria-labelledby="existing-workspaces-heading"><p className="berry-eyebrow">Authored work</p><h2 id="existing-workspaces-heading">Continue writing and review</h2><p>Authored documents, live Brief Packs and generated reports retain their own versions and editing workflows.</p><div className="berry-authored-links">
        {[['/workspaces', 'Open authored Workspaces'], ['/reports', 'Open reports'], ['/brief-packs', 'Open saved Brief Packs']].map(([href, label]) => <a key={href} href={legacyHref(href, pathname, context)}>{label} →</a>)}
      </div><p className="berry-scope-note">Each workspace includes a return to this investigation.</p></section>
    </div>
    <section className="berry-workspace-card berry-saved-investigations" aria-labelledby="saved-investigations-heading"><div className="berry-section-heading"><div><p className="berry-eyebrow">Live selections</p><h2 id="saved-investigations-heading">Saved investigations and views</h2></div><Button variant="ghost" busy={saved.isFetching} onClick={() => void saved.refetch()}>Refresh saved list</Button></div>
      {saved.isPending ? <p role="status" className="berry-loading">Loading saved investigations…</p> : saved.isError ? <EmptyState title="Saved investigations could not be loaded">{errorText(saved.error)}</EmptyState> : !rows.length ? <EmptyState compact title="Save your first investigation">Give the current selection a name above.</EmptyState>
        : <ul className="berry-saved-list">{rows.map(row => <li key={row.id}><div><h3>{row.name}</h3><p>{row.is_investigation ? `${BERRY_LABELS[row.filters.berry] ?? 'Selected berry'} · ${LENS_LABELS[row.filters.lens as keyof typeof LENS_LABELS] ?? 'Saved view'}` : 'Existing saved view'} · version {row.revision} · {displayDate(row.updated_at)}</p></div><Badge tone={row.is_investigation ? 'sage' : 'neutral'}>{row.is_investigation ? 'Live investigation' : 'Existing view'}</Badge><SavedDestination row={row} pathname={pathname} /></li>)}</ul>}
    </section>
    <section className="berry-workspace-card berry-output" aria-labelledby="output-heading"><p className="berry-eyebrow">Dated, cited output</p><h2 id="output-heading">Review the complete PDF contents</h2><p>Choose sections, review their full record and source counts, then download the exact reviewed data basis.</p>
      <fieldset className="berry-output-sections" disabled={previewing || downloading}><legend>Included sections</legend>{OUTPUT_SECTIONS.map(([id, label]) => <label key={id}><input type="checkbox" checked={sectionIds.includes(id)} onChange={event => setSectionIds(previous => event.target.checked ? OUTPUT_SECTIONS.map(([key]) => key).filter(key => key === id || previous.includes(key)) : previous.filter(key => key !== id))} />{label}</label>)}</fieldset>
      <label className="berry-annex-choice"><input type="checkbox" checked={includeDemo} disabled={previewing || downloading} onChange={event => setIncludeDemo(event.target.checked)} /><span>Include synthetic sensory demo annex<small>Fictitious specimens · current demo selection · overall liking on a 1–9 scale.</small></span></label>
      <Button variant="secondary" busy={previewing} disabled={blocked || !sectionIds.length || downloading} onClick={() => void makePreview()}>Preview complete output</Button>
      {!sectionIds.length && <p role="status">Choose at least one section.</p>}{outputError && <p className="berry-workspace-error" role="alert">{outputError}</p>}{outputMessage && <p role="status">{outputMessage}</p>}
      {reviewed && !currentReview && <p role="status">The investigation changed. Review a fresh preview before downloading.</p>}
      {currentReview && <div className="berry-output-preview" aria-label="Reviewed PDF contents"><h3>Preview of the full output</h3><p className="berry-output-scope"><strong>{previewScopeLabel(currentReview.preview.scope)}</strong><br />{GEOGRAPHY_LABELS[currentReview.preview.scope.geographic_basis] ?? 'Recorded geographic basis'} · {currentReview.preview.scope.comparison_companies.length} company comparison subjects · {currentReview.preview.scope.comparison_varieties.length} cultivar comparison subjects</p>
        {!!currentReview.preview.scope.comparison_companies.length && <p><strong>Company pins:</strong> {currentReview.preview.scope.comparison_companies.map(label => label.startsWith('company-') ? 'Unavailable selected company' : label).join(' · ')}</p>}
        {!!currentReview.preview.scope.comparison_varieties.length && <p><strong>Cultivar pins:</strong> {currentReview.preview.scope.comparison_varieties.map(label => label.startsWith('variety-') ? 'Unavailable selected cultivar' : label).join(' · ')}</p>}
        {currentReview.preview.section_ids.includes('comparison') && <p>The selected comparison uses {currentReview.selection.context.comparison_kind === 'company' ? 'company' : 'cultivar'} profiles.</p>}
        <p>Standing geographic basis: {GEOGRAPHY_LABELS[outputScope?.standing_geographic_basis ?? 'company_connections'] ?? 'Recorded geographic basis'}. Actor roles: {outputScope?.actor_roles?.length ? outputScope.actor_roles.map(label => label.replaceAll('_', ' ')).join(' · ') : 'All authored roles'}. Relationships: {outputScope?.relationship_types?.length ? outputScope.relationship_types.map(label => label.replaceAll('_', ' ')).join(' · ') : 'All recorded relationship types'}.</p>
        <p>Developments published {currentReview.preview.scope.news_from || 'from the earliest retained date'} {currentReview.preview.scope.news_to ? `through ${currentReview.preview.scope.news_to}` : 'through the latest retained date'}. Standing portfolio records keep their own recorded scope.</p>
        <p>{currentReview.preview.date_note}</p><table className="berry-table"><caption>Complete selected content, including rows beyond the current viewport</caption><thead><tr><th>Section</th><th>Full rows</th><th>Cited sources</th></tr></thead><tbody>{currentReview.preview.sections.map(section => <tr key={section.id}><th scope="row">{section.title}<small>{section.basis}</small></th><td>{section.row_count}</td><td>{section.source_ids.length}</td></tr>)}</tbody></table>
        <p><strong>{currentReview.preview.sources.length} sources in the complete appendix.</strong> Generated-at time and applied scope appear in the PDF.</p>
        {currentReview.preview.issues.length > 0 && <div className="berry-issue">{currentReview.preview.issues.map((issue, index) => <p key={index}>{issue.message}</p>)}</div>}
        {currentReview.preview.synthetic_annex && <aside className="berry-synthetic-label"><strong>Synthetic demonstration annex · {currentReview.preview.synthetic_annex.specimen_count} fictitious specimens</strong><p>{currentReview.preview.synthetic_annex.specimen_labels.join(' · ')}</p><p>Illustrative overall liking, 1–9. These values describe fictitious demo specimens.</p></aside>}
        <details className="berry-output-sources"><summary>Review the source appendix ({currentReview.preview.sources.length})</summary><ol>{currentReview.preview.sources.map(source => <li key={source.id}>{source.url ? <SourceLink external href={source.url}>{source.title || 'Untitled retained source'}</SourceLink> : <span>{source.title || 'Untitled retained source'}</span>}{source.published && <small>Published {source.published}</small>}{source.captured && <small>Captured {source.captured}</small>}</li>)}</ol></details>
        <Button variant="primary" busy={downloading} onClick={() => void download()}>Download reviewed PDF</Button>
      </div>}
    </section>
  </div>;
}
export default WorkspacesPage;
