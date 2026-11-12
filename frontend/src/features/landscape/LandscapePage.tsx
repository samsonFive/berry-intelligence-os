import { useCallback, useLayoutEffect, useMemo, useState } from 'react';
import { useSurfaceReady } from '../../app/SurfaceScroll';
import { legacyHref } from '../../app/legacy';
import { Badge, Button, EmptyState, EntityButton, Preview } from '../../components/ui';
import { hasBlockingIssues, investigationHref, serializeInvestigation, splitIds, type EntityType, type InvestigationContext, type Lens } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { BerryDataGrid } from '../grids/BerryDataGrid';
import { SensoryDemo } from '../demo/SensoryDemo';
import { type CompanyPage, type ComparisonModel, type DevelopmentsModel, type LandscapeEdge, type LandscapeModel, type LandscapeNewsModel, type LandscapeNode, type MonitoringCompany, type Portrait, type SourceMetadata } from './models';
import { Link } from 'react-router-dom';
import { Citation } from './Citation';
import { DevelopmentCard } from './DevelopmentCard';
import { useReadModel } from './useReadModel';
import { developmentsContext } from './developments-context';
import { landscapeNewsContext } from './company-set-context';
import { CompanyRoster } from './CompanyRoster';
import { mergeConnectionPortraits } from './connection-portraits';
import { BrandMediaGallery } from '../brand-media/BrandMedia';
import { VerifiedCompanyLogo } from '../brand-media/VerifiedCompanyLogo';
import { useBrandMedia } from '../brand-media/useBrandMedia';
import './landscape.css';
import './connections.css';
import './landscape-workspace.css';
import { InvestigationScopeBar } from '../../components/InvestigationScopeBar';
import { LANDSCAPE_VIEWS as LENSES } from '../../components/WorkspaceChrome';



/** Module keys describe domain inputs, not unrelated panel or router revisions. */
function standingContext(context: InvestigationContext): InvestigationContext {
  return { ...context, company_set: 'all', focus: '', cohort_companies: '', cohort_varieties: '', lens: 'connections', comparison_kind: 'company',
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

function Relationship({ edge, model, sources, compact = false }: { edge: LandscapeEdge; model: LandscapeModel; sources: Map<string, SourceMetadata>; compact?: boolean }) {
  const { dispatch } = useInvestigation();
  return <div className={`berry-relationship-edge${compact ? ' berry-connection-compact-edge' : ''}`}>
    <div>
      <span className="berry-relationship-role"><Preview label="Recorded relationship" content={<EdgeSupport edge={edge} sources={sources} />}
        onOpenDetail={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: edge.id }, origin: 'direct' })}>{edge.role}</Preview></span>
      <div className="berry-explicit-path"><NodeControl node={model.nodes[edge.subject_id]} /><span aria-label="connects to">→</span><NodeControl node={model.nodes[edge.object_id]} /></div>
      {edge.status !== 'active' && <Badge tone={edge.status === 'disputed' ? 'warning' : 'neutral'}>{edge.status_label}</Badge>}
      {edge.caveat && <p className="berry-material-caveat">{edge.caveat}</p>}
      {!compact && <div className="berry-inline-citations berry-relationship-evidence">{edge.evidence_ids.map(id => <Citation key={id} id={id} source={sources.get(id)} parent={{ type: 'relationship', id: edge.id }} />)}</div>}
    </div>
  </div>;
}

