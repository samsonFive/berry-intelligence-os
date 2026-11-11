import { isNativeSurfacePath } from "../contracts/investigation.ts";

/** Layout memory contains only bounded native paths, opaque history keys and coordinates. */
export const SURFACE_MEMORY_KEY = "berry:surface-scroll:v1";
const PATHS = new Set(["/app/landscape", "/app/briefing", "/app/workspaces", "/app/learn"]);
const LIMIT = 64;
export interface ScrollPoint { x: number; y: number }
interface Entry extends ScrollPoint { path: string; key: string }
export interface SurfaceLocation { path: string; key: string }
const point = (value: unknown): ScrollPoint | null => {
  if (!value || typeof value !== "object") return null;
  const { x, y } = value as ScrollPoint;
  return [x, y].every(n => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 10_000_000) ? { x, y } : null;
};
const validLocation = ({ path, key }: SurfaceLocation) => PATHS.has(path) && /^[a-zA-Z0-9_-]{1,100}$/.test(key);
const surfaceLocation = (location: SurfaceLocation): SurfaceLocation | null => isNativeSurfacePath(location.path)
  ? { path: location.path.startsWith("/app/learn/") ? "/app/learn" : location.path, key: location.key } : null;

export class SurfaceMemory {
  private surfaces = new Map<string, ScrollPoint>();
  private entries = new Map<string, Entry>();
  private active: SurfaceLocation | null = null;
  private target: ScrollPoint | null = null;
  private cleared = false;

  constructor(serialized?: string | null) {
    try {
      const data = JSON.parse(serialized ?? "null");
      if (data?.v !== 1) return;
      for (const value of (Array.isArray(data.surfaces) ? data.surfaces : []).slice(-4)) {
        const position = point(value);
        if (position && PATHS.has(value.path)) this.surfaces.set(value.path, position);
      }
      for (const value of (Array.isArray(data.entries) ? data.entries : []).slice(-LIMIT)) {
        const position = point(value);
        if (position && validLocation(value)) this.entries.set(value.key, { ...position, key: value.key, path: value.path });
      }
    } catch { /* Unavailable or invalid session storage starts with empty UI memory. */ }
  }

  begin(destination: SurfaceLocation, navigation: "POP" | "PUSH" | "REPLACE"): boolean {
    const location = surfaceLocation(destination);
    if (this.cleared || !location || !validLocation(location)) return false;
    if (this.active?.key === location.key && this.active.path === location.path) return false;
    const sameSurface = this.active?.path === location.path;
    const entry = this.entries.get(location.key);
    this.active = location;
    // Direct actions within a surface retain its current viewport; history restores its own entry.
    this.target = sameSurface && navigation !== "POP" ? null
      : entry?.path === location.path ? { x: entry.x, y: entry.y }
        : this.surfaces.get(location.path) ?? { x: 0, y: 0 };
    if (!this.target) this.record(this.surfaces.get(location.path) ?? { x: 0, y: 0 });
    return !sameSurface;
  }

  pending(destination: SurfaceLocation): ScrollPoint | null {
    const location = surfaceLocation(destination);
    return location && this.active?.key === location.key && this.active.path === location.path ? this.target : null;
  }

  defer(destination: SurfaceLocation): void {
    const location = surfaceLocation(destination);
    if (!location || this.cleared || this.target || this.active?.key !== location.key || this.active.path !== location.path) return;
    const position = this.entries.get(location.key) ?? this.surfaces.get(location.path);
    if (position) this.target = { x: position.x, y: position.y };
  }

  observe(position: ScrollPoint): void {
    if (!this.target) this.record(position);
  }

  finish(position: ScrollPoint): void {
    this.target = null;
    this.record(position);
  }

  private record(position: ScrollPoint): void {
    if (!this.active || this.cleared || !point(position)) return;
    this.surfaces.set(this.active.path, { ...position });
    this.entries.delete(this.active.key);
    this.entries.set(this.active.key, { ...this.active, ...position });
    if (this.entries.size > LIMIT) this.entries.delete(this.entries.keys().next().value!);
  }

  clear(): void {
    this.cleared = true;
    this.target = null;
    this.surfaces.clear();
    this.entries.clear();
  }

  serialize(): string {
    return JSON.stringify({ v: 1, surfaces: [...this.surfaces].map(([path, position]) => ({ path, ...position })), entries: [...this.entries.values()] });
  }
}
