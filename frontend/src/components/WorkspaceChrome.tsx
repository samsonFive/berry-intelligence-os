import { Link, useLocation } from 'react-router-dom';
import { investigationHref, type Berry, type Lens } from '../contracts/investigation';
import { useInvestigation } from '../state/InvestigationProvider';
import { legacyHref } from '../app/legacy';
import { brandFlavorContext } from '../features/demo/sensory-model';

export const LANDSCAPE_VIEWS: Array<{ id: Lens; label: string }> = [
  { id: 'connections', label: 'Connections' }, { id: 'portfolio', label: 'Portfolio' },
  { id: 'geography', label: 'Geography' }, { id: 'comparison', label: 'Comparison' },
  { id: 'news', label: 'News' }, { id: 'sensory', label: 'Flavor simulation' },
];

/** The same page-navigation hierarchy as the established authored workspace. */
export function WorkspaceNavigation() {
  const { context, dispatch } = useInvestigation();
  const { pathname } = useLocation();
  const landscape = pathname === '/app/landscape';
  const title = landscape ? 'Berry landscape' : pathname.startsWith('/app/learn') ? 'Learn'
    : pathname === '/app/briefing' ? 'Briefing' : 'Investigation tools';
  return <nav className="berry-workspace-nav" aria-label="Workspace quick navigation">
    <span className="berry-workspace-nav-title">{title}</span>
    <div>{landscape ? LANDSCAPE_VIEWS.map(view => <button type="button" key={view.id}
      aria-pressed={context.lens === view.id} onClick={() => dispatch(view.id === 'sensory' ? { type: 'replaceContext', context: brandFlavorContext(context), origin: 'direct' } : { type: 'setLens', lens: view.id, origin: 'direct' })}>{view.label}</button>)
      : <><Link to={investigationHref('/app/landscape', context)}>Landscape</Link><a href={legacyHref('/workspaces', pathname, context)}>Research pages</a></>}
    </div>
  </nav>;
}

export function InvestigationSidebar() {
  const { context, dispatch } = useInvestigation();
  const { pathname } = useLocation();
  const crops: Array<[Berry, string]> = [['all', 'All berries'], ['berry-blueberry', 'Blueberry'],
    ['berry-strawberry', 'Strawberry'], ['berry-raspberry', 'Raspberry'], ['berry-blackberry', 'Blackberry']];
  return <aside className="berry-research-sidebar" aria-label="Investigation navigation">
    <p className="berry-eyebrow">COMPETITIVE INTELLIGENCE</p><h2>Landscape</h2>
    <nav aria-label="Crop landscapes">{crops.map(([berry, label]) => <button key={berry} type="button"
      aria-current={context.berry === berry ? 'true' : undefined} onClick={() => dispatch({ type: 'applyScope', scope: { ...context, berry }, origin: 'direct' })}>{label}</button>)}</nav>
    <p className="berry-eyebrow">COMPANY SET</p>
    <nav aria-label="Company set">{(['all', 'watched'] as const).map(company_set => <button key={company_set} type="button"
      aria-current={context.company_set === company_set ? 'true' : undefined} onClick={() => dispatch({ type: 'setCompanySet', company_set, origin: 'direct' })}>{company_set === 'all' ? 'All companies' : 'Shared watched companies'}</button>)}</nav>
    <p className="berry-eyebrow">RESEARCH</p>
    <nav aria-label="Investigation research"><a href={legacyHref('/workspaces', pathname, context)}>Workspaces →</a>
      <Link to={investigationHref('/app/workspaces', context)}>Save / export</Link></nav>
    <details className="berry-sidebar-help"><summary>About this view</summary><p>Company sets use the shared workspace Watch list. Comparison pins and source review remain independent.</p></details>
  </aside>;
}
