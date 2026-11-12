/** Ports the existing Learn teaching templates; no generated science or media. */
import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import type { LearningResource, TeachingDiagramModel } from './models';
import { safeSourceHref } from './markdown';
import './learn-teaching.css';

function TeachingIcon({ kind }: { kind: string }) {
  const icons: Record<string, ReactNode> = {
    search: <><circle cx="27" cy="27" r="15"/><path d="m38 38 15 15M19 27h16M27 19v16"/></>,
    eye: <><path d="M5 32q27-32 54 0-27 32-54 0Z"/><circle cx="32" cy="32" r="9"/></>,
    leaf: <path d="M14 51C5 18 32 9 52 12c0 26-13 43-38 39Zm0 0 30-30"/>,
    branch: <><path d="M32 55V29M32 29 14 12M32 29l18-17M8 19V8h11M45 8h11v11"/><circle cx="32" cy="43" r="5"/></>,
    tools: <path d="m13 52 31-31M40 8c-3 13 1 18 15 17M49 8l6 6M12 13l37 37M8 11l5-5 12 9-7 7Z"/>,
    loop: <path d="M51 23A21 21 0 1 0 52 42M51 10v14H37"/>,
    drop: <><path d="M32 6C24 18 13 29 13 39a19 19 0 0 0 38 0C51 29 40 18 32 6Z"/><path d="M22 40q0 8 9 9"/></>,
    air: <path d="M8 22h31q16 0 10-12M8 33h42q13 0 8 12M8 44h23q11 0 7 11"/>,
    berry: <><circle cx="32" cy="34" r="19"/><path d="M25 14q-1-9 7-10 7 0 8 10M21 29h1M33 26h1M44 32h1M25 41h1M37 44h1"/></>,
    shield: <><path d="M32 6 52 14v18q0 16-20 26-20-10-20-26V14Z"/><path d="m22 31 7 7 15-16"/></>,
    sun: <><circle cx="32" cy="32" r="12"/><path d="M32 3v9M32 52v9M3 32h9M52 32h9M11 11l7 7M46 46l7 7M11 53l7-7M46 18l7-7"/></>,
    moon: <path d="M44 8A24 24 0 1 0 56 44 25 25 0 0 1 44 8Z"/>,
    thermometer: <><path d="M25 36V12a7 7 0 0 1 14 0v24a14 14 0 1 1-14 0ZM32 20v28M46 15h9M46 25h6"/><circle cx="32" cy="48" r="4"/></>,
    calendar: <><rect x="9" y="12" width="46" height="43" rx="4"/><path d="M9 24h46M21 6v13M43 6v13m-22 16h7m8 0h7M21 45h7m8 0h7"/></>,
    roots: <path d="M32 5v22M32 21Q11 23 12 7q18-1 20 14Zm0-3Q51 20 52 5q-18-1-20 13ZM6 28h52M32 28v30M32 37 18 47M32 45l14 10M20 45l-7-4M44 53l7-3"/>,
    bed: <><path d="M5 49 17 29h30l12 20M5 49h54M32 29V10M32 22Q16 25 15 12q14-1 17 10Zm0-5q14 2 17-12-14-1-17 12Z"/><circle cx="24" cy="39" r="3"/><path d="M36 37v8M42 37v8"/></>,
    flower: <><path d="M32 38v22M32 49q-14 2-16-9 13-1 16 9Z"/><path d="M27 15c-7-18-21 0-10 7-18 5-5 24 6 14 0 18 20 18 18 0 14 9 24-10 7-14 8-16-12-24-15-8Z"/><circle cx="32" cy="26" r="6"/></>,
    ruler: <path d="m9 44 35-35 12 12-35 35ZM20 33l7 7M29 24l7 7M38 15l7 7"/>,
    scale: <path d="M32 12v44M12 20h40M22 56h20M14 20 5 39h18Zm36 0-9 19h18Z"/>,
    trellis: <path d="M12 8v50M52 8v50M6 19h52M6 40h52M31 58V15M31 36 19 25M31 28l14-16M31 49l14-13"/>,
    box: <path d="m10 20 22-12 22 12v26L32 58 10 46ZM10 20l22 12 22-12M32 32v26"/>,
  };
  return <svg className="berry-learn-icon" viewBox="0 0 64 64" aria-hidden="true" focusable="false">{icons[kind] ?? icons.box}</svg>;
}

