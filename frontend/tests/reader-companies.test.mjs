import assert from 'node:assert/strict';
import test from 'node:test';
import { readerOrganizations } from '../src/features/detail/reader-companies.ts';

test('Reader company branding uses exact source associations and keeps mentions qualified', () => {
  assert.deepEqual(readerOrganizations({ entities: [
    { id: 'company-one', name: 'One', entity_type: 'company' },
    { id: 'brand-one', name: 'One label', entity_type: 'brand' },
    { id: 'company-two', name: 'Two' },
    { id: 'company-three', name: 'Explicit conflicting type', entity_type: 'brand' },
  ], company_mentions: [{ id: 'company-one', name: 'Alias' }, { id: 'company-two', name: 'Two' }, { id: 'company-four', name: 'Four' }] }), [
    { id: 'company-one', name: 'One', kind: 'company', association: 'linked' },
    { id: 'brand-one', name: 'One label', kind: 'brand', association: 'linked' },
    { id: 'company-two', name: 'Two', kind: 'company', association: 'linked' },
    { id: 'company-four', name: 'Four', kind: 'company', association: 'mentioned' },
  ]);
});

test('unassociated sources do not borrow publisher, pinned or ancestor company branding', () => {
  assert.deepEqual(readerOrganizations(), []);
  assert.deepEqual(readerOrganizations({ source_name: 'Publisher', cohort_companies: 'company-one', ancestry: 'company-one' }), []);
  assert.deepEqual(readerOrganizations({ company_mentions: [{ id: '../company-one', name: 'Invalid' }] }), []);
});