function CompanyBand({ portrait, model, sources, companyIds }: { portrait: Portrait; model: LandscapeModel; sources: Map<string, SourceMetadata>; companyIds: string[] }) {
  const { context, dispatch } = useInvestigation();
  const pins = splitIds(context.cohort_companies), pinned = pins.includes(portrait.actor.id);
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
  const markets = portrait.markets.filter(market => market.edges.length);
  const allEdges = [...new Map([...portrait.edges, ...portrait.portfolio_edges, ...markets.flatMap(market => market.edges)].map(edge => [edge.id, edge])).values()];
  return <article className="berry-relationship-row" data-selected={context.focus === portrait.actor.id ? 'true' : undefined}>
    <div className="berry-relationship-actor">
      <div className="berry-comparison-identity"><VerifiedCompanyLogo id={portrait.actor.id} name={portrait.actor.label} companyIds={companyIds} inspectable />
        <EntityButton compact name={portrait.actor.label} selected={context.focus === portrait.actor.id}
          onClick={() => dispatch({ type: 'focusEntity', entity: { type: 'company', id: portrait.actor.id }, origin: 'direct' })} /></div>
      <Button size="small" variant="ghost" aria-pressed={pinned} disabled={!pinned && pins.length >= 5}
        onClick={() => dispatch({ type: 'togglePin', entity: { type: 'company', id: portrait.actor.id }, origin: 'direct' })}>{pinned ? 'Unpin comparison' : 'Pin for comparison'}</Button>
      <details className="berry-connection-info"><summary aria-label={`Connection details for ${portrait.actor.label}`}>Info</summary><div>
        <p><strong>Identity</strong> · {portrait.actor.identity_status}</p>{portrait.actor.identity_note && <p>{portrait.actor.identity_note}</p>}
        {allEdges.map(edge => <section key={edge.id}><button className="berry-text-button" type="button"
          onClick={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: edge.id }, origin: 'direct' })}>{edge.label}</button>
          <EdgeSupport edge={edge} sources={sources} /></section>)}
        {!!portrait.actor.evidence_ids.length && <section><strong>Company sources</strong><div className="berry-inline-citations">{portrait.actor.evidence_ids.map(id => <Citation key={id} id={id} source={sources.get(id)} />)}</div></section>}
      </div></details>
    </div>
    <div className="berry-relationship-path">
      {visibleEdges.map(edge => <Relationship compact key={edge.id} edge={edge} model={model} sources={sources} />)}
      {!edges.length && <Unknown label="No genetics path recorded in this scope" />}
      {edges.length > 2 && <Button size="small" variant="ghost" onClick={() => setExpanded(value => !value)}>{expanded ? 'Show fewer connections' : `Show all ${edges.length} connections`}</Button>}
      {sourceNames.length > 0 && <details className="berry-source-named"><summary>Source-named cultivars · role unassigned</summary>
        {sourceNames.map((item, index) => <span key={`${item.source.id}-${index}`}>{item.name} <Citation id={item.source.id} source={item.source} /></span>)}
      </details>}
    </div>
    <div className="berry-relationship-activity">{markets.map(market => <div className="berry-activity-record" key={market.country}>
      <strong>{market.country}</strong>{market.edges.map(edge => <div key={edge.id}>
        <span className="berry-connection-direction" aria-label={`${model.nodes[edge.subject_id]?.label ?? 'Recorded subject'} connects to ${model.nodes[edge.object_id]?.label ?? 'recorded object'}`}>{edge.subject_id === portrait.actor.id ? '→' : '←'}</span>{' '}
        <Preview label="Geographic activity basis" onOpenDetail={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: edge.id }, origin: 'direct' })}
          content={<EdgeSupport edge={edge} sources={sources} />}>{edge.location_label === 'Location reported · check source' ? 'Location only' : edge.location_label}</Preview>
        {edge.caveat && <p className="berry-material-caveat">{edge.caveat}</p>}
        {edge.status !== 'active' && <Badge tone="warning">{edge.status_label}</Badge>}
      </div>)}</div>)}
      {!markets.length && <Unknown label="No geographic activity recorded in this scope" />}
    </div>
  </article>;
}

function Connections({ model }: { model: LandscapeModel }) {
  const sources = useMemo(() => new Map(model.sources.map(source => [source.id, source])), [model.sources]);
  const [allActors, setAllActors] = useState(false);
  const portraits = useMemo(() => {
    const rows = mergeConnectionPortraits(model);
    // Presentation order uses populated record types, never a performance score.
    const genetics = (row: Portrait) => [...row.edges, ...row.portfolio_edges].some(edge =>
      [model.nodes[edge.subject_id]?.type, model.nodes[edge.object_id]?.type].some(type => type === 'variety' || type === 'breeding_program'));
    const typedActivity = (row: Portrait) => row.markets.some(market => market.edges.some(edge => Boolean(edge.location_label && edge.location_label !== 'Location reported · check source')));
    return rows.sort((a, b) => Number(genetics(b) && typedActivity(b)) - Number(genetics(a) && typedActivity(a))
      || Number(genetics(b)) - Number(genetics(a)) || Number(typedActivity(b)) - Number(typedActivity(a)) || a.actor.label.localeCompare(b.actor.label));
  }, [model]);
  const visible = allActors ? portraits : portraits.slice(0, 4);
  if (!portraits.length) return <EmptyState title="No role-bearing connections match this scope">Change the applied scope to inspect other recorded relationships. Missing captured relationships do not establish an absence of activity.</EmptyState>;
  return <section className="berry-connections-table" aria-label="Companies, genetics and activity"><div className="berry-section-heading"><h2>Companies, genetics and activity</h2></div>
    <div className="berry-relationship-header" aria-hidden="true"><span>Actor</span><span>Recorded genetics connections</span><span>Geographic activity</span></div>
    <div className="berry-relationship-bands">{visible.map(portrait => <CompanyBand key={portrait.actor.id} portrait={portrait} model={model} sources={sources} companyIds={portraits.map(row => row.actor.id)} />)}</div>
    {portraits.length > 4 && <Button variant="ghost" onClick={() => setAllActors(value => !value)}>{allActors ? 'Show the initial connected actors' : `Show all ${portraits.length} actors in this scope`}</Button>}
  </section>;
}

