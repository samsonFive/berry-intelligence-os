/** Shared selectors only. Canonical records and source bodies remain server-owned. */
export const CONTEXT_FIELDS = [
  "ctx_v", "berry", "countries", "geo_basis", "actor_roles", "relationship_types",
  "news_from", "news_to", "focus", "cohort_companies", "cohort_varieties", "lens",
  "comparison_kind", "detail_path", "q", "q_scope", "saved_view_id", "saved_revision", "demo_specimens",
] as const;
export type ContextField = typeof CONTEXT_FIELDS[number];
export type Berry = "all" | "berry-blueberry" | "berry-strawberry" | "berry-raspberry" | "berry-blackberry";
export type GeographyBasis = "company_connections" | "source_geography" | "variety_growing" | "rights";
export type Lens = "connections" | "portfolio" | "geography" | "comparison" | "sensory";
export type EntityType = "company" | "variety";
export type DetailType = EntityType | "geography" | "relationship" | "source" | "observation";
export interface EntityRef { type: EntityType; id: string }
export type DetailSection = "article" | "brief";
export interface DetailRef { type: DetailType; id: string; section?: DetailSection }
export interface InvestigationContext {
  ctx_v: "1";
  berry: Berry;
  countries: string;
  geo_basis: GeographyBasis;
  actor_roles: string;
  relationship_types: string;
  news_from: string;
  news_to: string;
  focus: string;
  cohort_companies: string;
  cohort_varieties: string;
  lens: Lens;
  comparison_kind: EntityType;
  detail_path: string;
  q: string;
  q_scope: "scope" | "catalog";
  saved_view_id: string;
  saved_revision: string;
  /** Empty selects the complete synthetic fixture, independent of real entity cohorts. */
  demo_specimens: string;
}
export interface ContextIssue {
  code: string;
  field: string;
  message: string;
  values?: string[];
  id?: string;
}
export interface NormalizedContext { context: InvestigationContext; issues: ContextIssue[] }
export const EMPTY_CONTEXT: Readonly<InvestigationContext> = Object.freeze({
  ctx_v: "1", berry: "all", countries: "", geo_basis: "company_connections",
  actor_roles: "", relationship_types: "", news_from: "", news_to: "", focus: "",
  cohort_companies: "", cohort_varieties: "", lens: "connections", comparison_kind: "company",
  detail_path: "", q: "", q_scope: "scope", saved_view_id: "", saved_revision: "", demo_specimens: "",
});
export const PRESENTATION_CONTEXT: Readonly<InvestigationContext> = Object.freeze({
  ...EMPTY_CONTEXT, berry: "berry-blueberry",
  countries: "geography-chile,geography-china,geography-peru",
});
export const CANONICAL_ID = /^[A-Za-z0-9_.-]{1,180}$/;
const DETAIL_TYPES: readonly string[] = ["company", "variety", "geography", "relationship", "source", "observation"];
const ENUMS = {
  berry: ["all", "berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry"],
  geo_basis: ["company_connections", "source_geography", "variety_growing", "rights"],
  lens: ["connections", "portfolio", "geography", "comparison", "sensory"],
  comparison_kind: ["company", "variety"], q_scope: ["scope", "catalog"],
} as const;

export function splitIds(value: string): string[] { return value ? value.split(",").filter(Boolean) : []; }
export function refString(ref: DetailRef): string { return `${ref.type}:${ref.id}${ref.type === "source" && ref.section === "brief" ? "@brief" : ""}`; }
export function sameDetailIdentity(left: DetailRef, right: DetailRef): boolean { return left.type === right.type && left.id === right.id; }
export function parseRef(value: string): DetailRef | null {
  const match = /^([^:@]+):([^:@]+)(?:@(article|brief))?$/.exec(value);
  if (!match) return null;
  const [, type, id, section] = match;
  return DETAIL_TYPES.includes(type) && CANONICAL_ID.test(id) && (!section || type === "source")
    ? { type: type as DetailType, id, ...(section === "brief" ? { section: "brief" as const } : {}) } : null;
}
export function detailPath(context: Pick<InvestigationContext, "detail_path">): DetailRef[] {
  return context.detail_path.split("~").map(parseRef).filter((ref): ref is DetailRef => ref !== null);
}
export function currentDetail(context: Pick<InvestigationContext, "detail_path">): DetailRef | null {
  return detailPath(context).at(-1) ?? null;
}
function validDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number(value.slice(0, 4)) < 1) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.valueOf()) && date.toISOString().slice(0, 10) === value;
}

