import type { InvestigationContext } from '../../contracts/investigation';
import { InvestigationApiError } from '../../api/client.ts';

const ROOT = '/api/investigations/v1';
export class WorkspaceRequestError extends InvestigationApiError {}
export interface SavedInvestigation {
  id: string; name: string; filters: Record<string, string>; revision: number;
  archived: boolean; updated_at: string; kind: string; surface: string;
  href: string; is_investigation: boolean;
}
export const OUTPUT_SECTIONS = [
  ['readout', 'Scope findings'], ['relationships', 'Recorded relationships'],
  ['portfolio', 'Company and cultivar portfolio'], ['geography', 'Geographic activity'],
  ['comparison', 'Selected comparison'], ['developments', 'Relevant developments'],
] as const;
export type OutputSection = typeof OUTPUT_SECTIONS[number][0];
export interface OutputSelection {
  context: InvestigationContext; section_ids: OutputSection[]; include_demo: boolean;
}
export interface OutputPreview {
  api_v: 1; content_hash: string; section_ids: OutputSection[]; include_demo: boolean;
  scope: { berry: string; countries: string[]; geographic_basis: string; news_from: string; news_to: string;
    comparison_companies: string[]; comparison_varieties: string[] };
  sections: { id: OutputSection; title: string; row_count: number; basis: string; source_ids: string[] }[];
  sources: { id: string; title?: string; url?: string; published?: string; captured?: string }[];
  issues: { message: string }[]; date_note: string;
  synthetic_annex: null | { specimen_count: number; specimen_labels: string[]; selection_mode: string };
}
async function checked(response: Response): Promise<Response> {
  if (response.redirected || response.status === 401)
    throw new WorkspaceRequestError('Sign in to continue with this investigation.', 401);
  if (!response.ok) {
    const body = response.headers.get('content-type')?.includes('application/json') ? await response.json() : null;
    const message = typeof body?.detail === 'string' ? body.detail : 'The requested workspace action could not be completed.';
    throw new WorkspaceRequestError(message.slice(0, 500), response.status);
  }
  return response;
}
async function json(path: string, payload?: unknown, signal?: AbortSignal) {
  const response = await checked(await fetch(ROOT + path, {
    method: payload === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store', signal,
    headers: { Accept: 'application/json', ...(payload === undefined ? {} : { 'Content-Type': 'application/json' }) },
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
  }));
  if (!response.headers.get('content-type')?.includes('application/json'))
    throw new WorkspaceRequestError('The server returned an incompatible workspace response.', 502);
  const body = await response.json();
  if (body?.api_v !== 1) throw new WorkspaceRequestError('The server returned an unsupported workspace version.', 502);
  return body;
}
function savedRow(value: unknown): SavedInvestigation {
  const row = value as SavedInvestigation | null;
  if (!row || typeof row.id !== 'string' || typeof row.name !== 'string' || !Number.isSafeInteger(row.revision)
    || row.revision < 1 || typeof row.is_investigation !== 'boolean' || typeof row.href !== 'string'
    || !row.href.startsWith('/') || row.href.startsWith('//') || row.href.includes('\\')
    || !row.filters || typeof row.filters !== 'object' || Array.isArray(row.filters)
    || Object.values(row.filters).some(item => typeof item !== 'string'))
    throw new WorkspaceRequestError('A saved view is incompatible. Open its existing workspace to review it.', 502);
  return row;
}
export async function listSaved(signal?: AbortSignal): Promise<SavedInvestigation[]> {
  const body = await json('/saved', undefined, signal);
  if (!Array.isArray(body.data)) throw new WorkspaceRequestError('Saved views could not be read.', 502);
  return body.data.map(savedRow);
}
export async function getSaved(id: string): Promise<SavedInvestigation> {
  return savedRow((await json(`/saved/${encodeURIComponent(id)}`)).data);
}
export async function saveInvestigation(payload: { name: string; context: InvestigationContext;
  id?: string; revision?: number; save_as_new: boolean }): Promise<SavedInvestigation> {
  return savedRow((await json('/saved', payload)).data);
}
export async function previewOutput(selection: OutputSelection): Promise<OutputPreview> {
  const body = await json('/export/preview', selection);
  if (!/^[a-f0-9]{64}$/.test(body.content_hash ?? '') || !Array.isArray(body.sections) || !Array.isArray(body.sources))
    throw new WorkspaceRequestError('The output preview is incompatible. Review a fresh preview.', 502);
  return body as OutputPreview;
}
export async function downloadOutput(selection: OutputSelection, expectedHash: string): Promise<Blob> {
  const response = await checked(await fetch(ROOT + '/export/pdf', {
    method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: { 'Content-Type': 'application/json', Accept: 'application/pdf' },
    body: JSON.stringify({ ...selection, expected_content_hash: expectedHash }),
  }));
  if (!response.headers.get('content-type')?.includes('application/pdf')
    || response.headers.get('x-investigation-content-hash') !== expectedHash)
    throw new WorkspaceRequestError('The output did not match the reviewed preview. Review it again.', 502);
  const blob = await response.blob();
  if (await blob.slice(0, 5).text() !== '%PDF-') throw new WorkspaceRequestError('The PDF could not be read.', 502);
  return blob;
}
