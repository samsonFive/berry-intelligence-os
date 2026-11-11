import { serializeInvestigation } from "../contracts/investigation.ts";
import type { ContextIssue, InvestigationContext } from "../contracts/investigation.ts";
export interface InvestigationEnvelope<T> {
  api_v: 1;
  request_id: string;
  revision: number;
  scope_key: string;
  applied_scope: Record<string, unknown>;
  issues: ContextIssue[];
  data: T;
}
export class InvestigationApiError extends Error {
  status: number;
  issues: ContextIssue[];
  constructor(message: string, status: number, issues: ContextIssue[] = []) {
    super(message);
    this.name = "InvestigationApiError";
    this.status = status;
    this.issues = issues;
  }
  get requiresSession(): boolean { return this.status === 401 || this.status === 403; }
}
/** Endpoint is a fixed API suffix; callers cannot send credentials to another origin. */
export async function getInvestigation<T>(endpoint: string, context: InvestigationContext, revision: number, signal?: AbortSignal): Promise<InvestigationEnvelope<T>> {
  if (!Number.isSafeInteger(revision) || revision < 0) throw new InvestigationApiError("Unsupported investigation revision.", 400);
  if (!/^\/[a-z][a-z0-9/_-]*(?:\?[^#]*)?$/.test(endpoint) || endpoint.includes("..") || endpoint.includes(":") || endpoint.startsWith("//"))
    throw new InvestigationApiError("Unsupported investigation endpoint.", 400);
  const [path, query = ""] = endpoint.split("?", 2);
  const params = new URLSearchParams(serializeInvestigation(context));
  for (const [key, value] of new URLSearchParams(query)) {
    if (["type", "id"].includes(key)) params.set(key, value);
    else throw new InvestigationApiError("Unsupported detail parameter.", 400);
  }
  params.set("revision", String(revision));
  const response = await fetch(`/api/investigations/v1${path}?${params}`, {
    signal, credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" },
  });
  if (response.redirected || response.status === 401) throw new InvestigationApiError("Sign in to continue this investigation.", 401);
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : body?.detail?.message;
    const message = typeof detail === "string" ? detail : typeof body?.message === "string" ? body.message : "The investigation could not be loaded.";
    throw new InvestigationApiError(message.slice(0, 500), response.status, body?.issues ?? body?.detail?.issues ?? []);
  }
  if (!body || body.api_v !== 1 || body.revision !== revision || typeof body.request_id !== "string" || typeof body.scope_key !== "string" || !Array.isArray(body.issues))
    throw new InvestigationApiError("The server returned an incompatible investigation response.", 502);
  return body as InvestigationEnvelope<T>;
}
export function investigationQueryKey(endpoint: string, context: InvestigationContext, revision: number): readonly unknown[] {
  return ["investigation", endpoint, serializeInvestigation(context), revision] as const;
}
