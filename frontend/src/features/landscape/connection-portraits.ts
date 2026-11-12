import type { LandscapeModel, LandscapeNode, Portrait } from './models.ts';

function unique<T extends { id: string }>(rows: T[]): T[] {
  return [...new Map(rows.map(row => [row.id, row])).values()];
}

function nodes(rows: LandscapeNode[]): LandscapeNode[] {
  const merged = new Map<string, LandscapeNode>();
  for (const row of rows) {
    const before = merged.get(row.id);
    merged.set(row.id, { ...(before ?? row), evidence_ids: [...new Set([...(before?.evidence_ids ?? []), ...row.evidence_ids])] });
  }
  return [...merged.values()];
}

/** All berry-specific portraits contribute; canonical IDs alone define identity.
 * This merges recorded collections only, without traversing or transferring roles. */
export function mergeConnectionPortraits(model: Pick<LandscapeModel, 'market_rows' | 'portfolios'>): Portrait[] {
  const merged = new Map<string, Portrait>();
  for (const row of [...model.market_rows, ...model.portfolios]) {
    const before = merged.get(row.actor.id);
    const markets = new Map<string, Portrait['markets'][number]>();
    for (const market of [...(before?.markets ?? []), ...row.markets]) {
      const previous = markets.get(market.country);
      markets.set(market.country, { country: market.country, edges: unique([...(previous?.edges ?? []), ...market.edges]) });
    }
    merged.set(row.actor.id, {
      actor: nodes([...(before ? [before.actor] : []), row.actor])[0],
      programs: nodes([...(before?.programs ?? []), ...row.programs]),
      varieties: nodes([...(before?.varieties ?? []), ...row.varieties]),
      edges: unique([...(before?.edges ?? []), ...row.edges]),
      portfolio_edges: unique([...(before?.portfolio_edges ?? []), ...row.portfolio_edges]),
      markets: [...markets.values()],
    });
  }
  return [...merged.values()];
}
