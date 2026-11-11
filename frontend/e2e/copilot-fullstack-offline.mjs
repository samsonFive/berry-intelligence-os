/** Real browser -> authenticated FastAPI -> Node SDK -> locally mocked Responses.
 * This is an OFFLINE regression, never real-provider/G1 acceptance.
 * Run with existing dependencies: node frontend/e2e/copilot-fullstack-offline.mjs
 * Options: BERRY_TEST_PYTHON, BERRY_PLAYWRIGHT_ROOT/MODULE, BERRY_CHROMIUM_PATH,
 * BERRY_FULLSTACK_PORT (18994), BERRY_FULLSTACK_RUNTIME_PORT (18230).
 */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import fs from 'node:fs/promises';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { installCommandDiagnostics, sanitizeRunEnvelope } from './command-diagnostics.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const runtimeRoot = process.env.BERRY_PLAYWRIGHT_ROOT ?? path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node');
const runtimeRequire = createRequire(path.join(runtimeRoot, 'package.json'));
const { chromium } = runtimeRequire(process.env.BERRY_PLAYWRIGHT_MODULE || 'playwright');
const port = Number(process.env.BERRY_FULLSTACK_PORT || 18994);
const runtimePort = Number(process.env.BERRY_FULLSTACK_RUNTIME_PORT || 18230);
for (const value of [port, runtimePort]) assert.ok(Number.isInteger(value) && value >= 1024 && value <= 65535);
assert.notEqual(port, runtimePort);
const base = `http://127.0.0.1:${port}`;
const token = randomBytes(48).toString('base64url');
const username = 'offline-fullstack-reviewer';
const password = randomBytes(32).toString('base64url');
const secret = randomBytes(48).toString('base64url');
const environment = { ...process.env, COPILOTKIT_TELEMETRY_DISABLED: 'true' };
for (const name of ['PERPLEXITY_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY','MINIMAX_API_KEY']) delete environment[name];
const scratch = await fs.mkdtemp(path.join(root, '.experience-fullstack-offline-'));
const children = [], providerReceipts = [], runtimeDiagnostics = [], runs = [], requests = [], responses = [], pageErrors = [], blockedBrowserHosts = [];
let browser, page, runtimeReady = false, childFailure = false;
function start(executable, args, env, runtime = false) {
  const child = spawn(executable, args, { cwd: root, windowsHide: true, stdio: ['ignore','pipe','pipe'], env });
  children.push(child);
  child.once('error', () => { childFailure = true; });
  for (const stream of [child.stdout, child.stderr]) {
    let remainder = '';
    stream.on('data', bytes => {
      const lines = (remainder + bytes.toString()).split(/\r?\n/); remainder = lines.pop() ?? '';
      for (const line of lines) {
        if (runtime && line.includes('listening on loopback')) runtimeReady = true;
        // Unrecognized process output is discarded; no raw request/log body is retained.
        const fixture = 'Berry offline provider fixture: ', diagnostic = 'Berry command diagnostic: ';
        try {
          if (runtime && line.startsWith(fixture)) providerReceipts.push(JSON.parse(line.slice(fixture.length)));
          if (runtime && line.startsWith(diagnostic)) runtimeDiagnostics.push(JSON.parse(line.slice(diagnostic.length)));
        } catch { childFailure = true; }
      }
    });
  }
  return child;
}
async function stop(child) {
  if (!child.pid || child.exitCode !== null) return;
  if (process.platform === 'win32') return new Promise(resolve => {
    const task = spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
    task.once('exit', resolve); task.once('error', resolve);
  });
  return new Promise(resolve => {
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve(); }, 5000);
    child.once('exit', () => { clearTimeout(timer); resolve(); }); child.kill('SIGTERM');
  });
}
let report;
try {
  start(process.execPath, ['--import', './copilot-runtime/tests/fullstack-offline-preload.mjs', 'copilot-runtime/server.mjs'], {
    ...environment, BERRY_FULLSTACK_OFFLINE: '1', BIOS_COPILOT_MODEL: 'perplexity:openai/gpt-5.6-sol',
    PERPLEXITY_API_KEY: 'synthetic-fullstack-offline-key', BIOS_COPILOT_RUNTIME_TOKEN: token,
    BIOS_COPILOT_PORT: String(runtimePort), BIOS_RESEARCH_CREDIT_FREE_ONLY: '1', BIOS_COPILOT_ALLOW_PAID_COMPARISON: '1',
  }, true);
  const deadline = Date.now() + 120000;
  while (!runtimeReady) {
    if (childFailure || children.some(child => child.exitCode !== null)) throw new Error('The guarded offline runtime could not start');
    if (Date.now() > deadline) throw new Error('The guarded offline runtime did not become ready');
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  assert.equal(providerReceipts[0]?.type, 'offline_fetch_guard_installed');
  start(process.env.BERRY_TEST_PYTHON || 'python', ['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(port),'--lifespan','off','--log-level','warning'], {
    ...environment, PYTHONDONTWRITEBYTECODE: '1', BIOS_MODE: 'authoring', BIOS_REMOTE_INTERACTIVE: 'true',
    BIOS_DATA_DIR: path.join(root, 'data'), BIOS_INBOX_DIR: scratch,
    BIOS_REVIEW_USERNAME: username, BIOS_REVIEW_PASSWORD: password, BIOS_SESSION_SECRET: secret,
    BIOS_COPILOT_RUNTIME_URL: `http://127.0.0.1:${runtimePort}/copilot`, BIOS_COPILOT_RUNTIME_TOKEN: token,
    BIOS_RESEARCH_CREDIT_FREE_ONLY: 'true', SOURCE_POLLING_ENABLED: 'false', BIOS_SOURCE_POLLING_ENABLED: 'false',
  });
  const defaultChromium = process.platform === 'win32' ? path.join(os.homedir(), 'AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe') : '';
  const executablePath = process.env.BERRY_CHROMIUM_PATH || (defaultChromium && await fs.stat(defaultChromium).catch(() => null) ? defaultChromium : undefined);
  browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(installCommandDiagnostics);
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== base) { blockedBrowserHosts.push(url.hostname); await route.abort('blockedbyclient'); return; }
    if (url.pathname === '/api/investigations/v1/copilot' && request.method() === 'POST') {
      const envelope = request.postDataJSON();
      const sanitized = sanitizeRunEnvelope(envelope);
      if (sanitized) runs.push(sanitized);
      requests.push({ method: envelope.method });
    }
    // In this joined fixture, gateway and SDK traffic is NEVER fulfilled/mocked here.
    await route.continue();
  });
  page = await context.newPage();
  page.on('pageerror', error => pageErrors.push({ name: error.name }));
  page.on('response', response => {
    if (new URL(response.url()).pathname === '/api/investigations/v1/copilot') responses.push({ status: response.status(), streaming: (response.headers()['content-type'] ?? '').includes('text/event-stream') });
  });
  const appDeadline = Date.now() + 90000;
  while (true) {
    if (childFailure || children.some(child => child.exitCode !== null)) throw new Error('A local fixture process exited before browser readiness');
    try { const response = await page.goto(base + '/app/landscape', { waitUntil: 'domcontentloaded', timeout: 10000 }); if (response?.ok()) break; } catch {}
    if (Date.now() > appDeadline) throw new Error('The local offline app did not become ready');
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  assert.equal(new URL(page.url()).pathname, '/login', 'The real gateway application must require its private session');
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await Promise.all([page.waitForURL(url => !url.pathname.startsWith('/login')), page.locator('button[type="submit"]').click()]);
  await page.goto(base + '/app/landscape?ctx_v=1&berry=berry-blueberry&countries=geography-chile,geography-china,geography-peru', { waitUntil: 'domcontentloaded' });
  const clientAsset = path.basename(await page.locator('script[type="module"]').first().getAttribute('src'));
  if(process.env.BERRY_EXPECTED_CLIENT_ASSET)assert.equal(clientAsset,process.env.BERRY_EXPECTED_CLIENT_ASSET);
  console.log(JSON.stringify({ stage: 'offline-fullstack-authenticated', real_provider_requests: 0 }));
  await page.getByRole('button', { name: 'Ask Berry', exact: true }).click();
  await page.locator('#berry-command').fill('Compare Fall Creek and Costa in China');
  await page.getByRole('button', { name: 'Run command', exact: true }).click();
  await page.waitForFunction(() => new URL(location.href).searchParams.get('lens') === 'comparison' && new URL(location.href).searchParams.get('countries') === 'geography-china', null, { timeout: 60000 });
  await page.getByRole('status').filter({ hasText: 'Comparison opened in the main analytical field.' }).waitFor({ timeout: 20000 });
  await page.waitForFunction(() => window.__berryCommandWire?.terminals.length === 3 && window.__berryCommandWire?.lookups.length === 3, null, { timeout: 10000 });
  const wire = await page.evaluate(() => window.__berryCommandWire);
  assert.equal(pageErrors.length, 0); assert.equal(wire.read_errors, 0); assert.equal(runs.length, 3);
  assert.deepEqual(wire.tool_calls.map(row => row.tool_name), ['search_catalog','search_catalog','search_catalog','show_portfolio_comparison']);
  assert.ok(wire.tool_calls.every(row => row.revision === 0));
  assert.ok(wire.lookups.every(row => row.status === 200));
  assert.ok(wire.terminals.every(row => row.type === 'RUN_FINISHED'));
  assert.ok(runs.every(row => row.registered_tools.length === 7 && row.unknown_tool_count === 0));
  assert.equal(runs[1].tool_results.length, 3);
  assert.equal(runs[2].tool_results.find(row => row.tool_name === 'show_portfolio_comparison')?.code, 'applied');
  assert.deepEqual(providerReceipts.filter(row => row.type === 'mock_responses_request').map(row => row.stage), [1,2,3]);
  assert.equal(providerReceipts.some(row => row.type === 'blocked_outbound_fetch'), false);
  assert.equal(runtimeDiagnostics.some(row => row.type === 'command_provider_error'), false);
  const selectors = Object.fromEntries(['countries','cohort_companies','lens'].map(key => [key, new URL(page.url()).searchParams.get(key)]));
  assert.equal(selectors.cohort_companies, 'company-fall-creek-farm-and-nursery,company-costa-group-holdings');
  report = { status: 'PASS', client_asset: clientAsset, offline_fixture: true, real_provider_requests: 0, actual_gateway: true, actual_sdk_runtime: true,
    sdk_requests: requests, sdk_responses: responses, runs, wire, provider_receipts: providerReceipts, runtime_diagnostics: runtimeDiagnostics,
    selectors, blocked_browser_requests: blockedBrowserHosts.length, page_errors: pageErrors };
} catch (error) {
  report = { status: 'FAIL', offline_fixture: true, real_provider_requests: 0, message: error.message,
    sdk_requests: requests, sdk_responses: responses, runs, wire: await page?.evaluate(() => window.__berryCommandWire).catch(() => undefined), provider_receipts: providerReceipts, runtime_diagnostics: runtimeDiagnostics,
    page_errors: pageErrors, blocked_browser_requests: blockedBrowserHosts.length };
  process.exitCode = 1;
} finally {
  try { await browser?.close(); } finally {
    for (const child of children.reverse()) await stop(child);
    assert.equal(path.dirname(path.resolve(scratch)), root, 'Cleanup stays inside the fixture checkout');
    assert.ok(path.basename(scratch).startsWith('.experience-fullstack-offline-'));
    await fs.rm(scratch, { recursive: true, force: true });
  }
}
const artifact = path.join(root, 'artifacts/experience-consolidation/v1/offline-fullstack-diagnostics.json');
await fs.mkdir(path.dirname(artifact), { recursive: true });
await fs.writeFile(artifact, JSON.stringify(report, null, 2));
console.log(JSON.stringify({ ...report, artifact }));
