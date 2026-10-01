// Expand only the section requested by a link; plain disclosures work without JS.
(() => {
  function reveal() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return; }
    if (!id) return;
    const target = document.getElementById(id);
    if (!target) return;
    const child = target.querySelector(':scope > details.variety-section');
    if (child) child.open = true;
    let node = target;
    while (node) {
      if (node.tagName === 'DETAILS') node.open = true;
      node = node.parentElement;
    }
    if (target.classList.contains('variety-candidate')) {
      const summary = target.querySelector('summary');
      summary?.focus({ preventScroll: true });
    }
    target.scrollIntoView({ block: 'start' });
  }
  window.addEventListener('hashchange', reveal);
  reveal();
})();