/** Exact qualitative SVG/caption content from _learn_curriculum_schematic.html. */
function CurriculumIllustration({ kind, slug }: { kind?: string; slug?: string }) {
  const id = useId();
  const labels: Record<string, { title: string; description: string; caption: string }> = {
    wax: { title: 'Light meeting the wax coating above blueberry skin', description: 'Light reaches an irregular wax surface. Some light scatters back; darker pigmented skin lies underneath. Layers are enlarged and not to scale.', caption: 'The outer coating and the skin are different layers. Enlarged schematic; no measured spectrum or thickness.' },
    bed: { title: 'Cross-section of a covered, raised planting bed', description: 'A plant grows through an opening in plastic mulch over a raised bed. A drip line sits below the surface. This is not a tunnel or a dimensioned plan.', caption: 'The cover sits on the bed; water reaches the root area through drip irrigation. Components are illustrative.' },
    roots: { title: 'The root zone connects plant and soil conditions', description: 'Roots extend from a plant into soil containing water-filled spaces. The diagram does not show measured pH, a pathogen or a diagnosed plant.', caption: slug === 'phytophthora' ? 'Water-filled soil pores can provide a route for swimming spores. No pathogen is depicted or diagnosed here.' : 'Acidity and drainage describe different parts of the root environment. A soil test measures what this drawing cannot.' },
    trellis: { title: 'Canes arranged on a simple support', description: 'Two posts support horizontal wires. Branched canes are arranged between them. Heights, pruning cuts and fruiting stages are not specified.', caption: 'A front view of support and trained growth. A real design follows the crop, growth habit and harvest system.' },
    compression: { title: 'A simplified fruit compression test', description: 'An upper plate moves toward a berry resting on a base. The drawing describes compression, not puncture, and supplies no force or calibration.', caption: 'Resistance depends on the test and the sample. This is a qualitative compression schematic, with no numeric result.' },
  };
  const label = kind ? labels[kind] : undefined;
  if (!label) return null;
  return <figure className="berry-learn-mechanism"><svg viewBox="0 0 360 180" role="img" aria-labelledby={`${id}-title ${id}-desc`}>
    <title id={`${id}-title`}>{label.title}</title><desc id={`${id}-desc`}>{label.description}</desc>
    {kind === 'wax' && <><path className="berry-learn-skin" d="M35 128h290v34H35Z"/><path className="berry-learn-wax" d="m35 126 14-12 11 10 15-19 14 15 16-16 12 19 16-17 14 15 14-18 12 20 16-15 14 12 17-19 13 17 15-11 16 15 15-18 14 11 13-8 14 16Z"/><path className="berry-learn-light" d="m80 31 70 64m-15-2 15 2-3-15m24 2 44-57m-14 4 14-4-1 14m-34 48 87-26m-13-5 13 5-8 11"/><text x="37" y="22">Light in</text><text x="214" y="26">Scattered light</text><text x="43" y="91">Wax</text><text x="45" y="152" fill="white">Pigmented skin</text></>}
    {kind === 'bed' && <><path className="berry-learn-soil" d="m30 151 50-59h200l50 59Z"/><path className="berry-learn-cover" d="m30 151 50-59h83m35 0h82l50 59"/><path className="berry-learn-stem" d="M180 102V32m0 30q-31-1-35-25 28-3 35 25Zm0-12q22-2 29-26-27-1-29 26Z"/><path className="berry-learn-roots" d="M180 102v35m0-24-23 15m23-5 22 16"/><circle className="berry-learn-water" cx="127" cy="109" r="7"/><text x="11" y="71">Plastic mulch</text><text x="211" y="164">Raised bed</text><text x="64" y="171">Drip line</text><path className="berry-learn-callout" d="m75 75 17 16m18 62 15-35"/></>}
    {kind === 'roots' && <><path className="berry-learn-soil" d="M20 86h320v79H20Z"/><path className="berry-learn-stem" d="M173 94V28m0 26q-30 0-35-26 29-2 35 26Zm0-10q25 0 30-26-25-2-30 26Z"/><path className="berry-learn-roots" d="M173 92v63m0-53-28 18m28-7 30 17m-58-10-19 19m37-13-8 24m41-22 24 15m-50-4 14 20"/><path className="berry-learn-water" d="M71 106q-15 19 0 24 15-5 0-24Zm199 13q-14 19 0 24 14-5 0-24Z"/><text x="229" y="60">Root zone</text><path className="berry-learn-callout" d="m249 66-39 49"/></>}
    {kind === 'trellis' && <><path className="berry-learn-post" d="M55 25v134M305 25v134"/><path className="berry-learn-wire" d="M45 61h270M45 114h270"/><path className="berry-learn-stem" d="M179 160V46m0 48-60-34m60 62 59-62m-59 84-81-30m81-5 55-16"/><circle className="berry-learn-water" cx="120" cy="61" r="5"/><circle className="berry-learn-water" cx="238" cy="61" r="5"/><text x="71" y="25">Support wires</text><text x="207" y="174">Trained canes</text></>}
    {kind === 'compression' && <><circle className="berry-learn-fruit" cx="180" cy="105" r="32"/><path className="berry-learn-cover" d="M137 61h86M135 141h90M180 61V35"/><path className="berry-learn-light" d="M180 7v21m-7-9 7 9 7-9"/><path className="berry-learn-callout" d="m76 61 52 0m106 80h47"/><text x="20" y="48">Plate</text><text x="242" y="127">Base</text><text x="143" y="172">Fruit sample</text></>}
  </svg><figcaption>{label.caption}</figcaption></figure>;
}

