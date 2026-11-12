import { Fragment, useId, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { DetailRef, DetailType } from '../../contracts/investigation';

export interface ProfileSource {
  id: string; title: string; url?: string; source_name?: string;
  status?: string; review?: string; published?: string; captured?: string;
}
export interface ProfileItem {
  id?: string; type?: DetailType; label?: string; value?: string; summary?: string;
  status?: string; status_label?: string; caveat?: string; review?: string;
  scope_kind?: string; notes?: string; confidence?: string;
  subject_id?: string; object_id?: string; location_label?: string;
  company_geography?: boolean; genetic_geography?: boolean;
  evidence_ids?: string[]; sources?: ProfileSource[];
}
interface Section { title: string; items: ProfileItem[] }

/** Keep exact records and notes; only their presentation is condensed. */
function ProfileRows({ item, sources, open, renderSource, expansions, identity }: {
  item: ProfileItem; sources: Map<string, ProfileSource>; open: (detail: DetailRef) => void;
  renderSource: (source: ProfileSource, trigger?: string) => ReactNode; expansions: Set<string>; identity: string;
}) {
  const [expanded, setExpanded] = useState(() => expansions.has(identity));
  const region = useId();
  const linked = new Map((item.sources ?? []).map(source => [source.id, source]));
  for (const id of item.evidence_ids ?? []) if (!linked.has(id)) linked.set(id, sources.get(id) ?? { id, title: id });
  const notes = [...new Set([item.summary, item.notes].filter((note): note is string => Boolean(note)))];
  const materialStatus = item.type === 'relationship' && item.status && item.status !== 'active'
    ? item.status_label || item.status.replaceAll('_', ' ') : '';
  const canOpen = Boolean(item.id && item.type && ['company', 'variety', 'geography', 'relationship', 'source', 'observation'].includes(item.type));
  return <tbody>
    <tr className="berry-profile-record">
      <th scope="row">{canOpen ? <button type="button" className="berry-profile-record-link"
        data-detail-trigger={`${item.type}:${item.id}`} onClick={() => open({ type: item.type!, id: item.id! })}>
        {item.label || 'Inspect record'}</button> : item.label || 'Recorded observation'}</th>
      <td><span>{item.value || '—'}</span>
        {materialStatus && <strong className="berry-profile-qualification">{materialStatus}</strong>}
        {(item.company_geography || item.genetic_geography) && item.location_label && <span className="berry-profile-qualification">{item.location_label}</span>}
        {item.caveat && <span className="berry-profile-qualification">{item.caveat}</span>}
      </td>
      <td className="berry-profile-info-cell"><button type="button" aria-expanded={expanded} aria-controls={region}
        aria-label={`Info for ${item.label || 'record'}`} onClick={() => setExpanded(current => {
          const next = !current; if (next) expansions.add(identity); else expansions.delete(identity); return next;
        })}>Info</button></td>
    </tr>
    {expanded && <tr className="berry-profile-info-row"><td colSpan={3}><div id={region}>
      {notes.map(note => <p key={note}>{note}</p>)}
      <dl>{[
        ['Status', item.status_label || item.status], ['Review', item.review], ['Scope', item.scope_kind],
        ['Confidence', item.confidence], ['Recorded subject', item.subject_id], ['Recorded object', item.object_id],
      ].filter(([, value]) => Boolean(value)).map(([label, value]) => <Fragment key={label}><dt>{label}</dt><dd>{value}</dd></Fragment>)}</dl>
      {linked.size > 0 && <div className="berry-profile-sources">{[...linked.values()].map(source => <div key={source.id}>{renderSource(source, `profile:${identity}:source:${source.id}`)}</div>)}</div>}
    </div></td></tr>}
  </tbody>;
}

export function ProfileSheet({ sections, sources, open, renderSource, expansions, scrollPositions, identity }: {
  sections: Section[]; sources: ProfileSource[]; open: (detail: DetailRef) => void;
  renderSource: (source: ProfileSource, trigger?: string) => ReactNode; expansions: Set<string>; scrollPositions: Map<string, number>; identity: string;
}) {
  const sourceMap = new Map(sources.map(source => [source.id, source]));
  const tables = useRef(new Map<number, HTMLDivElement>());
  useLayoutEffect(() => {
    for (const [index, element] of tables.current) element.scrollTop = scrollPositions.get(`${identity}:${index}`) ?? 0;
  }, [identity, scrollPositions]);
  return <>{sections.map((section, index) => section.items.length > 0 && <section className="berry-detail-section berry-profile-section" key={`${section.title}-${index}`}>
    <h3>{section.title === 'Connections within this investigation' ? 'Connections' : section.title === 'Recorded portfolio roles' ? 'Cultivars / roles' : section.title}
      {section.title === 'Connections within this investigation' && <small>This investigation</small>}
      {section.title === 'Recorded portfolio roles' && <small>Company-wide</small>}</h3>
    <div className="berry-profile-table-wrap" ref={element => { if (element) tables.current.set(index, element); else tables.current.delete(index); }}
      onScroll={event => scrollPositions.set(`${identity}:${index}`, event.currentTarget.scrollTop)}><table className="berry-profile-sheet">
      <thead><tr><th scope="col">{section.title === 'Recorded portfolio roles' ? 'Cultivar' : 'Recorded connection'}</th><th scope="col">Role / detail</th><th scope="col"><span className="berry-sr-only">Information</span></th></tr></thead>
      {section.items.map((item, itemIndex) => <ProfileRows key={item.id ?? itemIndex} item={item} sources={sourceMap} open={open} renderSource={renderSource}
        expansions={expansions} identity={`${identity}:${index}:${item.id ?? itemIndex}`} />)}
    </table></div>
  </section>)}</>;
}
