(function () {
  'use strict';
  function fallback(image) {
    if (!image.matches('[data-publisher-image]')) return;
    var figure = image.closest('[data-article-visual]');
    if (!figure) return;
    var panel = figure.querySelector('[data-image-fallback]');
    var replacement = panel.querySelector('img');
    replacement.src = replacement.dataset.fallbackSrc;
    panel.hidden = false;
    image.hidden = true;
  }
  // Capture errors for both the initial grid and the dynamically inserted Reader.
  document.addEventListener('error', function (event) {
    if (event.target instanceof HTMLImageElement) fallback(event.target);
  }, true);
  function check(node) {
    if (!node.querySelectorAll) return;
    node.querySelectorAll('[data-publisher-image]').forEach(function (image) {
      if (image.complete && image.naturalWidth === 0) fallback(image);
    });
  }
  check(document);
  new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) { mutation.addedNodes.forEach(check); });
  }).observe(document.body, {childList: true, subtree: true});
})();
