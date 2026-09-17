(function () {
  var root = document.querySelector("[data-briefing-root]");
  if (!root) return;

  var layer = root.querySelector("[data-briefing-reader-layer]");
  var dialog = root.querySelector("#briefing-reader");
  var lastFocus = null;
  var live = null;
  var openerStorageKey = "dailyBriefingReaderOpener";

  function readerOpeners() {
    return Array.prototype.slice.call(
      root.querySelectorAll("[data-briefing-open-reader][data-item-id]")
    );
  }

  function rememberOpener(opener) {
    var openers = readerOpeners();
    var position = openers.indexOf(opener);
    if (position < 0) return;
    try {
      window.sessionStorage.setItem(openerStorageKey, JSON.stringify({
        itemId: opener.getAttribute("data-item-id"),
        position: position
      }));
    } catch (error) {
      // Storage can be disabled; the item-id fallback below still restores focus.
    }
  }

  function storedOpener() {
    var saved = null;
    try {
      saved = JSON.parse(window.sessionStorage.getItem(openerStorageKey) || "null");
    } catch (error) {
      saved = null;
    }
    var openers = readerOpeners();
    if (saved && openers[saved.position] &&
        openers[saved.position].getAttribute("data-item-id") === saved.itemId) {
      return openers[saved.position];
    }
    var readerId = new URL(window.location.href).searchParams.get("reader");
    return openers.find(function (opener) {
      return opener.getAttribute("data-item-id") === readerId;
    }) || null;
  }

  function forgetOpener() {
    try {
      window.sessionStorage.removeItem(openerStorageKey);
    } catch (error) {
      // Storage can be disabled without affecting reader behavior.
    }
  }

  function ensureLive() {
    if (live) return live;
    live = document.getElementById("daily-briefing-live");
    if (!live) {
      live = document.createElement("div");
      live.id = "daily-briefing-live";
      live.className = "visually-hidden";
      live.setAttribute("aria-live", "polite");
      live.setAttribute("aria-atomic", "true");
      root.appendChild(live);
    }
    return live;
  }

  function announce(msg) {
    var region = ensureLive();
    region.textContent = "";
    window.setTimeout(function () { region.textContent = msg; }, 0);
  }

  function closeHref() {
    var url = new URL(window.location.href);
    url.searchParams.delete("reader");
    return url.pathname + (url.search ? url.search : "") + (url.hash || "");
  }

  function focusableIn(container) {
    if (!container) return [];
    return Array.prototype.slice.call(
      container.querySelectorAll(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
      )
    ).filter(function (el) {
      return !el.hasAttribute("disabled") && el.getAttribute("aria-hidden") !== "true";
    });
  }

  function closeReader() {
    if (!layer) {
      window.location.href = closeHref();
      return;
    }
    layer.hidden = true;
    document.body.classList.remove("daily-briefing-reader-open");
    if (window.history && window.history.replaceState) {
      window.history.replaceState({}, "", closeHref());
    }
    announce("Reader closed. Feed filters preserved.");
    if (lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus();
    }
    forgetOpener();
  }

  function openReaderEffects() {
    if (!layer || !dialog) return;
    lastFocus = storedOpener() || document.activeElement;
    layer.hidden = false;
    document.body.classList.add("daily-briefing-reader-open");
    window.setTimeout(function () {
      var closeBtn = dialog.querySelector("[data-briefing-reader-close]");
      if (closeBtn) closeBtn.focus();
      else dialog.focus();
      announce("In-app reader opened.");
    }, 0);
  }

  root.addEventListener("click", function (event) {
    var opener = event.target.closest("[data-briefing-open-reader][data-item-id]");
    if (opener) rememberOpener(opener);
    var closer = event.target.closest("[data-briefing-reader-close]");
    if (closer) {
      event.preventDefault();
      closeReader();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (!layer || layer.hidden) return;

    if (event.key === "Escape") {
      event.preventDefault();
      closeReader();
      return;
    }

    if (event.key !== "Tab" || !dialog) return;
    var nodes = focusableIn(dialog);
    if (!nodes.length) return;
    var first = nodes[0];
    var last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  if (layer && root.getAttribute("data-reader-open") === "1" && dialog) {
    openReaderEffects();
  }
})();