function PageControls({ page, count, label, onPage }: { page: CompanyPage; count: number; label: string; onPage: (offset: number) => void }) {
  return <nav className="berry-roster-pages" aria-label={`${label} pages`}>
    <span>{count ? `${page.offset + 1}–${page.offset + count} of ${page.total}` : `${page.total} results · no rows on this page`}</span>
    <Button size="small" variant="ghost" disabled={page.offset === 0} onClick={() => onPage(Math.max(0, page.offset - page.limit))}>Previous</Button>
    <Button size="small" variant="ghost" disabled={!page.has_more || page.next_offset === null} onClick={() => { if (page.next_offset !== null) onPage(page.next_offset); }}>Next</Button>
  </nav>;
}

function RosterGeographies({ geographies, sources }: { geographies: MonitoringCompany['geographies']; sources: Map<string, SourceMetadata> }) {
  const { dispatch } = useInvestigation();
  if (!geographies.length) return <span className="berry-material-caveat">Not recorded in scope</span>;
  return <><div className="berry-roster-geographies">{geographies.map((geo, index) => <div key={`${geo.relationship_id}-${index}`}><button className="berry-text-button" type="button" title={`${geo.label} · ${geo.activity}`} onClick={() => dispatch({ type: 'openDetail', detail: { type: 'relationship', id: geo.relationship_id }, origin: 'direct' })}><strong>{geo.label}</strong>{geo.activity !== 'Location reported · check source' && <> · {geo.activity}</>}</button>{geo.status !== 'Documented relationship' && <p className="berry-material-caveat">{geo.status}</p>}{geo.caveat && <p className="berry-material-caveat">{geo.caveat}</p>}</div>)}</div>
    {geographies.some(geo => geo.activity === 'Location reported · check source') && <span className="berry-material-caveat">Includes location-only records</span>}
    <details className="berry-roster-records"><summary>Activity review and sources · {geographies.length} records</summary>{geographies.map((geo, index) => <div key={`${geo.relationship_id}-${index}`}><strong>{geo.label} · {geo.activity}</strong><p className="berry-material-caveat">{geo.status} · {geo.review}</p><div className="berry-inline-citations">{geo.evidence_ids.map(id => <Citation key={id} id={id} source={sources.get(id)} parent={{ type: 'relationship', id: geo.relationship_id }} />)}</div></div>)}</details>
  </>;
}

function MonitoringRoster({ model, onReady }: { model: LandscapeModel; onReady: (ready: boolean) => void }) {
  const sources = useMemo(() => new Map(model.sources.map(source => [source.id, source])), [model.sources]);
  return <><CompanyRoster model={model} onReady={onReady} renderNode={node => <NodeControl node={node} />}
    renderEdge={edge => <Relationship edge={edge} model={model} sources={sources} />}
    renderGeographies={geographies => <RosterGeographies geographies={geographies} sources={sources} />} />
    <details className="berry-deeper-connections"><summary>Explore applied-scope company and genetics connections · independent of the roster set</summary><Connections model={model} /></details></>;
}