export function TeachingDiagram({ diagram, slug }: { diagram: TeachingDiagramModel; slug?: string }) {
  const id = useId();
  const [selection, setSelection] = useState({ title: diagram.title, index: 0 });
  const selected = selection.title === diagram.title && selection.index < diagram.steps.length ? selection.index : 0;
  return <section className="berry-learn-teaching" aria-labelledby={`${id}-title`}>
    <p className="berry-eyebrow">Illustrative teaching diagram</p><h2 id={`${id}-title`}>{diagram.title}</h2><p>{diagram.intro}</p>
    <CurriculumIllustration kind={diagram.illustration} slug={slug}/>
    <div className="berry-learn-steps" role="group" aria-label={diagram.mode === 'process' ? 'Explore the process' : 'Compare the parts of the explanation'}>
      {diagram.steps.map((step, index) => <article key={index}><span aria-hidden="true">{String(index + 1).padStart(2, '0')}</span><TeachingIcon kind={step.icon}/>
        <h3><button type="button" aria-pressed={selected === index} aria-controls={`${id}-step-${index}`} onClick={() => setSelection({ title: diagram.title, index })}>{step.title}</button></h3><p>{step.caption}</p>
      </article>)}
    </div>
    <div className="berry-learn-step-detail" aria-live="polite" aria-atomic="true">{diagram.steps.map((step, index) => <article key={index} id={`${id}-step-${index}`} hidden={selected !== index}><h3>{step.title}</h3><p>{step.detail}</p></article>)}</div>
    <p className="berry-learn-limit">{diagram.limit}</p>
    <footer><small>{diagram.attribution || 'Original schematic by Berry Intelligence; no publisher graphics copied.'} Sources checked {diagram.checked_on || 'October 2, 2026'}.</small>
      {diagram.sources.map((source, index) => { const href = safeSourceHref(source.url); return href ? <a key={index} href={href} target="_blank" rel="noopener noreferrer">{source.title} ↗</a> : null; })}</footer>
  </section>;
}

export function LearningFigure({ figure }: { figure: LearningResource }) {
  const image = safeSourceHref(figure.image_url), source = safeSourceHref(figure.url), license = safeSourceHref(figure.license_url);
  // Only the API's curated teaching figure may display an image. A vague reuse
  // statement on ordinary media remains a source link, matching legacy Learn.
  if (!image || !figure.license || !figure.attribution) return source
    ? <p><a href={source} target="_blank" rel="noopener noreferrer">{figure.title || 'Teaching image at source'}</a></p> : null;
  return <figure className="berry-learn-photo"><img src={image} alt={figure.alt || figure.title || 'Teaching photograph'} loading="lazy" referrerPolicy="no-referrer"/>
    <figcaption>{figure.caption}<small>{figure.attribution}</small>{source && <a href={source} target="_blank" rel="noopener noreferrer">Photo source</a>}
      {license ? <> · <a href={license} target="_blank" rel="noopener noreferrer">{figure.license}</a></> : <span> · {figure.license}</span>}</figcaption></figure>;
}

