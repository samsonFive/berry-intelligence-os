(function () {
  "use strict";
  var root = document.body;
  if (!root.hasAttribute("data-personal-digest")) return;
  var reader = null, mode = "article", positions = {}, actionChain = Promise.resolve(), digestDirty = false, lastReaderId = null;
  var status = document.querySelector(".digest-status"), statusTimer;
  function announce(message, panel) {
    var local = panel && panel.querySelector(".reader-action-status");
    if (local) local.textContent = message;
    else if (status) { status.textContent = message; clearTimeout(statusTimer); statusTimer = setTimeout(function () { status.textContent = ""; }, 6000); }
  }
  function scroller() { return reader && (reader.closest(".offcanvas-body") || document.scrollingElement); }
  function request(id, payload) {
    var result = actionChain.catch(function () {}).then(function () {
      return fetch("/digest/stories/" + encodeURIComponent(id), {method: "POST", credentials: "same-origin", keepalive: true,
        headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)}).then(function (response) {
        if (!response.ok) throw new Error("Could not save this change. Try again.");
        return response.json();
      });
    });
    actionChain = result;
    return result;
  }
  function remember() {
    if (!reader || reader.dataset.authoring !== "true") return Promise.resolve();
    var scroll = scroller();
    positions[mode] = scroll ? Math.round(scroll.scrollTop) : 0;
    return request(reader.dataset.itemId, {action: "location", mode: mode, position: positions[mode]});
  }
  function applyMode(next) {
    if (!reader) return;
    mode = next;
    reader.querySelectorAll("[data-personal-pane]").forEach(function (pane) { pane.hidden = pane.dataset.personalPane !== mode; });
    reader.querySelectorAll("[data-personal-mode]").forEach(function (button) { button.setAttribute("aria-pressed", String(button.dataset.personalMode === mode)); });
    var scroll = scroller();
    if (scroll) scroll.scrollTop = positions[mode] || 0;
  }
  function setupReader() {
    reader = document.querySelector("#v2ReaderBody [data-personal-reader]") || document.querySelector(".full-personal-reader [data-personal-reader]");
    if (!reader) return;
    var stored = reader.querySelector("[data-reading-location]");
    lastReaderId = reader.dataset.itemId;
    var location = stored ? JSON.parse(stored.textContent) : {};
    positions = location.positions || {};
    applyMode(location.mode === "brief" ? "brief" : "article");
  }
  function updateButtons(id, decision) {
    document.querySelectorAll('[data-personal-action][data-item-id="' + CSS.escape(id) + '"]').forEach(function (button) {
      var action = button.dataset.personalAction;
      if (action === "save" || action === "unsave") {
        var label = decision.saved ? "Remove saved mark" : "Save story";
        button.dataset.personalAction = decision.saved ? "unsave" : "save";
        button.setAttribute("aria-label", label); button.setAttribute("aria-pressed", String(decision.saved));
        button.classList.toggle("selected", decision.saved);
        var tooltip = button.querySelector(".action-tooltip"); if (tooltip) tooltip.textContent = label;
      } else if (action === "useful" || action === "not_relevant" || action === "clear_feedback") {
        var positive = button.getAttribute("aria-label") === "Useful";
        var selected = decision.reaction === (positive ? "up" : "down");
        button.dataset.personalAction = selected ? "clear_feedback" : (positive ? "useful" : "not_relevant");
        button.setAttribute("aria-pressed", String(selected)); button.classList.toggle("selected", selected);
      }
    });
  }
  document.addEventListener("click", function (event) {
    var widthButton = event.target.closest("[data-personal-wide]");
    if (widthButton) {
      var panel = document.getElementById("v2ReaderOffcanvas");
      var wide = panel.classList.toggle("is-wide");
      widthButton.setAttribute("aria-pressed", String(wide));
      widthButton.textContent = wide ? "Narrower" : "Wider";
      widthButton.setAttribute("aria-label", wide ? "Narrower reading view" : "Wider reading view");
    }
    var button = event.target.closest("[data-personal-action]");
    if (button && !button.disabled) {
      var id = button.dataset.itemId, action = button.dataset.personalAction, panel = button.closest("[data-personal-reader]");
      button.disabled = true;
      request(id, {action: action}).then(function (result) {
        updateButtons(id, result.decision);
        digestDirty = true;
        if (!panel) refreshDigest();
        announce(action === "mark_read" ? "Reading completed. Your saved mark is unchanged." : action === "start" ? "Marked in progress." : "Saved your change.", panel);
      }).catch(function (error) { announce(error.message, panel); }).finally(function () { button.disabled = false; });
    }
    var modeButton = event.target.closest("[data-personal-mode]");
    if (modeButton && reader) {
      var next = modeButton.dataset.personalMode;
      if (next !== mode) {
        remember().catch(function (error) { announce(error.message, reader); });
        applyMode(next);
        remember().catch(function (error) { announce(error.message, reader); });
      }
    }
    var capture = event.target.closest("[data-personal-capture]");
    if (capture && reader) {
      var activeReader = reader, id = reader.dataset.itemId;
      capture.disabled = true; capture.textContent = "Loading article…";
      fetch("/api/digest/" + encodeURIComponent(id) + "/capture", {method: "POST", credentials: "same-origin"}).then(function (response) {
        if (!response.ok) throw new Error("Article could not be loaded. You can read at the publisher.");
        return response.text();
      }).then(function (html) {
        // A late capture must never replace the next story the user opened.
        if (reader !== activeReader || !activeReader.isConnected) return;
        activeReader.outerHTML = html; setupReader(); applyMode("article");
        if (!reader.querySelector(".article-prose")) announce("Article text could not be loaded here. Try again, read at the publisher or use the Brief.", reader);
      }).catch(function (error) { announce(error.message, activeReader); }).finally(function () { if (capture.isConnected) { capture.disabled = false; capture.textContent = "Load available article text"; } });
    }
    if (!event.target.closest(".glass-more")) { var more = document.querySelector(".glass-more"); if (more) more.open = false; }
    document.querySelectorAll(".filter-multi[open]").forEach(function (details) {
      if (!details.contains(event.target)) details.open = false;
    });
  });
  document.addEventListener("change", function (event) {
    if (event.target.matches("[data-digest-window]")) document.querySelector(".custom-dates").hidden = event.target.value !== "custom";
    if (event.target.matches('[form="complete-selected"]')) { var complete = document.querySelector("[data-complete-selected]"); if (complete) complete.disabled = !document.querySelector('[form="complete-selected"]:checked'); }
  });
  var filters = document.querySelector(".digest-filters");
  if (filters) filters.addEventListener("submit", function () {
    filters.querySelectorAll("[data-multi-value]").forEach(function (input) {
      var name = input.dataset.multiValue;
      input.value = Array.from(filters.querySelectorAll('[name="' + name + '"]:checked')).map(function (checkbox) { return checkbox.value; }).join(",");
      filters.querySelectorAll('[name="' + name + '"]').forEach(function (checkbox) { checkbox.disabled = true; });
    });
  });
  document.addEventListener("bios:reader-unloading", function () { remember().catch(function (error) { announce(error.message, reader); }); reader = null; });
  document.addEventListener("bios:reader-loaded", setupReader);
  var overlay = document.getElementById("v2ReaderOffcanvas");
  function refreshDigest() {
    if (!digestDirty || !document.querySelector(".digest-grid")) return;
    var focused = document.activeElement && document.activeElement.closest("[data-intel-card]");
    var focusId = (focused && focused.dataset.itemId) || lastReaderId;
    var url = new URL(window.location.href); url.searchParams.delete("story");
    actionChain.catch(function () {}).then(function () {
      return fetch(url, {credentials: "same-origin"}).then(function (response) { if (!response.ok) throw new Error("Refresh your Digest to see the latest reading state."); return response.text(); });
    }).then(function (html) {
      if (overlay && (overlay.classList.contains("show") || overlay.classList.contains("showing"))) return;
      var page = new DOMParser().parseFromString(html, "text/html");
      [".digest-grid", "[data-digest-counts]", "[data-digest-matching]", ".digest-pagination"].forEach(function (selector) {
        var current = document.querySelector(selector), next = page.querySelector(selector);
        if (current && next) current.innerHTML = next.innerHTML;
      });
      digestDirty = false;
      document.dispatchEvent(new CustomEvent("bios:intelligence-updated"));
      var opener = focusId && document.querySelector('[data-intel-card][data-item-id="' + CSS.escape(focusId) + '"] [data-open-reader]');
      if (!opener && focusId) opener = document.querySelector(".digest-grid [data-open-reader]") || document.getElementById("digest-main");
      if (opener) opener.focus({preventScroll: true});
      var complete = document.querySelector("[data-complete-selected]"); if (complete) complete.disabled = true;
    }).catch(function (error) { announce(error.message); });
  }
  if (overlay) {
    overlay.addEventListener("hide.bs.offcanvas", function () { remember().catch(function (error) { announce(error.message, reader); }); });
    overlay.addEventListener("hidden.bs.offcanvas", refreshDigest);
  }
  window.addEventListener("pagehide", function () { remember().catch(function () {}); });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    var visible = Array.from(document.querySelectorAll(".icon-action")).find(function (button) { var tip = button.querySelector(".action-tooltip"); return tip && getComputedStyle(tip).visibility === "visible"; });
    if (visible) { visible.dataset.tooltipDismissed = "true"; event.stopImmediatePropagation(); event.preventDefault(); }
    var more = document.querySelector(".glass-more"); if (more && more.open) { more.open = false; more.querySelector("summary").focus(); event.stopImmediatePropagation(); event.preventDefault(); }
  }, true);
  document.addEventListener("pointerout", function (event) { var button = event.target.closest(".icon-action"); if (button && !button.contains(event.relatedTarget)) delete button.dataset.tooltipDismissed; });
  document.addEventListener("focusout", function (event) { var button = event.target.closest(".icon-action"); if (button) delete button.dataset.tooltipDismissed; });
  document.addEventListener("focusin", function (event) {
    document.querySelectorAll(".filter-multi[open]").forEach(function (details) { if (!details.contains(event.target)) details.open = false; });
  });
  document.addEventListener("toggle", function (event) {
    var details = event.target;
    if (!details.matches || !details.matches(".filter-multi") || !details.open) return;
    var panel = details.querySelector("div");
    if (!panel) return;
    panel.style.transform = "";
    var bounds = panel.getBoundingClientRect();
    var width = document.documentElement.clientWidth;
    var shift = bounds.right > width - 12 ? width - 12 - bounds.right : bounds.left < 12 ? 12 - bounds.left : 0;
    if (shift) panel.style.transform = "translateX(" + shift + "px)";
  }, true);
  setupReader();
  document.addEventListener("error", function (event) {
    var image = event.target;
    if (image && image.matches && image.matches("img.digest-image, img.reader-image")) image.hidden = true;
  }, true);
})();
