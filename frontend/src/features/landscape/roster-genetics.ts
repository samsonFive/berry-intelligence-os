import type { LandscapeModel, LandscapeNode } from './models.ts';

export interface RosterQualifierPath {
  edgeId: string;
  subjectId: string;
  objectId: string;
  subjectLabel: string;
  objectLabel: string;
  subjectType?: LandscapeNode['type'];
  objectType?: LandscapeNode['type'];
}

export interface RosterQualifierGroup {
  /** Exact authored tuple, independent of display names or path ordering. */
  key: string;
  role: string;
  status: string;
  status_label: string;
  caveat: string;
  edgeIds: string[];
  paths: RosterQualifierPath[];
}

/** Join existing portraits by canonical actor ID; do not add a graph traversal or transfer roles. */
export function rosterGenetics(model: LandscapeModel, companyId: string) {
  const portraits = [...model.portfolios, ...model.market_rows].filter(row => row.actor.id === companyId);
  const programs = [...new Map(portraits.flatMap(row => row.programs).map(node => [node.id, node])).values()];
  const varieties = [...new Map(portraits.flatMap(row => row.varieties).map(node => [node.id, node])).values()];
  const edges = [...new Map(portraits.flatMap(row => [...row.edges, ...row.portfolio_edges])
    .filter(edge => !edge.company_geography && !edge.genetic_geography).map(edge => [edge.id, edge])).values()];
  const nodes = new Map([...portraits.map(row => row.actor), ...programs, ...varieties,
    ...Object.values(model.nodes ?? {})].map(node => [node.id, node]));
  const groups = new Map<string, RosterQualifierGroup>();
  for (const edge of edges) {
    // Group only material qualifications. All ordinary paths still remain in edges.
    if (edge.status === 'active' && !edge.caveat) continue;
    const key = JSON.stringify([edge.role, edge.status, edge.status_label, edge.caveat]);
    const group: RosterQualifierGroup = groups.get(key) ?? { key, role: edge.role, status: edge.status,
      status_label: edge.status_label, caveat: edge.caveat, edgeIds: [], paths: [] };
    const subject = nodes.get(edge.subject_id), object = nodes.get(edge.object_id);
    group.edgeIds.push(edge.id);
    group.paths.push({ edgeId: edge.id, subjectId: edge.subject_id, objectId: edge.object_id,
      subjectLabel: subject?.label ?? edge.subject_id, objectLabel: object?.label ?? edge.object_id,
      subjectType: subject?.type, objectType: object?.type });
    groups.set(key, group);
  }
  return {
    programs, varieties, edges,
    // Never attribute a whole group to the roster company: paths retain their
    // own named subjects/objects, including program→cultivar and company→partner.
    qualifierGroups: [...groups.values()],
  };
}
