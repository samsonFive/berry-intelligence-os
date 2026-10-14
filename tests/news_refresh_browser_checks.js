// Execute the shipped refresh script against a minimal DOM and mocked transport.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('app/static/news_workspace.js', 'utf8');

async function scenario(states, expire=false, fromNavigation=false) {
  let redirect, posts=0, now=0;
  const scheduled=[], listeners={};
  const button={disabled:false, addEventListener:(name, callback)=>listeners[name]=callback};
  const status={textContent:''};
  const document={querySelector(selector) {
    if (selector==='[data-news-workspace]') return {dataset:{}};
    if (selector==='[data-news-refresh]') return button;
    if (selector==='[data-news-refresh-status]') return status;
    return null;
  }, querySelectorAll:()=>[]};
  const window={location:{href:'https://example.org/today?berry=berry-blueberry&window=7d&view=unreviewed&page=3&story=old'+(fromNavigation?'&refresh=1':''),replace:value=>redirect=value},history:{state:{},replaceState(state,title,url){window.location.href=url.toString();}},addEventListener:()=>{}};
  class TestDate extends Date {static now(){return now;}}
  const fetch=async (url, options)=>{
    if (options.method==='POST') {posts++; return {ok:true};}
    assert.equal(options.cache,'no-store');
    return {ok:true,json:async()=>states.shift() || {}};
  };
  vm.runInNewContext(script,{document,window,fetch,URL,Intl,Date:TestDate,setTimeout:callback=>scheduled.push(callback),clearTimeout:()=>{}});
  if (!fromNavigation) listeners.click();
  await new Promise(setImmediate);
  for (let i=0;i<10 && scheduled.length;i++) {
    if(expire) now=600001;
    scheduled.shift()();
    await new Promise(setImmediate);
  }
  assert.equal(posts,1);
  return {redirect,button,status};
}
(async()=>{
  for(const status of ['ready','partial']) {
    const result=await scenario([{}, {status:'running'}, {status,message:'Done'}]);
    const target=new URL(result.redirect);
    assert.equal(target.searchParams.get('berry'),'berry-blueberry');
    assert.equal(target.searchParams.get('window'),'7d');
    assert.equal(target.searchParams.get('view'),'unreviewed');
    assert.equal(target.searchParams.has('page'),false);
    assert.equal(target.searchParams.has('story'),false);
  }
  const failed=await scenario([{status:'failed',message:'Capture failed'}]);
  assert.equal(failed.redirect,undefined);
  assert.equal(failed.button.disabled,false);
  assert.equal(failed.status.textContent,'Capture failed');
  const missing=await scenario([{}],true);
  assert.equal(missing.redirect,undefined);
  assert.equal(missing.button.disabled,false);
  assert.match(missing.status.textContent,/longer than expected/);
  const navigation=await scenario([{status:'ready'}],false,true);
  assert.equal(new URL(navigation.redirect).searchParams.has('refresh'),false);
  assert.equal(new URL(navigation.redirect).searchParams.get('berry'),'berry-blueberry');
  console.log('5 refresh scenarios passed: ready/partial, failure, bounded timeout and one-click News navigation.');
})().catch(error=>{console.error(error);process.exitCode=1;});
