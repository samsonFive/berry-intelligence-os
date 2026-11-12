export interface ReaderOrganization {
  id: string; name: string; kind: 'company' | 'brand'; association: 'linked' | 'mentioned';
}
interface SourceAssociations {
  entities?: Array<{ id: string; name: string; entity_type?: string }>;
  company_mentions?: Array<{ id: string; name: string }>;
}

/** Use only source associations; publishers, pins and detail ancestry are unrelated. */
export function readerOrganizations(card?: SourceAssociations): ReaderOrganization[] {
  const companies = new Map<string, ReaderOrganization>();
  for (const entity of card?.entities ?? []) {
    const kind = /^company-[A-Za-z0-9_.-]+$/.test(entity.id) ? 'company'
      : /^brand-[A-Za-z0-9_.-]+$/.test(entity.id) ? 'brand' : null;
    if (kind && entity.id.length <= 180 && (!entity.entity_type || entity.entity_type === kind))
      companies.set(entity.id, { id: entity.id, name: entity.name, kind, association: 'linked' });
  }
  for (const mention of card?.company_mentions ?? []) {
    if (!companies.has(mention.id) && mention.id.length <= 180 && /^company-[A-Za-z0-9_.-]+$/.test(mention.id))
      companies.set(mention.id, { id: mention.id, name: mention.name, kind: 'company', association: 'mentioned' });
  }
  return [...companies.values()];
}
