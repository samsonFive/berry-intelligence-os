import { useLayoutEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button, EmptyState } from '../../components/ui';
import { splitIds } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { clearPrivateSession } from '../../app/PrivateQueryProvider';
import { BrandLogo } from '../brand-media/BrandMedia';
import { useBrandMedia } from '../brand-media/useBrandMedia';
import { BRAND_DEMO_IDS, parseSensoryFixture, type SensoryFixture, type FlavorMetricId } from './sensory-model';
import './sensory.css';

async function loadSensory(signal: AbortSignal): Promise<SensoryFixture> {
  const response = await fetch('/api/investigations/v1/demo/sensory', { signal, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
  if ([401, 403].includes(response.status)) clearPrivateSession();
  if (response.redirected || !response.ok || !(response.headers.get('content-type') ?? '').includes('application/json')) throw new Error('The isolated flavor comparison could not be loaded.');
  return parseSensoryFixture(await response.json());
}

function LegacySpecimens({ fixture }: { fixture: SensoryFixture }) {
  const { context, dispatch } = useInvestigation();
  const requested = splitIds(context.demo_specimens);
  const allIds = fixture.specimens.map(row => row.id);
  const unavailable = requested.filter(id => !allIds.includes(id));
  const selected = requested.length ? requested.filter(id => allIds.includes(id)) : allIds;
  const rows = fixture.specimens.filter(row => selected.includes(row.id));
  const start = 180, end = 670, step = 48, top = 35;
  const axisY = top + Math.max(rows.length, 1) * step;
  const x = (value: number) => start + (value - 1) / 8 * (end - start);
  return <section aria-labelledby="sensory-heading" data-synthetic="true" data-demo-namespace={fixture.namespace}>
    <p className="berry-synthetic-label">Synthetic demonstration · fictitious specimens</p>
    <div className="berry-section-heading"><div><h2 id="sensory-heading">{fixture.metric.label}</h2><p>Illustrative specimens, independent of berry, geography and publication-date filters.</p></div></div>
    {unavailable.length > 0 && <div className="berry-issue" role="status">{unavailable.length} saved demo {unavailable.length === 1 ? 'specimen is' : 'specimens are'} unavailable in this fixture. Their identifiers stay separate from company and cultivar selections.
      <Button size="small" variant="ghost" onClick={() => dispatch({ type: 'setDemoCohort', ids: [], origin: 'direct' })}>Use all available demo specimens</Button>
      {selected.length > 0 && <Button size="small" variant="ghost" onClick={() => dispatch({ type: 'setDemoCohort', ids: selected, origin: 'direct' })}>Remove unavailable demo selections</Button>}
    </div>}
    <fieldset className="berry-demo-cohort"><legend>Demo specimens</legend>{fixture.specimens.map(specimen => <label key={specimen.id}><input type="checkbox" checked={selected.includes(specimen.id)} disabled={selected.includes(specimen.id) && selected.length === 1}
      aria-describedby="demo-selection-help" onChange={() => {
        const ids = requested.length ? requested : allIds;
        dispatch({ type: 'setDemoCohort', ids: selected.includes(specimen.id) ? ids.filter(id => id !== specimen.id) : [...ids, specimen.id], origin: 'direct' });
      }} />{specimen.label}</label>)}</fieldset>
    <p className="berry-scope-note berry-demo-selection-help" id="demo-selection-help">Keep at least one available specimen selected. This demo cohort is retained in the investigation link and saved selectors.</p>
    {rows.length ? <div className="berry-sensory-chart"><svg viewBox={`0 0 720 ${axisY + 65}`} role="img" aria-labelledby="sensory-chart-title sensory-chart-description">
      <title id="sensory-chart-title">Synthetic {fixture.metric.label}, on a scale from 1 to 9</title>
      <desc id="sensory-chart-description">{rows.map(row => `${row.label}: ${row.value}`).join('; ')}. Fictitious specimen scores for demonstration only.</desc>
      {Array.from({ length: 9 }, (_, i) => i + 1).map(tick => <g key={tick}><line className="berry-sensory-guide" x1={x(tick)} x2={x(tick)} y1={top - 14} y2={axisY} /><text x={x(tick)} y={axisY + 24} fontSize="12" textAnchor="middle">{tick}</text></g>)}
      <line className="berry-sensory-axis" x1={start} x2={end} y1={axisY} y2={axisY} />
      {rows.map((row, index) => <g key={row.id}><text x={start - 20} y={top + index * step + 5} textAnchor="end" fontSize="13">{row.label}</text><circle className="berry-sensory-dot" cx={x(row.value)} cy={top + index * step} r="7" /><text x={x(row.value) + 15} y={top + index * step + 4} fontSize="12">{row.value}</text></g>)}
      <text x={(start + end) / 2} y={axisY + 51} textAnchor="middle" fontSize="12">{fixture.metric.label} · 1–9</text>
    </svg></div> : <EmptyState compact title="Choose an available demo specimen">Use a listed specimen above or explicitly restore all available demo specimens. Unavailable selections have not been replaced silently.</EmptyState>}
    <p className="berry-scope-note">Illustrative scores, not measured consumer results. Demo selection keeps your company and cultivar pins.</p>
    <details className="berry-demo-method"><summary>About these synthetic values</summary><p>{fixture.disclaimer}</p><p>{fixture.scope_note}</p></details>
  </section>;
}


export function SensoryDemo({ onReady }: { onReady?: (ready: boolean) => void } = {}) {
  const { context, dispatch } = useInvestigation();
  const [metricId, setMetricId] = useState<FlavorMetricId>('sweetness');
  const query = useQuery({ queryKey: ['investigation', 'synthetic-brand-sensory-v1'], queryFn: ({ signal }) => loadSensory(signal) });
  const fixture = query.data;
  const media = useBrandMedia(fixture?.brand_profiles.map(row => row.canonical_entity.id) ?? []);
  useLayoutEffect(() => onReady?.(!query.isPending), [onReady, query.isPending]);
  if (query.isPending) return <p className="berry-loading" role="status">Loading simulated brand flavor profiles…</p>;
  if (query.isError || !fixture) return <EmptyState title="Flavor comparison unavailable">{query.error instanceof Error ? query.error.message : 'The fixture is unavailable.'}</EmptyState>;
  const requested = splitIds(context.demo_specimens);
  const brandIds = fixture.brand_profiles.map(row => row.id);
  const knownIds = [...brandIds, ...fixture.specimens.map(row => row.id)];
  const unavailable = requested.filter(id => !knownIds.includes(id));
  const rows = fixture.brand_profiles.filter(row => requested.includes(row.id));
  const legacyIds = requested.filter(id => fixture.specimens.some(row => row.id === id));
  const useBrands = () => dispatch({ type: 'setDemoCohort', ids: [...BRAND_DEMO_IDS], origin: 'direct' });
  if (!rows.length && (!requested.length || legacyIds.length)) return <><section className="berry-flavor-intro" data-synthetic="true"><span className="berry-simulated-badge">SIMULATED</span><h2>Compare retail brand flavor profiles</h2><p>Sweetness, acidity, aroma, firmness and overall liking across six retail brand labels.</p><Button onClick={useBrands}>Compare six retail brands</Button></section><LegacySpecimens fixture={fixture} /></>;
  const metric = fixture.metrics.find(item => item.id === metricId) ?? fixture.metrics[0];
  const x = (value: number) => 160 + (value - 1) / 8 * 440;
  const axisY = 24 + Math.max(rows.length, 1) * 35;
  return <section className="berry-flavor-demo" aria-labelledby="flavor-heading" data-synthetic="true" data-demo-namespace={fixture.namespace}>
    <header className="berry-flavor-heading"><div><span className="berry-simulated-badge">SIMULATED</span><h2 id="flavor-heading">Retail brand flavor comparison</h2><p>Illustrative blueberry profiles demonstrate the comparison. These are not measured brand results.</p></div></header>
    {unavailable.length > 0 && <div className="berry-issue" role="status">{unavailable.length} saved demo selections are unavailable; their IDs remain in this investigation. <Button size="small" onClick={useBrands}>Use the six available brands</Button></div>}
    <fieldset className="berry-brand-choices"><legend>Brands in this comparison</legend>{fixture.brand_profiles.map(profile => <label key={profile.id} data-selected={requested.includes(profile.id)}><input type="checkbox" checked={requested.includes(profile.id)} disabled={requested.includes(profile.id) && rows.length === 1 && !legacyIds.length} onChange={() => dispatch({ type: 'setDemoCohort', ids: requested.includes(profile.id) ? requested.filter(id => id !== profile.id) : [...requested, profile.id], origin: 'direct' })} /><BrandLogo asset={media?.[profile.canonical_entity.id]?.logo} name={profile.brand_label} /><span><strong>{profile.brand_label}</strong><small>SIMULATED profile</small></span></label>)}</fieldset>
    <div className="berry-flavor-toolbar"><label>Compare attribute<select aria-label="Compare flavor attribute" value={metric.id} onChange={event => setMetricId(event.target.value as FlavorMetricId)}>{fixture.metrics.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label><p><strong>1</strong> {metric.minimum_label} · <strong>9</strong> {metric.maximum_label}</p><Button size="small" onClick={useBrands}>Select all six</Button></div>
    {rows.length ? <div className="berry-flavor-panels">
      <section className="berry-flavor-panel" aria-labelledby="flavor-chart-heading"><header><h3 id="flavor-chart-heading">{metric.label}</h3><span className="berry-simulated-badge">SIMULATED · 1–9</span></header><svg viewBox={`0 0 650 ${axisY + 58}`} role="img" aria-labelledby="flavor-chart-title flavor-chart-desc"><title id="flavor-chart-title">SIMULATED {metric.label}</title><desc id="flavor-chart-desc">{rows.map(row => `${row.brand_label}: ${row.values[metric.id]}`).join('; ')}. 1 means {metric.minimum_label}; 9 means {metric.maximum_label}. Illustrative values only.</desc>{Array.from({ length: 9 }, (_, index) => index + 1).map(tick => <g key={tick}><line className="berry-flavor-guide" x1={x(tick)} x2={x(tick)} y1="12" y2={axisY} /><text x={x(tick)} y={axisY + 20} textAnchor="middle">{tick}</text></g>)}{rows.map((row,index) => <g key={row.id}><text x="145" y={28 + index * 35} textAnchor="end">{row.brand_label}</text><line className="berry-flavor-stem" x1={x(1)} x2={x(row.values[metric.id])} y1={24+index*35} y2={24+index*35} /><circle className="berry-flavor-point" cx={x(row.values[metric.id])} cy={24+index*35} r="5" /><text x={x(row.values[metric.id])+11} y={28+index*35}>{row.values[metric.id].toFixed(1)}</text></g>)}<text x="380" y={axisY+46} textAnchor="middle">{metric.label} · {metric.scale_type === 'intensity' ? 'intensity' : 'preference'} · 1–9</text></svg></section>
      <section className="berry-flavor-panel berry-flavor-matrix" aria-labelledby="flavor-matrix-heading"><header><h3 id="flavor-matrix-heading">Full flavor profiles</h3><span className="berry-simulated-badge">SIMULATED</span></header><div className="berry-table-wrap"><table className="berry-table"><caption>SIMULATED ratings · all values use a 1–9 scale</caption><thead><tr><th>Brand</th>{fixture.metrics.map(item => <th key={item.id} data-current={item.id === metric.id}><abbr title={`${item.minimum_label} (1) to ${item.maximum_label} (9)`}>{item.label}</abbr></th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.id}><th scope="row">{row.brand_label}</th>{fixture.metrics.map(item => <td key={item.id} data-current={item.id === metric.id}>{row.values[item.id].toFixed(1)}</td>)}</tr>)}</tbody></table></div><p>Intensity describes attribute strength. Overall liking describes preference.</p></section>
    </div> : <EmptyState compact title="Choose an available brand">Use a listed brand above. Unavailable selections have not been replaced.</EmptyState>}
    {legacyIds.length > 0 && <details className="berry-flavor-legacy"><summary>Also selected: {legacyIds.length} earlier fictitious specimens</summary><LegacySpecimens fixture={fixture} /></details>}
    <details className="berry-demo-method"><summary>About this simulation and brand identities</summary><p>All scores are deterministic illustrative values, independent of company tiers. They are not measured results, a quality ranking, or a brand performance claim.</p><p>Brand labels link to the existing typed company or brand identities; no company has been converted into a brand record. Selected profiles remain in the investigation link and saved selections. Normal cited exports omit simulated values unless the separate simulation annex is explicitly included.</p></details>
  </section>;
}
export default SensoryDemo;
