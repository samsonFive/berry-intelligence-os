// Measure the real shell so sheet tabs, anchor targets and the alphabet clear it.
(() => {
  const sheet = document.querySelector('.variety-sheet-shell');
  if (!sheet) return;
  const header = document.querySelector('.glass-header');
  const tabs = sheet.querySelector('[aria-label="Variety sections"]');
  function measure() {
    const height = Math.ceil(header?.getBoundingClientRect().height || 0);
    sheet.style.setProperty('--variety-shell-height', `${height}px`);
    sheet.style.setProperty('--variety-section-offset', `${height + Math.ceil(tabs?.getBoundingClientRect().height || 40) + 14}px`);
  }
  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(measure);
    if (header) observer.observe(header);
    if (tabs) observer.observe(tabs);
  }
  window.addEventListener('resize', measure);
  function markSection() {
    tabs?.querySelectorAll('a[href^="#"]').forEach(link => {
      if (link.hash === location.hash && location.hash) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }
  window.addEventListener('hashchange', markSection);
  markSection();
  measure();
})();
