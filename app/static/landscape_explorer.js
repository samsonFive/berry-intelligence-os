(() => {
  const root = document.querySelector('[data-landscape-explorer]');
  if (!root) return;
  const readyStart = performance.now();
  const bundle = JSON.parse(document.getElementById('landscape-bundle').textContent);
  const sources = new Map(bundle.sources.map(row => [row.id, row]));
  const edges = new Map(bundle.edges.map(row => [row.id, row]));
  const content = root.querySelector('[data-evidence-content]');
  const panel = root.querySelector('.lx-evidence');
  const el = (tag, text, className) => { const node = document.createElement(tag); if (text) node.textContent = text; if (className) node.className = className; return node; };
  function syncLinks() {
    root.querySelectorAll('a[href*="/landscapes/explorer?"]').forEach(a => {
      if (a.dataset.focus || a.dataset.resetFocus !== undefined) return;
      const url = new URL(a.href); url.searchParams.set('focus', bundle.filters.focus || ''); url.searchParams.set('edge', bundle.filters.edge || ''); a.href = url.pathname + url.search;
    });
    root.querySelectorAll('a[href*="/landscapes/explorer/export/"], a[href*="/landscapes/explorer/briefing?"]').forEach(a => {
      const url = new URL(a.href); url.searchParams.set('focus', bundle.filters.focus || ''); url.searchParams.set('edge', bundle.filters.edge || ''); a.href = url.pathname + url.search;
    });
  }
  function setURL(key, value) { const url = new URL(location.href); url.searchParams.set(key, value); history.replaceState(null, '', url); bundle.filters[key] = value; syncLinks(); }
  function sourceLink(source) { if (!source.url) return el('small', 'Original URL not recorded.'); const a = el('a', 'Read original source ↗'); a.href = source.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; }
  function selectEdge(id, focusPanel = true) {
    const edge = edges.get(id); if (!edge) return;
    panel.hidden = false; root.setAttribute('data-evidence-open', '');
    setURL('edge', id);
    root.querySelectorAll('[data-relationship]').forEach(row => row.classList.toggle('is-selected', row.dataset.relationship === id));
    content.replaceChildren(el('h3', edge.label), el('span', edge.status_label, 'lx-status ' + edge.status));
    if (edge.caveat) content.append(el('p', edge.caveat, 'lx-lead'));
    content.append(el('p', edge.review, 'lx-muted'));
    [edge.subject_id, edge.object_id].forEach(key => { if (bundle.nodes[key].identity_note) content.append(el('p', `${bundle.nodes[key].label}: ${bundle.nodes[key].identity_note}`, 'lx-muted')); });
    const dates = el('dl');
    [['Effective', edge.effective || 'Not recorded'], ['Published', edge.published.join(' · ') || 'Not recorded'], ['First captured', edge.first_seen || 'Not recorded']].forEach(([key, value]) => dates.append(el('dt', key), el('dd', value)));
    const dateDetails = el('details'); dateDetails.append(el('summary', 'Dates & connection details'), el('p', edge.scope_kind), dates); content.append(dateDetails, el('h4', 'Supporting sources'));
    edge.evidence_ids.forEach(sid => {
      const source = sources.get(sid); const article = el('article');
      article.append(el('h4', source.title), el('small', `Source ${source.number} · ${source.review}`), el('p', source.summary, 'lx-source-summary'), sourceLink(source));
      if (source.varieties?.length) {
        const names = el('section', null, 'lx-source-varieties'); names.append(el('h4', 'Varieties named in this source'));
        const chips = el('div', null, 'lx-variety-chips');
        source.varieties.forEach(row => { const a = el('a', row.name + (row.catalog_id ? '' : ' · review')); a.href = row.href; a.title = row.label; if (!row.catalog_id) a.className = 'provisional'; chips.append(a); });
        names.append(chips, el('small', 'Catalog links and names awaiting identity review. A mention does not approve breeder, owner or growing-region claims.')); article.append(names);
      }
      if (source.significance) { const why = el('details'); why.append(el('summary', 'Why this source was flagged'), el('p', source.significance)); article.append(why); }
      const details = el('details'); details.append(el('summary', 'Source details & locator'), el('p', source.locator), el('small', `Published: ${source.published || 'unknown'} · Captured: ${source.captured || 'unknown'}`), el('small', `Origin: ${source.origin}`), el('small', source.id)); article.append(details); content.append(article);
    });
    const provenance = el('details'); provenance.append(el('summary', 'Relationship notes & registry reference'), el('p', edge.notes), el('small', edge.id), el('small', `Stored confidence: ${edge.confidence}. Source review is separate from claim verification.`)); content.append(provenance);
    if (focusPanel) { panel.focus({preventScroll:true}); if (matchMedia('(max-width:760px)').matches) panel.scrollIntoView({behavior:'smooth', block:'start'}); }
  }
  function selectFocus(id, showAll = false) {
    const node = bundle.nodes[id]; if (!node || node.type === 'geography') return;
    const start = performance.now();
    setURL('focus', id);
    root.querySelector('[name=focus]').value = id;
    const related = bundle.edges.filter(edge => edge.subject_id === id || edge.object_id === id);
    if (bundle.filters.edge && !related.some(edge => edge.id === bundle.filters.edge)) root.querySelector('[data-clear-edge]').click();
    const neighbors = new Set([id, ...related.flatMap(edge => [edge.subject_id, edge.object_id])]);
    root.querySelectorAll('[data-node]').forEach(card => { card.classList.toggle('is-focused', card.dataset.node === id); card.classList.toggle('is-neighbor', neighbors.has(card.dataset.node)); });
    root.querySelectorAll('[data-focus]').forEach(a => { if (a.dataset.focus === id) a.setAttribute('aria-current','true'); else a.removeAttribute('aria-current'); });
    root.querySelectorAll('[data-relationship]').forEach(row => row.classList.toggle('is-neighbor', row.dataset.subject === id || row.dataset.object === id));
    const section = root.querySelector('.lx-focus'); section.hidden = bundle.filters.view === 'explain';
    root.querySelector('[data-focus-title]').textContent = node.label;
    const diagram = root.querySelector('[data-focus-diagram]'); diagram.replaceChildren();
    related.slice(0, showAll ? related.length : 6).forEach(edge => {
      const row = el('div', null, 'lx-connection');
      [edge.subject_id, edge.object_id].forEach((key, index) => {
        if (index) { const button = el('button', edge.role + ' →', 'lx-edge'); button.type = 'button'; button.dataset.edge = edge.id; button.append(el('small', edge.status_label)); if (edge.caveat) button.append(el('small', edge.caveat)); row.append(button); }
        if (bundle.nodes[key].type === 'geography') { row.append(el('span', bundle.nodes[key].label)); return; }
        const a = el('a', bundle.nodes[key].label); const url = new URL(location.href); url.searchParams.set('focus', key); url.searchParams.set('edge', ''); a.href = url.pathname + url.search; a.dataset.focus = key; row.append(a);
      }); diagram.append(row);
    });
    if (!showAll && related.length > 6) { const more = el('button', `Show all ${related.length} connections · ${related.length - 6} more`, 'lx-edge'); more.type = 'button'; more.dataset.expandFocus = id; diagram.append(more); }
    if (!related.length) diagram.append(el('p', 'No connections match this focus. Try another scope.'));
    const resetURL = new URL(location.href); resetURL.searchParams.set('focus',''); resetURL.searchParams.set('edge',''); root.querySelector('[data-reset-focus]').href = resetURL.pathname + resetURL.search;
    root.dataset.highlightMs = (performance.now() - start).toFixed(2);
  }
  root.addEventListener('click', event => {
    const expand = event.target.closest('[data-expand-focus]'); if (expand) { selectFocus(expand.dataset.expandFocus, true); return; }
    const edgeButton = event.target.closest('[data-edge]'); if (edgeButton) { selectEdge(edgeButton.dataset.edge); return; }
    const focusLink = event.target.closest('[data-focus]'); if (focusLink && !event.ctrlKey && !event.metaKey && bundle.filters.view !== 'explain') { event.preventDefault(); selectFocus(focusLink.dataset.focus); root.querySelector('.lx-focus').scrollIntoView({behavior:'smooth', block:'nearest'}); return; }
    const source = event.target.closest('[data-source-link]'); if (source) { const details = root.querySelector('.lx-source-index'); details.open = true; }
    if (event.target.closest('[data-clear-edge]')) { setURL('edge', ''); panel.hidden = true; root.removeAttribute('data-evidence-open'); content.replaceChildren(el('p', 'Select a connection to inspect its sources.', 'lx-lead')); root.querySelectorAll('.is-selected').forEach(row => row.classList.remove('is-selected')); }
  });
  root.addEventListener('keydown', event => { if (event.key === 'Escape') root.querySelector('[data-clear-edge]').click(); });
  const windowControl = root.querySelector('[name=window]');
  function customDates() { root.querySelectorAll('[data-custom-date]').forEach(label => { label.hidden = windowControl.value !== 'custom'; }); }
  windowControl.addEventListener('change', customDates); customDates();
  // Restore both explicit URL selections. A subsequent focus change may still
  // close unrelated evidence, but loading a shared view must not discard it.
  const initialEdge = bundle.filters.edge;
  if (bundle.filters.focus) selectFocus(bundle.filters.focus);
  if (initialEdge) selectEdge(initialEdge, false);
  root.dataset.readyMs = (performance.now() - readyStart).toFixed(2);
})();
