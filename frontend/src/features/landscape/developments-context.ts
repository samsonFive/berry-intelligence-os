import type { InvestigationContext } from '../../contracts/investigation.ts';
import type { LandscapeModel } from './models';

/** Immutable module inputs; backend alone resolves valid cohort/focus precedence. */
export function developmentsContext(context: InvestigationContext, nodes?: LandscapeModel['nodes']): InvestigationContext {
  const next = { ...context, detail_path: '', demo_specimens: '', saved_view_id: '', saved_revision: '', q: '', q_scope: 'scope' as const, relationship_types: '' };
  const focal = !nodes || nodes[context.focus] ? context.focus : '';
  const cohort = context.comparison_kind === 'company' ? context.cohort_companies : context.cohort_varieties;
  // Retain a focal fallback until the server establishes whether a typed cohort
  // contains valid subjects. Never silently replace an all-invalid cohort.
  if (context.lens === 'comparison' && cohort) return { ...next, focus: focal };
  return { ...next, lens: 'connections', comparison_kind: 'company', cohort_companies: '', cohort_varieties: '', focus: focal };
}
