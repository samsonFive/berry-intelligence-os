import { EMPTY_CONTEXT, detailPath, normalizeContext, refString, sameContext, sameDetailIdentity, splitIds } from "../contracts/investigation.ts";
import type { ContextIssue, DetailRef, DetailSection, EntityRef, EntityType, InvestigationContext, Lens, NormalizedContext } from "../contracts/investigation.ts";

export interface InvestigationState extends NormalizedContext { revision: number }
type Origin = "direct" | "grid" | "copilot" | "restore";
type ActionMetadata = { origin?: Origin; expectedRevision?: number };
export type InvestigationAction = ActionMetadata & (
  | { type: "applyScope"; scope: Partial<InvestigationContext> }
  | { type: "focusEntity"; entity: EntityRef }
  | { type: "togglePin"; entity: EntityRef }
  | { type: "setCohort"; kind: EntityType; ids: string[] }
  | { type: "setLens"; lens: Lens; comparison_kind?: EntityType }
  | { type: "setCompanySet"; company_set: InvestigationContext["company_set"] }
  | { type: "openDetail"; detail: DetailRef }
  | { type: "setDetailSection"; section: DetailSection }
  | { type: "closeDetail" }
  | { type: "dismissDetails" }
  | { type: "setDemoCohort"; ids: string[] }
  | { type: "replaceContext"; context: Partial<InvestigationContext> }
  | { type: "setSearch"; q: string; q_scope?: "scope" | "catalog" }
);
export interface ActionResult { state: InvestigationState; accepted: boolean; changed: boolean; history: "push" | "replace" }
const SCOPE_FIELDS = ["berry", "countries", "geo_basis", "actor_roles", "relationship_types", "news_from", "news_to"] as const;
export function initialInvestigation(value: NormalizedContext = { context: { ...EMPTY_CONTEXT }, issues: [] }): InvestigationState {
  return { ...value, revision: 0 };
}
function panelPath(context: InvestigationContext, detail: DetailRef): string {
  const path = detailPath(context);
  const found = path.findIndex(item => sameDetailIdentity(item, detail));
  return (found >= 0 ? [...path.slice(0, found), detail] : [...path, detail]).slice(-8).map(refString).join("~");
}
export function reduceInvestigation(state: InvestigationState, action: InvestigationAction): ActionResult {
  if (action.expectedRevision !== undefined && action.expectedRevision !== state.revision)
    return { state, accepted: false, changed: false, history: "push" };
  let candidate: Partial<InvestigationContext> = { ...state.context };
  let history: "push" | "replace" = "push";
  let actionIssues: ContextIssue[] = [];
  switch (action.type) {
    case "applyScope":
      for (const field of SCOPE_FIELDS) if (action.scope[field] !== undefined) Object.assign(candidate, { [field]: action.scope[field] });
      break;
    case "focusEntity":
      candidate.focus = action.entity.id;
      candidate.detail_path = panelPath(state.context, action.entity);
      break;
    case "togglePin": {
      const field = action.entity.type === "company" ? "cohort_companies" : "cohort_varieties";
      const ids = splitIds(state.context[field]);
      candidate[field] = (ids.includes(action.entity.id) ? ids.filter(id => id !== action.entity.id) : [...ids, action.entity.id]).join(",");
      break;
    }
    case "setCohort": candidate[action.kind === "company" ? "cohort_companies" : "cohort_varieties"] = action.ids.join(","); break;
    case "setLens":
      candidate.lens = action.lens;
      if (action.comparison_kind) candidate.comparison_kind = action.comparison_kind;
      break;
    case "setCompanySet": candidate.company_set = action.company_set; break;
    case "openDetail": candidate.detail_path = panelPath(state.context, action.detail); break;
    case "setDetailSection": {
      const path = detailPath(state.context);
      const last = path.at(-1);
      if (last?.type === "source") candidate.detail_path = [...path.slice(0, -1), { ...last, section: action.section }].map(refString).join("~");
      break;
    }
    case "closeDetail": candidate.detail_path = detailPath(state.context).slice(0, -1).map(refString).join("~"); break;
    case "dismissDetails": candidate.detail_path = ""; break;
    case "setDemoCohort": candidate.demo_specimens = action.ids.join(","); break;
    case "replaceContext": candidate = action.context; break;
    case "setSearch": candidate.q = action.q; if (action.q_scope) candidate.q_scope = action.q_scope; history = "replace"; break;
  }
  const normalized = normalizeContext(candidate);
  actionIssues = normalized.issues;
  const changed = !sameContext(state.context, normalized.context);
  return {
    state: { context: normalized.context, issues: actionIssues, revision: changed ? state.revision + 1 : state.revision },
    accepted: true, changed, history,
  };
}
export function revisionMatches(currentRevision: number, expectedRevision: number): boolean {
  return Number.isSafeInteger(expectedRevision) && currentRevision === expectedRevision;
}
export function isFocalEntity(context: InvestigationContext, entity: EntityRef): boolean {
  return context.focus === entity.id;
}
