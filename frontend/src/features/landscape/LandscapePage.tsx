import { useCallback, useLayoutEffect, useMemo, useState } from 'react';
import { useSurfaceReady } from '../../app/SurfaceScroll';
import { Badge, Button, EmptyState, EntityButton, Preview } from '../../components/ui';
import { hasBlockingIssues, investigationHref, serializeInvestigation, splitIds, type EntityType, type InvestigationContext, type Lens } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { BerryDataGrid } from '../grids/BerryDataGrid';
import { SensoryDemo } from '../demo/SensoryDemo';
import { type ComparisonModel, type DevelopmentsModel, type LandscapeEdge, type LandscapeModel, type LandscapeNode, type Portrait, type SourceMetadata } from './models';
import { Link } from 'react-router-dom';
import { Citation } from './Citation';
import { DevelopmentCard } from './DevelopmentCard';
import { useReadModel } from './useReadModel';
import { developmentsContext } from './developments-context';
import './landscape.css';

const LENSES: Array<{ id: Lens; label: string }> = [
  { id: 'connections', label: 'Connections' }, { id: 'portfolio', label: 'Portfolio' },
  { id: 'geography', label: 'Geography' }, { id: 'comparison', label: 'Comparison' }, { id: 'sensory', label: 'Sensory demo' },
];

/** Module keys describe domain inputs, not unrelated panel or router revisions. */
function standingContext(context: InvestigationContext): InvestigationContext {
  return { ...context, focus: '', cohort_companies: '', cohort_varieties: '', lens: 'connections', comparison_kind: 'company',
    detail_path: '', demo_specimens: '', news_from: '', news_to: '', q: '', q_scope: 'scope', saved_view_id: '', saved_revision: '' };
}

function Unknown({ label = 'Unknown: no recorded observation' }: { label?: string }) {
  return <span className="berry-unknown" aria-label={label}>—</span>;
}

function NodeControl({ node }: { node: LandscapeNode | undefined }) {
  const { context, dispatch } = useInvestigation();
  if (!node) return <Unknown label="Identity unavailable" />;
  if (node.type === 'company' || node.type === 'variety') return <EntityButton compact name={node.label} selected={context.focus === node.id}
    onClick={() => dispatch({ type: 'focusEntity', entity: { type: node.type as EntityType, id: node.id }, origin: 'direct' })} />;
  if (node.type === 'geography') return <button className="berry-text-button" type="button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'geography', id: node.id }, origin: 'direct' })}>{node.label}</button>;
  return <span>{node.label}<span className="berry-program-label">Breeding program</span></span>;
}

function EdgeSupport({ edge, sources }: { edge: LandscapeEdge; sources: Map<string, SourceMetadata> }) {
  return <><p>{edge.notes}</p><p className="berry-muted">{edge.status_label} · {edge.review}</p><p className="berry-muted">{edge.scope_kind}</p>
    <div className="berry-inline-citations">{edge.evidence_ids.map(id => <Citation key={id} id={id} source={sources.get(id)} parent={{ type: 'relationship', id: edge.id }} />)}</div></>;
}

function Relationship({ edge, model, sources }: { edge: LandscapeEdge; model: LandscapeModel; sources: Map<string, SourceMetadata> }) {
  const { dispatch } = useInvestigation();
  return <div className="berry-relationship-edge">
    <div>
      <span className="berry-relationship-role"><Preview label="Recorded relationship" content={<EdgeSupport edge={edge} sources={sources} />}
        onOpenDetail={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: edge.id }, origin: 'direct' })}>{edge.role}</Preview></span>
      <div className="berry-explicit-path"><NodeControl node={model.nodes[edge.subject_id]} /><span aria-label="connects to">→</span><NodeControl node={model.nodes[edge.object_id]} /></div>
      {edge.status !== 'active' && <Badge tone={edge.status === 'disputed' ? 'warning' : 'neutral'}>{edge.status_label}</Badge>}
      {edge.caveat && <p className="berry-material-caveat">{edge.caveat}</p>}
    </div>
  </div>;
}

