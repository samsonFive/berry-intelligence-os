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
// Inspect padded source assets without changing the source or its reuse status.
function preparePhotoZoom(frame, img) {
  const controls = frame.closest?.('figure')?.querySelector('[data-photo-zoom]');
  if (!controls) return;
  const input = controls.querySelector('input');
  const output = controls.querySelector('output');
  if (!input || !output) return;
  controls.hidden = true;
  input.value = '1';
  output.textContent = '1×';
  input.oninput = () => {
    const value = Number(input.value);
    const zoom = Number.isFinite(value) ? Math.min(5, Math.max(1, value)) : 1;
    img.style.transform = `scale(${zoom})`;
    output.textContent = `${zoom}×`;
  };
  const ready = () => { controls.hidden = !img.naturalWidth; };
  img.addEventListener('load', ready);
  img.addEventListener('error', () => { controls.hidden = true; });
  if (img.complete) ready();
}
// Retain attribution and the original-source link when an image cannot load.
(() => {
  document.querySelectorAll('[data-variety-photo]').forEach(frame => {
    const img = frame.querySelector('img');
    const fallback = frame.querySelector('span');
    if (!img || !fallback) return;
    preparePhotoZoom(frame, img);
    function unavailable() { img.hidden = true; fallback.hidden = false; }
    img.addEventListener('error', unavailable);
    if (img.complete && !img.naturalWidth) unavailable();
  });
})();

// An explicit private-view choice: retain it only for this tab's session.
// No request goes to the app and no saved reuse/publication status changes.
(() => {
  document.querySelectorAll('[data-photo-session]').forEach(container => {
    const button = container.querySelector('[data-photo-session-toggle]');
    const frame = container.querySelector('[data-photo-session-frame]');
    const status = container.querySelector('[data-photo-session-status]');
    if (!button || !frame || !status) return;
    const key = 'bios:variety-photo-session:v1:' + JSON.stringify([
      container.dataset.sourceUrl, container.dataset.imageUrl
    ]);
    let accepted = false;
    let remembered = true;
    try { accepted = window.sessionStorage.getItem(key) === 'show'; }
    catch (_) { remembered = false; }
    function render() {
      const zoom = container.closest('figure')?.querySelector('[data-photo-zoom]');
      if (zoom) zoom.hidden = true;
      frame.querySelector('img')?.remove();
      const fallback = frame.querySelector('span');
      if (fallback) fallback.hidden = true;
      frame.hidden = !accepted;
      button.textContent = accepted ? 'Hide photo' : 'Ignore permission';
      button.setAttribute('aria-pressed', String(accepted));
      status.textContent = accepted
        ? `${remembered ? 'Session preview' : 'Preview in this view'} · Permission unconfirmed`
        : 'Permission unconfirmed · source link available';
      if (!accepted) return;
      const img = document.createElement('img');
      img.alt = container.dataset.caption;
      img.loading = 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.width = 320;
      img.height = 200;
      img.addEventListener('error', () => {
        img.hidden = true;
        if (fallback) fallback.hidden = false;
      });
      frame.prepend(img);
      preparePhotoZoom(frame, img);
      img.src = container.dataset.imageUrl;
    }
    button.addEventListener('click', () => {
      accepted = !accepted;
      try {
        if (accepted) window.sessionStorage.setItem(key, 'show');
        else window.sessionStorage.removeItem(key);
      } catch (_) { remembered = false; }
      render();
      if (accepted) container.closest('figure')?.scrollIntoView({block: 'nearest', inline: 'start', behavior: 'auto'});
    });
    button.hidden = false;
    render();
  });
})();
