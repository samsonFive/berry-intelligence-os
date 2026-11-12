import { decodeGridLayout, encodeGridLayout, GridLayoutError, validateSheetLayout, validViewKey } from "./layout-codec.ts";
import type { ColumnCatalog, GridLayoutSnapshot, LoadedGridLayout, SheetLayout } from "./layout-codec.ts";

export interface AccountLayoutState { status: "unloaded" | "loading" | "ready" | "saving" | "conflict" | "error" | "disposed"; revision: number | null; conflict: boolean }
interface Options { viewKey: string; catalog: ColumnCatalog; fetch?: typeof fetch; sessionEvents?: EventTarget; onSessionRequired?: () => void }
const SESSION_EVENT = "berry:session-transition";

/** No account ID is sent by the client: the existing session owns the server row. */
export class AccountGridLayouts {
  private wire: SheetLayout | null = null;
  private writable = false;
  private state: AccountLayoutState = { status: "unloaded", revision: null, conflict: false };
  private chain: Promise<unknown> = Promise.resolve();
  private active: AbortController | null = null;
  private events: EventTarget | undefined;
  private readonly sessionTransition = () => this.dispose();
  private readonly request: typeof fetch;
  private readonly options: Options;
  constructor(options: Options) {
    this.options = options;
    if (!validViewKey(options.viewKey)) throw new GridLayoutError("Unsupported account layout destination.");
    this.request = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.events = options.sessionEvents ?? (typeof window !== "undefined" ? window : undefined);
    this.events?.addEventListener(SESSION_EVENT, this.sessionTransition);
  }
  getState(): AccountLayoutState { return { ...this.state }; }
  private assertSession(): void { if (this.state.status === "disposed") throw new GridLayoutError("This grid layout session has ended.", "disposed"); }
  dispose(): void {
    this.active?.abort(); this.active = null; this.wire = null; this.writable = false;
    this.state = { status: "disposed", revision: null, conflict: false };
    this.events?.removeEventListener(SESSION_EVENT, this.sessionTransition);
  }
  private enqueue<T>(operation: () => Promise<T>): Promise<T> {
    const task = this.chain.catch(() => {}).then(() => {
      this.assertSession();
      return operation();
    });
    this.chain = task; return task;
  }
  private async transfer(method: "GET" | "POST", payload?: SheetLayout, signal?: AbortSignal): Promise<SheetLayout> {
    const controller = new AbortController(); this.active = controller;
    const combined = signal ? AbortSignal.any([controller.signal, signal]) : controller.signal;
    try {
      const response = await this.request(`/api/ui/sheets/${this.options.viewKey}`, { method, credentials: "same-origin", cache: "no-store", signal: combined,
        headers: { Accept: "application/json", ...(method === "POST" ? { "Content-Type": "application/json" } : {}) }, ...(payload ? { body: JSON.stringify(payload) } : {}) });
      this.assertSession();
      if (response.redirected || [401, 403].includes(response.status)) {
        this.dispose(); this.options.onSessionRequired?.(); this.events?.dispatchEvent(new Event(SESSION_EVENT));
        throw new GridLayoutError("Sign in to restore or save your grid layout.", "session");
      }
      const text = await response.text();
      this.assertSession();
      if (new TextEncoder().encode(text).byteLength > 20_000) throw new GridLayoutError("The saved grid layout response is too large.");
      let body: unknown = null;
      if ((response.headers.get("content-type") ?? "").includes("application/json")) { try { body = JSON.parse(text); } catch { /* Handled as an invalid response below. */ } }
      if (!response.ok) {
        const detail = body && typeof body === "object" && "detail" in body && typeof body.detail === "string" ? body.detail.slice(0, 500) : "The grid layout could not be saved. Changes remain in this tab.";
        if (response.status === 409) { this.state = { ...this.state, status: "conflict", conflict: true }; throw new GridLayoutError(detail, "conflict"); }
        throw new GridLayoutError(detail, response.status >= 500 ? "network" : "invalid");
      }
      return validateSheetLayout(body);
    } catch (error) {
      if (error instanceof GridLayoutError) throw error;
      this.assertSession();
      throw new GridLayoutError(combined.aborted ? "Grid layout loading or saving was cancelled." : "Saved grid layouts could not be reached. Changes remain in this tab.", "network");
    } finally { if (this.active === controller) this.active = null; }
  }
  load(signal?: AbortSignal): Promise<LoadedGridLayout> {
    return this.enqueue(async () => {
      this.state = { ...this.state, status: "loading" };
      try {
        const wire = await this.transfer("GET", undefined, signal);
        this.assertSession();
        const result = decodeGridLayout(wire, this.options.catalog);
        this.wire = wire; this.writable = result.writable;
        this.state = { status: "ready", revision: wire.revision, conflict: false }; return result;
      } catch (error) { if (this.state.status !== "disposed") this.state = { ...this.state, status: this.state.conflict ? "conflict" : "error" }; throw error; }
    });
  }
  save(snapshot: GridLayoutSnapshot, signal?: AbortSignal): Promise<LoadedGridLayout> {
    const captured = structuredClone(snapshot);
    return this.enqueue(async () => {
      if (this.state.conflict) throw new GridLayoutError("This layout changed in another tab. Reload its saved layout before saving again.", "conflict");
      if (!this.wire) throw new GridLayoutError("Restore the saved layout before saving changes.", "unloaded");
      if (!this.writable) throw new GridLayoutError("The earlier layout is preserved. Choose a new layout namespace before saving.", "migration");
      const payload = encodeGridLayout(captured, this.options.catalog, this.wire);
      this.state = { ...this.state, status: "saving" };
      try {
        const wire = await this.transfer("POST", payload, signal);
        this.assertSession();
        if (wire.revision !== payload.revision + 1) throw new GridLayoutError("The server returned an incompatible saved layout revision.");
        const result = decodeGridLayout(wire, this.options.catalog);
        if (!result.writable) throw new GridLayoutError("The server returned an incompatible saved grid layout.");
        this.wire = wire; this.state = { status: "ready", revision: wire.revision, conflict: false }; return result;
      } catch (error) { if (this.state.status !== "disposed" && !this.state.conflict) this.state = { ...this.state, status: "error" }; throw error; }
    });
  }
}
