import { getInvestigation, InvestigationApiError } from '../../api/client.ts';
import type { InvestigationEnvelope } from '../../api/client.ts';
import type { InvestigationContext } from '../../contracts/investigation.ts';
import type { MonitoringModel } from './models.ts';

type ReadPage = (endpoint: string, context: InvestigationContext, revision: number, signal?: AbortSignal) => Promise<InvestigationEnvelope<MonitoringModel>>;
const basis = (page: MonitoringModel) => JSON.stringify([page.company_set, page.company_set_key, page.basis, page.total, page.universe_count,
  page.matching_count, page.search_basis, page.watched_count, page.unavailable_watch_count, page.tier_groups, page.tier_basis]);

/** Read every existing bounded API page before exposing one coherent roster.
 * A changed universe, duplicate identity or interrupted read never becomes a
 * silently truncated "All" result. No account or selector state is written. */
export async function loadCompleteMonitoring(context: InvestigationContext, revision: number, signal?: AbortSignal,
  read: ReadPage = getInvestigation): Promise<InvestigationEnvelope<MonitoringModel>> {
  let first: InvestigationEnvelope<MonitoringModel> | undefined, offset = 0;
  const companies: MonitoringModel['companies'] = [], seen = new Set<string>();
  for (;;) {
    signal?.throwIfAborted();
    const envelope = await read(`/monitoring?offset=${offset}&limit=100`, context, revision, signal);
    signal?.throwIfAborted();
    const page = envelope.data;
    const validGroups = Array.isArray(page?.tier_groups) && new Set(page.tier_groups.map(group => group.tier)).size === page.tier_groups.length
      && page.tier_groups.every(group => Number.isSafeInteger(group.count) && group.count >= 0 && Number.isSafeInteger(group.matching_count) && group.matching_count >= 0)
      && page.tier_groups.reduce((sum, group) => sum + group.count, 0) === page.universe_count
      && page.tier_groups.reduce((sum, group) => sum + group.matching_count, 0) === page.total;
    const invalid = !page || !Array.isArray(page.companies) || !Number.isSafeInteger(page.total) || page.total < 0
      || !Number.isSafeInteger(page.universe_count) || page.universe_count < page.total || !validGroups || typeof page.has_more !== 'boolean'
      || typeof page.company_set_key !== 'string' || page.matching_count !== page.total
      || page.offset !== offset || page.limit !== 100 || page.companies.length > 100
      || envelope.revision !== revision || page.company_set !== context.company_set
      || first && (envelope.scope_key !== first.scope_key || basis(page) !== basis(first.data));
    if (invalid) throw new InvestigationApiError('The company roster changed while loading. Reload it to read one complete company set.', 409);
    first ??= envelope;
    for (const company of page.companies) {
      if (company?.type !== 'company' || !/^[A-Za-z0-9_.-]{1,180}$/.test(company?.id ?? '') || ['.', '..'].includes(company.id) || seen.has(company.id))
        throw new InvestigationApiError('The company roster contains incompatible or repeated identities. Reload it before continuing.', 409);
      seen.add(company.id); companies.push(company);
    }
    if (companies.length > page.total) throw new InvestigationApiError('The company roster count changed. Reload the company set.', 409);
    if (!page.has_more) {
      if (page.next_offset !== null || companies.length !== page.total)
        throw new InvestigationApiError('The complete company roster could not be loaded. Try again.', 409);
      if (offset > 0) {
        const confirmed = await read('/monitoring?offset=0&limit=100', context, revision, signal);
        signal?.throwIfAborted();
        if (confirmed.scope_key !== first.scope_key || confirmed.revision !== revision
          || JSON.stringify(confirmed.data) !== JSON.stringify(first.data))
          throw new InvestigationApiError('The company roster changed during loading. Reload the company set.', 409);
      }
      return { ...first, data: { ...first.data, companies, offset: 0, limit: companies.length, has_more: false, next_offset: null } };
    }
    const next = offset + page.companies.length;
    if (!page.companies.length || page.next_offset !== next || next >= page.total)
      throw new InvestigationApiError('The company roster page sequence changed. Reload the company set.', 409);
    offset = next;
  }
}
