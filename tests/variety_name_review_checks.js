const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// Exercise the real loader in a small DOM fixture; no browser or network calls.
const source = fs.readFileSync('app/static/variety_workspace.js', 'utf8')
  .split('// Keep candidate navigation')[0];
const listeners = {};
const actions = {};
const results = {innerHTML: 'Not checked yet'};
const refresh = {hidden: true, disabled: false, addEventListener: (event, callback) => {actions[event] = callback;}};
const section = {open: false, dataset: {reviewUrl: '/api/varieties/variety-fixture/name-review'},
  querySelector: selector => selector.includes('results') ? results : refresh,
  addEventListener: (event, callback) => {listeners[event] = callback;}};
const requests = [];
const timers = new Map();
let timerId = 0;
vm.runInNewContext(source, {
  document: {querySelectorAll: () => [section]}, AbortController,
  setTimeout: callback => {timers.set(++timerId, callback); return timerId;},
  clearTimeout: id => timers.delete(id),
  fetch: (url, options) => new Promise((resolve, reject) => {
    requests.push({url, options, resolve, reject});
    options.signal.addEventListener('abort', () => reject(new Error('aborted')));
  }),
});
const flush = () => new Promise(resolve => setImmediate(resolve));
const reply = (request, text, overrides = {}) => request.resolve({
  ok: true, redirected: false, text: async () => text, ...overrides,
});

(async () => {
  assert.equal(requests.length, 0, 'A closed section must not start the global name audit');
  section.open = true; listeners.toggle();
  assert.equal(requests.length, 1);
  assert.equal(refresh.disabled, true);
  assert.equal(requests[0].options.credentials, 'same-origin');
  section.open = false; listeners.toggle(); section.open = true; listeners.toggle();
  assert.equal(requests.length, 1, 'Repeated toggles duplicated an active audit');
  reply(requests[0], '<p>Current name matches</p>'); await flush();
  assert.equal(results.innerHTML, '<p>Current name matches</p>');
  assert.equal(refresh.disabled, false); assert.equal(timers.size, 0);
  section.open = false; listeners.toggle(); section.open = true; listeners.toggle();
  assert.equal(requests.length, 1, 'Reopening the same loaded section repeated work');
  actions.click(); assert.equal(requests.length, 2);
  reply(requests[1], '<form>Private login page</form>', {redirected: true}); await flush();
  assert(!results.innerHTML.includes('<form>'));
  assert(results.innerHTML.includes('Open the full name review') || results.innerHTML.includes('open the full name review'));
  assert.equal(refresh.disabled, false);
  actions.click(); assert.equal(requests.length, 3);
  [...timers.values()][0](); await flush();
  assert(results.innerHTML.includes('could not be loaded'));
  assert.equal(refresh.disabled, false); assert.equal(timers.size, 0);
  actions.click(); assert.equal(requests.length, 4);
  reply(requests[3], '<p>Fresh results after review</p>'); await flush();
  assert.equal(results.innerHTML, '<p>Fresh results after review</p>');
  assert.equal(refresh.hidden, false);
  process.stdout.write('Closed/deferred, duplicate, refresh, expired-login, timeout and recovery checks passed.\n');
})().catch(error => {console.error(error); process.exitCode = 1;});
