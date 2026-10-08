// Execute the shipped script against isolated DOM/storage adapters, without a browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../app/static/variety_workspace.js'), 'utf8');

function page(storage, { blocked = false, image = 'https://publisher.test/a.jpg', source = 'https://publisher.test/a' } = {}) {
  const containers = [image, 'https://publisher.test/b.jpg'].map(imageUrl => {
    const button = { hidden: true, attributes: {}, setAttribute(k,v) { this.attributes[k] = v; },
      addEventListener(event, action) { assert.equal(event, 'click'); this.click = action; } };
    const status = {};
    const fallback = { hidden: true };
    const figure = { scrolls: [], scrollIntoView(options) { this.scrolls.push(options); } };
    const frame = { hidden: true, img: null, querySelector(selector) {
      return selector === 'img' ? this.img : selector === 'span' ? fallback : null;
    }, prepend(img) { this.img = img; img.parent = this; } };
    return { button, frame, status, fallback, figure,
      closest(selector) { assert.equal(selector, 'figure'); return figure; },
      dataset: { sourceUrl: source, imageUrl, caption: 'A credited, named fruit photo' },
      querySelector(selector) { return { '[data-photo-session-toggle]': button,
        '[data-photo-session-frame]': frame, '[data-photo-session-status]': status }[selector]; } };
  });
  let created = 0;
  const deny = () => { throw new Error('Persistent writes and network calls are forbidden'); };
  const document = {
    querySelector() { return null; }, getElementById() { return null; },
    querySelectorAll(selector) { return selector === '[data-photo-session]' ? containers : []; },
    createElement(tag) {
      assert.equal(tag, 'img'); created++;
      return { hidden: false, events: {}, addEventListener(name, action) { this.events[name] = action; },
        remove() { this.parent.img = null; } };
    }
  };
  const window = { addEventListener() {}, fetch: deny, localStorage: { getItem: deny, setItem: deny },
    sessionStorage: {
      getItem(key) { if (blocked) throw new Error('Unavailable'); return storage.get(key) || null; },
      setItem(key, value) { if (blocked) throw new Error('Unavailable'); storage.set(key, value); },
      removeItem(key) { if (blocked) throw new Error('Unavailable'); storage.delete(key); }
    } };
  vm.runInNewContext(script, { document, window, location: { hash: '' } });
  return { containers, created: () => created };
}

const storage = new Map();
const first = page(storage);
assert.equal(first.created(), 0); // No image element/request before a choice.
assert.ok(first.containers.every(c => c.frame.hidden && !c.button.hidden));
first.containers[0].button.click();
assert.equal(first.created(), 1);
assert.equal(first.containers[0].frame.img.src, 'https://publisher.test/a.jpg');
assert.equal(first.containers[0].frame.img.referrerPolicy, 'no-referrer');
assert.equal(first.containers[0].button.attributes['aria-pressed'], 'true');
assert.equal(first.containers[1].frame.img, null); // Other assets remain blocked.
assert.equal(first.containers[0].figure.scrolls.length, 1);
assert.equal(first.containers[0].figure.scrolls[0].inline, 'start');
assert.equal(first.containers[0].figure.scrolls[0].block, 'nearest');
assert.equal(first.containers[1].figure.scrolls.length, 0);
assert.equal(storage.size, 1);

const reload = page(storage);
assert.equal(reload.created(), 1); // Same tab session retains the exact chosen asset.
assert.equal(reload.containers[1].frame.img, null);
assert.ok(reload.containers.every(c => c.figure.scrolls.length === 0)); // Restore does not move the page.
assert.equal(page(storage, { image: 'https://publisher.test/replacement.jpg' }).created(), 0);
assert.equal(page(storage, { source: 'https://publisher.test/replacement' }).created(), 0);
assert.equal(page(new Map()).created(), 0); // A fresh session has no override.
reload.containers[0].button.click();
assert.equal(reload.containers[0].frame.img, null);
assert.equal(reload.containers[0].button.attributes['aria-pressed'], 'false');
assert.equal(reload.containers[0].figure.scrolls.length, 0); // Hiding does not jump the page.
assert.equal(storage.size, 0);
assert.equal(page(storage).created(), 0);

const noStorage = page(storage, { blocked: true });
noStorage.containers[0].button.click();
assert.ok(noStorage.containers[0].frame.img);
assert.match(noStorage.containers[0].status.textContent, /this view.*Permission unconfirmed/);
noStorage.containers[0].frame.img.events.error();
assert.ok(noStorage.containers[0].frame.img.hidden);
assert.equal(noStorage.containers[0].fallback.hidden, false);
noStorage.containers[0].button.click();
assert.ok(noStorage.containers[0].frame.hidden);
assert.equal(storage.size, 0);
