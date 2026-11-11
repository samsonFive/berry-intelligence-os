import type { InvestigationContext } from "../../contracts/investigation.ts";
import { CANONICAL_ID, normalizeContext } from "../../contracts/investigation.ts";
import type { InvestigationAction } from "../../state/reducer.ts";
import type { InvestigationEnvelope } from "../../api/client.ts";

export interface CommandHost {
  context: InvestigationContext;
  getRevision: () => number;
  dispatch: (action: InvestigationAction) => boolean;
  read: <T>(endpoint: string, context: InvestigationContext, revision: number) => Promise<InvestigationEnvelope<T>>;
}
export interface CommandResult { ok: boolean; code: string; message: string; revision?: number }
export const staleCommand = (): CommandResult => ({ ok: false, code: "stale_command", message: "The investigation changed. Submit the command again to apply it to the current view." });
export function fresh(host: CommandHost, revision: number): boolean { return Number.isSafeInteger(revision) && revision === host.getRevision(); }
function validIds(ids: string[], cap: number): boolean { return ids.length > 0 && ids.length <= cap && ids.every(id => CANONICAL_ID.test(id)) && new Set(ids).size === ids.length; }

/** One revision-checked action: the model supplies selectors, never factual cells. */
export async function compareCommand(host: CommandHost, args: {
  revision: number; kind: "company" | "variety"; ids: string[]; countries?: string[];
}): Promise<CommandResult> {
  if (!fresh(host, args.revision)) return staleCommand();
  if (!validIds(args.ids, args.kind === "company" ? 5 : 4) ||
      (args.countries && (args.countries.length > 20 || !args.countries.every(id => CANONICAL_ID.test(id)))))
    return { ok: false, code: "invalid_selection", message: "Choose valid canonical comparison subjects and countries." };
  const candidate = { ...host.context, lens: "comparison" as const, comparison_kind: args.kind,
    [args.kind === "company" ? "cohort_companies" : "cohort_varieties"]: args.ids.join(","),
    ...(args.countries ? { countries: args.countries.join(",") } : {}),
  };
  if (normalizeContext(candidate).issues.length) return { ok: false, code: "invalid_context", message: "Resolve the current investigation selection before applying this command." };
  const response = await host.read<{ invalid_ids: string[]; overflow_ids: string[] }>("/comparison", candidate, args.revision);
  if (!fresh(host, args.revision)) return staleCommand();
  if (response.data.invalid_ids.length || response.data.overflow_ids.length)
    return { ok: false, code: "unavailable_identity", message: "Some comparison subjects could not be resolved. Use the catalog to choose current identities." };
  const applied = host.dispatch({ type: "replaceContext", context: candidate, origin: "copilot", expectedRevision: args.revision });
  return applied ? { ok: true, code: "applied", message: "Comparison opened in the main analytical field.", revision: host.getRevision() } : staleCommand();
}

export async function detailCommand(host: CommandHost, args: {
  revision: number; type: "company" | "variety" | "source"; id: string; focus?: boolean;
}): Promise<CommandResult> {
  if (!fresh(host, args.revision)) return staleCommand();
  if (!CANONICAL_ID.test(args.id)) return { ok: false, code: "invalid_id", message: "Choose a canonical identity or source." };
  await host.read(`/detail?type=${args.type}&id=${encodeURIComponent(args.id)}`, host.context, args.revision);
  if (!fresh(host, args.revision)) return staleCommand();
  const action: InvestigationAction = args.focus && args.type !== "source"
    ? { type: "focusEntity", entity: { type: args.type, id: args.id }, origin: "copilot", expectedRevision: args.revision }
    : { type: "openDetail", detail: { type: args.type, id: args.id }, origin: "copilot", expectedRevision: args.revision };
  return host.dispatch(action) ? { ok: true, code: "applied", message: "Opened the existing detail view.", revision: host.getRevision() } : staleCommand();
}
