// Keep the source inventory dense; fetch only the details a reader opens.
(() => {
  const loaders = new Map();
  document.querySelectorAll('details[data-portfolio-source]').forEach(details => {
    const panel = details.querySelector('[data-portfolio-source-panel]');
    const link = panel?.querySelector('[data-portfolio-source-link]');
    if (!panel || !link) return;
    let pending = false;
    let loaded = false;
    async function load() {
      if (pending || loaded) return;
      pending = true;
      panel.setAttribute('aria-busy', 'true');
      const status = document.createElement('p');
      status.setAttribute('role', 'status');
      status.textContent = 'Loading source details…';
      panel.replaceChildren(status, link);
      try {
        const endpoint = new URL(link.href, window.location.href);
        if (endpoint.origin !== window.location.origin) throw Error('Unexpected source destination');
        endpoint.searchParams.set('fragment', '1');
        const response = await fetch(endpoint.href, {
          credentials: 'same-origin', cache: 'no-store', redirect: 'error',
          headers: {'Accept': 'text/html'},
        });
        if (!response.ok || response.headers.get('X-Berry-Portfolio-Fragment') !== '1') {
          throw Error('Source details unavailable');
        }
        const destination = new URL(response.url);
        if (destination.origin !== endpoint.origin || destination.pathname !== endpoint.pathname) {
          throw Error('Source destination changed');
        }
        const template = document.createElement('template');
        template.innerHTML = await response.text();
        const body = template.content.querySelector('[data-portfolio-source-content]');
        if (!body || template.content.children.length !== 1) throw Error('Incomplete source details');
        panel.replaceChildren(body);
        loaded = true;
      } catch (_error) {
        status.textContent = 'Source details could not load. Try again, or open the source check page.';
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'v2-btn v2-btn-quiet';
        retry.textContent = 'Try again';
        retry.addEventListener('click', load);
        panel.replaceChildren(status, retry, link);
      } finally {
        pending = false;
        panel.setAttribute('aria-busy', 'false');
      }
    }
    loaders.set(details, load);
    details.addEventListener('toggle', () => { if (details.open) load(); });
    if (details.open) load();
  });
  function openHash() {
    let id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); } catch (_error) { return; }
    if (!id.startsWith('portfolio-source-')) return;
    const row = document.getElementById(id);
    const details = row?.querySelector('details[data-portfolio-source]');
    const load = loaders.get(details);
    if (load) { details.open = true; load(); }
  }
  window.addEventListener('hashchange', openHash);
  window.addEventListener('pageshow', openHash);
  openHash();
})();
