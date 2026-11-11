/* Local-only browser QA. Credentials are generated in memory and never printed.
 * JSON-lines stdin drives one continuous authenticated browser context/video.
 * Provider access requires the explicit single-command runtime flag and permit.
 * The default rehearsal does not start model turns or perform canonical writes.
 */
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');
const readline = require('node:readline');
const { chromium } = require(process.env.BERRY_PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const artifactDir = path.join(root, 'artifacts/experience-consolidation/v1');
const port = Number(process.env.BERRY_REHEARSAL_PORT || 18992);
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Use a valid explicit rehearsal port');
const base = `http://127.0.0.1:${port}`;
const rehearsalInbox = path.resolve(root, process.env.BERRY_REHEARSAL_INBOX || 'inbox/experience-rehearsal');
const inboxRelative = path.relative(root, rehearsalInbox);
if (inboxRelative.startsWith('..') || path.isAbsolute(inboxRelative)) throw new Error('Keep the rehearsal inbox inside the isolated checkout');
const copilotEnabled = process.env.BERRY_REHEARSAL_COPILOT === '1';
const runtimePort = Number(process.env.BERRY_REHEARSAL_RUNTIME_PORT || 18228);
if (!Number.isInteger(runtimePort) || runtimePort < 1024 || runtimePort > 65535) throw new Error('Use a valid explicit runtime port');
const approvedCommand = 'Compare Fall Creek and Costa in China';
const errors = [], providerRequests = [];
let server, commandRuntime, browser, context, page, logs = '', queue = Promise.resolve();
let authenticatedState;
let exportSelection, exportPreview;
let paidCommandConsumed = false;
const runtimeDiagnostics = [];
const diagnosticKeys = {
  command_model_request: ['tool_count', 'excluded_tool_count'],
  command_provider_response: ['request_id'],
  command_provider_finish: ['terminal_event', 'input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_tokens'],
  command_provider_error: ['terminal_event', 'category', 'name', 'http_status', 'provider_code', 'param', 'request_id'],
};
function retainRuntimeDiagnostic(line) {
  const prefix = 'Berry command diagnostic: ';
  if (!line.startsWith(prefix)) return;
  try {
    const value = JSON.parse(line.slice(prefix.length));
    const keys = diagnosticKeys[value?.type];
    if (!keys) return;
    const record = { type: value.type };
    for (const key of keys) {
      const item = value[key];
      if (typeof item === 'number' && Number.isSafeInteger(item) && item >= 0) record[key] = item;
      if (typeof item === 'string' && /^[A-Za-z0-9_.:-]{1,120}$/.test(item)) record[key] = item;
    }
    runtimeDiagnostics.push(record);
    if (runtimeDiagnostics.length > 100) runtimeDiagnostics.shift();
  } catch { /* Unrecognized log text and raw error payloads are discarded. */ }
}

async function stopChild(child) {
  if (!child || child.exitCode !== null) return;
  if (process.platform !== 'win32') { child.kill(); return; }
  // Windows venv's launcher owns a base-Python child. Stop this verified spawned
  // tree so terminating the launcher cannot leave its uvicorn child behind.
  await new Promise(resolve => {
    const stopper = spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
    stopper.once('exit', resolve); stopper.once('error', resolve);
  });
}
const stopServer = () => stopChild(server);
const stopRuntime = () => stopChild(commandRuntime);

async function startApprovedRuntime(token) {
  if (!process.env.PERPLEXITY_API_KEY) throw new Error('The approved Perplexity key is missing from inherited process environment');
  commandRuntime = spawn(process.execPath, ['copilot-runtime/server.mjs'], { cwd: root, windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env,
      BIOS_COPILOT_MODEL: 'perplexity:openai/gpt-5.6-sol', BIOS_COPILOT_ALLOW_PAID_COMPARISON: '1',
      BIOS_RESEARCH_CREDIT_FREE_ONLY: '1', BIOS_COPILOT_RUNTIME_TOKEN: token, BIOS_COPILOT_PORT: String(runtimePort),
    } });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('The dedicated command runtime did not become ready')), 120000);
    const finish = callback => { clearTimeout(timer); callback(); };
    commandRuntime.stdout.on('data', bytes => {
      if (bytes.toString().includes('listening on loopback')) finish(resolve);
      // Other runtime payload/log text is intentionally discarded.
    });
    let diagnosticRemainder = '';
    commandRuntime.stderr.on('data', bytes => {
      const lines = (diagnosticRemainder + bytes.toString()).split(/\r?\n/);
      const remaining = lines.pop() || '';
      diagnosticRemainder = remaining.length < 4000 && ('Berry command diagnostic: '.startsWith(remaining) || remaining.startsWith('Berry command diagnostic: ')) ? remaining : '';
      for (const line of lines) retainRuntimeDiagnostic(line);
    });
    commandRuntime.once('error', () => finish(() => reject(new Error('The dedicated command runtime could not start'))));
    commandRuntime.once('exit', code => finish(() => reject(new Error(`The dedicated command runtime exited with code ${code}`))));
  });
  console.log(JSON.stringify({ stage: 'approved-command-runtime-ready', provider: 'perplexity', model: 'openai/gpt-5.6-sol', inheritedKeyPresent: true }));
}

