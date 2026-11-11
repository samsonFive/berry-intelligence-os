import { useLayoutEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button, EmptyState } from '../../components/ui';
import { splitIds } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';

interface SensoryFixture {
  api_v: 1;
  synthetic: true;
  namespace: string;
  metric: { id: string; label: string; minimum: 1; maximum: 9 };
  specimens: Array<{ id: string; label: string; value: number }>;
  scope_note: string;
  disclaimer: string;
}

async function loadSensory(signal: AbortSignal): Promise<SensoryFixture> {
  const response = await fetch('/api/investigations/v1/demo/sensory', { signal, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
  if (response.redirected || !response.ok || !(response.headers.get('content-type') ?? '').includes('application/json')) throw new Error('The isolated sensory demonstration could not be loaded.');
  const fixture = await response.json() as SensoryFixture;
  if (fixture.api_v !== 1 || fixture.synthetic !== true || !fixture.namespace || fixture.metric?.minimum !== 1 || fixture.metric.maximum !== 9
    || !Array.isArray(fixture.specimens) || fixture.specimens.some(row => !row.id || !row.label || !Number.isFinite(row.value) || row.value < 1 || row.value > 9)
    || new Set(fixture.specimens.map(row => row.id)).size !== fixture.specimens.length) throw new Error('The sensory fixture has an unsupported format.');
  return fixture;
}

export function SensoryDemo({ onReady }: { onReady?: (ready: boolean) => void } = {}) {
  const { context, dispatch } = useInvestigation();
  const query = useQuery({ queryKey: ['investigation', 'synthetic-sensory-v1'], queryFn: ({ signal }) => loadSensory(signal) });
  useLayoutEffect(() => onReady?.(!query.isPending), [onReady, query.isPending]);
  if (query.isPending) return <p className="berry-loading" role="status">Loading the isolated sensory demonstration…</p>;
  if (query.isError || !query.data) return <EmptyState title="Sensory demonstration unavailable">{query.error instanceof Error ? query.error.message : 'The fixture is unavailable. Your real investigation is unchanged.'}</EmptyState>;
  const fixture = query.data;
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

export default SensoryDemo;