export function normalizeContext(input: Partial<Record<ContextField, unknown>>): NormalizedContext {
  const context: InvestigationContext = { ...EMPTY_CONTEXT };
  const issues: ContextIssue[] = [];
  const issue = (field: string, code: string, message: string, values?: string[]) => {
    issues.push({ field, code, message, ...(values?.length ? { values } : {}) });
  };
  const text = (field: ContextField, max = 4096): string => {
    const raw = input[field];
    if (raw === undefined || raw === null) return "";
    if (typeof raw !== "string") { issue(field, "invalid_type", `${field} must be text.`); return ""; }
    if (raw.length > max) issue(field, "input_too_long", `${field} exceeds its supported length.`);
    return raw.trim();
  };
  if (input.ctx_v !== undefined && input.ctx_v !== "1") {
    issue("ctx_v", "unsupported_version", "This investigation version is not supported.");
    Object.assign(context, { ctx_v: text("ctx_v") });
  }
  for (const field of Object.keys(ENUMS) as (keyof typeof ENUMS)[]) {
    const raw = text(field, 64);
    const value = field === "berry" && ["blueberry", "strawberry", "raspberry", "blackberry"].includes(raw) ? `berry-${raw}` : raw;
    if (!value && input[field] === undefined) continue;
    Object.assign(context, { [field]: value });
    if (!(ENUMS[field] as readonly string[]).includes(value)) issue(field, "invalid_value", `Unsupported ${field.replaceAll("_", " ")}.`, [value]);
  }
  for (const field of ["countries", "actor_roles", "relationship_types", "cohort_companies", "cohort_varieties", "demo_specimens"] as const) {
    const values = text(field).split(",").map(value => value.trim()).filter(Boolean);
    const invalid = values.filter(value => !CANONICAL_ID.test(value) || (field === "demo_specimens" && !/^demo-specimen-[A-Za-z0-9_.-]+$/.test(value)));
    if (invalid.length) issue(field, "invalid_identifier", "Some selected identifiers are invalid.", invalid);
    const unique = [...new Set(values)];
    if (unique.length > 40) issue(field, "excessive_selection", "At most 40 identifiers can be retained in one selection.");
    const cap = field === "cohort_companies" ? 5 : field === "cohort_varieties" ? 4 : 40;
    if (cap < 40 && unique.length > cap) issue(field, "overflow", `Only the first ${cap} selected subjects are compared; remove or reorder the remaining selection.`, unique.slice(cap));
    context[field] = unique.join(",");
  }
  for (const field of ["news_from", "news_to"] as const) {
    const value = text(field, 10);
    context[field] = value;
    if (value && !validDate(value)) issue(field, "invalid_date", "Use a real publication date in YYYY-MM-DD format.", [value]);
  }
  if (context.news_from && context.news_to && context.news_from > context.news_to)
    issue("news_from", "date_order", "Publication start date is later than the end date.");
  const focusInput = text("focus", 190);
  const typedFocus = parseRef(focusInput);
  const focus = typedFocus && ["company", "variety"].includes(typedFocus.type) ? typedFocus.id : focusInput;
  context.focus = focus;
  if (focus && !CANONICAL_ID.test(focus)) issue("focus", "invalid_reference", "The focal subject is invalid.", [focus]);
  const path = text("detail_path").split("~").filter(Boolean);
  const invalidDetails = path.filter(value => !parseRef(value));
  if (invalidDetails.length) issue("detail_path", "invalid_reference", "Some detail references are invalid.", invalidDetails);
  if (path.length > 8) issue("detail_path", "detail_overflow", "At most eight detail ancestors can be restored.", path.slice(0, -8));
  context.detail_path = path.map(value => { const ref = parseRef(value); return ref ? refString(ref) : value; }).join("~");
  context.q = text("q", 200).replace(/[\u0000-\u001f\u007f]/g, "");
  const savedId = text("saved_view_id", 180);
  context.saved_view_id = savedId;
  if (savedId && !CANONICAL_ID.test(savedId)) issue("saved_view_id", "invalid_identifier", "The saved investigation identifier is invalid.", [savedId]);
  const savedRevision = text("saved_revision", 10);
  context.saved_revision = savedRevision;
  if (savedRevision && !/^\d{1,10}$/.test(savedRevision)) issue("saved_revision", "invalid_revision", "The saved investigation revision is invalid.");
  return { context, issues };
}

export function parseInvestigation(search: string | URLSearchParams): NormalizedContext {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  const input: Partial<Record<ContextField, unknown>> = {};
  const duplicateIssues: ContextIssue[] = [];
  for (const field of CONTEXT_FIELDS) {
    if (!params.has(field)) continue;
    input[field] = ["countries", "actor_roles", "relationship_types", "cohort_companies", "cohort_varieties", "demo_specimens"].includes(field) ? params.getAll(field).join(",") : params.getAll(field).at(-1);
    if (params.getAll(field).length > 1) duplicateIssues.push({ field, code: "duplicate_parameter", message: `Repeated ${field} parameters are ambiguous.` });
  }
  const result = normalizeContext(input);
  return { context: result.context, issues: [...duplicateIssues, ...result.issues] };
}

/** Explicit defaults, including All/empty countries, defeat legacy cookie defaults. */
export function serializeInvestigation(context: InvestigationContext): string {
  const normalized = normalizeContext(context).context;
  const params = new URLSearchParams();
  for (const field of CONTEXT_FIELDS) {
    if (normalized[field] !== "" || field === "countries") params.set(field, normalized[field]);
  }
  return params.toString();
}
export function isNativeSurfacePath(path: string): boolean {
  if (/^\/app\/(landscape|briefing|workspaces|learn)$/.test(path)) return true;
  const learning = /^\/app\/learn\/(concept|lesson)\/([A-Za-z0-9_.-]{1,180})$/.exec(path);
  return Boolean(learning && ![".", ".."].includes(learning[2]));
}
export function investigationHref(path: string, context: InvestigationContext): string {
  if (!isNativeSurfacePath(path)) throw new Error("Unsupported application destination.");
  return `${path}?${serializeInvestigation(context)}`;
}
export function sameContext(left: InvestigationContext, right: InvestigationContext): boolean {
  return CONTEXT_FIELDS.every(field => left[field] === right[field]);
}
export function scopeKey(context: InvestigationContext): string {
  const fields: ContextField[] = ["berry", "countries", "geo_basis", "actor_roles", "relationship_types", "news_from", "news_to"];
  return fields.map(field => `${field}=${context[field]}`).join("&");
}
export function hasBlockingIssues(issues: ContextIssue[]): boolean {
  return issues.some(issue => issue.code !== "overflow");
}
