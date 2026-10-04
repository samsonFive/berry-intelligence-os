(function () {
  "use strict";
  var form = document.querySelector("[data-fidelity-form]");
  if (!form) return;
  document.addEventListener("keydown", function (event) {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || event.repeat) return;
    if (document.querySelector(".offcanvas.show, .offcanvas.showing")) return;
    if (event.target.closest("input, textarea, select, button, a, summary, [contenteditable=true], [role=button]")) return;
    var selectors = {n: "[data-fidelity-next]", p: "[data-fidelity-prev]", a: "[data-fidelity-affirm]", r: "[data-fidelity-reject]", i: "[data-fidelity-investigate]"};
    var selector = selectors[event.key.toLowerCase()];
    var target = selector && document.querySelector(selector);
    if (target) { event.preventDefault(); target.click(); }
  });
})();
