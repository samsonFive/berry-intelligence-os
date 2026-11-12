import type { LandscapeModel } from './models.ts';

/** Join existing portraits by canonical actor ID; do not add a graph traversal or transfer roles. */
export function rosterGenetics(model: LandscapeModel, companyId: string) {
  const portraits = [...model.portfolios, ...model.market_rows].filter(row => row.actor.id === companyId);
  return {
    programs: [...new Map(portraits.flatMap(row => row.programs).map(node => [node.id, node])).values()],
    varieties: [...new Map(portraits.flatMap(row => row.varieties).map(node => [node.id, node])).values()],
    edges: [...new Map(portraits.flatMap(row => [...row.edges, ...row.portfolio_edges])
      .filter(edge => !edge.company_geography && !edge.genetic_geography).map(edge => [edge.id, edge])).values()],
  };
}
