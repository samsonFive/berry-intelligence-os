import { InvestigationApiError } from '../../api/client.ts';

export const EDITABLE_COMPANY_TIERS = [
  { value: 'tier1', label: 'Tier 1' }, { value: 'tier2', label: 'Tier 2' },
  { value: 'tier3', label: 'Tier 3' }, { value: 'untiered', label: 'Untiered' },
] as const;
export interface CompanyTierResult { id: string; assigned_tier: string; assigned_tier_label: string; changed: boolean }
export class CompanyTierConflict extends InvestigationApiError {
  current: Pick<CompanyTierResult, 'assigned_tier' | 'assigned_tier_label'>;
  constructor(current: CompanyTierConflict['current']) {
    super('This company’s tier changed in another tab. Reload the roster before saving again.', 409);
    this.current = current;
  }
}

/** One explicit authoritative mark, never a cohort/context/domain-record write. */
export async function saveCompanyTier(id: string, tier: string, expectedTier: string, signal?: AbortSignal): Promise<CompanyTierResult> {
  if (typeof id !== 'string' || !/^[A-Za-z0-9_.-]{1,180}$/.test(id) || ['.', '..'].includes(id)
      || typeof tier !== 'string' || typeof expectedTier !== 'string' || !expectedTier || expectedTier.length > 200
      || !EDITABLE_COMPANY_TIERS.some(option => option.value === tier) && tier !== expectedTier)
    throw new InvestigationApiError('Choose an available company and an explicit tier.', 400);
  const response = await fetch(`/api/investigations/v1/companies/${encodeURIComponent(id)}/tier`, {
    method: 'POST', credentials: 'same-origin', cache: 'no-store', signal,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ tier, expected_tier: expectedTier }),
  });
  if (response.redirected || response.status === 401 || response.status === 403) throw new InvestigationApiError('Sign in to change company tiers.', 401);
  const body = response.headers.get('content-type')?.includes('application/json') ? await response.json() : null;
  if (response.status === 409 && body?.detail?.code === 'tier_conflict' && body.detail.id === id
      && typeof body.detail.assigned_tier === 'string' && typeof body.detail.assigned_tier_label === 'string')
    throw new CompanyTierConflict({ assigned_tier: body.detail.assigned_tier, assigned_tier_label: body.detail.assigned_tier_label });
  if (!response.ok) {
    const message = typeof body?.detail === 'string' ? body.detail : body?.detail?.message;
    throw new InvestigationApiError(typeof message === 'string' ? message.slice(0, 500) : 'The company tier could not be saved.', response.status);
  }
  const result = body?.data;
  if (body?.api_v !== 1 || typeof body.request_id !== 'string' || result?.id !== id || result.assigned_tier !== tier
      || typeof result.assigned_tier_label !== 'string' || typeof result.changed !== 'boolean')
    throw new InvestigationApiError('The server returned incompatible company-tier metadata.', 502);
  return result as CompanyTierResult;
}
