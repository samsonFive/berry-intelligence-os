// Keep candidate navigation below the actual shell height, including wrapped mobile nav.
(() => {
  const bar = document.querySelector('[data-candidate-quick-nav]');
  if (!bar) return;
  const workspace = bar.closest('.candidate-workspace');
  const header = document.querySelector('.glass-header');
  const picker = bar.querySelector('[data-candidate-letter-picker]');
  if (picker) {
    picker.addEventListener('change', () => { window.location.assign(picker.value); });
    bar.dataset.enhanced = 'true';
  }
  function measure() {
    const headerHeight = Math.ceil(header?.getBoundingClientRect().height || 0);
    workspace.style.setProperty('--candidate-header-height', `${headerHeight}px`);
    workspace.style.setProperty('--candidate-scroll-offset', `${headerHeight + Math.ceil(bar.getBoundingClientRect().height) + 16}px`);
  }
  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(measure);
    if (header) observer.observe(header);
    observer.observe(bar);
  }
  window.addEventListener('resize', measure);
  measure();
})();

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
