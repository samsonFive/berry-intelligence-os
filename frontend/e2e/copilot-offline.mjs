/**
 * Offline client regression, NOT real provider/G1 acceptance.
 *
 * Run: node frontend/e2e/copilot-offline.mjs
 * BERRY_TEST_PYTHON selects an existing interpreter with the repo dependencies.
 * BERRY_PLAYWRIGHT_ROOT selects a directory containing package.json/node_modules;
 * BERRY_PLAYWRIGHT_MODULE may instead be an absolute installed Playwright module.
 * BERRY_CHROMIUM_PATH optionally selects an existing Chromium executable.
 * BERRY_OFFLINE_PORT defaults to 18993 (independent of the live rehearsal).
 * No package/browser installs, provider runtime, provider call or build occurs.
 * Every browser request outside the fixture's loopback origin is blocked. All
 * Copilot run requests are intercepted with synthetic AG-UI events; only local
 * read-only /options and /comparison APIs use the actual application backend.
 */
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createGuardedHandler } from '../../copilot-runtime/server.mjs';
import { installCommandDiagnostics, sanitizeRunEnvelope } from './command-diagnostics.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const runtimeRoot = process.env.BERRY_PLAYWRIGHT_ROOT
  ?? path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node');
const runtimeRequire = createRequire(path.join(runtimeRoot, 'package.json'));
const { chromium } = runtimeRequire(process.env.BERRY_PLAYWRIGHT_MODULE || 'playwright');
const port = Number(process.env.BERRY_OFFLINE_PORT || 18993);
assert.ok(Number.isInteger(port) && port >= 1024 && port <= 65535, 'Use a valid independent fixture port');
const base = `http://127.0.0.1:${port}`;
const expectedTools = ['search_catalog','show_portfolio_comparison','show_company_summary','show_evidence_detail','show_related_developments','show_geography_connections','show_sensory_demo'];
const config = { model:'openai:synthetic-offline', apiKey:'synthetic-offline', token:'synthetic-offline-runtime-token-32characters', port:18229 };
const handler = createGuardedHandler(config);
const originalFetch = globalThis.fetch;
let metadataNetworkAttempts = 0;
let info;
try {
  globalThis.fetch = async () => { metadataNetworkAttempts++; throw new Error('Offline SDK discovery attempted network access'); };
  const metadata = await handler(new Request('http://127.0.0.1:18229/copilot', {method:'POST',headers:{'X-Berry-Runtime-Token':config.token,'Content-Type':'application/json'},body:JSON.stringify({method:'info'})}));
  assert.equal(metadata.status,200);
  info = await metadata.text();
  assert.equal(metadataNetworkAttempts,0,'SDK info must never invoke a provider');
} finally { globalThis.fetch = originalFetch; }
const childEnvironment = {...process.env,PYTHONDONTWRITEBYTECODE:'1',BIOS_MODE:'authoring',BIOS_REMOTE_INTERACTIVE:'false',BIOS_DATA_DIR:path.join(root,'data'),BIOS_INBOX_DIR:path.join(root,'.tmp-client-fixture-inbox'),BIOS_COPILOT_RUNTIME_URL:'',BIOS_COPILOT_RUNTIME_TOKEN:'',BIOS_RESEARCH_CREDIT_FREE_ONLY:'true',SOURCE_POLLING_ENABLED:'false',BIOS_SOURCE_POLLING_ENABLED:'false'};
for (const name of ['PERPLEXITY_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY','MINIMAX_API_KEY']) delete childEnvironment[name];
const server = spawn(process.env.BERRY_TEST_PYTHON || 'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(port),'--lifespan','off','--log-level','warning'],{
  cwd:root, windowsHide:true, stdio:['ignore','pipe','pipe'], env:childEnvironment
});
let serverErrors=0, spawnError;
server.once('error', error => { spawnError = error; });
server.stderr.on('data',()=>serverErrors++); server.stdout.on('data',()=>{});
let browser;
const requests=[],errors=[],externals=[],apiReads=[],routeErrors=[],sanitizedRuns=[];
let actionRevision;
let frontendTools;
function events(body, calls, text) {
  const list=[{type:'RUN_STARTED',threadId:body.threadId,runId:body.runId}];
  const active=calls.map((call,index)=>({...call,toolCallId:`fixture-${requests.length}-${index}`,raw:JSON.stringify(call.args)}));
  // Interleave three open tool streams, as a provider's parallel calls may do.
  for(const call of active)list.push({type:'TOOL_CALL_START',toolCallId:call.toolCallId,toolCallName:call.name,parentMessageId:`fixture-message-${requests.length}`});
  for(const half of [0,1])for(const call of active){
    const middle=Math.floor(call.raw.length/2);
    list.push({type:'TOOL_CALL_ARGS',toolCallId:call.toolCallId,delta:half===0?call.raw.slice(0,middle):call.raw.slice(middle)});
  }
  for(const call of active)list.push({type:'TOOL_CALL_END',toolCallId:call.toolCallId});
  if(text)list.push({type:'TEXT_MESSAGE_START',messageId:'fixture-ack',role:'assistant'},{type:'TEXT_MESSAGE_CONTENT',messageId:'fixture-ack',delta:text},{type:'TEXT_MESSAGE_END',messageId:'fixture-ack'});
  list.push({type:'RUN_FINISHED',threadId:body.threadId,runId:body.runId});
  return list.map(event=>`data: ${JSON.stringify(event)}\n\n`).join('');
}
try {
  const configuredChromium = process.env.BERRY_CHROMIUM_PATH;
  const localChromium = process.platform === 'win32'
    ? path.join(os.homedir(),'AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe') : '';
  const executablePath = configuredChromium || (localChromium && await fs.stat(localChromium).catch(() => null) ? localChromium : undefined);
  browser=await chromium.launch({headless:true,...(executablePath ? {executablePath} : {})});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.addInitScript(installCommandDiagnostics);
  await context.route('**/*',async route=>{
    try {
    const request=route.request(),url=new URL(request.url());
    if(url.origin!==base){externals.push(url.hostname);await route.abort('blockedbyclient');return;}
    if(url.pathname==='/api/investigations/v1/copilot/status'){await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({api_v:1,configured:true,requires_explicit_command:true,conversation_retention:'session-only'})});return;}
    if(url.pathname.startsWith('/api/investigations/v1/copilot')){
      assert.equal(url.pathname,'/api/investigations/v1/copilot','All SDK traffic must remain in the mocked single endpoint');
      const envelope=request.postDataJSON();
      if(envelope.method==='info'){await route.fulfill({status:200,contentType:'application/json',body:info});return;}
      if(['agent/connect','agent/stop'].includes(envelope.method)){await route.fulfill({status:200,contentType:'text/event-stream',body:''});return;}
      assert.equal(envelope.method,'agent/run','Unexpected SDK method must not reach a real runtime');
      sanitizedRuns.push(sanitizeRunEnvelope(envelope));
      const body=typeof envelope.body==='string'?JSON.parse(envelope.body):envelope.body;
      frontendTools ??= body.tools;
      const revision=JSON.parse(body.context.find(item=>item.description.includes('selectors only')).value).revision;
      requests.push({method:envelope.method,tools:body.tools.map(tool=>tool.name),context_count:body.context.length,revision,message_roles:body.messages.map(message=>message.role)});
      const n=requests.length;
      const calls=n===1?[{name:'search_catalog',args:{revision,kind:'company',query:'Fall Creek'}},{name:'search_catalog',args:{revision,kind:'company',query:'Costa'}},{name:'search_catalog',args:{revision,kind:'geography',query:'China'}}]:n===2?[{name:'show_portfolio_comparison',args:{revision,kind:'company',ids:['company-fall-creek-farm-and-nursery','company-costa-group-holdings'],countries:['geography-china']}}]:[];
      if(n===2)actionRevision=revision;
      await route.fulfill({status:200,contentType:'text/event-stream',body:events(body,calls,n===3?'Comparison opened.':'')});return;
    }
    if(url.pathname==='/api/investigations/v1/options')apiReads.push({path:'options',q:url.searchParams.get('q')});
    if(url.pathname==='/api/investigations/v1/comparison')apiReads.push({path:'comparison',revision:url.searchParams.get('revision')});
    await route.continue();
    } catch(error) {
      routeErrors.push(error.message);
      await route.abort('blockedbyclient').catch(()=>{});
    }
  });
  const page=await context.newPage();
  page.on('pageerror',error=>errors.push({kind:'pageerror',name:error.name}));
  const deadline=Date.now()+90000;
  while(true){
    if(spawnError)throw new Error('Configure BERRY_TEST_PYTHON with an existing dependency-equipped interpreter');
    if(server.exitCode!==null)throw new Error(`Offline fixture server exited with code ${server.exitCode}`);
    try{const r=await page.goto(`${base}/app/landscape?ctx_v=1&berry=berry-blueberry&countries=geography-chile,geography-china,geography-peru`,{waitUntil:'domcontentloaded',timeout:10000});if(r?.ok())break;}catch{}
    if(Date.now()>deadline)throw Error('Offline server did not become ready');
    await new Promise(resolve=>setTimeout(resolve,1000));
  }
  console.log(JSON.stringify({stage:'offline-app-loaded',runtime_info_status:200}));
  const clientAsset = path.basename(await page.locator('script[type="module"]').first().getAttribute('src'));
  if(process.env.BERRY_EXPECTED_CLIENT_ASSET)assert.equal(clientAsset,process.env.BERRY_EXPECTED_CLIENT_ASSET);
  await page.getByRole('button',{name:'Ask Berry',exact:true}).click();
  await page.locator('#berry-command').fill('Compare Fall Creek and Costa in China');
  await page.getByRole('button',{name:'Run command',exact:true}).click();
  await page.waitForFunction(()=>new URL(location.href).searchParams.get('lens')==='comparison'&&new URL(location.href).searchParams.get('countries')==='geography-china',null,{timeout:45000});
  await page.getByRole('status').filter({hasText:'Comparison opened in the main analytical field.'}).waitFor({timeout:20000});
  const selected=Object.fromEntries(['countries','cohort_companies','lens','focus'].map(key=>[key,new URL(page.url()).searchParams.get(key)]));
  assert.deepEqual(requests[0].tools.sort(),expectedTools.sort());
  assert.equal(requests[0].revision,actionRevision);
  assert.equal(selected.cohort_companies,'company-fall-creek-farm-and-nursery,company-costa-group-holdings');
  assert.equal(errors.length,0);
  assert.equal(routeErrors.length,0,'Unexpected SDK methods or wire shapes must fail the offline fixture');
  assert.equal(metadataNetworkAttempts,0);
  assert.equal(requests.length,3,'The fixture must exercise frontend tool continuations and final acknowledgement');
  await page.waitForFunction(()=>window.__berryCommandWire?.terminals.length===3&&window.__berryCommandWire?.lookups.length===3,null,{timeout:10000});
  const diagnostics=await page.evaluate(()=>window.__berryCommandWire);
  assert.deepEqual(diagnostics.tool_calls.map(row=>row.tool_name),['search_catalog','search_catalog','search_catalog','show_portfolio_comparison']);
  assert.deepEqual(diagnostics.tool_calls.slice(0,3).map(row=>row.query),['fall creek','costa','china']);
  assert.equal(diagnostics.tool_calls.every(row=>row.revision===actionRevision),true);
  assert.equal(diagnostics.lookups.every(row=>row.status===200),true);
  assert.equal(diagnostics.read_errors,0);
  assert.equal(sanitizedRuns[1].tool_results.length,3);
  assert.equal(sanitizedRuns[1].tool_results.every(row=>row.tool_name==='search_catalog'&&row.result_count>0),true);
  assert.equal(sanitizedRuns[2].tool_results.find(row=>row.tool_name==='show_portfolio_comparison')?.code,'applied');
  const report={status:'PASS',client_asset:clientAsset,synthetic_sdk_runs:requests.length,requests,api_reads:apiReads,selectors:selected,blocked_external_count:externals.length,page_errors:errors,provider_requests:0};
  const artifact=path.join(root,'artifacts/experience-consolidation/v1/offline-client-tools.json');
  await fs.mkdir(path.dirname(artifact),{recursive:true});
  // Static registered definitions only; no messages, context or tool results.
  await fs.writeFile(artifact,JSON.stringify(frontendTools,null,2));
  const diagnosticArtifact=path.join(root,'artifacts/experience-consolidation/v1/offline-command-diagnostics.json');
  await fs.writeFile(diagnosticArtifact,JSON.stringify({offline_fixture:true,provider_requests:0,wire:diagnostics,runs:sanitizedRuns},null,2));
  console.log(JSON.stringify({...report,diagnostics,run_receipts:sanitizedRuns,sanitized_tool_schema_artifact:artifact,diagnostic_artifact:diagnosticArtifact}));
}catch(error){console.log(JSON.stringify({status:'FAIL',message:error.message,requests,api_reads:apiReads,page_errors:errors,route_errors:routeErrors,blocked_external_count:externals.length,server_error_chunks:serverErrors}));process.exitCode=1;}
finally{
 try { await browser?.close(); } finally {
 if(server.pid&&server.exitCode===null){
   if(process.platform==='win32') await new Promise(resolve=>{const task=spawn('taskkill.exe',['/PID',String(server.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});task.once('exit',resolve);task.once('error',resolve);});
   else await new Promise(resolve=>{
     const timer=setTimeout(()=>{server.kill('SIGKILL');resolve();},5000);
     server.once('exit',()=>{clearTimeout(timer);resolve();});server.kill('SIGTERM');
   });
 }
 }
}
