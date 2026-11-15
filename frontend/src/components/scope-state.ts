import { EMPTY_CONTEXT, splitIds } from '../contracts/investigation.ts';
import type { InvestigationContext } from '../contracts/investigation.ts';

export const SCOPE_FIELDS = ['berry', 'countries', 'geo_basis', 'actor_roles', 'relationship_types', 'news_from', 'news_to'] as const;
export function scopeHasChanges(applied: InvestigationContext, draft: InvestigationContext): boolean {
  return SCOPE_FIELDS.some(field => draft[field] !== applied[field]);
}

/** Scope/search filters reset independently of comparison selections and display. */
export function resetInvestigationContext(context: InvestigationContext): InvestigationContext {
  return { ...EMPTY_CONTEXT, lens: context.lens, comparison_kind: context.comparison_kind,
    cohort_companies: context.cohort_companies, cohort_varieties: context.cohort_varieties, demo_specimens: context.demo_specimens };
}

export function appliedScopeLabels(context: InvestigationContext, countries: readonly { id: string; name?: string; label?: string }[]): string[] {
  const berry = context.berry === 'all' ? 'All berries' : context.berry.slice(6, 7).toUpperCase() + context.berry.slice(7);
  const places = splitIds(context.countries).map(id => {
    const country = countries.find(item => item.id === id);
    return country?.name ?? country?.label ?? id.replace(/^geography-/, '').replaceAll('-', ' ');
  });
  const labels = [berry, places.length ? places.join(', ') : 'All geographies', context.company_set === 'watched' ? 'Watched companies' : 'All companies'];
  const basis = { company_connections: 'Company connections', source_geography: 'Source geography', variety_growing: 'Cultivar growing', rights: 'Rights' };
  labels.push(basis[context.geo_basis]);
  if (context.actor_roles) labels.push(`Roles: ${splitIds(context.actor_roles).join(', ').replaceAll('_', ' ')}`);
  if (context.relationship_types) labels.push(`Relationships: ${splitIds(context.relationship_types).join(', ').replaceAll('_', ' ')}`);
  if (context.news_from || context.news_to) labels.push(`Published ${context.news_from || 'any date'} – ${context.news_to || 'present'}`);
  if (context.q) labels.push(`Company search: “${context.q}”`);
  return labels;
}
