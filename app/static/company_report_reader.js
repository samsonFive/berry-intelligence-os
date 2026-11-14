(() => {
  const root = document.querySelector('[data-company-report-reader]');
  if (!root) return;
  const input = root.querySelector('[data-reader-company-search]');
  const links = Array.from(root.querySelectorAll('[data-reader-company]'));
  const rows = Array.from(root.querySelectorAll('[data-reader-guide-company]'));
  const normalize = value => value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().trim();
  if (input) {
    input.addEventListener('input', () => {
      const query = normalize(input.value);
      let count = 0;
      links.forEach(link => {
        const matched = normalize(link.dataset.readerCompany || '').includes(query);
        link.hidden = !matched;
        if (matched) count += 1;
      });
      rows.forEach(row => { row.hidden = !normalize(row.dataset.readerGuideCompany || '').includes(query); });
      const output = root.querySelector('[data-reader-company-count]');
      if (output) output.textContent = query ? `${count} matching ${count === 1 ? 'company' : 'companies'}` : `${links.length} companies`;
      root.querySelectorAll('[data-reader-no-company], [data-reader-no-guide]').forEach(node => { node.hidden = count !== 0; });
    });
  }
  const jump = root.querySelector('[data-reader-jump]');
  if (jump) jump.classList.add('reader-auto-jump');
  if (jump) jump.querySelector('select')?.addEventListener('change', event => {
    const target = new URL(jump.action, window.location.href);
    target.hash = event.target.value ? 'company-reading' : 'report-reading';
    jump.action = target.href;
    jump.requestSubmit();
  });
  const active = root.querySelector('.reader-company-link[aria-current="page"]');
  if (active) {
    const rail = root.querySelector('.reader-company-links');
    if (rail && rail.scrollHeight > rail.clientHeight) rail.scrollTop = Math.max(0, active.offsetTop - rail.offsetTop - rail.clientHeight / 2);
  }
})();
