import type { LayoutColumn } from '../grids/layout-codec.ts';
import type { LandscapeModel, MonitoringCompany } from './models.ts';
import { rosterGenetics } from './roster-genetics.ts';

export const COMPANY_TIER_BUCKETS = ['tier1', 'tier2', 'tier3', 'untiered', 'watch', 'muted', 'other_legacy'] as const;
export const TIER_HEADER_FILTER = '\u0000berry-tier-header\u0000';
export interface RosterTierGroup { tier: string; label: string; count: number; matching_count: number }
export interface RosterTierHeader { row_kind: 'tier'; id: string; tier: string; label: string; count: number | null; matching_count: number | null; loaded_count: number }
export type CompanyRosterRow = MonitoringCompany | RosterTierHeader;
export const isRosterTierHeader = (row: CompanyRosterRow | undefined): row is RosterTierHeader => !!row && 'row_kind' in row && row.row_kind === 'tier';
export const companyTierBucket = (tier: string) => COMPANY_TIER_BUCKETS.includes(tier as typeof COMPANY_TIER_BUCKETS[number]) && tier !== 'other_legacy' ? tier : 'other_legacy';

/** Synthetic headers are presentation only. Every real company keeps its ID/reference. */
export function companyTierRows(companies: readonly MonitoringCompany[], groups: readonly RosterTierGroup[]): CompanyRosterRow[] {
  return COMPANY_TIER_BUCKETS.flatMap(tier => {
    const rows = companies.filter(company => companyTierBucket(company.assigned_tier) === tier);
    if (!rows.length) return [];
    const group = groups.find(group => group.tier === tier);
    return [{ row_kind: 'tier', id: `roster-tier-${tier}`, tier, label: group?.label ?? 'Tier metadata unavailable',
      count: group?.count ?? null, matching_count: group?.matching_count ?? null, loaded_count: rows.length } as RosterTierHeader, ...rows];
  });
}

/** User sort applies within the existing tier hierarchy, never across it. */
export function orderCompanyTierNodes<T extends { data?: CompanyRosterRow }>(nodes: readonly T[]): T[] {
  return COMPANY_TIER_BUCKETS.flatMap(tier => [
    ...nodes.filter(node => isRosterTierHeader(node.data) && node.data.tier === tier),
    ...nodes.filter(node => node.data && !isRosterTierHeader(node.data) && companyTierBucket(node.data.assigned_tier) === tier),
  ]);
}

/** Standard Community text matching, with presentation headers always retained. */
export function rosterTextMatch({ data, value, filterText, filterOption }: { data?: CompanyRosterRow; value: unknown; filterText: string | null; filterOption?: string | null }): boolean {
  if (isRosterTierHeader(data)) return true;
  const text = String(value ?? ''), filter = filterText ?? '';
  switch (filterOption) {
    case 'equals': return text === filter;
    case 'notEqual': return text !== filter;
    case 'contains': return text.includes(filter);
    case 'notContains': return !text.includes(filter);
    case 'startsWith': return text.startsWith(filter);
    case 'endsWith': return text.endsWith(filter);
    default: return false;
  }
}

/** Fixed semantic columns: changing a company page never creates another layout. */
export const COMPANY_ROSTER_VIEW_KEY = 'berry-company-roster-v1';
export const COMPANY_ROSTER_COLUMNS: readonly (LayoutColumn & { label: string })[] = [
  { colId: 'company.identity', label: 'Company / comparison', defaultWidth: 210, minWidth: 170, maxWidth: 1200, lockedVisible: true },
  { colId: 'company.genetics', label: 'Genetics / portfolio', defaultWidth: 360, minWidth: 250, maxWidth: 1200 },
  { colId: 'company.roles', label: 'Authored roles / berries', defaultWidth: 185, minWidth: 140, maxWidth: 1200 },
  { colId: 'company.geography', label: 'Geographic activity', defaultWidth: 240, minWidth: 180, maxWidth: 1200 },
  { colId: 'company.collection', label: 'Collection context', defaultWidth: 180, minWidth: 150, maxWidth: 1200, defaultHidden: true },
];

/** Full authored values feed AG Grid sorting/filtering and the same Cards model. */
export function companyRosterText(company: MonitoringCompany, model: LandscapeModel): Record<string, string> {
  const genetics = rosterGenetics(model, company.id);
  const nodeLabel = (id: string) => model.nodes[id]?.label ?? id;
  return {
    'company.identity': [company.label, company.identity_note, company.assigned_tier_label, company.in_scope ? '' : 'No standing links in this scope', company.watched ? 'Shared watch' : ''].filter(Boolean).join(' · '),
    'company.genetics': [...genetics.programs.map(node => node.label), ...genetics.varieties.map(node => node.label),
      ...genetics.edges.map(edge => [nodeLabel(edge.subject_id), edge.role, nodeLabel(edge.object_id), edge.status_label, edge.caveat, edge.notes].filter(Boolean).join(' · '))].join('; '),
    'company.roles': [...company.roles.map(role => role.replaceAll('_', ' ')), ...company.berry_ids.map(id => id.replace(/^berry-/, '').replaceAll('-', ' '))].join(' · '),
    'company.geography': company.geographies.map(geo => [geo.label, geo.activity, geo.status, geo.review, geo.caveat].filter(Boolean).join(' · ')).join('; '),
    'company.collection': [company.monitoring.state.replaceAll('_', ' '), company.monitoring.detail].filter(Boolean).join(' · '),
  };
}
