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
}

function NamedIdentity({ node, renderNode }: { node: LandscapeNode; renderNode: GeneticsProps['renderNode'] }) {
  return <>{/* This cell owns the authored note once, including if the shared renderer later gains it. */}
    {renderNode({ ...node, identity_note: undefined })}
    {node.identity_note && <span className="berry-roster-compact-identity-note">{node.identity_note}</span>}
  </>;
}

function Names({ nodes, renderNode }: { nodes: LandscapeNode[]; renderNode: GeneticsProps['renderNode'] }) {
  return <ul className="berry-roster-compact-names">{nodes.map(node => <li key={node.id}>
    <span className="berry-roster-compact-type">{node.type === 'breeding_program' ? 'Program' : 'Cultivar'}</span>
    <NamedIdentity node={node} renderNode={renderNode} />
  </li>)}</ul>;
}

/** Display the existing joined portraits; this component never traverses or infers a path. */
export function CompactGenetics({ id, model, renderNode, renderEdge }: GeneticsProps) {
  const { programs, varieties, edges, qualifierGroups } = rosterGenetics(model, id);
  const names = [...programs, ...varieties];
  const nodes = new Map([...model.portfolios.map(row => row.actor), ...model.market_rows.map(row => row.actor),
    ...Object.values(model.nodes ?? {})].map(node => [node.id, node]));
  const directCompanies = edges.flatMap(edge => {
    const otherId = edge.subject_id === id ? edge.object_id : edge.object_id === id ? edge.subject_id : '';
    const other = nodes.get(otherId);
    return other?.type === 'company' ? [{ edge, other, outgoing: edge.subject_id === id }] : [];
  });
  const typeLabel = (type: LandscapeNode['type'] | undefined) => type === 'breeding_program' ? 'program'
    : type === 'variety' ? 'cultivar' : type ?? 'unavailable identity';
  if (!names.length && !edges.length) return <span className="berry-roster-compact-unknown">Not recorded in scope</span>;
  return <div className="berry-roster-compact berry-roster-compact-genetics">
    {!!names.length && <>
      <p className="berry-roster-compact-counts">{[
        programs.length ? `${programs.length} ${programs.length === 1 ? 'program' : 'programs'}` : '',
        varieties.length ? `${varieties.length} ${varieties.length === 1 ? 'cultivar' : 'cultivars'}` : '',
      ].filter(Boolean).join(' · ')}</p>
      <Names nodes={names.slice(0, 4)} renderNode={renderNode} />
      {names.length > 4 && <details className="berry-roster-compact-details"><summary>All {names.length} names · 4 shown</summary>
        <Names nodes={names} renderNode={renderNode} />
      </details>}
    </>}
    {!names.length && !!directCompanies.length && <ul className="berry-roster-compact-direct">{directCompanies.map(({ edge, other, outgoing }) =>
      <li key={edge.id} data-roster-company-path={edge.id}><span className="berry-roster-compact-direction"
        aria-label={outgoing ? `This company connects to ${other.label}` : `${other.label} connects to this company`}>{outgoing ? '→' : '←'}</span>
        <span className="berry-roster-compact-type">Company</span><NamedIdentity node={other} renderNode={renderNode} />
        <span className="berry-roster-compact-direct-role"> · {edge.role}</span>
      </li>)}</ul>}
    {qualifierGroups.map(group => <details className="berry-roster-compact-details berry-roster-compact-qualification" key={group.key}>
      <summary><span>{group.paths.length} recorded {group.paths.length === 1 ? 'path' : 'paths'}
        <span className="berry-roster-compact-flow">{[...new Set(group.paths.map(path =>
          `${typeLabel(path.subjectType)} → ${typeLabel(path.objectType)}`))].join(' / ')}</span> · <strong>{group.role}</strong></span>
        <span className="berry-roster-compact-limit">{[group.status !== 'active' ? group.status_label : '', group.caveat].filter(Boolean).join(' · ')}</span>
      </summary>
      <div className="berry-roster-compact-paths">{edges.filter(edge => group.edgeIds.includes(edge.id)).map(edge =>
        <div key={edge.id} data-roster-path-id={edge.id}>{renderEdge(edge)}</div>)}</div>
    </details>)}
    {!!edges.length && <details className="berry-roster-compact-details"><summary>{edges.length} recorded paths · roles &amp; sources</summary>
      <div className="berry-roster-compact-paths">{edges.map(edge => <div key={edge.id} data-roster-path-id={edge.id}>{renderEdge(edge)}</div>)}</div>
    </details>}
  </div>;
}

export function CompactRoles({ roles, berryIds }: { roles: string[]; berryIds: string[] }) {
  const showRoles = (values: string[]) => <ul className="berry-roster-compact-role-list">{values.map(role => <li key={role}>{role.replaceAll('_', ' ')}</li>)}</ul>;
  return <div className="berry-roster-compact berry-roster-compact-roles">
    {roles.length ? showRoles(roles.slice(0, 3)) : <span className="berry-roster-compact-unknown">Roles unrecorded</span>}
    {roles.length > 3 && <details className="berry-roster-compact-details"><summary>All {roles.length} stored roles</summary>{showRoles(roles)}</details>}
    <div className="berry-roster-compact-berries">{berryIds.length
      ? berryIds.map(id => <span key={id}>{id.replace(/^berry-/, '').replaceAll('-', ' ')}</span>)
      : <span>Berries unrecorded</span>}</div>
  </div>;
}

const COLLECTION_LABELS: Record<string, string> = {
  source_blocked: 'Source blocked',
  no_supported_source: 'No linked source',
  manual_monitoring_required: 'Manual checks',
  source_configured_never_run: 'Not checked yet',
  linked_to_runnable_source: 'Configured / checked',
};

export function CompactCollection({ monitoring }: { monitoring: MonitoringCompany['monitoring'] }) {
  return <div className="berry-roster-compact berry-roster-compact-collection">
    <strong className="berry-roster-compact-state">{COLLECTION_LABELS[monitoring.state] ?? monitoring.state.replaceAll('_', ' ')}</strong>
    <details className="berry-roster-compact-details"><summary>Collection details</summary>
      <p>{monitoring.state.replaceAll('_', ' ')}</p><p>{monitoring.detail}</p>
    </details>
  </div>;
}
