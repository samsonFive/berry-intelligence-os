const fs = require('fs'), vm = require('vm'), assert = require('assert');
const script = fs.readFileSync('app/static/competitive_coverage.js', 'utf8');
function run(url, payload, bundle = null) {
  const nodes = [];
  function element(tag) { const node = {tag,children:[],append(...kids){this.children.push(...kids);},addEventListener(){}};nodes.push(node);return node; }
  const main = element('main');
  const document = { getElementById(id){return id === 'digest-main' ? main : id === 'ce-coverage-context' && payload ? {textContent:JSON.stringify(payload)} : id === 'landscape-bundle' && bundle ? {textContent:JSON.stringify(bundle)} : null;},createElement:element,createTextNode(v){return v;},querySelectorAll(){return [{href:'http://review.local/static/competitive_evaluation.css'}];},addEventListener(){},head:element('head') };
  const location = new URL(url);
  const window = {addEventListener(){}};
  vm.runInNewContext(script,{document,location,window,URL,URLSearchParams,Set,setTimeout});
  return nodes.filter(n=>n.tag==='a').map(n=>n.href);
}
let links=run('http://review.local/competitive-evaluation?companies=company-excluded,company-one',{companies:['company-one'],berry:'berry-blueberry',empty_cohort:false});
assert(links.every(u=>!u.includes('company-excluded')));assert(links.every(u=>u.includes('company-one')));
links=run('http://review.local/competitive-evaluation?companies=company-excluded',{companies:[],berry:'',empty_cohort:true});
assert(links.every(u=>u.includes('empty_cohort=1')&&!u.includes('company-excluded')));
links=run('http://review.local/competitive-evaluation?saved=snapshot-one',{companies:['company-captured'],berry:'berry-strawberry',empty_cohort:false});
assert(links.every(u=>u.includes('company-captured')&&u.includes('berry-strawberry')));
links=run('http://review.local/competitive-evaluation?companies=company-excluded',{companies:['company-one','seed-org-0054'],berry:'',empty_cohort:false});
assert(links.every(u=>u.includes('company-one')&&u.includes('seed-org-0054')&&!u.includes('company-excluded')));
links=run('http://review.local/landscapes/explorer?company=company-original',null,{filters:{companies:['company-bundle'],berry:'berry-blueberry'}});
assert(links.every(u=>u.includes('company-original')&&!u.includes('company-bundle')));
console.log('Five real-script coverage handoff cases pass: resolved, empty, saved, legacy IDs and unchanged Landscape scope.');
