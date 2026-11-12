import assert from 'node:assert/strict';
import test from 'node:test';
import { groupCropNotes } from '../src/features/learn/crop-notes.ts';

const raspberry = Object.freeze({ berry_id: 'berry-raspberry', berry_label: 'Raspberry', note: 'Authored raspberry note.' });
const blueberry = Object.freeze({ berry_id: 'berry-blueberry', berry_label: 'Blueberry', note: 'Authored blueberry note.' });
const blackberry = Object.freeze({ berry_id: 'berry-blackberry', berry_label: 'Blackberry', note: 'Authored blackberry note.' });

test('selected crop partitions all authored notes without changing text or within-group order', () => {
  const notes = Object.freeze([raspberry, blueberry, blackberry, raspberry]);
  const groups = groupCropNotes(notes, 'berry-blueberry');
  assert.equal(groups.isGlobal, false);
  assert.equal(groups.berryLabel, 'Blueberry');
  assert.deepEqual(groups.inContext, [blueberry]);
  assert.deepEqual(groups.alsoGlobal, [raspberry, blackberry, raspberry]);
  assert.equal(groups.inContext[0], blueberry);
  assert.equal(groups.inContext.length + groups.alsoGlobal.length, notes.length);
});

test('a selected crop with no authored note stays empty while other crops remain available', () => {
  const groups = groupCropNotes([raspberry, blackberry], 'berry-blueberry');
  assert.equal(groups.berryLabel, 'Blueberry');
  assert.deepEqual(groups.inContext, []);
  assert.deepEqual(groups.alsoGlobal, [raspberry, blackberry]);
});

test('All berries retains the original complete order without a separate other-crop group', () => {
  const notes = Object.freeze([raspberry, blueberry, blackberry]);
  const groups = groupCropNotes(notes, 'all');
  assert.equal(groups.isGlobal, true);
  assert.deepEqual(groups.inContext, notes);
  assert.deepEqual(groups.alsoGlobal, []);
  assert.notEqual(groups.inContext, notes);
});

test('group labels use authored crop metadata and empty notes never imply crop applicability', () => {
  const authored = { ...blueberry, berry_label: 'Authored blueberry label' };
  assert.equal(groupCropNotes([authored], 'berry-blueberry').berryLabel, authored.berry_label);
  const groups = groupCropNotes([], 'berry-blueberry');
  assert.deepEqual(groups.inContext, []);
  assert.deepEqual(groups.alsoGlobal, []);
});
