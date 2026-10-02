(function () {
  "use strict";
  document.querySelectorAll(".guide-jump a").forEach(function (link) {
    link.addEventListener("click", function (event) {
      var target = document.querySelector(link.getAttribute("href"));
      if (!target || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (location.hash !== link.hash) history.pushState(null, "", link.hash);
      target.focus({preventScroll: true});
      target.scrollIntoView({block: "start", behavior: "instant"});
    });
  });
})();