function LandscapeNews({ onReady }: { onReady: (ready: boolean) => void }) {
  const { context, issues } = useInvestigation();
  const newsContext = landscapeNewsContext(context);
  const key = serializeInvestigation(newsContext);
  const [page, setPage] = useState({ key: '', offset: 0 });
  const offset = page.key === key ? page.offset : 0;
  const query = useReadModel<LandscapeNewsModel>(`/news?offset=${offset}&limit=20`, newsContext, !hasBlockingIssues(issues));
  useLayoutEffect(() => onReady(!query.isPending), [onReady, query.isPending]);
  const news = query.data?.data;
  const onPage = (value: number) => setPage({ key, offset: value });
  return <section className="berry-landscape-news" aria-labelledby="landscape-news-heading">
    <div className="berry-section-heading"><div><h2 id="landscape-news-heading">{news?.heading ?? 'Landscape News'}</h2></div>
      <Link to={investigationHref('/app/briefing', context)}>Open scoped Briefing →</Link></div>
    {query.isPending ? <p className="berry-loading" role="status">Loading retained News…</p>
      : query.isError ? <EmptyState title="News unavailable" action={<Button onClick={() => void query.refetch()}>Try again</Button>}>{query.error instanceof Error ? query.error.message : 'The feed could not be loaded.'}</EmptyState>
        : news && <><div className="berry-news-toolbar"><PageControls page={news} count={news.cards.length} label="Landscape News" onPage={onPage} /></div>
          {news.cards.length ? <div className="news-grid berry-legacy-news-grid">{news.cards.map(card => <DevelopmentCard key={card.id} card={card} newsHref={news.briefing_href} />)}</div>
            : <EmptyState title="No retained News matches this company set and scope">No source geography, publication date or company selector has been widened. Missing retained News does not establish an absence of developments.</EmptyState>}
          <div className="berry-news-footer"><details className="berry-news-feed-basis"><summary>Feed basis</summary><p>{news.basis === 'workspace_watches' ? `${news.subject_count} shared watched companies · monitoring interest, not evidence approval or active collection.` : 'All companies · includes eligible industry News without a company link.'}</p><p>Source geography and source publication dates apply; focus and comparison pins do not narrow this feed.</p><p>{news.briefing_scope_note}</p></details><PageControls page={news} count={news.cards.length} label="Landscape News bottom" onPage={onPage} /></div>
        </>}
  </section>;
}

