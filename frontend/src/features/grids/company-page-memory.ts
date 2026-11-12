/** Grid pagination is transient UI memory, separate from selectors and saved layouts. */
export interface CompanyPageEntry {
  key: string;
  universe: string;
  index: number;
  epoch: number;
}
export interface CompanyPageRequest {
  key: string;
  universe: string;
  count: number;
  contextMatches: boolean;
  epoch: number;
}
export type PageNavigation = 'POP' | 'PUSH' | 'REPLACE';

/** Exact membership, independent of authored labels or incoming portrait order. */
export function companyUniverseIdentity(companies: readonly { id: string }[]): string {
  return JSON.stringify(companies.map(company => company.id).sort());
}

export class CompanyPageMemory {
  private entries = new Map<string, CompanyPageEntry>();
  private generation = 0;
  get epoch(): number { return this.generation; }
  get size(): number { return this.entries.size; }

  private accepts(request: CompanyPageRequest): boolean {
    return request.contextMatches && request.epoch === this.generation
      && /^[A-Za-z0-9_-]{1,100}$/.test(request.key) && typeof request.universe === 'string' && request.universe.length > 0
      && Number.isSafeInteger(request.count) && request.count > 0;
  }
  private clamp(index: number, count: number): number {
    return Number.isSafeInteger(index) ? Math.max(0, Math.min(count - 1, index)) : 0;
  }

  /** Read-only during render: transient old context must never erase a POP entry. */
  resolve(request: CompanyPageRequest, navigation: PageNavigation, mounted?: CompanyPageEntry | null): number {
    if (!this.accepts(request)) return 0;
    const saved = this.entries.get(request.key);
    if (saved?.universe === request.universe) return this.clamp(saved.index, request.count);
    if (navigation !== 'POP' && mounted?.epoch === this.generation && mounted.universe === request.universe)
      return this.clamp(mounted.index, request.count);
    return 0;
  }

  remember(request: CompanyPageRequest, index: number): boolean {
    if (!this.accepts(request)) return false;
    this.entries.delete(request.key);
    this.entries.set(request.key, { key: request.key, universe: request.universe,
      index: this.clamp(index, request.count), epoch: this.generation });
    if (this.entries.size > 64) this.entries.delete(this.entries.keys().next().value!);
    return true;
  }

  clear(): void { this.entries.clear(); this.generation++; }
}
