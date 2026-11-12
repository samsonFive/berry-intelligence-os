import type { InvestigationContext } from '../../contracts/investigation.ts';

export const BRAND_DEMO_IDS = ['demo-brand-driscolls', 'demo-brand-fruitist', 'demo-brand-ozblu',
  'demo-brand-naturipe', 'demo-brand-wish-farms', 'demo-brand-california-giant'] as const;
export const FLAVOR_METRICS = ['sweetness', 'acidity', 'aroma', 'firmness', 'overall_liking'] as const;
export type FlavorMetricId = typeof FLAVOR_METRICS[number];
export interface FlavorMetric {
  id: FlavorMetricId; label: string; scale_type: 'intensity' | 'hedonic'; minimum: 1; maximum: 9;
  minimum_label: string; maximum_label: string; unit: string;
}
export interface BrandProfile {
  id: string; brand_label: string; label: string; synthetic: true;
  canonical_entity: { type: 'company' | 'brand'; id: string };
  identity_basis: { note: string; urls: string[] };
  values: Record<FlavorMetricId, number>;
}
export interface SensoryFixture {
  api_v: 1; synthetic: true; namespace: string;
  metric: { id: string; label: string; minimum: 1; maximum: 9 };
  specimens: Array<{ id: string; label: string; value: number }>;
  metrics: FlavorMetric[]; brand_profiles: BrandProfile[];
  scope_note: string; disclaimer: string;
}
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const rating = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 1 && value <= 9;

/** Validate isolated demo data without converting its typed entity references. */
export function parseSensoryFixture(raw: unknown): SensoryFixture {
  const fail = () => { throw new Error('The isolated flavor comparison has an unsupported format.'); };
  if (!record(raw) || raw.api_v !== 1 || raw.synthetic !== true || raw.namespace !== 'synthetic-sensory-v1'
    || !record(raw.metric) || raw.metric.minimum !== 1 || raw.metric.maximum !== 9
    || !Array.isArray(raw.specimens) || !Array.isArray(raw.metrics) || !Array.isArray(raw.brand_profiles)) return fail();
  const ids = new Set<string>();
  for (const row of raw.specimens) {
    if (!record(row) || typeof row.id !== 'string' || !/^demo-specimen-[A-Za-z0-9_.-]+$/.test(row.id)
      || typeof row.label !== 'string' || !row.label || !rating(row.value) || ids.has(row.id)) return fail();
    ids.add(row.id);
  }
  if (raw.metrics.length !== FLAVOR_METRICS.length || raw.brand_profiles.length > 20) return fail();
  const metricIds = new Set<string>();
  for (const metric of raw.metrics) {
    if (!record(metric) || !FLAVOR_METRICS.includes(metric.id as FlavorMetricId) || metricIds.has(String(metric.id))
      || metric.minimum !== 1 || metric.maximum !== 9 || !metric.label || !metric.minimum_label || !metric.maximum_label
      || metric.scale_type !== (metric.id === 'overall_liking' ? 'hedonic' : 'intensity')) return fail();
    metricIds.add(String(metric.id));
  }
  for (const row of raw.brand_profiles) {
    if (!record(row) || typeof row.id !== 'string' || !/^demo-brand-[A-Za-z0-9_.-]+$/.test(row.id) || ids.has(row.id)
      || row.synthetic !== true || typeof row.brand_label !== 'string' || !row.brand_label || typeof row.label !== 'string'
      || !row.label.includes('SIMULATED') || !record(row.canonical_entity) || !record(row.values)
      || !['company', 'brand'].includes(String(row.canonical_entity.type)) || typeof row.canonical_entity.id !== 'string'
      || !row.canonical_entity.id.startsWith(`${row.canonical_entity.type}-`)
      || FLAVOR_METRICS.some(id => !rating((row.values as Record<string, unknown>)[id]))) return fail();
    ids.add(row.id);
  }
  return raw as unknown as SensoryFixture;
}

/** Choosing the brand view is one explicit navigation, retaining all other scope. */
export function brandFlavorContext(context: InvestigationContext): InvestigationContext {
  return { ...context, lens: 'sensory', demo_specimens: context.demo_specimens || BRAND_DEMO_IDS.join(',') };
}
