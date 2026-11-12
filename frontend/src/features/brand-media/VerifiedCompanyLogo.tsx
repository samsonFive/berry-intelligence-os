import { useMemo, useState } from 'react';
import { companyLogoBatch } from './company-logo-batches';
import { useBrandMedia } from './useBrandMedia';
import { BrandLogo } from './BrandMedia';
import './verified-company-logo.css';

/** Curated company logos only; no discovery, fallback brand or image acquisition.
 * The query lives in the logo child, never in an AG column-definition owner. */
export function VerifiedCompanyLogo({ id, name, companyIds, className = '', inspectable = false }: {
  id: string; name: string; companyIds?: readonly string[]; className?: string; inspectable?: boolean;
}) {
  const key = companyIds?.join('\u0000') ?? id;
  const batch = useMemo(() => companyLogoBatch(id, companyIds), [id, key]);
  const media = useBrandMedia(batch), entity = media?.[id];
  const asset = entity?.entity_type === 'company' ? entity.logo : null;
  const [failed, setFailed] = useState('');
  const identity = asset ? `${asset.id}:${asset.image_url}` : '';
  if (!asset || failed === identity) return null;
  if (inspectable) return <div className={`berry-verified-company-logo berry-verified-company-logo--inspectable ${className}`}><BrandLogo asset={asset} name={name} /></div>;
  const credit = [asset.caption, asset.attribution, asset.historical_status === 'historical' ? 'Historical reference' : ''].filter(Boolean).join(' · ');
  return <span className={`berry-verified-company-logo ${className}`} title={credit || `${name} logo`}>
    <img src={asset.image_url} alt={`${name} logo`} width="64" height="28" decoding="async" referrerPolicy="no-referrer"
      data-background={asset.background} onError={() => setFailed(identity)} />
    {credit && <span className="berry-verified-logo-credit">{credit}</span>}
  </span>;
}
