import type { LandscapeEdge, LandscapeModel, LandscapeNode } from '../landscape/models.ts';

export interface PortfolioRow {
  id: string;
  variety: LandscapeNode;
  byCompany: Record<string, LandscapeEdge[]>;
}

/** A company may have one portrait per berry; columns are canonical identities,
 * while every portrait still contributes its exact cultivar relationship edges. */
export function portfolioData(model: Pick<LandscapeModel, 'portfolios' | 'nodes'>) {
  const companies = [...new Map(model.portfolios.map(row => [row.actor.id, row.actor])).values()];
  const result = new Map<string, PortfolioRow>();
  for (const portrait of model.portfolios) {
    for (const edge of portrait.portfolio_edges) {
      const variety = [model.nodes[edge.subject_id], model.nodes[edge.object_id]].find(node => node?.type === 'variety');
      if (!variety) continue;
      const row = result.get(variety.id) ?? { id: variety.id, variety, byCompany: {} };
      const edges = row.byCompany[portrait.actor.id] ?? [];
      if (!edges.some(item => item.id === edge.id)) edges.push(edge);
      row.byCompany[portrait.actor.id] = edges;
      result.set(variety.id, row);
    }
  }
  return { companies, rows: [...result.values()].sort((a, b) => a.variety.label.localeCompare(b.variety.label)) };
}
