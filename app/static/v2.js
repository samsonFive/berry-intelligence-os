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
  function bindStandaloneReaderLink(link) {
    if (!link || link.dataset.readerBound === "1" || link.closest("[data-intel-card]")) return;
    link.dataset.readerBound = "1";
    link.addEventListener("click", function (event) {
      if (!overlay || event.metaKey || event.ctrlKey) return;
      var id = link.getAttribute("data-item-id");
      if (!id) {
        var match = (link.getAttribute("href") || "").match(/\/intelligence\/([^/?#]+)/);
        id = match ? decodeURIComponent(match[1]) : "";
      }
      if (!id) return;
      event.preventDefault();
      if (searchOpen) closeSearch();
      var cardIndex = cards.findIndex(function (card) { return itemIdFromCard(card) === id; });
      loadReaderById(id, link, cardIndex >= 0 ? cardIndex : undefined);
    });
  }
  document.querySelectorAll("[data-open-reader]").forEach(function (link) {
    if (link.closest("[data-intel-card]")) return;
    bindStandaloneReaderLink(link);
  });
  document.querySelectorAll("[data-intel-card] form").forEach(function (form) {
    form.addEventListener("submit", function () { copyReviewer(form); });
  });

  var prev = document.getElementById("v2ReaderPrev");
  var next = document.getElementById("v2ReaderNext");
  if (prev) prev.addEventListener("click", function () { if (cards.length) loadReader(active - 1); });
  if (next) next.addEventListener("click", function () { if (cards.length) loadReader(active + 1); });

  var searchEl = document.getElementById("v2SearchOffcanvas");
  var searchInput = document.getElementById("v2SearchInput");
  var searchStatus = document.getElementById("v2SearchStatus");
  var searchResults = document.getElementById("v2SearchResults");
  var topbarInput = document.getElementById("global-search");
  var searchInstance = null;
  var searchOpen = false;
  var searchTimer = 0;
  var searchGen = 0;
  var searchIndex = -1;

  function searchBerry() {
    var select = document.getElementById("v2-berry");
    return select && select.value ? select.value : "global";
  }
  function ensureSearch() {
    if (!searchEl || !window.bootstrap) return null;
    if (!searchInstance) {
      searchInstance = window.bootstrap.Offcanvas.getOrCreateInstance(searchEl, { backdrop: true, keyboard: false });
      searchEl.addEventListener("shown.bs.offcanvas", function () {
        searchOpen = true;
        if (searchInput) searchInput.focus();
      });
      searchEl.addEventListener("hidden.bs.offcanvas", function () {
        searchOpen = false;
        searchIndex = -1;
        if (topbarInput) topbarInput.blur();
      });
    }
    return searchInstance;
  }
  function openSearch(initial) {
    var instance = ensureSearch();
    if (!instance) {
      window.location.href = "/search" + (initial ? "?q=" + encodeURIComponent(initial) : "");
      return;
    }
    if (searchInput && typeof initial === "string") searchInput.value = initial;
    instance.show();
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
      if (searchInput.value.trim()) runSearch(searchInput.value.trim());
    }
  }
  function closeSearch() {
    if (searchInstance) searchInstance.hide();
  }
  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }
  function resultRow(row) {
    var extra = row.matched_label ? '<span class="v2-search-alias">' + escapeHtml(row.matched_label) + "</span>" : "";
    var sub = row.subtitle ? '<span class="v2-search-sub">' + escapeHtml(row.subtitle) + "</span>" : "";
    var reader = row.open_reader ? ' data-open-reader data-item-id="' + escapeHtml(row.item_id || row.id) + '"' : "";
    return (
      '<li><a href="' + escapeHtml(row.href) + '"' + reader + ">" +
      '<span class="v2-search-title">' + escapeHtml(row.title) + "</span>" +
      '<span class="v2-search-state v2-search-state-' + escapeHtml(row.state) + '">' + escapeHtml(row.state_label) + "</span>" +
      extra + sub +
      "</a></li>"
    );
  }
  function renderSearch(payload) {
    if (!searchResults || !searchStatus) return;
    searchIndex = -1;
    if (!payload || !payload.q) {
      searchStatus.textContent = "Type to search across objects.";
      searchResults.innerHTML = "";
      return;
    }
    if (payload.empty) {
      searchStatus.textContent = "No objects matched “" + payload.q + "”. This is name/title/alias navigation, not Q&A.";
      searchResults.innerHTML = "";
      return;
    }
    var html = "";
    if (payload.ambiguous) {
      html += '<p class="banner banner-warning">More than one canonical object matches. Nothing was auto-selected.</p>';
    }
    (payload.groups || []).forEach(function (group) {
      html += '<section class="v2-search-group" data-search-group="' + escapeHtml(group.id) + '"><h2>' + escapeHtml(group.label) + "</h2>";
      if (group.in_context && group.in_context.length) {
        html += '<ul class="v2-search-list">' + group.in_context.map(resultRow).join("") + "</ul>";
      }
      if (group.also_global && group.also_global.length) {
        html += '<h3 class="v2-search-global-label">Also in Global</h3>';
        html += '<ul class="v2-search-list v2-search-list-global">' + group.also_global.map(resultRow).join("") + "</ul>";
      }
      html += "</section>";
    });
    searchStatus.textContent = payload.result_count + " grouped result" + (payload.result_count === 1 ? "" : "s") +
      (payload.elapsed_ms != null ? " · " + payload.elapsed_ms + " ms" : "");
    searchResults.innerHTML = html;
    searchResults.querySelectorAll("[data-open-reader]").forEach(bindStandaloneReaderLink);
  }
  function runSearch(term) {
    var gen = ++searchGen;
    if (!term) {
      renderSearch({ q: "", empty: true });
      return;
    }
    if (searchStatus) searchStatus.textContent = "Searching…";
    var params = new URLSearchParams({
      q: term,
      berry: searchBerry(),
      include_global: "1",
      include_private: "1",
      limit: "8"
    });
    fetch("/api/search/global?" + params.toString(), { credentials: "same-origin" })
      .then(function (res) { if (!res.ok) throw new Error("search failed"); return res.json(); })
      .then(function (payload) { if (gen === searchGen) renderSearch(payload); })
      .catch(function () {
        if (gen !== searchGen) return;
        if (searchStatus) searchStatus.textContent = "Search is unavailable. Open the full search page.";
      });
  }
  function searchLinks() {
    return searchResults ? Array.prototype.slice.call(searchResults.querySelectorAll("a")) : [];
  }
  function highlightSearch(index) {
    var links = searchLinks();
    if (!links.length) { searchIndex = -1; return; }
    searchIndex = Math.max(0, Math.min(links.length - 1, index));
    links.forEach(function (link, i) { link.classList.toggle("is-current", i === searchIndex); });
    links[searchIndex].scrollIntoView({ block: "nearest" });
  }
  function debounceSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () {
      if (searchInput) runSearch(searchInput.value.trim());
    }, 160);
  }
  if (searchInput) {
    searchInput.addEventListener("input", debounceSearch);
    searchInput.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        highlightSearch(searchIndex + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        highlightSearch(searchIndex <= 0 ? 0 : searchIndex - 1);
      } else if (event.key === "Enter") {
        var links = searchLinks();
        if (searchIndex >= 0 && links[searchIndex]) {
          event.preventDefault();
          links[searchIndex].click();
        }
      } else if (event.key === "Escape") {
        event.preventDefault();
        closeSearch();
      }
    });
  }
  if (topbarInput) {
    topbarInput.addEventListener("focus", function () { openSearch(topbarInput.value); });
    topbarInput.addEventListener("click", function () { openSearch(topbarInput.value); });
  }
  var topbarForm = document.getElementById("v2TopbarSearch");
  if (topbarForm) {
    topbarForm.addEventListener("submit", function (event) {
      if (!searchEl) return;
      event.preventDefault();
      openSearch(topbarInput ? topbarInput.value : "");
    });
  }

  document.addEventListener("keydown", function (event) {
    if (inFormField(event.target) && event.target !== topbarInput) {
      if (searchOpen && event.key === "Escape") {
        event.preventDefault();
        closeSearch();
      }
      return;
    }
    var key = event.key;
    var openShortcut = (key === "k" || key === "K") && (event.metaKey || event.ctrlKey);
    var slash = key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey;
    if (openShortcut || slash) {
      event.preventDefault();
      openSearch(searchInput ? searchInput.value : "");
      return;
    }
    if (event.key === "Escape" && searchOpen) {
      event.preventDefault();
      closeSearch();
      return;
    }
    if (event.key === "Escape" && overlayOpen) {
      event.preventDefault();
      closeOverlay();
      return;
    }
    if (searchOpen) return;
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
