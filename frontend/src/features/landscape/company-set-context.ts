import type { InvestigationContext } from '../../contracts/investigation.ts';

/** The company universe is independent of the five-subject comparison and Reader. */
export function monitoringContext(context: InvestigationContext): InvestigationContext {
  return { ...context, focus: '', cohort_companies: '', cohort_varieties: '', comparison_kind: 'company', lens: 'connections',
    detail_path: '', demo_specimens: '', news_from: '', news_to: '', saved_view_id: '', saved_revision: '' };
}

/** Source eligibility retains publication dates; focus and pins never trim News. */
export function landscapeNewsContext(context: InvestigationContext): InvestigationContext {
  return { ...monitoringContext(context), lens: 'news', news_from: context.news_from, news_to: context.news_to, relationship_types: '', q: '', q_scope: 'scope' };
}
