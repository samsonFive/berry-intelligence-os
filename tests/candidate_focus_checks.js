const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../app/static/variety_workspace.js'), 'utf8');

function page({headerBottom = 133, navTop = 133, navHeight = 60, hasBar = true} = {}) {
  const events = new Map(), frames = new Map(), scrolls = [], styles = new Map();
  let nextFrame = 1;
  const workspace = {style: {setProperty: (key, value) => styles.set(key, value)},
    addEventListener: (name, listener) => events.set(name, listener)};
  const bar = {closest: () => workspace, querySelector: () => null,
    contains: target => Boolean(target.inNav),
    getBoundingClientRect: () => ({top: navTop, bottom: navTop + navHeight, height: navHeight})};
  const header = {getBoundingClientRect: () => ({top: 0, bottom: headerBottom, height: headerBottom})};
  const document = {activeElement: null, querySelectorAll: () => [],
    querySelector(selector) {
      if (selector === '[data-candidate-quick-nav]') return hasBar ? bar : null;
      if (selector === '.glass-header') return header;
      return null;
    }};
  const windowEvents = new Map();
  const window = {addEventListener: (name, listener) => windowEvents.set(name, listener),
    cancelAnimationFrame(id) {frames.delete(id);},
    requestAnimationFrame(fn) {const id = nextFrame++; frames.set(id, fn); return id;},
    scrollBy(options) {scrolls.push(options);}};
  vm.runInNewContext(script, {document, window, location: {hash: ''}});
  function target(top, options = {}) {
    return {isConnected: true, top, inNav: false,
      getBoundingClientRect() {return {top: this.top, bottom: this.top + 20, width: 100, height: 20};}, ...options};
  }
  return {scrolls, styles, document, target,
    focus(node) {document.activeElement = node; events.get('focusin')?.({target: node});},
    flush() {for (const [id, fn] of [...frames]) {frames.delete(id); fn();}},
    resize(nextHeader, nextNavTop) {headerBottom = nextHeader; navTop = nextNavTop; windowEvents.get('resize')?.();},
    hasFocusListener: events.has('focusin')};
}

const phone = page();
phone.focus(phone.target(168.765625));
assert.equal(phone.scrolls.length, 0, 'wait until browser focus scrolling has settled');
phone.flush();
assert.equal(phone.scrolls.length, 1);
assert.equal(phone.scrolls[0].top, -32.234375);
assert.equal(phone.scrolls[0].behavior, 'instant');
assert.equal(phone.styles.get('--candidate-scroll-offset'), '209px');

const visible = page();
visible.focus(visible.target(480)); visible.flush();
visible.focus(visible.target(145, {inNav: true})); visible.flush();
assert.equal(visible.scrolls.length, 0, 'visible content and navigation focus do not move the page');

const race = page();
race.focus(race.target(100));
race.document.activeElement = race.target(500); race.flush();
assert.equal(race.scrolls.length, 0, 'a stale focus target cannot scroll');
race.focus(race.target(100, {isConnected: false})); race.flush();
race.focus(race.target(100, {getBoundingClientRect: () => ({width: 0, height: 0, top: 100})})); race.flush();
assert.equal(race.scrolls.length, 0);
race.focus(race.target(100)); race.focus(race.target(500)); race.flush();
assert.equal(race.scrolls.length, 0, 'rapid focus transitions use the current control');

const beforeSticky = page({navTop: 600});
beforeSticky.focus(beforeSticky.target(100)); beforeSticky.flush();
assert.equal(beforeSticky.scrolls[0].top, -41, 'filters clear only the header before the nav sticks');

const resize = page();
resize.focus(resize.target(500)); resize.flush();
resize.resize(180, 180);
assert.equal(resize.scrolls.length, 0, 'resize and manual scrolling do not pull back an old focus');
resize.focus(resize.target(200)); resize.flush();
assert.equal(resize.scrolls[0].top, -48, 'the next focus uses the actual wrapped header');

assert.equal(page({hasBar: false}).hasFocusListener, false);
console.log('Sticky focus clearance, visible/nav controls, focus races, hidden controls, unstuck nav, resize and pages without candidate navigation passed.');
