import type { LearningContent } from './models.ts';

type CropNote = LearningContent['berry_notes'][number];

/** Keep all authored notes, distinguishing selected-crop context without inferring applicability. */
export function groupCropNotes(notes: readonly CropNote[], berry: string) {
  const isGlobal = berry === 'all';
  const inContext = isGlobal ? [...notes] : notes.filter(note => note.berry_id === berry);
  const alsoGlobal = isGlobal ? [] : notes.filter(note => note.berry_id !== berry);
  const berryLabel = inContext[0]?.berry_label
    ?? berry.replace(/^berry-/, '').replace(/^./, character => character.toUpperCase());
  return { isGlobal, berryLabel, inContext, alsoGlobal };
}
