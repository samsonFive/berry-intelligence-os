(function () {
  var DESKTOP = 1100;
  var SIDEBAR_KEY = "bios-v2-sidebar";
  var app = document.getElementById("v2-app");
  var toggle = document.getElementById("v2NavToggle");
  var offcanvasEl = document.getElementById("v2NavOffcanvas");
  var navInstance = null;

  function isDesktop() {
    return window.matchMedia("(min-width: " + DESKTOP + "px)").matches;
  }
  function setToggleState(expanded, label) {
    if (!toggle) return;
    toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    toggle.setAttribute("aria-label", label);
  }
  function applyStoredSidebar() {
    if (!app || !isDesktop()) return;
    var collapsed = false;
    try { collapsed = sessionStorage.getItem(SIDEBAR_KEY) === "collapsed"; } catch (err) { collapsed = false; }
    app.classList.toggle("v2-app--sidebar-collapsed", collapsed);
    setToggleState(!collapsed, collapsed ? "Expand navigation" : "Collapse navigation");
  }
  applyStoredSidebar();
  window.addEventListener("resize", function () {
    if (isDesktop()) {
      applyStoredSidebar();
      if (navInstance) navInstance.hide();
    } else {
      setToggleState(false, "Open navigation");
    }
  });

  if (toggle && app) {
    if (offcanvasEl && window.bootstrap) {
      navInstance = window.bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl);
      offcanvasEl.addEventListener("shown.bs.offcanvas", function () {
        setToggleState(true, "Close navigation");
      });
      offcanvasEl.addEventListener("hidden.bs.offcanvas", function () {
        setToggleState(false, "Open navigation");
        toggle.focus();
      });
    }
    toggle.addEventListener("click", function () {
      if (isDesktop()) {
        var collapsed = !app.classList.contains("v2-app--sidebar-collapsed");
        app.classList.toggle("v2-app--sidebar-collapsed", collapsed);
        try { sessionStorage.setItem(SIDEBAR_KEY, collapsed ? "collapsed" : "expanded"); } catch (err) { /* ignore */ }
        setToggleState(!collapsed, collapsed ? "Expand navigation" : "Collapse navigation");
        return;
      }
      if (navInstance) navInstance.toggle();
    });
  }

  var cards = Array.prototype.slice.call(document.querySelectorAll("[data-intel-card]"));
  var overlay = document.getElementById("v2ReaderOffcanvas");
  var overlayBody = document.getElementById("v2ReaderBody");
  var overlayInstance = null;
  var lastTrigger = null;
  var overlayOpen = false;
  var loadGen = 0;
  var active = 0;

  function inFormField(target) {
    return target && target.closest && target.closest("input, textarea, select, [contenteditable='true']");
  }
  function selectCard(index, opts) {
    if (!cards.length) return;
    active = Math.max(0, Math.min(cards.length - 1, index));
    cards.forEach(function (card, i) {
      card.classList.toggle("is-current", i === active);
    });
    if (!opts || !opts.skipFocus) {
      cards[active].focus({ preventScroll: true });
    }
    cards[active].scrollIntoView({ block: "nearest" });
  }
  function current() { return cards[active]; }
  function submitAction(name) {
    var root = overlayOpen && overlay ? overlay : current();
    if (!root) return;
    if (root.dataset && root.dataset.pending === "false") return;
    var button = root.querySelector("[data-" + name + "]");
    if (button && button.closest("form")) button.closest("form").requestSubmit();
  }
  function copyReviewer(form) {
    var reviewer = document.getElementById("feed-reviewer");
    if (!reviewer) return;
    var field = form.querySelector("[name=reviewer]");
    if (field) field.value = reviewer.value;
  }
  function itemIdFromCard(card) {
    return card && card.getAttribute("data-item-id");
  }
  function closeOverlay() {
    if (overlayInstance) overlayInstance.hide();
  }
  function focusReaderHeading() {
    var heading = overlayBody && overlayBody.querySelector(".v2-reader-title");
    if (!heading) return;
    heading.setAttribute("tabindex", "-1");
    heading.focus();
  }
  function ensureOverlay() {
    if (!overlay || !window.bootstrap) return null;
    if (!overlayInstance) {
      overlayInstance = window.bootstrap.Offcanvas.getOrCreateInstance(overlay, { backdrop: true, keyboard: false });
      overlay.addEventListener("shown.bs.offcanvas", function () {
        overlayOpen = true;
        focusReaderHeading();
      });
      overlay.addEventListener("hidden.bs.offcanvas", function () {
        overlayOpen = false;
        if (lastTrigger && lastTrigger.focus) lastTrigger.focus();
      });
    }
    return overlayInstance;
  }
  function loadReaderById(id, trigger, cardIndex) {
    if (!id || !overlay || !overlayBody) return;
    if (typeof cardIndex === "number") selectCard(cardIndex, { skipFocus: true });
    lastTrigger = trigger || lastTrigger;
    var gen = ++loadGen;
    overlayBody.innerHTML = "<p class=\"empty-state\">Loading…</p>";
    var instance = ensureOverlay();
    if (instance) instance.show();
    fetch("/api/intelligence/" + encodeURIComponent(id) + "/reader", { credentials: "same-origin" })
      .then(function (res) {
        if (!res.ok) throw new Error("Reader unavailable");
        return res.text();
      })
      .then(function (html) {
        if (gen !== loadGen) return;
        overlayBody.innerHTML = html;
        overlayBody.querySelectorAll("form").forEach(function (form) {
          form.addEventListener("submit", function () { copyReviewer(form); });
        });
        var title = overlayBody.querySelector(".v2-reader-title");
        var titleEl = document.getElementById("v2ReaderTitle");
        if (titleEl) titleEl.textContent = title ? title.textContent : "Reader";
        if (overlayOpen) focusReaderHeading();
      })
      .catch(function () {
        if (gen !== loadGen) return;
        overlayBody.innerHTML = "<p class=\"empty-state\">Could not load this item. <a href=\"/intelligence/" + encodeURIComponent(id) + "\">Open full reader</a></p>";
      });
  }
  function loadReader(index) {
    var card = cards[index];
    if (!card) return;
    loadReaderById(itemIdFromCard(card), card.querySelector("[data-open-reader]") || card, index);
  }

  cards.forEach(function (card, index) {
    card.addEventListener("click", function (event) {
      selectCard(index);
      if (event.target.closest("form, button, .v2-chip, a:not([data-open-reader])")) return;
      if (event.target.closest("[data-open-reader]") && overlay) {
        event.preventDefault();
        loadReader(index);
      }
    });
    var openers = card.querySelectorAll("[data-open-reader]");
    openers.forEach(function (link) {
      link.addEventListener("click", function (event) {
        if (!overlay || event.metaKey || event.ctrlKey) return;
        event.preventDefault();
        selectCard(index);
        loadReader(index);
      });
    });
  });
  document.querySelectorAll("[data-open-reader]").forEach(function (link) {
    if (link.closest("[data-intel-card]")) return;
    link.addEventListener("click", function (event) {
      if (!overlay || event.metaKey || event.ctrlKey) return;
      var id = link.getAttribute("data-item-id");
      if (!id) {
        var match = (link.getAttribute("href") || "").match(/\/intelligence\/([^/?#]+)/);
        id = match ? decodeURIComponent(match[1]) : "";
      }
      if (!id) return;
      event.preventDefault();
      var cardIndex = cards.findIndex(function (card) { return itemIdFromCard(card) === id; });
      loadReaderById(id, link, cardIndex >= 0 ? cardIndex : undefined);
    });
  });
  document.querySelectorAll("[data-intel-card] form").forEach(function (form) {
    form.addEventListener("submit", function () { copyReviewer(form); });
  });

  var prev = document.getElementById("v2ReaderPrev");
  var next = document.getElementById("v2ReaderNext");
  if (prev) prev.addEventListener("click", function () { if (cards.length) loadReader(active - 1); });
  if (next) next.addEventListener("click", function () { if (cards.length) loadReader(active + 1); });

  document.addEventListener("keydown", function (event) {
    if (inFormField(event.target)) return;
    if (event.key === "Escape" && overlayOpen) {
      event.preventDefault();
      closeOverlay();
      return;
    }
    if (!cards.length) return;
    if (event.key === "j") {
      event.preventDefault();
      if (overlayOpen) loadReader(active + 1);
      else selectCard(active + 1);
    } else if (event.key === "k") {
      event.preventDefault();
      if (overlayOpen) loadReader(active - 1);
      else selectCard(active - 1);
    } else if (event.key === "Enter" || event.key === "o") {
      event.preventDefault();
      if (overlay) loadReader(active);
      else {
        var read = current() && current().querySelector("[data-read]");
        if (read) window.location.href = read.href;
      }
    } else if (event.key === "a") { event.preventDefault(); submitAction("promote"); }
    else if (event.key === "s") { event.preventDefault(); submitAction("save"); }
    else if (event.key === "r") { event.preventDefault(); submitAction("reject"); }
  });
  if (cards.length) active = 0;
})();
