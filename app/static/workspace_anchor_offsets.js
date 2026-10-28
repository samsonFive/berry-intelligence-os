// Section jumps clear the actual shared header, including wrapped/zoomed navigation.
(() => {
  const header = document.querySelector('.glass-header');
  if (!header) return;
  function measure() {
    const value = `${Math.ceil(header.getBoundingClientRect().height) + 16}px`;
    const style = document.documentElement.style;
    if (style.getPropertyValue('--glass-anchor-offset') !== value) {
      style.setProperty('--glass-anchor-offset', value);
    }
  }
  measure();
  if ('ResizeObserver' in window) new ResizeObserver(measure).observe(header);
  window.addEventListener('resize', measure);
  window.addEventListener('pageshow', measure);
  document.fonts?.ready.then(measure);
})();
