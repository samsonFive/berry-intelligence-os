/** Company-column windows are local display state, independent of cohorts/scope. */
export const COMPANY_COLUMNS_PER_PAGE = 10;
export const COMPANY_COLUMN_SIZES = [10, 25, 50, 'all'] as const;
export type CompanyColumnSize = typeof COMPANY_COLUMN_SIZES[number];
export const DEFAULT_COMPANY_COLUMN_SIZE: CompanyColumnSize = 25;
export const validCompanyColumnSize = (value: unknown): value is CompanyColumnSize => COMPANY_COLUMN_SIZES.some(size => size === value);
export const LEGACY_PORTFOLIO_VIEW_KEY = 'berry-portfolio-v1';

export interface CompanyPage<T> {
  companies: T[]; total: number; index: number; count: number;
  start: number; end: number; paged: boolean; size: number; choice: CompanyColumnSize; membershipBound: boolean;
}

export function companyPage<T extends { id: string }>(companies: readonly T[], requested = 0, choice: CompanyColumnSize = COMPANY_COLUMNS_PER_PAGE): CompanyPage<T> {
  if (!validCompanyColumnSize(choice)) throw new Error('Choose a supported company-column display size.');
  if (companies.some(company => !/^[A-Za-z0-9_.-]{1,180}$/.test(company.id)) || new Set(companies.map(company => company.id)).size !== companies.length)
    throw new Error('Company columns need distinct recorded identities. No saved layout was changed.');
  const size = choice === 'all' ? Math.max(1, companies.length) : choice;
  const membershipBound = companies.length > COMPANY_COLUMNS_PER_PAGE;
  const paged = companies.length > size;
  // Membership remains stable across label edits or reordered API results.
  const ordered = membershipBound ? [...companies].sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0) : [...companies];
  const count = Math.max(1, Math.ceil(ordered.length / size));
  const index = Math.max(0, Math.min(count - 1, Number.isFinite(requested) ? Math.floor(requested) : 0));
  const start = index * size, end = Math.min(start + size, ordered.length);
  return { companies: ordered.slice(start, end), total: ordered.length, index, count, start, end, paged, size, choice, membershipBound };
}

export async function companyPageViewKey(ids: readonly string[], paged: boolean): Promise<string> {
  if (new Set(ids).size !== ids.length || ids.some(id => !/^[A-Za-z0-9_.-]{1,180}$/.test(id)) || !paged && ids.length > COMPANY_COLUMNS_PER_PAGE)
    throw new Error('The company-column group could not be identified safely.');
  if (!paged) return LEGACY_PORTFOLIO_VIEW_KEY;
  const identity = `berry-portfolio-company-page:v2\0${JSON.stringify([...ids].sort())}`;
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(identity));
  return `berry-pg-v2-${Array.from(new Uint8Array(digest)).map(byte => byte.toString(16).padStart(2, '0')).join('')}`;
}

export function companyPageSwitchBlocked(phase: string): boolean {
  return ['loading', 'pending', 'saving', 'conflict'].includes(phase);
}
