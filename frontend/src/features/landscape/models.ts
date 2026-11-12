export interface LandscapeNode {
  id: string;
  label: string;
  type: 'company' | 'variety' | 'breeding_program' | 'geography';
  identity_status: string;
  identity_note?: string;
  evidence_ids: string[];
}
export interface LandscapeEdge {
  id: string;
  subject_id: string;
  object_id: string;
  predicate: string;
  role: string;
  label: string;
  status: string;
  status_label: string;
  review: string;
  notes: string;
  caveat: string;
  location_label: string;
  scope_kind: string;
  evidence_ids: string[];
  company_geography: boolean;
  genetic_geography: boolean;
  href?: string;
}
export interface SourceMetadata {
  id: string;
  title: string;
  url?: string;
  source_name?: string;
  review?: string;
  published?: string | null;
  captured?: string | null;
  number?: number;
  varieties?: Array<{ id?: string; name: string; catalog_id?: string; href?: string; status?: string }>;
}
export interface Portrait {
  actor: LandscapeNode;
  programs: LandscapeNode[];
  varieties: LandscapeNode[];
  edges: LandscapeEdge[];
  portfolio_edges: LandscapeEdge[];
  markets: Array<{ country: string; edges: LandscapeEdge[] }>;
}
export interface CatalogOption {
  id: string;
  label: string;
  type: string;
  status: string;
  in_scope: boolean;
}
export interface RetainedSourceLink { url: string; label: string; kind: string }
export interface NewsDecision { reaction: 'up' | 'down' | null; saved: boolean }
export interface NewsTag { id: string; name: string; description?: string; version?: string | number }
export interface NewsCard {
  id: string;
  headline: string;
  deck?: string;
  source_name?: string;
  source_url?: string;
  source_link_url?: string;
  source_link_label?: string;
  full_reader_href?: string;
  published_at?: string | null;
  image_url?: string;
  reference_image?: { url: string; alt?: string; title?: string; label?: string; note?: string; credit?: string; creator?: string; license?: string; source_url?: string } | null;
  source_reviewed: boolean;
  trusted: boolean;
  translated?: boolean;
  translation_pending?: boolean;
  media_label?: string;
  media_note?: string;
  company_mentions?: Array<{ id: string; name: string }>;
  scope_match?: { kind: 'primary' | 'related_context'; primary_label: string; subject_labels: string[]; basis: 'recorded_link' | 'unreviewed_mention' };
  coverage_sources?: Array<{ id: string; source_name?: string; published_date?: string; captured_at?: string; captured_date?: string }>;
  independence?: string;
  retained_source_links?: RetainedSourceLink[];
  crop_labels?: string[];
  decision?: NewsDecision;
  entities?: Array<{ id: string; name: string; entity_type?: string; profile_url?: string; verification_status?: string; candidate?: boolean; tier?: string; favorite?: boolean; is_registry?: boolean; monogram?: string }>;
  geography_chips?: Array<{ id: string; name: string; href?: string }>;
  assigned_tags?: NewsTag[];
}
export interface DevelopmentsModel {
  cards: NewsCard[];
  basis: 'scope' | 'focus' | 'comparison';
  heading: string;
  briefing_href: string;
  matching_count: number;
  briefing_scope_note?: string;
}
export interface CompanyPage {
  company_set: 'all' | 'watched';
  basis: 'all_companies' | 'workspace_watches';
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
  next_offset: number | null;
}
export interface MonitoringCompany {
  id: string;
  label: string;
  type: 'company';
  identity_status: string;
  identity_note: string;
  roles: string[];
  berry_ids: string[];
  in_scope: boolean;
  watched: boolean;
  monitoring: { state: string; detail: string };
  geographies: Array<{ id: string; label: string; relationship_id: string; activity: string; status: string; review: string; caveat: string; evidence_ids: string[] }>;
}
export interface MonitoringModel extends CompanyPage {
  companies: MonitoringCompany[];
  universe_count: number;
  matching_count: number;
  search_basis: string;
  watched_count: number;
  unavailable_watch_count: number;
  scope_note: string;
}
export interface LandscapeNewsModel extends CompanyPage {
  cards: NewsCard[];
  sources: SourceMetadata[];
  heading: string;
  subject_count: number;
  matching_count: number;
  scope_applicability: Record<string, unknown>;
  briefing_href: string;
  briefing_scope_note: string;
}
export interface LandscapeModel {
  nodes: Record<string, LandscapeNode>;
  edges: LandscapeEdge[];
  sources: SourceMetadata[];
  market_rows: Portrait[];
  portfolios: Portrait[];
  findings: Array<{ id: string; text: string; relationship_ids: string[]; evidence_ids: string[] }>;
  scope_notes: string[];
  options: {
    countries: CatalogOption[];
    companies: CatalogOption[];
    varieties: CatalogOption[];
    matching_count: number;
    limit_per_type: number;
    search_basis: string;
  };
}
export interface Party { id: string; name: string; href?: string }
export interface CompanyComparison {
  comparison_kind: 'company';
  companies: Array<{
    id: string;
    name: string;
    roles: Record<string, Party[]>;
    geographies: Party[];
    berries: string[];
    rights_published: Array<{ id: string; title?: string; kind?: string; published_date?: string }>;
  }>;
  role_matrix: Array<{ bucket: string; label: string; counts: number[] }>;
  invalid_ids: string[];
  overflow_ids: string[];
}
export interface VarietyObservation {
  id: string;
  statement: string;
  fact_status?: string;
  evidence_id?: string;
  does_not_prove?: string[];
  geography?: Party[];
}
export interface VarietyComparison {
  comparison_kind: 'variety';
  varieties: Array<{ id: string; identity: { name?: string; display_name?: string; title?: string }; berries: string[]; roles: Record<string, Party[]>; countries_observed: Party[] }>;
  dimensions: Array<{ name: string; cells: Array<{ variety_id: string; rows: VarietyObservation[]; has_data: boolean }> }>;
  role_labels: Record<string, string>;
  invalid_ids: string[];
  overflow_ids: string[];
}
export type ComparisonModel = CompanyComparison | VarietyComparison;

export function safeHref(raw: string | null | undefined, fallback = '#'): string {
  if (!raw) return fallback;
  if (raw.startsWith('/') && !raw.startsWith('//') && !raw.includes('\\')) return raw;
  try {
    const url = new URL(raw);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : fallback;
  } catch { return fallback; }
}
