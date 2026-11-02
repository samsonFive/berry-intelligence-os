// Execute the production controller with a minimal DOM to check URL restoration.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor() { this.dataset = {}; this.children = []; this.hidden = false; this.classList = {toggle() {}, remove() {}}; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  setAttribute(key, value) { this[key] = value; }
  removeAttribute(key) { delete this[key]; }
  focus() {}
  querySelectorAll() { return []; }
}
const panel = new Element(), content = new Element(), root = new Element();
const focusSection = new Element(), diagram = new Element(), title = new Element();
const field = new Element(), windowControl = new Element(), reset = new Element();
const clear = new Element();
const savedFocus = new Element(), savedEdge = new Element();
const savedBerry = new Element(); savedBerry.name = 'berry';
const berryControl = new Element(), compareControl = new Element();
berryControl.name = 'berry'; compareControl.name = 'compare';
berryControl.value = 'berry-blueberry'; compareControl.value = 'berry-strawberry';
const traitContext = new Element();
savedFocus.name = 'focus'; savedEdge.name = 'edge';
const savedLink = {dataset:{savedView:''},href:'http://localhost/landscapes/explorer?saved_view=existing'};
root.querySelectorAll = selector => {
  if (selector === '[data-save-selection] input[type=hidden]') return [savedFocus,savedEdge,savedBerry];
  if (selector === 'a[href*="/landscapes/explorer?"]') return [savedLink];
  return [];
};
const handlers = {};
clear.closest = selector => selector === '[data-clear-edge]' ? clear : null;
clear.click = () => handlers.click({target: clear});
windowControl.addEventListener = () => {};
root.addEventListener = (name, handler) => { handlers[name] = handler; };
const selectors = {'[data-evidence-content]':content, '.lx-evidence':panel,
  '[data-scope-form] [name=focus]':field, '[data-clear-edge]':clear, '.lx-focus':focusSection,
  '[data-focus-title]':title, '[data-focus-diagram]':diagram,
  '.lx-focus [data-reset-focus]':reset, '[data-scope-form] [name=window]':windowControl};
selectors['[data-trait-context]'] = traitContext;
selectors['[data-scope-form] [name=berry]'] = berryControl;
selectors['[data-scope-form] [name=compare]'] = compareControl;
root.querySelector = selector => {
  assert.ok(selector in selectors, 'Unexpected DOM dependency: ' + selector);
  return selectors[selector];
};
const nodes = {
  company: {label:'Company',type:'company'}, variety: {label:'Variety',type:'variety',berry_ids:['berry-blueberry']},
  other: {label:'Other company',type:'company'}, program: {label:'Program',type:'breeding_program'}
};
const edges = [
  {id:'related',subject_id:'company',object_id:'variety',role:'Breeder',status_label:'Documented',evidence_ids:[]},
  {id:'selected',subject_id:'other',object_id:'program',label:'Other company owns Program',status:'disputed',status_label:'Disputed',review:'Reviewed source',published:[],evidence_ids:[]}
];
const bundle = {filters:{berry:'berry-blueberry',compare:'berry-strawberry',focus:'variety',edge:'selected',view:'portrait'},nodes,edges,sources:[]};
const location = {href:'http://localhost/landscapes/explorer?focus=variety&edge=selected'};
const coverageEvents = [];
const context = {URL, performance, console, location,
  CustomEvent: class { constructor(type) { this.type = type; } },
  window: {dispatchEvent(event) { coverageEvents.push({type:event.type, url:location.href}); }},
  history:{replaceState(_,__,url) {location.href = String(url);}},
  matchMedia:() => ({matches:false}),
  document:{querySelector:() => root, getElementById:() => ({textContent:JSON.stringify(bundle)}), createElement:() => new Element()}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../app/static/landscape_explorer.js'),'utf8'),context);
assert.equal(field.value,'variety');
assert.equal(title.textContent,'Variety');
assert.equal(new URL(location.href).searchParams.get('focus'),'variety');
assert.equal(new URL(location.href).searchParams.get('edge'),'selected');
assert.equal(panel.hidden,false);
assert.equal(savedFocus.value,'variety');
assert.equal(savedEdge.value,'selected');
assert.equal(savedLink.href,'http://localhost/landscapes/explorer?saved_view=existing');
assert.equal(content.children[0].textContent,'Other company owns Program');
// Deliberately changing focus still closes unrelated evidence.
focusSection.scrollIntoView = () => {};
const focusLink = {dataset:{focus:'company'},closest:selector => selector === '[data-focus]' ? focusLink : null};
handlers.click({target:focusLink,preventDefault() {}});
assert.equal(new URL(location.href).searchParams.get('edge'),'');
assert.equal(panel.hidden,true);
assert.equal(savedFocus.value,'company');
assert.equal(savedEdge.value,'');
assert.ok(coverageEvents.some(event => event.type === 'bios:coverage-scope-changed' && new URL(event.url).searchParams.get('focus') === 'company'), 'Captured coverage receives the changed company scope');
// Selecting another crop clears only an incompatible genetics focus before Apply.
const varietyLink = {dataset:{focus:'variety'},closest:selector => selector === '[data-focus]' ? varietyLink : null};
handlers.click({target:varietyLink,preventDefault() {}});
handlers.change({target:{name:'berry',value:'berry-blueberry'}});
assert.equal(field.value,'variety');
berryControl.value = 'berry-strawberry';
handlers.change({target:berryControl});
assert.equal(field.value,'');
handlers.click({target:focusLink,preventDefault() {}});
handlers.change({target:{name:'berry',value:'berry-strawberry'}});
assert.equal(field.value,'company');
// Changing an unapplied crop, then selecting a rendered company, must not
// change the selectors persisted by Save this view.
handlers.click({target:focusLink,preventDefault() {}});
assert.equal(savedBerry.value,'berry-blueberry');
// A rendered variety can be selected again while new controls are pending.
// Apply must clear that incompatible focus; Save must keep the rendered scope.
handlers.click({target:varietyLink,preventDefault() {}});
assert.equal(savedBerry.value,'berry-blueberry');
assert.equal(savedFocus.value,'variety');
handlers.submit({target:{matches:selector => selector === '[data-save-selection]'}});
assert.equal(field.value,'variety');
handlers.submit({target:{matches:selector => selector === '[data-scope-form]'}});
assert.equal(field.value,'');
// A pending pair must use both native controls, not a stale applied crop,
// while the saved pair continues to describe the rendered data.
bundle.filters = {...bundle.filters,view:'compare',pair:'1',compare:'berry-blackberry',edge:''};
berryControl.value='berry-blueberry'; compareControl.value='berry-blackberry';
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../app/static/landscape_explorer.js'),'utf8'),context);
berryControl.value='berry-strawberry'; compareControl.value='berry-blueberry';
handlers.change({target:compareControl});
assert.equal(field.value,'variety');
compareControl.value='berry-blackberry';
handlers.change({target:compareControl});
assert.equal(field.value,'');
console.log('Landscape restores focus and independent evidence; subsequent focus changes retain clear behavior.');
