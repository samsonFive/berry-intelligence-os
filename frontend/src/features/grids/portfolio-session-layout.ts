/** RAM-only layouts for windows beyond the existing forty-column account wire. */
export interface PortfolioSessionColumn {
  colId: string; width?: number | null; hide?: boolean | null; sort?: 'asc' | 'desc' | null;
  sortIndex?: number | null; pinned?: 'left' | 'right' | boolean | null; flex?: number | null;
}
export interface PortfolioSessionSnapshot {
  columns: PortfolioSessionColumn[]; filterModel: Record<string, unknown>; quickFilter: string;
}

export class PortfolioSessionLayouts {
  private entries = new Map<string, { identity: string; snapshot: PortfolioSessionSnapshot }>();
  private generation = 0;
  get epoch(): number { return this.generation; }
  get size(): number { return this.entries.size; }
  private identity(ids: readonly string[]): string { return JSON.stringify([...ids].sort()); }
  load(key: string, ids: readonly string[], epoch: number): PortfolioSessionSnapshot | null {
    const entry = this.entries.get(key);
    return epoch === this.generation && entry?.identity === this.identity(ids) ? structuredClone(entry.snapshot) : null;
  }
  save(key: string, ids: readonly string[], snapshot: PortfolioSessionSnapshot, epoch: number): boolean {
    if (epoch !== this.generation) return false;
    if (!/^[a-z0-9-]{1,80}$/.test(key) || new Set(ids).size !== ids.length
      || snapshot.columns.length !== ids.length || new Set(snapshot.columns.map(column => column.colId)).size !== ids.length
      || snapshot.columns.some(column => !ids.includes(column.colId)) || snapshot.quickFilter.length > 200)
      throw new Error('This session layout could not be matched to its exact columns.');
    const serialized = JSON.stringify(snapshot);
    if (new TextEncoder().encode(serialized).byteLength > 256 * 1024)
      throw new Error('This session layout exceeds the supported display-memory size.');
    this.entries.delete(key);
    this.entries.set(key, { identity: this.identity(ids), snapshot: JSON.parse(serialized) });
    if (this.entries.size > 64) this.entries.delete(this.entries.keys().next().value!);
    return true;
  }
  clear(): void { this.entries.clear(); this.generation++; }
}