export function TeachingResources({ resources }: { resources: LearningResource[] }) {
  return <section className="berry-learn-resources"><h2>Teaching visuals</h2><p>Illustrations explain the idea; they are not Evidence about a particular farm.</p>
    {resources.map((resource, index) => { const href = safeSourceHref(resource.url); return <article key={index}>
      <p>{resource.kind && <span>{resource.kind} · </span>}{href ? <a href={href} target="_blank" rel="noopener noreferrer">{resource.title}</a> : resource.title}</p>
      {resource.publisher && <small>{resource.publisher}</small>}{resource.caption && <p>{resource.caption}</p>}
      {resource.reuse_basis && <small>{resource.reuse_basis}</small>}
      {resource.attribution && <small>{resource.attribution}</small>}
      {resource.license && <small>{safeSourceHref(resource.license_url)
        ? <a href={safeSourceHref(resource.license_url)} target="_blank" rel="noopener noreferrer">{resource.license}</a> : resource.license}</small>}
      {safeSourceHref(resource.source_page) && <a href={safeSourceHref(resource.source_page)} target="_blank" rel="noopener noreferrer">Source page</a>}
    </article>; })}
  </section>;
}

function Cane({ secondYear, fruit }: { secondYear?: boolean; fruit: boolean }) {
  return <svg viewBox="0 0 260 170" role="img" aria-label={secondYear ? 'Second-year floricane bearing fruit' : 'First-year cane growing; primocane-fruiting types may also bear fruit'}>
    <path d="M20 156H240M128 156Q112 100 137 15M128 86Q80 74 60 40M129 105Q182 91 202 53" fill="none" stroke={secondYear ? '#8c6e45' : '#4c8b43'} strokeWidth="5"/>
    <ellipse cx="78" cy="52" rx="24" ry="10" transform="rotate(30 78 52)" fill={secondYear ? '#7b9f55' : '#8abb5e'}/><ellipse cx="183" cy="67" rx="24" ry="10" transform="rotate(-30 183 67)" fill={secondYear ? '#7b9f55' : '#8abb5e'}/>
    {fruit && <g><circle cx="60" cy="45" r="13" fill="#b72d65"/><circle cx="202" cy="58" r="13" fill="#b72d65"/></g>}
  </svg>;
}

/** Existing authored cane-year teaching behavior; the explanation is not a crop score. */
export function CaneCalendar({ sourceLink }: { sourceLink?: ReactNode } = {}) {
  const [primocane, setPrimocane] = useState(false);
  return <section className="berry-learn-teaching berry-learn-cane"><p className="berry-eyebrow">Illustrative teaching diagram</p><h2>Follow the cane, then the fruit.</h2>
    <div role="group" aria-label="Fruiting habit"><button type="button" aria-pressed={!primocane} onClick={() => setPrimocane(false)}>Floricane-fruiting</button><button type="button" aria-pressed={primocane} onClick={() => setPrimocane(true)}>Primocane-fruiting</button></div>
    <p role="status">{primocane ? 'Primocane-fruiting types can bear fruit in the cane’s first year. Retaining part of the cane can allow a second-year crop; not every region or production system uses both crops.' : 'Floricane-fruiting types grow a cane in its first year and bear fruit on that cane in its second year.'}</p>
    <div className="berry-learn-cane-stages"><article><span>Year 1</span><Cane fruit={primocane}/><h3>Primocane</h3><p>{primocane ? 'May fruit on first-year canes' : 'First-year growth'}</p></article><span aria-hidden="true">→</span><article><span>Year 2</span><Cane secondYear fruit/><h3>Floricane</h3><p>{primocane ? 'A second crop depends on pruning and region' : 'Second-year fruiting'}</p></article></div>
    <p>A cane is a primocane in year one and a floricane in year two. Fruiting habit and pruning determine whether it carries fruit in either year. The crown produces new canes as old ones finish.</p>
    <details><summary>Check your understanding: does “primocane” mean sweeter fruit?</summary><p>No. It names a cane’s first year of growth. A “primocane-fruiting” variety can fruit in that year; it is not a sweetness or quality grade.</p></details>
    <small>Illustration by Berry Intelligence from this lesson’s cited extension guides; schematic, not to scale. Raspberry and blackberry only. Blueberry does not follow this two-year cane calendar. {sourceLink ?? <a href="#learning-sources">See sources</a>}.</small>
  </section>;
}
