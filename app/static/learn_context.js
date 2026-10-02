(function () {
  "use strict";
  var selected = "", panel = document.createElement("div"), sample = document.createElement("span");
  panel.className = "learn-context-selection"; panel.hidden = true;
  panel.setAttribute("role", "group"); panel.setAttribute("aria-label", "Selected text learning actions");
  var action = document.createElement("button"); action.type = "button"; action.textContent = "Research & add to Learn";
  var dismiss = document.createElement("button"); dismiss.type = "button"; dismiss.textContent = "×"; dismiss.setAttribute("aria-label", "Dismiss learning action");
  panel.append(sample, action, dismiss); document.body.append(panel);
  function selection() {
    var choice = window.getSelection(), anchor = choice && choice.anchorNode, element = anchor && (anchor.nodeType === 1 ? anchor : anchor.parentElement);
    // Input fields and private editing forms are deliberately excluded.
    if (!element || !element.closest("#digest-main, #v2ReaderBody") || element.closest("input, textarea, select, form, pre, .learn-provenance")) return "";
    return String(choice).trim().slice(0, 2000);
  }
  function rememberOrigin(reader) {
    try {
      sessionStorage.setItem("bios:learn-return", JSON.stringify({path: location.pathname + location.search + location.hash,
        story: reader ? reader.dataset.itemId : "", readerScroll: reader ? (reader.closest(".offcanvas-body") || document.scrollingElement).scrollTop : 0,
        mode: reader && reader.querySelector("[data-personal-mode][aria-pressed='true']") ? reader.querySelector("[data-personal-mode][aria-pressed='true']").dataset.personalMode : "article",
        pageScroll: window.scrollY}));
    } catch (_) {}
  }
  function openTopic(text) {
    var reader = document.querySelector("[data-personal-reader]"), title = reader && reader.querySelector(".v2-reader-title");
    var heading = document.querySelector("#digest-main h1");
    var topic = text || (title && title.textContent.trim()) || (heading && heading.textContent.trim()) || "Berry learning topic";
    rememberOrigin(reader);
    var origin = location.pathname + location.search + location.hash, query = new URLSearchParams({topic: topic.slice(0, 220), excerpt: text, return_to: origin});
    var scope = new URLSearchParams(location.search), berry = scope.get("berry"), country = scope.get("countries");
    if (berry && berry.indexOf(",") < 0) query.set("berry", berry);
    if (country && country.indexOf(",") < 0) query.set("geography", country);
    location.assign("/learn/research/new?" + query.toString());
  }
  function showSelection() {
    selected = selection(); panel.hidden = !selected; sample.textContent = selected;
    var choice = window.getSelection(), anchor = choice && choice.anchorNode;
    var element = anchor && (anchor.nodeType === 1 ? anchor : anchor.parentElement);
    var modal = element && element.closest(".offcanvas.show");
    (modal || document.body).append(panel);
  }
  document.addEventListener("mouseup", function (event) { if (!panel.contains(event.target)) showSelection(); });
  document.addEventListener("selectionchange", function () { if (selection()) showSelection(); });
  document.addEventListener("keyup", function (event) { if (event.key === "Escape") {panel.hidden = true; return;} if (event.key.indexOf("Arrow") === 0 || event.key === "Shift") showSelection(); });
  action.addEventListener("click", function () { if (selected) openTopic(selected); });
  dismiss.addEventListener("click", function () { panel.hidden = true; });
  document.addEventListener("click", function (event) { if (event.target.closest("[data-learn-reader-topic]")) openTopic(selection()); });
  // Existing Reader hydration owns opening and persistent article position.
  // This local hint only restores the exact return page; it does not send text.
  var hint;
  try { hint = JSON.parse(sessionStorage.getItem("bios:learn-return") || "null"); } catch (_) {}
  if (hint && hint.path === location.pathname + location.search + location.hash && !location.pathname.startsWith("/learn")) {
    window.scrollTo(0, hint.pageScroll || 0);
    var restoreReader = function () {
      var reader = document.querySelector("[data-personal-reader]");
      if (!reader || reader.dataset.itemId !== hint.story) return;
      var mode = reader.querySelector("[data-personal-mode='" + (hint.mode === "brief" ? "brief" : "article") + "']");
      if (mode) mode.click();
      var scroll = reader.closest(".offcanvas-body") || document.scrollingElement;
      scroll.scrollTop = hint.readerScroll || 0;
      // Images may not have their final height when the Reader is hydrated.
      // Restore once they settle, unless the user has already resumed reading.
      var cancelled = false, finished = false, timer;
      function cancel() { cancelled = true; finish(); }
      function finish() {
        if (finished) return;
        finished = true; clearTimeout(timer);
        ["wheel", "touchstart", "keydown"].forEach(function (name) { scroll.removeEventListener(name, cancel); });
        if (!cancelled && reader.isConnected) scroll.scrollTop = hint.readerScroll || 0;
      }
      ["wheel", "touchstart", "keydown"].forEach(function (name) { scroll.addEventListener(name, cancel, {passive: true}); });
      var images = Array.from(reader.querySelectorAll("img")).filter(function (img) { return !img.complete; });
      timer = setTimeout(finish, 2000);
      Promise.all(images.map(function (img) { return new Promise(function (resolve) {
        img.addEventListener("load", resolve, {once: true}); img.addEventListener("error", resolve, {once: true});
      }); })).then(function () { requestAnimationFrame(finish); });
      sessionStorage.removeItem("bios:learn-return"); document.removeEventListener("bios:reader-loaded", restoreReader);
    };
    document.addEventListener("bios:reader-loaded", restoreReader);
    restoreReader();
  }
})();
