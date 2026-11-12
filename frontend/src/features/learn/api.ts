/** Learning owns its filters; investigation selectors remain navigation context. */
import { InvestigationApiError } from '../../api/client.ts';
import type { InvestigationEnvelope } from '../../api/client.ts';
import { serializeInvestigation } from '../../contracts/investigation.ts';
import type { InvestigationContext } from '../../contracts/investigation.ts';
import type { LearningCatalog, LearningContent, LearningKind, LearningSelection } from './models.ts';

export const DEFAULT_LEARNING_SELECTION: LearningSelection = { q: '', pillar: '', knowledge_class: '', kind: 'all', offset: 0, limit: 40 };
const SAFE_ID = /^[A-Za-z0-9_-]{1,180}$/;
export function learningRequestURL(context: InvestigationContext, revision: number, selection: LearningSelection,
  entry?: { kind: LearningKind; id: string }, returnTo = ''): string {
  if (!Number.isSafeInteger(revision) || revision < 0) throw new InvestigationApiError('Unsupported investigation revision.', 400);
  if (selection.q.length > 200 || !['all','concept','lesson'].includes(selection.kind)
    || !Number.isSafeInteger(selection.offset) || selection.offset < 0 || selection.offset > 100_000
    || !Number.isSafeInteger(selection.limit) || selection.limit < 1 || selection.limit > 100)
    throw new InvestigationApiError('Choose a bounded learning catalog selection.', 400);
  if (entry && (!['concept','lesson'].includes(entry.kind) || !SAFE_ID.test(entry.id)))
    throw new InvestigationApiError('Choose an available educational entry.', 400);
  const params = new URLSearchParams(serializeInvestigation(context));
  // q is always explicit, including empty. A global catalog search such as
  // Costa must never silently become a filter on the educational library.
  for (const key of ['q','pillar','knowledge_class','kind','offset','limit'] as const) params.set(key, String(selection[key]));
  params.set('revision', String(revision));
  if (returnTo) params.set('return_to', returnTo);
  const suffix = entry ? `/${entry.kind}/${encodeURIComponent(entry.id)}` : '';
  return `/api/investigations/v1/learning${suffix}?${params}`;
}

async function read<T>(url: string, revision: number, selected: boolean, signal?: AbortSignal): Promise<InvestigationEnvelope<T>> {
  const response = await fetch(url, { signal, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
  if (response.redirected || response.status === 401) throw new InvestigationApiError('Sign in to continue reading Learn.', 401);
  let body;
  try { body = (response.headers.get('content-type') ?? '').includes('application/json') ? await response.json() : null; }
  catch { throw new InvestigationApiError('Learn returned an unreadable response. Try again.', 502); }
  if (!response.ok) throw new InvestigationApiError(typeof body?.detail === 'string' ? body.detail.slice(0, 500) : 'Learn could not be loaded.', response.status);
  if (!body || body.api_v !== 1 || body.revision !== revision || typeof body.request_id !== 'string'
    || typeof body.scope_key !== 'string' || !Array.isArray(body.issues) || !body.data)
    throw new InvestigationApiError('Learn returned an incompatible response.', 502);
  const data = body.data;
  const valid = selected ? data.item && ['concept','lesson'].includes(data.item.kind) && typeof data.item.id === 'string'
    && ['sections','citations','media','berry_notes','related'].every(key => Array.isArray(data[key]))
    : ['concepts','lessons'].every(key => Array.isArray(data.collections?.[key]?.items))
      && Array.isArray(data.facets?.pillars) && Array.isArray(data.facets?.knowledge_classes) && data.counts;
  if (!valid) throw new InvestigationApiError('Learn returned an incompatible reading model.', 502);
  return body as InvestigationEnvelope<T>;
}
export function getLearningCatalog(context: InvestigationContext, revision: number, selection: LearningSelection, signal?: AbortSignal) {
  return read<LearningCatalog>(learningRequestURL(context, revision, selection), revision, false, signal);
}
export function getLearningContent(kind: LearningKind, id: string, context: InvestigationContext, revision: number, returnTo: string, signal?: AbortSignal) {
  return read<LearningContent>(learningRequestURL(context, revision, DEFAULT_LEARNING_SELECTION, { kind, id }, returnTo), revision, true, signal)
    .then(envelope => {
      if (envelope.data.item.kind !== kind || envelope.data.item.id !== id) throw new InvestigationApiError('Learn returned a different selected entry.', 502);
      return envelope;
    });
}

/** Cached lesson metadata never freezes a previous investigation's return URL. */
export function legacyExpansionHref(raw: string, returnTo: string): string | undefined {
  try {
    const origin = 'https://berry.invalid';
    const destination = new URL(raw, origin);
    if (destination.origin !== origin || !(destination.pathname === '/learn' || destination.pathname.startsWith('/learn/')) || raw.includes('\\')) return undefined;
    const back = new URL(returnTo, origin);
    const validBack = back.origin === origin && /^\/app\/learn(?:\/(concept|lesson)\/[A-Za-z0-9_-]{1,180})?$/.test(back.pathname)
      && returnTo.length <= 4096 && !/[\u0000-\u001f\\]/.test(returnTo);
    destination.searchParams.set('return_to', validBack ? back.pathname + back.search : '/app/learn');
    return destination.pathname + destination.search;
  } catch { return undefined; }
}