async function navigateWhenReady(targetPage, url, budget = 180000) {
  const deadline = Date.now() + budget;
  let lastError;
  while (Date.now() < deadline) {
    if (server?.exitCode !== null && server?.exitCode !== undefined) throw new Error(`The local rehearsal server exited with code ${server.exitCode}`);
    try {
      const response = await targetPage.goto(url, { waitUntil: 'domcontentloaded', timeout: Math.min(15000, Math.max(1000, deadline - Date.now())) });
      if (!response || response.status() < 500) return response;
      lastError = new Error(`Local startup returned HTTP ${response.status()}`);
    } catch (error) {
      if (!/ERR_CONNECTION_REFUSED|ERR_CONNECTION_RESET|ERR_EMPTY_RESPONSE|Timeout.*exceeded/i.test(error.message)) throw error;
      lastError = error;
    }
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
  throw new Error(`Local browser readiness timed out: ${lastError?.message || 'server not ready'}`);
}

async function initialize(command) {
  const username = 'experience-rehearsal';
  const password = randomBytes(32).toString('base64url');
  const signingSecret = randomBytes(48).toString('base64url');
  const runtimeToken = randomBytes(48).toString('base64url');
  await fs.mkdir(path.join(artifactDir, 'continuous'), { recursive: true });
  if (copilotEnabled) await startApprovedRuntime(runtimeToken);
  server = spawn(process.env.BERRY_TEST_PYTHON || 'python', ['-m', 'uvicorn', 'app.main:app',
    '--host', '127.0.0.1', '--port', String(port), '--log-level', 'warning', '--lifespan', 'off'], {
    cwd: root, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', BIOS_MODE: 'authoring',
      BIOS_DATA_DIR: path.join(root, 'data'), BIOS_INBOX_DIR: rehearsalInbox,
      BIOS_REMOTE_INTERACTIVE: 'true', BIOS_REVIEW_USERNAME: username,
      BIOS_REVIEW_PASSWORD: password, BIOS_SESSION_SECRET: signingSecret,
      BIOS_COPILOT_RUNTIME_URL: copilotEnabled ? `http://127.0.0.1:${runtimePort}/copilot` : '',
      BIOS_COPILOT_RUNTIME_TOKEN: copilotEnabled ? runtimeToken : '', BIOS_RESEARCH_CREDIT_FREE_ONLY: 'true',
      SOURCE_POLLING_ENABLED: 'false', BIOS_SOURCE_POLLING_ENABLED: 'false' },
  });
  console.log(JSON.stringify({ stage: 'local-server-starting', port }));
  for (const stream of [server.stdout, server.stderr]) stream.on('data', bytes => { logs = (logs + bytes.toString()).slice(-6000); });
  browser = await chromium.launch({ headless: true, ...(process.env.BERRY_CHROMIUM_EXECUTABLE ? { executablePath: process.env.BERRY_CHROMIUM_EXECUTABLE } : {}) });
  console.log(JSON.stringify({ stage: 'chromium-launched' }));
  // Use the actual browser network path. Windows can deny Node's raw localhost
  // sockets even while the browser and PowerShell can reach this private server.
  const loginContext = await browser.newContext();
  const loginPage = await loginContext.newPage();
  await navigateWhenReady(loginPage, base + '/app/landscape');
  console.log(JSON.stringify({ stage: 'login-page-ready' }));
  if (!new URL(loginPage.url()).pathname.startsWith('/login')) throw new Error('Private shell failed anonymous access check');
  await loginPage.locator('input[name="username"]').fill(username);
  await loginPage.locator('input[name="password"]').fill(password);
  await Promise.all([
    loginPage.waitForURL(url => !url.pathname.startsWith('/login'), { timeout: 30000 }),
    loginPage.locator('button[type="submit"]').click(),
  ]);
  authenticatedState = await loginContext.storageState();
  await loginContext.close();
  console.log(JSON.stringify({ stage: 'authenticated-memory-only' }));
  // Preliminary inspection is unrecorded. The rehearsal module owns the one
  // continuous recording, avoiding video-finalization before its first frame.
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, storageState: authenticatedState });
  page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (/api\.openai|api\.anthropic|api\.perplexity/.test(request.url())) providerRequests.push(request.url().split('?')[0]);
  });
  const destination = command.path || '/app/landscape?ctx_v=1&berry=berry-blueberry&countries=geography-chile%2Cgeography-china%2Cgeography-peru';
  if (!destination.startsWith('/app/')) throw new Error('Use an application rehearsal destination');
  await page.goto(base + destination, { waitUntil: 'domcontentloaded' });
  return { authenticated: true, url: page.url(), artifacts: artifactDir };
}