function CompanyBand({ portrait, model, sources }: { portrait: Portrait; model: LandscapeModel; sources: Map<string, SourceMetadata> }) {
  const { context, dispatch } = useInvestigation();
  const pinned = splitIds(context.cohort_companies).includes(portrait.actor.id);
  const edgeOrder = (edge: LandscapeEdge) => {
    const subject = model.nodes[edge.subject_id]; const object = model.nodes[edge.object_id];
    if (edge.subject_id === portrait.actor.id && object?.type === 'breeding_program') return 0;
    if (subject?.type === 'breeding_program' && object?.type === 'variety') return 1;
    if (edge.subject_id === portrait.actor.id && object?.type === 'variety') return 2;
    if (subject?.type === 'variety' || object?.type === 'variety') return 3;
    return 4;
  };
  const edges = [...new Map([...portrait.edges, ...portrait.portfolio_edges].filter(edge => !edge.company_geography && !edge.genetic_geography).map(edge => [edge.id, edge])).values()]
    // Within the same recorded path type, show unqualified links first. Limited
    // links keep their material caveat and remain available in the complete set.
    .sort((a, b) => edgeOrder(a) - edgeOrder(b) || Number(Boolean(a.caveat)) - Number(Boolean(b.caveat))
      || a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
  const sourceNames = model.sources.filter(source => portrait.actor.evidence_ids.includes(source.id))
    .flatMap(source => (source.varieties ?? []).filter(variety => !portrait.varieties.some(node => node.id === variety.id || node.label === variety.name))
      .map(variety => ({ source, name: variety.name })));
  const [expanded, setExpanded] = useState(false);
  const visibleEdges = expanded ? edges : edges.slice(0, 2);
  return <article className="berry-relationship-row" data-selected={context.focus === portrait.actor.id ? 'true' : undefined}>
    <div className="berry-relationship-actor">
      <EntityButton name={portrait.actor.label} kind="Company" selected={context.focus === portrait.actor.id}
        onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'company', id: portrait.actor.id }, origin: 'direct' })} />
      {portrait.actor.identity_note && <Badge tone="warning">{portrait.actor.identity_note}</Badge>}
      <Button size="small" variant="ghost" aria-pressed={pinned} onClick={() => dispatch({ type: 'togglePin', entity: { type: 'company', id: portrait.actor.id }, origin: 'direct' })}>{pinned ? 'Unpin comparison' : 'Pin for comparison'}</Button>
    </div>
    <div className="berry-relationship-path">
      {visibleEdges.map(edge => <Relationship key={edge.id} edge={edge} model={model} sources={sources} />)}
      {!edges.length && <p className="berry-scope-note">Recorded geographic activity; no explicit program or cultivar edge in this scope.</p>}
      {edges.length > 2 && <Button size="small" variant="ghost" onClick={() => setExpanded(value => !value)}>{expanded ? 'Show fewer connections' : `Show all ${edges.length} connections`}</Button>}
      {sourceNames.length > 0 && <details className="berry-source-named"><summary>Source-named cultivars · role unassigned</summary>
        {sourceNames.map((item, index) => <span key={`${item.source.id}-${index}`}>{item.name} <Citation id={item.source.id} source={item.source} /></span>)}
      </details>}
    </div>
    <div className="berry-relationship-activity">{portrait.markets.filter(market => market.edges.length).map(market => <div className="berry-activity-record" key={market.country}>
      <strong>{market.country}</strong>{market.edges.map(edge => <div key={edge.id}>
        <Preview label="Geographic activity basis" onOpenDetail={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: edge.id }, origin: 'direct' })}
          content={<EdgeSupport edge={edge} sources={sources} />}>{edge.location_label}</Preview>
        {edge.caveat && <p className="berry-material-caveat">{edge.caveat}</p>}
        {edge.status !== 'active' && <Badge tone="warning">{edge.status_label}</Badge>}
      </div>)}</div>)}
      {!portrait.markets.some(market => market.edges.length) && <p className="berry-scope-note">Connected genetics · company location not established by these links.</p>}
    </div>
  </article>;
}

