"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const script = fs.readFileSync(path.join(__dirname, "../app/static/variety_coverage_sources.js"), "utf8");
const tick = () => new Promise(resolve => setImmediate(resolve));

function fixture(handler, hash = "") {
  const calls = [], events = {}, states = [];
  function element(tag) {
    return {tag, attrs: {}, listeners: {}, children: [],
      setAttribute(key, value) { this.attrs[key] = value; },
      addEventListener(key, callback) { this.listeners[key] = callback; },
      replaceChildren(...children) { this.children = children; },
    };
  }
  const link = {href: "https://workspace.test/varieties/coverage/source/source-a?berry=berry-blueberry"};
  const panel = element("div"); panel.querySelector = () => link;
  const details = element("details"); details.open = false; details.querySelector = () => panel;
  const row = {querySelector: () => details};
  const document = {
    querySelectorAll: () => [details], getElementById: id => id === "portfolio-source-source-a" ? row : null,
    createElement(tag) {
      const node = element(tag);
      if (tag === "template") Object.defineProperty(node, "innerHTML", {set(html) {
        const body = html.includes("data-portfolio-source-content") ? element("source-body") : null;
        node.content = {children: body ? [body] : [], querySelector: () => body};
      }});
      return node;
    },
  };
  const window = {location: {href: "https://workspace.test/varieties/coverage", origin: "https://workspace.test", hash},
    addEventListener: (key, value) => { events[key] = value; }};
  const context = {document, window, URL, Map, fetch: async (url, options) => {
    calls.push({url, options});
    states.push(panel.attrs["aria-busy"]);
    return handler(url, options, calls.length);
  }};
  vm.runInNewContext(script, context);
  return {calls, states, panel, details, link, events, window};
}
function success(url) {
  return {ok: true, url, headers: {get: () => "1"}, text: async () => '<div data-portfolio-source-content>Source warnings and names</div>'};
}

(async () => {
  const normal = fixture(success);
  assert.equal(normal.calls.length, 0, "Closed rows must not load source bodies");
  normal.details.open = true; normal.details.listeners.toggle(); normal.details.listeners.toggle();
  await tick();
  assert.equal(normal.calls.length, 1, "An in-flight opening must not duplicate the request");
  assert.equal(normal.panel.children[0].tag, "source-body");
  assert.equal(normal.states[0], "true");
  assert.equal(normal.panel.attrs["aria-busy"], "false");
  const call = normal.calls[0];
  assert.equal(new URL(call.url).searchParams.get("berry"), "berry-blueberry");
  assert.equal(new URL(call.url).searchParams.get("fragment"), "1");
  assert.equal(call.options.credentials, "same-origin");
  assert.equal(call.options.redirect, "error");
  assert.equal(call.options.cache, "no-store");
  normal.details.open = false; normal.details.listeners.toggle();
  normal.details.open = true; normal.details.listeners.toggle(); await tick();
  assert.equal(normal.calls.length, 1, "Reopening a loaded row keeps the content without extra clicks");

  for (const failure of ["network", "login", "missing", "wrong-url", "bad-body"]) {
    const failed = fixture((url, _options, count) => {
      if (count > 1) return success(url);
      if (failure === "network") throw Error("offline");
      const response = success(url);
      if (failure === "login") response.headers.get = () => null;
      if (failure === "missing") response.ok = false;
      if (failure === "wrong-url") response.url = "https://workspace.test/login";
      if (failure === "bad-body") response.text = async () => "<form>Login must never enter the source row</form>";
      return response;
    });
    failed.details.open = true; failed.details.listeners.toggle(); await tick();
    assert.match(failed.panel.children[0].textContent, /could not load/);
    assert.equal(failed.panel.children[2], failed.link, "Keep the normal page fallback after failure");
    assert.equal(failed.panel.attrs["aria-busy"], "false");
    failed.panel.children[1].listeners.click(); await tick();
    assert.equal(failed.calls.length, 2);
    assert.equal(failed.panel.children[0].tag, "source-body", "Retry must actually reveal source content");
  }
  const anchored = fixture(success, "#portfolio-source-source-a"); await tick();
  assert.equal(anchored.details.open, true);
  assert.equal(anchored.calls.length, 1, "An existing source bookmark must open and load its row");
  const different = fixture(success, "#portfolio-source-plan"); await tick();
  assert.equal(different.calls.length, 0, "The source plan anchor must not open an unrelated source");
  different.window.location.hash = "#portfolio-source-source-a"; different.events.hashchange(); await tick();
  assert.equal(different.calls.length, 1);
  const malformed = fixture(success, "#%broken"); await tick();
  assert.equal(malformed.calls.length, 0);
  const outside = fixture(success);
  outside.link.href = "https://other.test/source";
  outside.details.open = true; outside.details.listeners.toggle(); await tick();
  assert.equal(outside.calls.length, 0, "A source row must never fetch a different origin");
  assert.match(outside.panel.children[0].textContent, /could not load/);
})().catch(error => { console.error(error); process.exitCode = 1; });