function Geography({ model }: { model: LandscapeModel }) {
  const { dispatch } = useInvestigation();
  const sources = new Map(model.sources.map(source => [source.id, source]));
  const edges = model.edges.filter(edge => edge.company_geography || edge.genetic_geography);
  return <><div className="berry-section-heading"><h2>Geographic activity</h2></div>
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
  const media = useBrandMedia(result?.comparison_kind === 'company' ? result.companies.map(company => company.id) : []);
  const hasPackaging = result?.comparison_kind === 'company' && result.companies.some(company => media?.[company.id]?.packaging.length);
  const openEntity = (id: string, type: EntityType) => dispatch({ type: 'focusEntity', entity: { id, type }, origin: 'direct' });
  return <><div className="berry-section-heading"><h2>Compare {context.comparison_kind === 'company' ? 'companies' : 'cultivars'}</h2>
    <div className="berry-segmented" aria-label="Comparison subject type">{(['company', 'variety'] as const).map(kind => <button key={kind} type="button" aria-pressed={context.comparison_kind === kind} onClick={() => dispatch({ type: 'setLens', lens: 'comparison', comparison_kind: kind, origin: 'direct' })}>{kind === 'company' ? 'Companies' : 'Cultivars'}</button>)}</div></div>
    {selected.length === 0 ? <EmptyState title="Pin subjects to compare">Use the separate company and cultivar pins in Connections or Portfolio. Each cohort remains available when you switch the comparison type.</EmptyState>
      : query.isPending ? <p className="berry-loading" role="status">Loading the selected profiles…</p>
        : query.isError ? <EmptyState title="Comparison unavailable">{query.error instanceof Error ? query.error.message : 'The selected profiles could not be loaded.'}</EmptyState>
          : result && <>
            {(result.invalid_ids.length > 0 || result.overflow_ids.length > 0) && <div className="berry-issue">Unavailable: {result.invalid_ids.join(', ') || 'None'}. Beyond the supported comparison: {result.overflow_ids.join(', ') || 'None'}. All pins remain visible for explicit removal.</div>}
            {result.comparison_kind === 'company' ? result.companies.length > 0 && <div className="berry-table-wrap"><table className="berry-table berry-comparison-table"><thead><tr><th>Recorded dimension</th>{result.companies.map(company => <th key={company.id}><div className="berry-comparison-identity"><VerifiedCompanyLogo id={company.id} name={company.name} companyIds={result.companies.map(row => row.id)} inspectable /><EntityButton compact name={company.name} onClick={() => openEntity(company.id, 'company')} /></div></th>)}</tr></thead><tbody>
              {hasPackaging && <tr><th scope="row">Retail packaging</th>{result.companies.map(company => <td key={company.id}><BrandMediaGallery compact model={media?.[company.id]} /></td>)}</tr>}
              <tr><th scope="row">Declared berry portfolio</th>{result.companies.map(company => <td key={company.id}>{company.berries.join(' · ') || <Unknown />}</td>)}</tr>
              {result.role_matrix.map((role, index) => <tr key={role.bucket} className={index === 0 ? 'berry-comparison-section-start' : undefined}><th scope="row">{role.label}</th>{result.companies.map(company => <td key={company.id}>{company.roles[role.bucket]?.length ? <ul className="berry-comparison-list berry-cell-grid">{company.roles[role.bucket].map(party => <li key={party.id}><button type="button" className="berry-text-button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'variety', id: party.id }, origin: 'direct' })}>{party.name || model.nodes[party.id]?.label || party.id}</button></li>)}</ul> : <Unknown label="Unknown: no recorded cultivar relationship in this role" />}</td>)}</tr>)}
              <tr className="berry-comparison-section-start"><th scope="row">Recorded geographic context</th>{result.companies.map(company => <td key={company.id}>{company.geographies.length ? <ul className="berry-comparison-list berry-cell-grid berry-cell-grid--places">{company.geographies.map(geo => <li key={geo.id}><button className="berry-text-button" type="button" onClick={() => dispatch({ type: 'openDetail', detail: { type: 'geography', id: geo.id }, origin: 'direct' })}>{geo.name}</button></li>)}</ul> : <Unknown />}<p className="berry-material-caveat">Profile geography includes distinct company/observation bases; inspect before inferring growing.</p></td>)}</tr>
              <tr className="berry-comparison-section-start"><th scope="row">Published rights records</th>{result.companies.map(company => <td key={company.id}>{company.rights_published.length ? <ul className="berry-comparison-list berry-cell-grid berry-cell-grid--sources">{company.rights_published.map(row => <li key={row.id}><Citation id={row.id} />{row.kind && <span className="berry-material-caveat"> {row.kind}</span>}</li>)}</ul> : <Unknown />}</td>)}</tr>
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
  return <section id="landscape-developments" className="berry-developments berry-news-rail" aria-labelledby="developments-heading">
    <div className="berry-section-heading"><div><h2 id="developments-heading">Retained developments</h2><p className="berry-developments-subject">{developments?.heading ?? 'Relevant developments'}</p><p>Source geography · publication dates</p></div>
      {developments && <Link className="berry-button berry-button--ghost berry-button--small" to={investigationHref('/app/briefing', context)}>Open scoped Briefing →</Link>}</div>
    {query.isPending ? <p role="status" className="berry-loading">Loading developments for the current subject…</p>
      : query.isError ? <EmptyState compact title="Developments could not be loaded">{query.error instanceof Error ? query.error.message : 'Try reopening this view.'}</EmptyState>
        : developments && developments.cards.length ? <div className="news-grid berry-legacy-news-grid">{developments.cards.slice(0, 3).map(card => <DevelopmentCard key={card.id} card={card} newsHref={developments.briefing_href} />)}</div>
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
      {kind === 'company' && <VerifiedCompanyLogo id={id} name={model.nodes[id]?.label ?? id} companyIds={ids} />}
      <button className="berry-pin-name" type="button" title={model.nodes[id]?.label ?? id} onClick={() => dispatch({ type: 'openDetail', detail: { type: kind, id }, origin: 'direct' })}>{model.nodes[id]?.label ?? id}</button>
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
  const [railPreferences, setRailPreferences] = useState<Partial<Record<Lens, boolean>>>({});
  const fieldReady = useCallback((ready: boolean) => setReadyParts(previous => previous.key === readinessKey && previous.field === ready ? previous
    : { key: readinessKey, field: ready, rail: previous.key === readinessKey ? previous.rail : false }), [readinessKey]);
  const railReady = useCallback((ready: boolean) => setReadyParts(previous => previous.key === readinessKey && previous.rail === ready ? previous
    : { key: readinessKey, field: previous.key === readinessKey ? previous.field : false, rail: ready }), [readinessKey]);
  const asynchronousField = ['connections', 'portfolio', 'comparison', 'news', 'sensory'].includes(context.lens);
  const needsRail = context.lens !== 'news' && (railPreferences[context.lens] ?? context.lens === 'comparison');
  const currentParts = readyParts.key === readinessKey;
  useSurfaceReady(blocked || query.isError || Boolean(model && (!needsRail || currentParts && readyParts.rail) && (!asynchronousField || currentParts && readyParts.field)));
  const berry = context.berry === 'all' ? 'All berries' : context.berry.replace(/^berry-/, '').replace(/^./, character => character.toUpperCase());
  return <div className="berry-landscape-page">
    <div className="berry-page-heading berry-landscape-titlebar"><div className="berry-landscape-title"><h1>{context.berry === 'all' ? 'Berry landscape' : `${berry} landscape`}</h1></div>

    </div>
    <InvestigationScopeBar />
    {blocked ? <EmptyState title="Resolve the investigation selectors">Some URL or scope values are unsupported. Correct the selectors before loading; the application has not broadened the scope.</EmptyState>
      : query.isPending ? <p className="berry-loading" role="status">Loading the applied landscape…</p>
        : query.isError ? <EmptyState title="This landscape could not be loaded" action={<Button onClick={() => { void query.refetch(); }}>Try again</Button>}>{query.error instanceof Error ? query.error.message : 'The read service is unavailable.'}</EmptyState>
          : model && <>
            {!!query.data?.issues.length && <div className="berry-issue">{query.data.issues.map((issue, index) => <p key={index}>{issue.message}</p>)}</div>}
            {context.lens !== 'news' && model.findings.length > 0 && <section className="berry-readout" aria-labelledby="scope-readout-heading"><h2 className="berry-readout-title berry-sr-only" id="scope-readout-heading">Scope highlights</h2>
              <div className="berry-findings">{model.findings.slice(0, 3).map(finding => <article className="berry-finding" key={finding.id}><p>{finding.text}</p><div className="berry-inline-citations">{finding.evidence_ids.map(id => <Citation key={id} id={id} source={model.sources.find(source => source.id === id)} />)}</div></article>)}</div>
            </section>}
            <div className="berry-investigation-tools lw-view-tools berry-landscape-tools" role="group" aria-label="Landscape research tools"><label className="berry-company-set">Roster &amp; News<select value={context.company_set} onChange={event => dispatch({ type: 'setCompanySet', company_set: event.target.value as InvestigationContext['company_set'], origin: 'direct' })}><option value="all">All companies</option><option value="watched">Shared watched companies</option></select></label><CohortTray model={model} />{context.lens !== 'news' && <Button size="small" variant="ghost" aria-expanded={needsRail} aria-controls="landscape-developments" onClick={() => setRailPreferences(previous => ({ ...previous, [context.lens]: !needsRail }))}>Developments</Button>}<SubjectSelector model={model} /></div>
            <div className={`berry-analysis-layout${!needsRail ? ' berry-analysis-layout--full' : ''}`}><section className="berry-analytical berry-main-field" aria-label={`${LENSES.find(lens => lens.id === context.lens)?.label ?? 'Connections'} analytical field`}>
              {context.lens === 'connections' && <MonitoringRoster model={model} onReady={fieldReady} />}
              {context.lens === 'portfolio' && <><div className="berry-section-heading"><h2>Cultivar portfolio</h2></div><BerryDataGrid model={model} onReady={fieldReady} /></>}
              {context.lens === 'geography' && <Geography model={model} />}
              {context.lens === 'comparison' && <Comparison model={model} onReady={fieldReady} />}
              {context.lens === 'news' && <LandscapeNews onReady={fieldReady} />}
              {context.lens === 'sensory' && <SensoryDemo onReady={fieldReady} />}
            </section>{needsRail && <Developments model={model} onReady={railReady} />}</div>
            <details className="berry-method-notes"><summary>Scope and source basis</summary>{context.lens === 'comparison' && <p>Comparison shows complete selected profiles; berry, geography and publication filters do not trim portfolio records.</p>}{model.scope_notes.map((note, index) => <p key={index}>{note}</p>)}</details>
          </>}
  </div>;
}

export default LandscapePage;