function Connections({ model }: { model: LandscapeModel }) {
  const sources = useMemo(() => new Map(model.sources.map(source => [source.id, source])), [model.sources]);
  const [allActors, setAllActors] = useState(false);
  const portraits = useMemo(() => {
    const rows = new Map<string, Portrait>();
    for (const row of [...model.market_rows, ...model.portfolios]) if (!rows.has(row.actor.id)) rows.set(row.actor.id, row);
    // Presentation order uses populated record types, never a performance score.
    const genetics = (row: Portrait) => [...row.edges, ...row.portfolio_edges].some(edge =>
      [model.nodes[edge.subject_id]?.type, model.nodes[edge.object_id]?.type].some(type => type === 'variety' || type === 'breeding_program'));
    const typedActivity = (row: Portrait) => row.markets.some(market => market.edges.some(edge => Boolean(edge.location_label && edge.location_label !== 'Location reported · check source')));
    return [...rows.values()].sort((a, b) => Number(genetics(b) && typedActivity(b)) - Number(genetics(a) && typedActivity(a))
      || Number(genetics(b)) - Number(genetics(a)) || Number(typedActivity(b)) - Number(typedActivity(a)) || a.actor.label.localeCompare(b.actor.label));
  }, [model]);
  const visible = allActors ? portraits : portraits.slice(0, 2);
  if (!portraits.length) return <EmptyState title="No role-bearing connections match this scope">Change the applied scope to inspect other recorded relationships. Missing captured relationships do not establish an absence of activity.</EmptyState>;
  return <><div className="berry-section-heading"><div><h2>Companies, genetics and recorded activity</h2><p>Directed source-backed connections. Geographic activity retains its recorded meaning.</p></div></div>
    <div className="berry-relationship-header" aria-hidden="true"><span>Actor</span><span>Recorded genetics connections</span><span>Geographic activity</span></div>
    <div className="berry-relationship-bands">{visible.map(portrait => <CompanyBand key={portrait.actor.id} portrait={portrait} model={model} sources={sources} />)}</div>
    {portraits.length > 2 && <Button variant="ghost" onClick={() => setAllActors(value => !value)}>{allActors ? 'Show the initial connected actors' : `Show all ${portraits.length} actors in this scope`}</Button>}
  </>;
}

function Geography({ model }: { model: LandscapeModel }) {
  const { dispatch } = useInvestigation();
  const sources = new Map(model.sources.map(source => [source.id, source]));
  const edges = model.edges.filter(edge => edge.company_geography || edge.genetic_geography);
  return <><div className="berry-section-heading"><div><h2>Recorded geographic connections</h2><p>Company location, validation, planned entry and genetic-location relationships retain their own meaning.</p></div></div>
    {edges.length ? <div className="berry-table-wrap"><table className="berry-table"><thead><tr><th>Recorded subject</th><th>Place</th><th>Activity and basis</th><th>Supporting source</th></tr></thead><tbody>{edges.map(edge => {
      const subject = model.nodes[edge.subject_id]; const object = model.nodes[edge.object_id];
      const geography = subject?.type === 'geography' ? subject : object; const actor = subject?.type === 'geography' ? object : subject;
      return <tr key={edge.id}><th scope="row"><NodeControl node={actor} /></th><td><NodeControl node={geography} /></td><td>
        <button type="button" className="berry-text-button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: edge.id }, origin: 'direct' })}>{edge.location_label}</button>
        <p className="berry-material-caveat">{edge.scope_kind}</p>{edge.caveat && <p className="berry-material-caveat">{edge.caveat}</p>}
        {edge.status !== 'active' && <Badge tone="warning">{edge.status_label}</Badge>}</td><td>{edge.evidence_ids.map(id => <div key={id}><Citation id={id} source={sources.get(id)} /></div>)}</td></tr>;
    })}</tbody></table></div> : <EmptyState title="No geographic relationship is recorded in this scope">This does not establish an absence of activity or cultivar presence.</EmptyState>}
  </>;
}

