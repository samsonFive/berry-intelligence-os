import assert from 'node:assert/strict';
import test from 'node:test';
import { EMPTY_CONTEXT } from '../src/contracts/investigation.ts';
import { captureSave, capturedOutput, nativeSavedHref, outputKey, previewScopeLabel, responseStillCurrent } from '../src/features/workspaces/state.ts';

const row = { id: 'lview-existing', revision: 3, archived: false, is_investigation: true, href: '/app/landscape?ctx_v=1&berry=all&countries=', name: 'Existing' };
test('saving captures selectors independently and new saves never carry an overwrite target', () => {
  const context = { ...EMPTY_CONTEXT, cohort_companies: 'company-one', detail_path: 'source:ev-one@brief', demo_specimens: 'demo-specimen-fern', document_body: 'PRIVATE BODY' };
  const saved = captureSave(context, ' Current selection ', 'new', row);
  context.cohort_companies = 'company-newer';
  assert.equal(saved.name, 'Current selection'); assert.equal(saved.save_as_new, true);
  assert.equal(saved.context.cohort_companies, 'company-one'); assert.equal(saved.context.detail_path, 'source:ev-one@brief');
  assert.equal(saved.context.demo_specimens, 'demo-specimen-fern'); assert.equal('document_body' in saved.context, false);
  assert.equal('id' in saved, false); assert.equal('revision' in saved, false);
});

test('saved monitored News resolves the current shared watch universe without copying its members', () => {
  const saved = captureSave({ ...EMPTY_CONTEXT, company_set: 'watched', lens: 'news', cohort_companies: 'company-one' }, 'Monitored news', 'new');
  assert.equal(saved.context.company_set, 'watched');
  assert.equal(saved.context.lens, 'news');
  assert.equal(saved.context.cohort_companies, 'company-one');
  assert.equal('watched_company_ids' in saved.context, false);
  assert.notEqual(outputKey(capturedOutput(saved.context, ['readout'], false)), outputKey(capturedOutput({ ...saved.context, company_set: 'all' }, ['readout'], false)));
});
test('updates require an explicit current investigation revision and preserve legacy rows', () => {
  const saved = captureSave(EMPTY_CONTEXT, 'Updated', 'update', row);
  assert.equal(saved.id, row.id); assert.equal(saved.revision, 3); assert.equal(saved.save_as_new, false);
  assert.throws(() => captureSave(EMPTY_CONTEXT, 'Updated', 'update', { ...row, is_investigation: false }), /existing workspace/);
  assert.throws(() => captureSave(EMPTY_CONTEXT, 'x'.repeat(81), 'new'), /80/);
});
test('native saved navigation uses the returned href and rejects another origin or legacy route', () => {
  assert.equal(nativeSavedHref(row), row.href);
  for (const href of ['//outside.invalid/app/landscape', '/workspaces', '/app/learn/concept/..', '/\\outside.invalid']) assert.throws(() => nativeSavedHref({ ...row, href }));
});
test('ordinary output strips demo and saved references; an explicit annex captures the selected fixture cohort', () => {
  const context = { ...EMPTY_CONTEXT, demo_specimens: 'demo-specimen-fern', saved_view_id: 'lview-one', saved_revision: '3' };
  const normal = capturedOutput(context, ['readout'], false), annex = capturedOutput(context, ['readout'], true);
  assert.equal(normal.context.demo_specimens, ''); assert.equal(normal.context.saved_view_id, ''); assert.equal(normal.context.saved_revision, '');
  assert.equal(annex.context.demo_specimens, 'demo-specimen-fern');
  assert.equal(outputKey(normal), outputKey(capturedOutput({ ...context, demo_specimens: 'demo-specimen-amber' }, ['readout'], false)));
  assert.notEqual(outputKey(normal), outputKey(annex));
});
test('late save/preview/download results cannot replace a newer action or changed output selection', () => {
  assert.equal(responseStillCurrent(4, 4, 'selection-a', 'selection-a'), true);
  assert.equal(responseStillCurrent(4, 5, 'selection-a', 'selection-a'), false);
  assert.equal(responseStillCurrent(4, 4, 'selection-a', 'selection-b'), false);
});
test('export preview scope uses resolved human labels and keeps an unknown geography explicit', () => {
  assert.equal(previewScopeLabel({ berry: 'Blueberry', countries: ['Chile', 'China', 'Peru'] }), 'Blueberry · Chile · China · Peru');
  assert.equal(previewScopeLabel({ berry: 'All berries', countries: [] }), 'All berries · All geographies');
  assert.equal(previewScopeLabel({ berry: 'Blueberry', countries: ['geography-unavailable'] }), 'Blueberry · Unavailable selected geography');
});
