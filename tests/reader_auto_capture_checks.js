// Test shipped reader behavior with controlled transport and story changes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('app/static/personal_digest.js', 'utf8');

function boot() {
  const listeners = {}, overlayEvents = {}, captures = [];
  let panel, replacements = 0;
  const scroll = {scrollTop: 0};
  const makePanel = (id, automatic=true) => {
    const loading={textContent:''}, heading={textContent:'Loading publisher article…'}, retry={hidden:true}, status={textContent:''};
    const row = {dataset:{itemId:id,authoring:'true',autoCapture:String(automatic)},isConnected:true,
      closest:()=>scroll, setAttribute(){}, removeAttribute(){}, querySelectorAll:()=>[],
      querySelector(selector) {return {'[data-reader-loading]':loading,'.article-unavailable h3':heading,'[data-personal-capture]':retry,'.reader-action-status':status}[selector] || null;},
      loading,heading,retry,status};
    Object.defineProperty(row,'outerHTML',{set() {replacements++;row.isConnected=false;panel=makePanel(id,false);}});
    return row;
  };
  panel=makePanel('first');
  const document={body:{hasAttribute:()=>true},querySelector(selector) {
    if(selector.startsWith('#v2ReaderBody'))return panel;
    if(selector==='#v2ReaderOffcanvas')return {addEventListener:(event,callback)=>overlayEvents[event]=callback};
    return null;
  },getElementById:()=>({addEventListener:(event,callback)=>overlayEvents[event]=callback}),querySelectorAll:()=>[],addEventListener:(event,callback)=>listeners[event]=callback};
  const window={addEventListener(){}};
  const fetch=(url, options)=>{
    if(!url.startsWith('/api/digest/'))return Promise.resolve({ok:true,json:async()=>({})});
    let resolve; const promise=new Promise(done=>resolve=done);
    captures.push({url,options,resolve});return promise;
  };
  vm.runInNewContext(script,{document,window,fetch,AbortController,Promise,JSON,CSS:{escape:value=>value},setTimeout,clearTimeout});
  return {captures,listeners,overlayEvents,get panel(){return panel;},get replacements(){return replacements;},switchStory(id){listeners['bios:reader-unloading']();panel=makePanel(id);listeners['bios:reader-loaded']();}};
}
const settle=()=>new Promise(setImmediate);
(async()=>{
  const success=boot();
  assert.equal(success.captures.length,1); // Opening, without another click.
  success.listeners['bios:reader-loaded']();
  assert.equal(success.captures.length,1); // Repeated setup does not duplicate.
  success.captures[0].resolve({ok:true,text:async()=>'<article>Publisher text</article>'});
  await settle();
  assert.equal(success.replacements,1);
  assert.equal(success.captures.length,1); // Returned fragment cannot retry-loop.

  const stale=boot();
  stale.switchStory('second');
  assert.equal(stale.captures[0].options.signal.aborted,true);
  stale.captures[0].resolve({ok:true,text:async()=>'<article>Old story</article>'});
  await settle();assert.equal(stale.replacements,0);
  stale.captures[1].resolve({ok:true,text:async()=>'<article>Current story</article>'});
  await settle();assert.equal(stale.replacements,1);assert.equal(stale.panel.dataset.itemId,'second');

  const failed=boot();
  failed.captures[0].resolve({ok:false});await settle();
  assert.equal(failed.panel.retry.hidden,false);
  assert.match(failed.panel.heading.textContent,/isn’t available/);
  assert.equal(failed.captures.length,1);
  console.log('Reader automatic loading, duplicate prevention, stale-story cancellation and failure fallback passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
