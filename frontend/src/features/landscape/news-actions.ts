import { InvestigationApiError } from '../../api/client.ts';
import { CANONICAL_ID } from '../../contracts/investigation.ts';
import type { NewsDecision } from './models.ts';
export type NewsAction = 'useful' | 'not_relevant' | 'clear_feedback' | 'save' | 'unsave';
const ACTIONS = new Set<NewsAction>(['useful', 'not_relevant', 'clear_feedback', 'save', 'unsave']);
/** The existing News tag drawer uses this bounded marker; story/item/refresh have other effects. */
export function newsTagEditorHref(scopedHref: string, id: string): string {
  if (!CANONICAL_ID.test(id) || !scopedHref.startsWith('/') || scopedHref.startsWith('//') || scopedHref.includes('\\')) throw new Error('Use a local scoped News destination.');
  const url = new URL(scopedHref, 'https://native-news.invalid');
  if (!['/news', '/today'].includes(url.pathname)) throw new Error('Use the established News workspace.');
  for (const field of ['story', 'item', 'refresh']) url.searchParams.delete(field);
  url.searchParams.set('tags_for', id);
  return url.pathname + url.search;
}
/** Existing personal state only; never capture a body or change source/claim review. */
export async function saveNewsAction(id: string, action: NewsAction, signal?: AbortSignal): Promise<NewsDecision> {
  if (!CANONICAL_ID.test(id) || !ACTIONS.has(action)) throw new InvestigationApiError('Unsupported story action.', 400);
  const response = await fetch(`/digest/stories/${encodeURIComponent(id)}`, { method: 'POST', credentials: 'same-origin', cache: 'no-store',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ action }), signal, keepalive: true });
  if (response.redirected || response.status === 401 || response.status === 403) throw new InvestigationApiError('Sign in to save this story action.', response.status === 403 ? 403 : 401);
  if (!response.ok) throw new InvestigationApiError('Could not save this change. Try again.', response.status);
  const data = (response.headers.get('content-type') ?? '').includes('application/json') ? await response.json() : null;
  if (data?.ok !== true || typeof data.decision?.saved !== 'boolean' || ![null, 'up', 'down'].includes(data.decision?.reaction))
    throw new InvestigationApiError('The story action returned an incompatible response.', 502);
  return { reaction: data.decision.reaction, saved: data.decision.saved };
}
function record(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
/** Update exact-story personal metadata across cached feeds, preserving provenance. */
export function updateNewsDecision<T>(envelope: T, id: string, decision: NewsDecision): T {
  if (!record(envelope) || !record(envelope.data) || !Array.isArray(envelope.data.cards)) return envelope;
  let changed = false;
  const cards = envelope.data.cards.map(card => { if (!record(card) || card.id !== id) return card; changed = true; return { ...card, decision: { ...decision } }; });
  return changed ? { ...envelope, data: { ...envelope.data, cards } } as T : envelope;
}
