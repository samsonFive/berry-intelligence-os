(function () {
  "use strict";
  var selectors = Array.from(document.querySelectorAll(".scope-selector"));
  document.addEventListener("click", function (event) {
    selectors.forEach(function (details) { if (!details.contains(event.target)) details.open = false; });
  });
  document.addEventListener("focusin", function (event) {
    selectors.forEach(function (details) { if (!details.contains(event.target)) details.open = false; });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    var open = selectors.find(function (details) { return details.open; });
    if (open) { open.open = false; open.querySelector("summary").focus(); event.preventDefault(); }
  });
  selectors.forEach(function (details) {
    details.addEventListener("toggle", function () {
      if (!details.open) return;
      selectors.forEach(function (other) { if (other !== details) other.open = false; });
      var panel = details.querySelector("fieldset");
      panel.style.transform = "";
      var bounds = panel.getBoundingClientRect(), width = document.documentElement.clientWidth;
      var shift = bounds.right > width - 12 ? width - 12 - bounds.right : bounds.left < 12 ? 12 - bounds.left : 0;
      if (shift) panel.style.transform = "translateX(" + shift + "px)";
    });
  });
})();
