import { useEffect, useRef, useState } from 'react';
import { Button, Preview, SourceLink } from '../../components/ui';
import type { BrandMediaAsset, EntityBrandMedia } from './api';
import './brand-media.css';

const sourceLabel = { official: 'Official imagery', retailer: 'Retailer observation', consumer: 'Consumer sighting', unknown: '' };
function Context({ asset }: { asset: BrandMediaAsset }) {
  return <dl className="berry-brand-context">
    {asset.source_account && <div><dt>Account</dt><dd>{asset.source_account}</dd></div>}
    {asset.published_at && <div><dt>Published</dt><dd>{asset.published_at.slice(0, 10)}</dd></div>}
    {asset.match_basis && <div><dt>Identity basis</dt><dd>{asset.match_basis}</dd></div>}
  </dl>;
}
function Credit({ asset }: { asset: BrandMediaAsset }) {
  return asset.attribution ? <small className="berry-brand-credit">{asset.attribution}</small> : null;
}
function ImageInspector({ assets, selected, select, close, returnTo, broken }: {
  assets: BrandMediaAsset[]; selected: BrandMediaAsset; select: (id: string) => void; close: () => void;
  returnTo: HTMLElement | null; broken: (asset: BrandMediaAsset) => void;
}) {
  const closeButton = useRef<HTMLButtonElement>(null);
  const initialReturn = useRef(returnTo);
  const index = assets.findIndex(asset => asset.id === selected.id);
  const move = (step: number) => select(assets[(index + step + assets.length) % assets.length].id);
  useEffect(() => {
    closeButton.current?.focus({ preventScroll: true });
    closeButton.current?.scrollIntoView({ block: 'nearest' });
    return () => {
      const target = initialReturn.current;
      if (target?.isConnected && target.getClientRects().length) {
        target.focus({ preventScroll: true }); target.scrollIntoView({ block: 'nearest' });
      }
    };
  }, []);
  // Expansion stays in the current gallery's allocated content. Preview owns
  // hover/focus context; there is no second modal/Reader/Ask overlay controller.
  return <section className="berry-brand-inspector" aria-label="Image inspection"
    onKeyDown={event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); }
      if (assets.length > 1 && ['ArrowLeft', 'ArrowRight'].includes(event.key)) {
        event.preventDefault(); event.stopPropagation(); move(event.key === 'ArrowLeft' ? -1 : 1);
      }
    }}>
    <header><h3>{selected.caption || selected.kind_label}</h3><Button ref={closeButton} size="small" onClick={close} aria-label="Close image inspection">×</Button></header>
    <img className="berry-brand-expanded" src={selected.image_url} alt={selected.caption || selected.kind_label}
      referrerPolicy="no-referrer" onError={() => broken(selected)} />
    <p>{selected.kind_label}{selected.source_kind && sourceLabel[selected.source_kind] ? ` · ${sourceLabel[selected.source_kind]}` : ''}
      {selected.historical_status === 'historical' ? ' · Historical reference' : ''}</p>
    <Credit asset={selected} /><Context asset={selected} />
    <footer>{assets.length > 1 && <><Button size="small" onClick={() => move(-1)} aria-label="Previous image">←</Button><span>{index + 1} / {assets.length}</span><Button size="small" onClick={() => move(1)} aria-label="Next image">→</Button></>}
      {selected.inspection_href && <SourceLink external href={selected.inspection_href}>Inspect retained source</SourceLink>}
      {selected.source_page_url && <SourceLink external href={selected.source_page_url}>Original source</SourceLink>}
    </footer>
  </section>;
}
function failureKey(asset: BrandMediaAsset) { return `${asset.id}:${asset.image_url}`; }

export function BrandLogo({ asset, name }: { asset?: BrandMediaAsset | null; name: string }) {
  const [failed, setFailed] = useState('');
  const [open, setOpen] = useState(false);
  const figure = useRef<HTMLElement>(null);
  useEffect(() => { setOpen(false); }, [asset?.id, asset?.image_url]);
  if (!asset || failed === failureKey(asset)) return null;
  return <div className={`berry-brand-logo-area${open ? ' berry-brand-logo-area--expanded' : ''}`}><figure ref={figure} className="berry-brand-logo">
    <Preview label="Image source" detailLabel="Inspect image" content={<Context asset={asset} />}
      onOpenDetail={() => setOpen(true)}><img src={asset.image_url} alt={`${name} logo`} width="100" height="64"
        decoding="async" referrerPolicy="no-referrer" onError={() => setFailed(failureKey(asset))} /></Preview>
    <Credit asset={asset} />
  </figure>
    {open && <ImageInspector assets={[asset]} selected={asset} select={() => {}} close={() => setOpen(false)}
      returnTo={figure.current?.querySelector('button') ?? null} broken={item => setFailed(failureKey(item))} />}
  </div>;
}

export function BrandMediaGallery({ model, compact = false }: { model?: EntityBrandMedia; compact?: boolean }) {
  const [failed, setFailed] = useState<Set<string>>(() => new Set());
  const [active, setActive] = useState<string | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const groups = model ? [
    { key: 'packaging', title: 'Retail Packaging', assets: model.packaging },
    ...compact ? [] : [
      { key: 'observations', title: 'Retail observations', assets: model.observations },
      { key: 'official_images', title: 'Official imagery', assets: model.official_images },
      { key: 'social_images', title: 'Social imagery', assets: model.social_images },
    ],
  ].map(group => ({ ...group, assets: group.assets.filter(asset => !failed.has(failureKey(asset))) })).filter(group => group.assets.length) : [];
  const assets = groups.flatMap(group => group.assets);
  const selected = assets.find(asset => asset.id === active);
  useEffect(() => { if (active && !selected) setActive(null); }, [active, selected?.id]);
  const broken = (asset: BrandMediaAsset) => setFailed(previous => new Set([...previous, failureKey(asset)]));
  if (!assets.length) return null;
  return <div ref={root} className={`berry-brand-galleries${compact ? ' berry-brand-galleries--compact' : ''}`}>
    {groups.map(group => <section className="berry-brand-gallery" key={group.key} aria-label={group.title}>
      {!compact && <h3>{group.title}</h3>}<div className="berry-brand-grid">
        {group.assets.map(asset => <figure className="berry-brand-card" key={asset.id} data-media-asset-id={asset.id}>
          <Preview label="Supporting image context" detailLabel="Inspect image" content={<Context asset={asset} />}
            onOpenDetail={() => {
              opener.current = root.current?.querySelector<HTMLElement>(`[data-media-asset-id="${asset.id}"] button`) ?? null;
              setActive(asset.id);
            }}>
            <img src={asset.image_url} alt={asset.caption || asset.kind_label} width="300" height="210" loading="lazy"
              decoding="async" referrerPolicy="no-referrer" onError={() => broken(asset)} />
          </Preview>
          <figcaption><span>{asset.kind_label}{asset.source_kind && sourceLabel[asset.source_kind] ? ` · ${sourceLabel[asset.source_kind]}` : ''}</span>
            {asset.caption && <span>{asset.caption}</span>}
            {asset.historical_status === 'historical' && <span>Historical reference</span>}
            {asset.published_at && <span>Published {asset.published_at.slice(0, 10)}</span>}<Credit asset={asset} />
          </figcaption>
        </figure>)}
      </div>
    </section>)}
    {selected && <ImageInspector assets={assets} selected={selected} select={setActive} close={() => setActive(null)}
      returnTo={opener.current} broken={broken} />}
  </div>;
}
