"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sources = {tagName: "DETAILS", open: false};
const idea = {tagName: "SECTION"};
const other = {tagName: "DETAILS", open: false};
const nodes = {sources, "what-is-it": idea, other};
let click;
const context = {
  document: {
    querySelector: () => null,
    querySelectorAll: () => [],
    getElementById: id => nodes[id] || null,
    addEventListener: (name, callback) => { if (name === "click") click = callback; },
  },
  window: {},
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../app/static/learn_workspace.js"), "utf8"), context);
assert.equal(sources.open, false, "Ordinary lesson load must keep secondary sources folded");

function follow(id, options = {}) {
  const link = {getAttribute: () => "#" + id};
  const event = {
    button: 0,
    target: {closest: selector => selector === ".learn-jumps a[href^='#']" ? link : null},
    preventDefault: () => { throw Error("Do not replace native fragment navigation/history"); },
    ...options,
  };
  click(event);
}
follow("sources");
assert.equal(sources.open, true, "Sources jump must reveal the actual reference links in one click");
assert.equal(other.open, false, "Unrelated disclosures stay folded");
sources.open = false;
for (const modifier of ["ctrlKey", "metaKey", "shiftKey", "altKey"]) {
  follow("sources", {[modifier]: true});
  assert.equal(sources.open, false, "Modified navigation must not alter this page");
}
follow("sources", {button: 1});
assert.equal(sources.open, false);
follow("what-is-it");
assert.equal(idea.open, undefined, "Ordinary section jumps remain native");
follow("missing");
assert.equal(sources.open, false, "Missing targets must be harmless");
follow("sources");
assert.equal(sources.open, true, "Reopening after a user collapses sources must work");
