import { InvestigationApiError } from '../../api/client.ts';

export type MediaKind = 'logo' | 'profile_image' | 'pack_image' | 'pack_photo' | 'pack_render' | 'label_closeup' | 'shelf_observation' | 'campaign' | 'unclassified';
export interface BrandMediaAsset {
  id: string; entity_id: string; kind: MediaKind; kind_label: string; image_url: string;
  caption?: string; attribution?: string; source_page_url?: string; inspection_href?: string;
  published_at?: string; historical_status?: string; source_kind?: 'official' | 'retailer' | 'consumer' | 'unknown';
  source_account?: string; match_basis?: string; width?: number; height?: number;
}
export interface EntityBrandMedia {
  entity_id: string; entity_type: 'company' | 'brand' | 'retailer'; logo: BrandMediaAsset | null;
  packaging: BrandMediaAsset[]; observations: BrandMediaAsset[]; social_images: BrandMediaAsset[]; official_images: BrandMediaAsset[];
}
export interface BrandMediaResponse { version: 1; entities: Record<string, EntityBrandMedia> }
const ID = /^[A-Za-z0-9_.-]{1,180}$/;
const ASSET = /^asset-[a-f0-9]{24}$/;
const KINDS: readonly string[] = ['logo', 'profile_image', 'pack_image', 'pack_photo', 'pack_render', 'label_closeup', 'shelf_observation', 'campaign', 'unclassified'];

export function mediaEntityIds(input: readonly string[]): string[] {
  const ids = [...new Set(input)];
  if (!ids.length || ids.length > 20 || ids.some(id => !ID.test(id)))
    throw new InvestigationApiError('Choose 1–20 existing organizations for imagery.', 400);
  return ids;
}
export function publicMediaLink(value: unknown): string | undefined {
  if (typeof value !== 'string' || /[\x00-\x20\x7f\\]/.test(value)) return undefined;
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    return url.protocol === 'https:' && !url.username && !url.password && (!url.port || url.port === '443')
      && host.includes('.') && !/^[\d.]+$/.test(host) && !host.includes(':')
      && !host.endsWith('.local') && !host.endsWith('.internal') && !host.endsWith('.localhost') ? value : undefined;
  } catch { return undefined; }
}
export function mediaImageUrl(value: unknown): string | undefined {
  if (typeof value === 'string' && /^\/api\/brand-media\/asset-[a-f0-9]{24}\/image$/.test(value)) return value;
  return publicMediaLink(value);
}
export function mediaInspectionUrl(value: unknown): string | undefined {
  return typeof value === 'string' && /^\/api\/social\/ev-social-[a-f0-9]{24}\/reader\?media=metadata-only$/.test(value) ? value : undefined;
}
function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
function asset(value: unknown, entity: string): BrandMediaAsset | null {
  if (!object(value) || typeof value.id !== 'string' || !ASSET.test(value.id) || value.entity_id !== entity
      || !KINDS.includes(String(value.kind)) || typeof value.kind_label !== 'string') return null;
  const image = mediaImageUrl(value.image_url);
  if (!image) return null;
  const row: BrandMediaAsset = { id: value.id, entity_id: entity, kind: value.kind as MediaKind, kind_label: value.kind_label, image_url: image };
  for (const key of ['caption', 'attribution', 'published_at', 'historical_status', 'source_account', 'match_basis'] as const)
    if (typeof value[key] === 'string') row[key] = value[key];
  if (['official', 'retailer', 'consumer', 'unknown'].includes(String(value.source_kind))) row.source_kind = value.source_kind as BrandMediaAsset['source_kind'];
  row.source_page_url = publicMediaLink(value.source_page_url);
  row.inspection_href = mediaInspectionUrl(value.inspection_href);
  for (const key of ['width', 'height'] as const) if (Number.isSafeInteger(value[key]) && Number(value[key]) > 0) row[key] = Number(value[key]);
  return row;
}
export function parseBrandMedia(value: unknown, requested: readonly string[]): BrandMediaResponse {
  if (!object(value) || value.version !== 1 || !object(value.entities))
    throw new InvestigationApiError('The server returned incompatible media metadata.', 502);
  const entities: Record<string, EntityBrandMedia> = {};
  for (const [id, raw] of Object.entries(value.entities)) {
    if (!requested.includes(id) || !object(raw) || raw.entity_id !== id || !['company', 'brand', 'retailer'].includes(String(raw.entity_type)))
      throw new InvestigationApiError('The server returned incompatible media identities.', 502);
    const list = (key: string) => Array.isArray(raw[key]) ? raw[key].map(item => asset(item, id)).filter((item): item is BrandMediaAsset => !!item) : [];
    entities[id] = { entity_id: id, entity_type: raw.entity_type as EntityBrandMedia['entity_type'], logo: asset(raw.logo, id),
      packaging: list('packaging'), observations: list('observations'), social_images: list('social_images'), official_images: list('official_images') };
  }
  return { version: 1, entities };
}
/** Separate curated endpoint; never send this request through the investigation-envelope API. */
export async function getBrandMedia(input: readonly string[], signal?: AbortSignal): Promise<BrandMediaResponse> {
  const ids = mediaEntityIds(input);
  const response = await fetch(`/api/brand-media/entities?${new URLSearchParams({ ids: ids.join(',') })}`, {
    signal, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' },
  });
  if (response.redirected || response.status === 401 || response.status === 403)
    throw new InvestigationApiError('Sign in to inspect imagery.', 401);
  if (!response.ok) throw new InvestigationApiError('Imagery is unavailable.', response.status);
  if (!response.headers.get('content-type')?.includes('application/json'))
    throw new InvestigationApiError('The server returned incompatible media metadata.', 502);
  return parseBrandMedia(await response.json(), ids);
}
