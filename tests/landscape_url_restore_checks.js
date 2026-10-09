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
const handlers = {};
clear.closest = selector => selector === '[data-clear-edge]' ? clear : null;
clear.click = () => handlers.click({target: clear});
windowControl.addEventListener = () => {};
root.addEventListener = (name, handler) => { handlers[name] = handler; };
const selectors = {'[data-evidence-content]':content, '.lx-evidence':panel,
  '[name=focus]':field, '[data-clear-edge]':clear, '.lx-focus':focusSection,
  '[data-focus-title]':title, '[data-focus-diagram]':diagram,
  '[data-reset-focus]':reset, '[name=window]':windowControl};
root.querySelector = selector => {
  assert.ok(selector in selectors, 'Unexpected DOM dependency: ' + selector);
  return selectors[selector];
};
const nodes = {
  company: {label:'Company',type:'company'}, variety: {label:'Variety',type:'variety'},
  other: {label:'Other company',type:'company'}, program: {label:'Program',type:'breeding_program'}
};
const edges = [
  {id:'related',subject_id:'company',object_id:'variety',role:'Breeder',status_label:'Documented',evidence_ids:[]},
  {id:'selected',subject_id:'other',object_id:'program',label:'Other company owns Program',status:'disputed',status_label:'Disputed',review:'Reviewed source',published:[],evidence_ids:[]}
];
const bundle = {filters:{focus:'variety',edge:'selected',view:'portrait'},nodes,edges,sources:[]};
const location = {href:'http://localhost/landscapes/explorer?focus=variety&edge=selected'};
const context = {URL, performance, console, location,
  history:{replaceState(_,__,url) {location.href = String(url);}},
  matchMedia:() => ({matches:false}),
  document:{querySelector:() => root, getElementById:() => ({textContent:JSON.stringify(bundle)}), createElement:() => new Element()}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../app/static/landscape_explorer.js'),'utf8'),context);
assert.equal(field.value,'variety');
assert.equal(title.textContent,'Variety');
assert.equal(new URL(location.href).searchParams.get('focus'),'variety');
assert.equal(new URL(location.href).searchParams.get('edge'),'selected');
assert.equal(panel.hidden,false);
assert.equal(content.children[0].textContent,'Other company owns Program');
// Deliberately changing focus still closes unrelated evidence.
focusSection.scrollIntoView = () => {};
const focusLink = {dataset:{focus:'company'},closest:selector => selector === '[data-focus]' ? focusLink : null};
handlers.click({target:focusLink,preventDefault() {}});
assert.equal(new URL(location.href).searchParams.get('edge'),'');
assert.equal(panel.hidden,true);
console.log('Landscape restores focus and independent evidence; subsequent focus changes retain clear behavior.');
