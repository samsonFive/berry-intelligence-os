const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../app/static/workspace_anchor_offsets.js'), 'utf8');

function page({height = 64, observer = true, header = true} = {}) {
  const values = new Map(), events = new Map();
  let resized, currentHeight = height;
  const shell = {getBoundingClientRect() {return {height: currentHeight};}};
  const document = {querySelector(selector) {assert.equal(selector, '.glass-header'); return header ? shell : null;},
    documentElement: {style: {getPropertyValue: key => values.get(key), setProperty: (key, value) => values.set(key, value)}}};
  const window = {addEventListener: (name, fn) => events.set(name, fn)};
  const context = {document, window};
  if (observer) {
    context.ResizeObserver = window.ResizeObserver = class {
      constructor(fn) {resized = fn;}
      observe(target) {assert.equal(target, shell);}
    };
  }
  vm.runInNewContext(script, context);
  return {offset: () => values.get('--glass-anchor-offset'),
    wrap(nextHeight) {currentHeight = nextHeight; (resized || events.get('resize'))();},
    restore(nextHeight) {currentHeight = nextHeight; events.get('pageshow')();}};
}

const normal = page();
assert.equal(normal.offset(), '80px');
normal.wrap(132.5);
assert.equal(normal.offset(), '149px');
normal.restore(96);
assert.equal(normal.offset(), '112px');
const fallback = page({observer: false});
fallback.wrap(178);
assert.equal(fallback.offset(), '194px');
assert.equal(page({header: false}).offset(), undefined);
console.log('Shared header wrap, resize, restored-page and headerless checks passed.');