function Comparison({ model, onReady }: { model: LandscapeModel; onReady: (ready: boolean) => void }) {
  const { context, dispatch, issues } = useInvestigation();
  const comparisonContext: InvestigationContext = { ...standingContext(context), lens: 'comparison', comparison_kind: context.comparison_kind,
    cohort_companies: context.cohort_companies, cohort_varieties: context.cohort_varieties };
  const selected = splitIds(context.comparison_kind === 'company' ? context.cohort_companies : context.cohort_varieties);
  const query = useReadModel<ComparisonModel>('/comparison', comparisonContext, selected.length > 0 && !hasBlockingIssues(issues));
  useLayoutEffect(() => onReady(selected.length === 0 || !query.isPending), [onReady, selected.length, query.isPending]);
  const result = query.data?.data;
  const openEntity = (id: string, type: EntityType) => dispatch({ type: 'focusEntity', entity: { id, type }, origin: 'direct' });
  return <><div className="berry-section-heading"><div><h2>Compare the selected {context.comparison_kind === 'company' ? 'companies' : 'cultivars'}</h2><p>Full selected profiles · applied berry, countries and publication dates provide context and do not trim these portfolio records.</p></div>
    <div className="berry-segmented" aria-label="Comparison subject type">{(['company', 'variety'] as const).map(kind => <button key={kind} type="button" aria-pressed={context.comparison_kind === kind} onClick={() => dispatch({ type: 'setLens', lens: 'comparison', comparison_kind: kind, origin: 'direct' })}>{kind === 'company' ? 'Companies' : 'Cultivars'}</button>)}</div></div>
    {selected.length === 0 ? <EmptyState title="Pin subjects to compare">Use the separate company and cultivar pins in Connections or Portfolio. Each cohort remains available when you switch the comparison type.</EmptyState>
      : query.isPending ? <p className="berry-loading" role="status">Loading the selected profiles…</p>
        : query.isError ? <EmptyState title="Comparison unavailable">{query.error instanceof Error ? query.error.message : 'The selected profiles could not be loaded.'}</EmptyState>
          : result && <>
            {(result.invalid_ids.length > 0 || result.overflow_ids.length > 0) && <div className="berry-issue">Unavailable: {result.invalid_ids.join(', ') || 'None'}. Beyond the supported comparison: {result.overflow_ids.join(', ') || 'None'}. All pins remain visible for explicit removal.</div>}
            {result.comparison_kind === 'company' ? result.companies.length > 0 && <div className="berry-table-wrap"><table className="berry-table berry-comparison-table"><thead><tr><th>Recorded dimension</th>{result.companies.map(company => <th key={company.id}><EntityButton compact name={company.name} onClick={() => openEntity(company.id, 'company')} /></th>)}</tr></thead><tbody>
              <tr><th scope="row">Declared berry portfolio</th>{result.companies.map(company => <td key={company.id}>{company.berries.join(' · ') || <Unknown />}</td>)}</tr>
              {result.role_matrix.map(role => <tr key={role.bucket}><th scope="row">{role.label}</th>{result.companies.map(company => <td key={company.id}>{company.roles[role.bucket]?.length ? <ul className="berry-comparison-list">{company.roles[role.bucket].map(party => <li key={party.id}><button type="button" className="berry-text-button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'variety', id: party.id }, origin: 'direct' })}>{party.name || model.nodes[party.id]?.label || party.id}</button></li>)}</ul> : <Unknown label="Unknown: no recorded cultivar relationship in this role" />}</td>)}</tr>)}
              <tr><th scope="row">Recorded geographic context</th>{result.companies.map(company => <td key={company.id}>{company.geographies.length ? company.geographies.map(geo => <div key={geo.id}><button className="berry-text-button" type="button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'geography', id: geo.id }, origin: 'direct' })}>{geo.name}</button></div>) : <Unknown />}<p className="berry-material-caveat">Profile geography includes distinct company/observation bases; inspect before inferring growing.</p></td>)}</tr>
              <tr><th scope="row">Published rights records</th>{result.companies.map(company => <td key={company.id}>{company.rights_published.length ? company.rights_published.map(row => <div key={row.id}><Citation id={row.id} />{row.kind && <span className="berry-material-caveat"> {row.kind}</span>}</div>) : <Unknown />}</td>)}</tr>
            </tbody></table></div>
              : result.comparison_kind === 'variety' && result.varieties.length > 0 && <div className="berry-table-wrap"><table className="berry-table berry-comparison-table"><thead><tr><th>Recorded observation</th>{result.varieties.map(variety => <th key={variety.id}><EntityButton compact name={model.nodes[variety.id]?.label ?? variety.identity?.display_name ?? variety.identity?.name ?? variety.id} onClick={() => openEntity(variety.id, 'variety')} /></th>)}</tr></thead><tbody>
                {result.dimensions.map(dimension => <tr key={dimension.name}><th scope="row">{dimension.name}</th>{result.varieties.map(variety => {
                  const cell = dimension.cells.find(item => item.variety_id === variety.id);
                  return <td key={variety.id}>{cell?.has_data ? cell.rows.map((row, index) => <div key={`${row.id}-${index}`} className="berry-observation"><p>{row.statement}</p>{row.fact_status && <Badge>{row.fact_status}</Badge>}{row.evidence_id && <Citation id={row.evidence_id} />}{row.does_not_prove?.length ? <p className="berry-material-caveat">{row.does_not_prove.join(' · ')}</p> : null}</div>) : <Unknown />}</td>;
                })}</tr>)}
                <tr><th scope="row">Observed commercial markets</th>{result.varieties.map(variety => <td key={variety.id}>{variety.countries_observed.map(geo => geo.name).join(' · ') || <Unknown />}<p className="berry-material-caveat">Observed market does not establish growing origin.</p></td>)}</tr>
              </tbody></table>{result.dimensions.length === 0 && <p className="berry-scope-note berry-comparison-footnote">No comparable sourced trait dimensions are recorded for these selected cultivars. Missing observations are unknown.</p>}</div>}
          </>}
  </>;
}

function Developments({ model, onReady }: { model: LandscapeModel; onReady: (ready: boolean) => void }) {
  const { context, issues } = useInvestigation();
  const subjectContext = useMemo(() => developmentsContext(context, model.nodes), [context, model.nodes]);
  const query = useReadModel<DevelopmentsModel>('/developments', subjectContext, !hasBlockingIssues(issues));
  useLayoutEffect(() => onReady(!query.isPending), [onReady, query.isPending]);
  const developments = query.data?.data;
  return <section className="berry-developments berry-news-rail" aria-labelledby="developments-heading">
    <div className="berry-section-heading"><div><span className="berry-eyebrow">Retained developments</span><h2 id="developments-heading">{developments?.heading ?? 'Relevant developments'}</h2><p>Source geography · publication dates</p></div>
      {developments && <Link className="berry-button berry-button--ghost berry-button--small" to={investigationHref('/app/briefing', context)}>Open scoped Briefing →</Link>}</div>
    {query.isPending ? <p role="status" className="berry-loading">Loading developments for the current subject…</p>
      : query.isError ? <EmptyState compact title="Developments could not be loaded">{query.error instanceof Error ? query.error.message : 'Try reopening this view.'}</EmptyState>
        : developments && developments.cards.length ? <div className="berry-news-grid">{developments.cards.slice(0, 3).map(card => <DevelopmentCard key={card.id} card={card} />)}</div>
          : developments && <EmptyState compact title="No retained news matches this subject and scope" action={<Link className="berry-button berry-button--secondary" to={investigationHref('/app/briefing', context)}>Open scoped Briefing</Link>}>Missing captured news does not establish an absence of developments. The applied scope has not been broadened.</EmptyState>}
    {developments?.briefing_scope_note && <p className="berry-scope-note berry-developments-note">{developments.briefing_scope_note}</p>}
  </section>;
}

function CohortTray({ model }: { model: LandscapeModel }) {
  const { context, dispatch } = useInvestigation();
  return <div className="berry-cohort-trays">{(['company', 'variety'] as const).map(kind => {
    const ids = splitIds(kind === 'company' ? context.cohort_companies : context.cohort_varieties);
    if (!ids.length) return null;
    return <div className="berry-comparison-tray" key={kind}><span>{kind === 'company' ? 'Company pins' : 'Cultivar pins'}</span>{ids.map(id => <span className="berry-pin" data-outside-scope={!model.nodes[id] || undefined} key={id}>
      <button className="berry-pin-name" type="button" onClick={() => dispatch({ type: 'openDetail', detail: { type: kind, id }, origin: 'direct' })}>{model.nodes[id]?.label ?? id}</button>
      {!model.nodes[id] && <span>Outside scope / unavailable</span>}<button type="button" aria-label={`Remove ${model.nodes[id]?.label ?? id} from ${kind} comparison`} onClick={() => dispatch({ type: 'togglePin', entity: { type: kind, id }, origin: 'direct' })}>×</button>
    </span>)}<Button size="small" variant="ghost" onClick={() => dispatch({ type: 'setLens', lens: 'comparison', comparison_kind: kind, origin: 'direct' })}>Compare {kind === 'company' ? 'companies' : 'cultivars'}</Button></div>;
  })}</div>;
}

function SubjectSelector({ model }: { model: LandscapeModel }) {
  const { dispatch } = useInvestigation();
  const [query, setQuery] = useState('');
  const matches = Object.values(model.nodes).filter(node => ['company', 'variety'].includes(node.type) && node.label.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  return <details className="berry-subject-selector"><summary>Find within this investigation</summary><label className="berry-field-label">Search the loaded scope<input className="berry-input" type="search" value={query} onChange={event => setQuery(event.target.value)} /></label>
    <div className="berry-subject-results">{matches.slice(0, 30).map(node => <div key={node.id}><EntityButton compact name={node.label} onClick={() => dispatch({ type: 'focusEntity', entity: { type: node.type as EntityType, id: node.id }, origin: 'direct' })} /><span className="berry-entity-kind">{node.type}</span><Button size="small" variant="ghost" onClick={() => dispatch({ type: 'togglePin', entity: { type: node.type as EntityType, id: node.id }, origin: 'direct' })}>Toggle pin</Button></div>)}</div>
    <p className="berry-scope-note">{matches.length > 30 ? `Showing 30 of ${matches.length} matches. Refine the search. ` : `${matches.length} loaded matches. `}This searches the current investigation. <a href="/search">Open catalog search</a> for identities beyond scope.</p>
  </details>;
}

export function LandscapePage() {
  const { context, dispatch, issues } = useInvestigation();
  const baseContext = useMemo(() => standingContext(context), [context]);
  const blocked = hasBlockingIssues(issues);
  const query = useReadModel<LandscapeModel>('/landscape', baseContext, !blocked);
  const model = query.data?.data;
  const readinessKey = serializeInvestigation({ ...context, detail_path: '', saved_view_id: '', saved_revision: '' });
  const [readyParts, setReadyParts] = useState({ key: '', field: false, rail: false });
  const fieldReady = useCallback((ready: boolean) => setReadyParts(previous => previous.key === readinessKey && previous.field === ready ? previous
    : { key: readinessKey, field: ready, rail: previous.key === readinessKey ? previous.rail : false }), [readinessKey]);
  const railReady = useCallback((ready: boolean) => setReadyParts(previous => previous.key === readinessKey && previous.rail === ready ? previous
    : { key: readinessKey, field: previous.key === readinessKey ? previous.field : false, rail: ready }), [readinessKey]);
  const asynchronousField = context.lens === 'comparison' || context.lens === 'sensory';
  useSurfaceReady(blocked || query.isError || Boolean(model && readyParts.key === readinessKey && readyParts.rail && (!asynchronousField || readyParts.field)));
  const countries = splitIds(context.countries).map(id => model?.options.countries.find(option => option.id === id)?.label ?? id.replace(/^geography-/, '').replaceAll('-', ' '));
  const berry = context.berry === 'all' ? 'All berries' : context.berry.replace(/^berry-/, '').replace(/^./, character => character.toUpperCase());
  return <div className="berry-landscape-page">
    <div className="berry-page-heading"><div><p className="berry-eyebrow">Landscape investigation</p><h1>{context.berry === 'all' ? 'Berry landscape' : `${berry} landscape`}</h1><p className="berry-subtitle">{countries.length ? countries.join(' / ') : 'All geographies'} · recorded company and genetics connections</p></div></div>
    {blocked ? <EmptyState title="Resolve the investigation selectors">Some URL or scope values are unsupported. Correct the selectors before loading; the application has not broadened the scope.</EmptyState>
      : query.isPending ? <p className="berry-loading" role="status">Loading the applied landscape…</p>
        : query.isError ? <EmptyState title="This landscape could not be loaded" action={<Button onClick={() => { void query.refetch(); }}>Try again</Button>}>{query.error instanceof Error ? query.error.message : 'The read service is unavailable.'}</EmptyState>
          : model && <>
            {!!query.data?.issues.length && <div className="berry-issue">{query.data.issues.map((issue, index) => <p key={index}>{issue.message}</p>)}</div>}
            <section className="berry-readout" aria-labelledby="scope-readout-heading"><h2 className="berry-readout-title" id="scope-readout-heading">What this scope shows</h2>
              {model.findings.length ? <div className="berry-findings">{model.findings.slice(0, 3).map(finding => <article className="berry-finding" key={finding.id}><p>{finding.text}</p><div className="berry-inline-citations">{finding.evidence_ids.slice(0, 2).map(id => <Citation key={id} id={id} source={model.sources.find(source => source.id === id)} />)}</div></article>)}</div>
                : <p className="berry-scope-note">No sourced scope finding is available for the applied selection. Inspect the recorded relationships or deliberately change scope.</p>}
            </section>
            <div className="berry-commandbar"><div className="berry-segmented" aria-label="Analytical view">{LENSES.map(lens => <button key={lens.id} type="button" aria-pressed={context.lens === lens.id} onClick={() => dispatch({ type: 'setLens', lens: lens.id, origin: 'direct' })}>{lens.label}</button>)}</div></div>
            <CohortTray model={model} /><SubjectSelector model={model} />
            <div className="berry-analysis-layout"><section className="berry-analytical" aria-label={`${LENSES.find(lens => lens.id === context.lens)?.label ?? 'Connections'} analytical field`}>
              {context.lens === 'connections' && <Connections model={model} />}
              {context.lens === 'portfolio' && <><div className="berry-section-heading"><div><h2>The recorded cultivar portfolio</h2><p>Sourced roles and actual program links. Cultivar names stay fixed while you explore.</p></div></div><BerryDataGrid model={model} /></>}
              {context.lens === 'geography' && <Geography model={model} />}
              {context.lens === 'comparison' && <Comparison model={model} onReady={fieldReady} />}
              {context.lens === 'sensory' && <SensoryDemo onReady={fieldReady} />}
            </section><Developments model={model} onReady={railReady} /></div>
            <details className="berry-method-notes"><summary>Scope and source basis</summary>{model.scope_notes.map((note, index) => <p key={index}>{note}</p>)}</details>
          </>}
  </div>;
}

export default LandscapePage;