function locator(command) {
  const value = command.role ? page.getByRole(command.role, { name: command.name, exact: !!command.exact }) : page.locator(command.selector);
  return value.nth(command.index || 0);
}
async function operate(command) {
  switch (command.op) {
    case 'init': return initialize(command);
    case 'rehearse': {
      if (!browser || !authenticatedState) throw new Error('Initialize the real authenticated browser first');
      if (command.approvedCommand !== undefined && command.approvedCommand !== approvedCommand) throw new Error('Only the one explicitly approved comparison command is supported');
      if (command.approvedCommand && (!copilotEnabled || paidCommandConsumed)) throw new Error('The approved paid command is unavailable or already consumed');
      await context?.close(); context = null; page = null;
      const { pathToFileURL } = require('node:url');
      const moduleURL = pathToFileURL(path.join(root, 'frontend/e2e/experience-rehearsal.mjs'));
      moduleURL.searchParams.set('revision', String(Date.now()));
      const { runRehearsal } = await import(moduleURL.href);
      const result = await runRehearsal({ baseURL: base, storageState: authenticatedState, browser,
        revision: command.revision || 'working checkout', outputDir: path.join(artifactDir, `rehearsal-${Date.now()}`),
        ...(command.approvedCommand ? { approvedCopilotCommand: approvedCommand } : {}) });
      if (result.report.approved_provider_turn_requests?.length) {
        paidCommandConsumed = true;
        await stopRuntime();
        result.report.runtime_diagnostics = [...runtimeDiagnostics];
        await fs.writeFile(path.join(result.outputDir, 'acceptance.json'), JSON.stringify(result.report, null, 2));
      }
      return result;
    }
    case 'grid-rehearse': {
      if (!browser || !authenticatedState) throw new Error('Initialize the real authenticated browser first');
      await context?.close(); context = null; page = null;
      const { pathToFileURL } = require('node:url');
      const moduleURL = pathToFileURL(path.join(root, 'frontend/e2e/grid-rehearsal.mjs'));
      moduleURL.searchParams.set('revision', String(Date.now()));
      const { runGridRehearsal } = await import(moduleURL.href);
      return runGridRehearsal({ baseURL: base, storageState: authenticatedState, browser,
        revision: command.revision || 'working checkout', outputDir: path.join(artifactDir, `grid-rehearsal-${Date.now()}`) });
    }
    case 'briefing-rehearse':
    case 'workspaces-rehearse':
    case 'learn-rehearse': {
      if (!browser || !authenticatedState) throw new Error('Initialize the real authenticated browser first');
      if (copilotEnabled) throw new Error('Native feature rehearsals require an explicitly provider-disabled worker');
      await context?.close(); context = null; page = null;
      const feature = command.op.split('-')[0];
      const names = { briefing: 'runBriefingRehearsal', workspaces: 'runWorkspacesRehearsal', learn: 'runLearnRehearsal' };
      const { pathToFileURL } = require('node:url');
      const moduleURL = pathToFileURL(path.join(root, `frontend/e2e/${feature}-rehearsal.mjs`));
      moduleURL.searchParams.set('revision', String(Date.now()));
      const run = (await import(moduleURL.href))[names[feature]];
      return run({ baseURL: base, storageState: authenticatedState, browser,
        revision: command.revision || 'working checkout', outputDir: path.join(artifactDir, `${feature}-rehearsal-${Date.now()}`) });
    }
    case 'copilot-info': {
      if (!page || !copilotEnabled) throw new Error('Initialize the approved local runtime and browser first');
      return page.evaluate(async () => {
        const response = await fetch('/api/investigations/v1/copilot', { method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ method: 'info' }) });
        const body = await response.json();
        const agents = body.agents || body.data?.agents || {};
        return { status: response.status, agentIds: Object.keys(agents), metadataOnly: true };
      });
    }
    case 'review': {
      if (!browser || !authenticatedState) throw new Error('Initialize the authenticated browser first');
      const destination = command.path || '/app/landscape?ctx_v=1&berry=berry-blueberry&countries=geography-chile%2Cgeography-china%2Cgeography-peru';
      if (!destination.startsWith('/app/')) throw new Error('Use an application review destination');
      await context?.close();
      context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, storageState: authenticatedState });
      page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      await navigateWhenReady(page, base + destination);
      return { url: page.url(), review: true };
    }
    case 'server-log': return { recent: logs, serverPid: server?.pid, exitCode: server?.exitCode };
    case 'runtime-diagnostics': return { records: [...runtimeDiagnostics], raw_payloads_retained: false };
    case 'export-anonymous-check': {
      if (!browser) throw new Error('Initialize the private local server first');
      const anonymous = await browser.newContext();
      try {
        const probe = await anonymous.newPage();
        await probe.goto(base + '/login', { waitUntil: 'domcontentloaded' });
        const result = await probe.evaluate(async () => {
          const response = await fetch('/api/investigations/v1/export/preview', { method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ context: { ctx_v: '1', berry: 'berry-blueberry' }, section_ids: ['readout'], include_demo: false }) });
          return { status: response.status, redirected: response.redirected, destination: new URL(response.url).pathname,
            content_type: response.headers.get('content-type') };
        });
        if (result.status === 200 && !result.redirected && result.content_type?.includes('application/json')) throw new Error('Anonymous export unexpectedly returned domain content');
        if (![401, 403].includes(result.status) && result.destination !== '/login') throw new Error('Anonymous export did not reach the private-session gate');
        return { ...result, domain_content_exposed: false };
      } finally { await anonymous.close(); }
    }
    case 'export-preview': {
      if (!page) throw new Error('An authenticated browser page is required');
      exportSelection = { context: command.context || { ctx_v: '1', berry: 'berry-blueberry',
        countries: 'geography-chile,geography-china,geography-peru', geo_basis: 'company_connections' },
        section_ids: command.sections || ['readout', 'relationships', 'portfolio', 'geography', 'comparison', 'developments'], include_demo: command.include_demo === true };
      const result = await page.evaluate(async selection => {
        const response = await fetch('/api/investigations/v1/export/preview', { method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(selection) });
        return { status: response.status, body: await response.json() };
      }, exportSelection);
      if (result.status !== 200) throw new Error(`Current-data export preview returned HTTP ${result.status}: ${JSON.stringify(result.body).slice(0,500)}`);
      exportPreview = result.body;
      return { sections: exportPreview.sections, content_hash: exportPreview.content_hash,
        source_count: exportPreview.sources.length, include_demo: exportPreview.include_demo, scope: exportPreview.scope };
    }
    case 'export-pdf': {
      if (!page || !exportSelection || !exportPreview) throw new Error('Preview the current-data export first');
      const result = await page.evaluate(async selection => {
        const response = await fetch('/api/investigations/v1/export/pdf', { method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(selection) });
        return response.ok ? { status: response.status, bytes: Array.from(new Uint8Array(await response.arrayBuffer())) }
          : { status: response.status, error: await response.text() };
      }, { ...exportSelection, expected_content_hash: exportPreview.content_hash });
      if (result.status !== 200) throw new Error(`Current-data PDF returned HTTP ${result.status}: ${result.error?.slice(0,500)}`);
      const destination = path.join(artifactDir, exportSelection.include_demo ? 'current-investigation-with-synthetic-annex.pdf' : 'current-investigation.pdf');
      await fs.writeFile(destination, Buffer.from(result.bytes));
      return { path: destination, bytes: result.bytes.length, content_hash: exportPreview.content_hash, source_count: exportPreview.sources.length };
    }
    case 'inspect': return { url: page.url(), text: (await page.locator('body').innerText()).slice(0, 20000), errors, providerRequests };
    case 'click': await locator(command).click({ timeout: 20000 }); break;
    case 'fill': await locator(command).fill(command.value); break;
    case 'select': await locator(command).selectOption(command.values); break;
    case 'press': await page.keyboard.press(command.key); break;
    case 'focus': await locator(command).focus(); break;
    case 'wait': await page.getByText(command.text, { exact: !!command.exact }).first().waitFor({ timeout: 30000 }); break;
    case 'capture': {
      if (!/^[a-z0-9_-]+\.png$/i.test(command.name)) throw new Error('Use a simple screenshot filename');
      const destination = path.join(artifactDir, command.name);
      await page.screenshot({ path: destination, fullPage: !!command.fullPage });
      return { path: destination };
    }
    case 'viewport': await page.setViewportSize(command.size); break;
    case 'motion': await page.emulateMedia({ reducedMotion: command.value }); break;
    case 'reload': await page.reload({ waitUntil: 'domcontentloaded' }); break;
    case 'back': await page.goBack({ waitUntil: 'domcontentloaded' }); break;
    case 'forward': await page.goForward({ waitUntil: 'domcontentloaded' }); break;
    case 'goto':
      if (!command.path.startsWith('/app/')) throw new Error('Use an application destination');
      await page.goto(base + command.path, { waitUntil: 'domcontentloaded' }); break;
    case 'metrics': return page.evaluate(() => ({
      width: innerWidth, documentWidth: document.documentElement.scrollWidth,
      focus: document.activeElement?.getAttribute('aria-label') || document.activeElement?.textContent?.slice(0, 120),
      modal: !!document.querySelector('[aria-modal="true"]'),
      detailText: document.querySelector('.berry-detail')?.textContent?.slice(0, 2000),
      gridRows: document.querySelectorAll('.ag-row').length,
      rootInstances: document.querySelectorAll('.berry-shell').length,
      inertBackground: document.querySelector('.berry-main')?.inert,
    }));
    case 'close': {
      const recording = page?.video();
      await Promise.all([stopServer(), stopRuntime()]);
      await context?.close(); context = null; page = null;
      const video = recording ? await recording.path() : null;
      await browser?.close(); browser = null;
      return { video, errors, providerRequests };
    }
    default: throw new Error('Unsupported rehearsal operation');
  }
  return { url: page.url() };
}

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
input.on('line', line => {
  queue = queue.then(async () => {
    let command;
    try { command = JSON.parse(line); const value = await operate(command); console.log(JSON.stringify({ id: command.id, ok: true, value })); }
    catch (error) { console.log(JSON.stringify({ id: command?.id, ok: false, error: error.message })); }
  });
});
input.on('close', () => { void Promise.allSettled([stopServer(), stopRuntime()]); void queue.finally(async () => { await context?.close(); await browser?.close(); }); });
process.once('SIGINT', () => { void Promise.allSettled([stopServer(), stopRuntime(), context?.close(), browser?.close()]).finally(() => process.exit(0)); });
console.log(JSON.stringify({ ready: true, credentials: 'memory-only', providers: copilotEnabled ? 'one-approved-comparison-only' : 'disabled', pythonResearchCreditFreeOnly: true }));
