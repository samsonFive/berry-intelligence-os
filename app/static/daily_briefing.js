(function () {
  var root = document.querySelector("[data-briefing-root]");
  if (!root) return;

  var layer = root.querySelector("[data-briefing-reader-layer]");
  var dialog = root.querySelector("#briefing-reader");
  var lastFocus = null;

  function closeHref() {
    var url = new URL(window.location.href);
    url.searchParams.delete("reader");
    return url.pathname + (url.search ? url.search : "") + (url.hash || "");
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
    if (lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus();
    }
  }

  root.addEventListener("click", function (event) {
    var closer = event.target.closest("[data-briefing-reader-close]");
    if (closer) {
      event.preventDefault();
      closeReader();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && layer && !layer.hidden) {
      event.preventDefault();
      closeReader();
    }
  });

  if (layer && root.getAttribute("data-reader-open") === "1" && dialog) {
    lastFocus = document.activeElement;
    layer.hidden = false;
    document.body.classList.add("daily-briefing-reader-open");
    window.setTimeout(function () { dialog.focus(); }, 0);
  }
})();
