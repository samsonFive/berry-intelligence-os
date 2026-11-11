import { hasBlockingIssues, isNativeSurfacePath, normalizeContext, serializeInvestigation } from '../../contracts/investigation.ts';
import type { InvestigationContext } from '../../contracts/investigation.ts';
import type { OutputSelection, OutputSection, SavedInvestigation } from './api.ts';

export function captureSave(context: InvestigationContext, name: string, mode: 'new' | 'update', target?: SavedInvestigation) {
  const title = name.trim();
  if (!title || title.length > 80) throw new Error('Use a name between 1 and 80 characters.');
  const normalized = normalizeContext(context);
  if (hasBlockingIssues(normalized.issues)) throw new Error('Resolve the investigation selectors before saving.');
  if (mode === 'update' && (!target?.is_investigation || target.archived || !Number.isSafeInteger(target.revision) || target.revision < 1))
    throw new Error('Choose a saved investigation to update. Earlier saved views keep their existing workspace.');
  return { name: title, context: { ...normalized.context }, save_as_new: mode === 'new',
    ...(mode === 'update' && target ? { id: target.id, revision: target.revision } : {}) };
}
export function nativeSavedHref(row: SavedInvestigation): string {
  if (!row.is_investigation || !row.href.startsWith('/') || row.href.startsWith('//') || row.href.includes('\\')) throw new Error('Open this saved view in its existing workspace.');
  const url = new URL(row.href, 'https://workspace.invalid');
  if (url.origin !== 'https://workspace.invalid' || !isNativeSurfacePath(url.pathname)) throw new Error('The saved investigation has an unsupported destination.');
  return row.href;
}
export function capturedOutput(context: InvestigationContext, sections: readonly OutputSection[], includeDemo: boolean): OutputSelection {
  return { context: { ...context, saved_view_id: '', saved_revision: '', demo_specimens: includeDemo ? context.demo_specimens : '' }, section_ids: [...sections], include_demo: includeDemo };
}
export function outputKey(selection: OutputSelection): string {
  return JSON.stringify([serializeInvestigation(selection.context), selection.section_ids, selection.include_demo]);
}
export function responseStillCurrent(capturedRevision: number, currentRevision: number, capturedKey: string, currentKey: string): boolean {
  return capturedRevision === currentRevision && capturedKey === currentKey;
}
export const LENS_LABELS: Record<InvestigationContext['lens'], string> = {
  connections: 'Recorded connections', portfolio: 'Cultivar portfolio', geography: 'Geographic connections', comparison: 'Selected comparison', sensory: 'Synthetic sensory demo',
};
export const BERRY_LABELS: Record<string, string> = { all: 'All berries', 'berry-blueberry': 'Blueberry', 'berry-strawberry': 'Strawberry', 'berry-raspberry': 'Raspberry', 'berry-blackberry': 'Blackberry' };
/** The export presenter already resolves IDs to display names; never run those names through an ID lookup again. */
export function previewScopeLabel(scope: { berry: string; countries: string[] }): string {
  const berry = BERRY_LABELS[scope.berry] ?? scope.berry;
  const geographies = scope.countries.map(label => label.startsWith('geography-') ? 'Unavailable selected geography' : label);
  return `${berry} · ${geographies.length ? geographies.join(' · ') : 'All geographies'}`;
}
export const GEOGRAPHY_LABELS: Record<string, string> = { company_connections: 'Recorded company connections', source_geography: 'Source geography', variety_growing: 'Recorded cultivar growing', rights: 'Recorded rights context' };
