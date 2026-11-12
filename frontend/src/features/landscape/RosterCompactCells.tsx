import type { ReactNode } from 'react';
import type { LandscapeEdge, LandscapeModel, LandscapeNode, MonitoringCompany } from './models';
import { rosterGenetics } from './roster-genetics';
import './RosterCompactCells.css';

interface GeneticsProps {
  id: string;
  model: LandscapeModel;
  renderNode: (node: LandscapeNode) => ReactNode;
  /** Keep the existing exact endpoints, relationship activation and citations. */
  renderEdge: (edge: LandscapeEdge) => ReactNode;
  expanded?: boolean;
}

function NamedIdentity({ node, renderNode, expanded }: { node: LandscapeNode; renderNode: GeneticsProps['renderNode']; expanded: boolean }) {
  return <>{renderNode({ ...node, identity_note: undefined })}
    {expanded && node.identity_note && <span className="berry-roster-compact-identity-note">{node.identity_note}</span>}
  </>;
}

function Names({ nodes, renderNode, expanded = false }: { nodes: LandscapeNode[]; renderNode: GeneticsProps['renderNode']; expanded?: boolean }) {
  return <ul className="berry-roster-compact-names">{nodes.map(node => <li key={node.id}>
    <span className="berry-roster-compact-type">{node.type === 'breeding_program' ? 'Program' : 'Cultivar'}</span>
    <NamedIdentity node={node} renderNode={renderNode} expanded={expanded} />
  </li>)}</ul>;
}

/** Compact cells summarize the same exact paths shown in the roster-level dialog. */
export function CompactGenetics({ id, model, renderNode, renderEdge, expanded = false }: GeneticsProps) {
  const { programs, varieties, edges, qualifierGroups } = rosterGenetics(model, id);
  const names = [...programs, ...varieties];
  const shown = [...programs.slice(0, varieties.length ? 2 : 4), ...varieties.slice(0, programs.length ? 2 : 4)];
  const nodes = new Map([...model.portfolios.map(row => row.actor), ...model.market_rows.map(row => row.actor),
    ...Object.values(model.nodes ?? {})].map(node => [node.id, node]));
  const directCompanies = edges.flatMap(edge => {
    const otherId = edge.subject_id === id ? edge.object_id : edge.object_id === id ? edge.subject_id : '';
    const other = nodes.get(otherId);
    return other?.type === 'company' ? [{ edge, other, outgoing: edge.subject_id === id }] : [];
  });
  const limits = [...new Set(qualifierGroups.filter(group => group.status !== 'active').map(group =>
    `${group.edgeIds.length} ${group.status === 'disputed' ? 'disputed' : group.status === 'historical' ? 'historical' : group.status_label} ${group.role} ${group.edgeIds.length === 1 ? 'path' : 'paths'}`))];
  if (!names.length && !edges.length) return expanded
    ? <p>No genetics paths are recorded in the applied standing scope.</p> : <span>—</span>;
  return <div className={`berry-roster-compact berry-roster-compact-genetics${expanded ? ' berry-roster-compact--expanded' : ''}`}>
    {!!names.length && <>
      <p className="berry-roster-compact-counts">{[
        programs.length ? `${programs.length} ${programs.length === 1 ? 'program' : 'programs'}` : '',
        varieties.length ? `${varieties.length} ${varieties.length === 1 ? 'cultivar' : 'cultivars'}` : '',
        !expanded && names.length > shown.length ? `+${names.length - shown.length} more` : '',
      ].filter(Boolean).join(' · ')}</p>
      <Names nodes={expanded ? names : shown} renderNode={renderNode} expanded={expanded} />
    </>}
    {!expanded && !names.length && !!directCompanies.length && <ul className="berry-roster-compact-direct">{directCompanies.slice(0, 2).map(({ edge, other, outgoing }) =>
      <li key={edge.id} data-roster-company-path={edge.id}><span className="berry-roster-compact-direction"
        aria-label={outgoing ? `This company connects to ${other.label}` : `${other.label} connects to this company`}>{outgoing ? '→' : '←'}</span>
        <NamedIdentity node={other} renderNode={renderNode} expanded={false} /><span className="berry-roster-compact-direct-role"> · {edge.role}</span>
      </li>)}</ul>}
    {!expanded && !names.length && !directCompanies.length && <span>—</span>}
    {!expanded && !names.length && directCompanies.length > 2 && <p className="berry-roster-compact-counts">+{directCompanies.length - 2} more</p>}
    {!expanded && !!limits.length && <p className="berry-roster-compact-qualifier">{limits.join(' · ')}</p>}
    {expanded && !!edges.length && <section className="berry-roster-full-paths"><h4>All {edges.length} recorded paths</h4>
      <div className="berry-roster-compact-paths">{edges.map(edge => <div key={edge.id} data-roster-path-id={edge.id}>{renderEdge(edge)}
        {edge.notes && <p>{edge.notes}</p>}{edge.review && <p className="berry-roster-path-review">Review: {edge.review}</p>}
      </div>)}</div>
    </section>}
  </div>;
}

export function CompactRoles({ roles, berryIds, expanded = false }: { roles: string[]; berryIds: string[]; expanded?: boolean }) {
  if (!roles.length && !berryIds.length) return expanded ? <p>Company roles and berry links are not recorded.</p> : <span>—</span>;
  return <div className="berry-roster-compact berry-roster-compact-roles">
    {!!roles.length && <ul className="berry-roster-compact-role-list">{(expanded ? roles : roles.slice(0, 3)).map(role => <li key={role}>{role.replaceAll('_', ' ')}</li>)}</ul>}
    {!expanded && roles.length > 3 && <span className="berry-roster-compact-counts">+{roles.length - 3} more</span>}
    {!!berryIds.length && <div className="berry-roster-compact-berries">{berryIds.map(id => <span key={id}>{id.replace(/^berry-/, '').replaceAll('-', ' ')}</span>)}</div>}
    {expanded && !roles.length && <p>No authored company roles are recorded.</p>}
    {expanded && !berryIds.length && <p>No berry links are recorded.</p>}
  </div>;
}

/** Country and actual/planned/validation/location-only meaning remain visible. */
export function CompactGeographies({ geographies, open }: { geographies: MonitoringCompany['geographies']; open: (id: string) => void }) {
  if (!geographies.length) return <span>—</span>;
  return <ul className="berry-roster-compact-geographies">{geographies.map((geo, index) => <li key={`${geo.relationship_id}-${index}`}>
    <button type="button" className="berry-text-button" onClick={() => open(geo.relationship_id)}><strong>{geo.label}</strong>
      {' · '}{geo.activity === 'Location reported · check source' ? 'Location only' : geo.activity}
    </button>{geo.status !== 'Documented relationship' && <span className="berry-roster-geo-status"> · {geo.status}</span>}
  </li>)}</ul>;
}

const COLLECTION_LABELS: Record<string, string> = {
  source_blocked: 'Source blocked', no_supported_source: 'No linked source', manual_monitoring_required: 'Manual checks',
  source_configured_never_run: 'Not checked yet', linked_to_runnable_source: 'Configured / checked',
};

export function CompactCollection({ monitoring, expanded = false }: { monitoring: MonitoringCompany['monitoring']; expanded?: boolean }) {
  return <div className="berry-roster-compact berry-roster-compact-collection">
    <strong className="berry-roster-compact-state">{COLLECTION_LABELS[monitoring.state] ?? monitoring.state.replaceAll('_', ' ')}</strong>
    {expanded && <><p>{monitoring.state.replaceAll('_', ' ')}</p><p>{monitoring.detail}</p></>}
  </div>;
}
