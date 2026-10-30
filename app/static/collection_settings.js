(() => {
  const root = document.getElementById('collection-workspace');
  if (!root) return;
  const search = root.querySelector('#collection-filter');
  const removed = root.querySelector('#show-removed');
  const tabs = [...root.querySelectorAll('[role=tab]')];
  const panels = [...root.querySelectorAll('[data-sheet-panel]')];
  const alphabet = root.querySelector('.collection-alphabet');
  const letters = [...alphabet.querySelectorAll('[data-letter]')];
  const dialog = root.querySelector('#collection-editor');
  let stopPreview = () => {};
  function setupQueryBuilder() {
    stopPreview();
    const builder = dialog.querySelector('[data-query-builder]');
    if (!builder) return;
    const form = builder.closest('form');
    const field = name => form.elements.namedItem(name);
    const status = builder.querySelector('[data-preview-status]');
    const expression = builder.querySelector('[data-preview-expression]');
    const save = form.querySelector('button[value="save"]');
    let timer, controller, generation = 0;
    stopPreview = () => { clearTimeout(timer); controller?.abort(); generation++; };
    async function preview(version) {
      controller = new AbortController();
      try {
        const response = await fetch('/settings/collection/query-preview', {
          method: 'POST', body: new URLSearchParams(new FormData(form)), signal: controller.signal,
          headers: {'Accept': 'application/json'}
        });
        const result = await response.json();
        if (version !== generation) return;
        if (!response.ok) throw new Error(result.error || result.detail || 'Reload the page to preview this search.');
        expression.textContent = result.expression;
        builder.querySelector('[data-destination-help]').textContent = result.help;
        status.textContent = 'This topic, berry and region will be searched together:';
        save.disabled = false;
      } catch (error) {
        if (version !== generation || error.name === 'AbortError') return;
        status.textContent = error.message || 'Preview unavailable. Change a field to retry.';
      }
    }
    function update() {
      clearTimeout(timer); controller?.abort();
      const version = ++generation;
      save.disabled = true; expression.textContent = '';
      const destinationHelp = field('group').selectedOptions?.[0]?.dataset.help;
      if (destinationHelp) builder.querySelector('[data-destination-help]').textContent = destinationHelp;
      const advanced = field('input_mode').value === 'advanced';
      builder.querySelector('[data-simple-help]').hidden = advanced;
      builder.querySelector('[data-advanced-help]').hidden = !advanced;
      status.textContent = field('query_input').value.trim() ? 'Preparing preview…' : 'Enter a topic to preview the search.';
      if (field('query_input').value.trim()) timer = setTimeout(() => preview(version), 250);
    }
    builder.addEventListener('input', update);
    builder.addEventListener('change', update);
    builder.querySelector('[data-query-example]').addEventListener('click', () => {
      field('label').value = 'Floricane developments';
      field('query_input').value = 'Floricane'; field('scope_berry').value = 'blackberry';
      field('scope_region').value = 'global'; field('input_mode').value = 'simple'; field('term_match').value = 'any';
      field('search_language').value = 'automatic';
      update();
    });
    update();
  }
  const add = root.querySelector('#collection-add');
  const dimensions = [...root.querySelectorAll('[data-dimension-filter]')];
  const dimensionBar = root.querySelector('.collection-dimension-filters');
  let active, visible = [], ticking = false, jumpHighlight = null;
  const initial = location.hash.slice(1);
  const records = new Map(panels.map(panel => [panel.id, [...panel.querySelectorAll('[data-entry]')].map(element => {
    const normalized = element.dataset.name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
    const letter = /^[A-Z]/.test(normalized) ? normalized[0] : '#';
    return {element, letter, text: `${element.textContent} ${element.dataset.search || ''}`.toLocaleLowerCase()};
  })]));
  const setLetter = letter => letters.forEach(button => {
    if (button.dataset.letter === letter) button.setAttribute('aria-current', 'true');
    else button.removeAttribute('aria-current');
  });
  function filter() {
    jumpHighlight = null;
    const query = search.value.trim().toLocaleLowerCase();
    visible = [];
    (records.get(active) || []).forEach(row => {
      const matchesColumns = dimensions.every(select => !select.value || select.disabled || (row.element.dataset[select.dataset.dimensionFilter] || '').split('|').includes(select.value));
      row.element.hidden = (!removed.checked && row.element.dataset.removed === 'true') || !row.text.includes(query) || !matchesColumns;
      if (!row.element.hidden) visible.push(row);
    });
    const panel = document.getElementById(active);
    const empty = panel.querySelector('[data-empty]');
    if (empty) empty.hidden = visible.length > 0;
    const count = panel.querySelector('[data-panel-count]');
    if (count) count.textContent = `${visible.length} entries`;
    root.querySelector('#collection-filter-status').textContent = active === 'schedule' ? '' : `${visible.length} shown`;
    const available = new Set(visible.map(row => row.letter));
    letters.forEach(button => { button.disabled = !available.has(button.dataset.letter); });
    setLetter(visible[0]?.letter);
  }
  function selectTab(tab, focus = false) {
    active = tab.getAttribute('aria-controls');
    tabs.forEach(button => { const selected = button === tab; button.setAttribute('aria-selected', String(selected)); button.tabIndex = selected ? 0 : -1; });
    panels.forEach(panel => { panel.hidden = panel.id !== active; });
    const schedule = active === 'schedule';
    search.disabled = schedule; removed.disabled = schedule; alphabet.hidden = schedule;
    dimensionBar.hidden = schedule;
    dimensions.forEach(select => {
      const field = select.dataset.dimensionFilter;
      const applicable = !schedule && (active === 'terms' || !['workflow', 'provider'].includes(field));
      select.disabled = !applicable;
      select.closest('[data-filter-field]').hidden = !applicable;
      const previous = select.value;
      const values = [...new Set((records.get(active) || []).filter(row => removed.checked || row.element.dataset.removed !== 'true').flatMap(row => (row.element.dataset[field] || '').split('|').filter(Boolean)))].sort((a,b) => a.localeCompare(b));
      select.replaceChildren(new Option(`All ${field === 'berry' ? 'berries' : field + 's'}`, ''), ...values.map(value => new Option(value, value)));
      select.value = values.includes(previous) ? previous : '';
    });
    if (add) {
      add.hidden = schedule;
      const kind = active === 'terms' ? 'query' : active === 'feeds' ? 'feed' : 'source';
      add.dataset.openEditor = `add-${kind}`;
      add.dataset.createKind = kind;
      add.textContent = active === 'terms' ? '+ Add keyword monitor' : active === 'feeds' ? '+ Add feed' : '+ Add source';
    }
    filter();
    if (focus) tab.focus();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectTab(tab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) { event.preventDefault(); selectTab(tabs[next], true); }
    });
  });
  root.addEventListener('click', event => {
    const opener = event.target.closest('[data-open-editor]');
    if (!opener) return;
    const template = document.getElementById(opener.dataset.openEditor);
    if (!template) return;
    root.querySelectorAll('.is-current').forEach(row => row.classList.remove('is-current'));
    opener.closest('[data-entry]')?.classList.add('is-current');
    dialog.replaceChildren(template.content.cloneNode(true));
    setupQueryBuilder();
    const sourceType = dialog.querySelector('select[name="source_type"]');
    if (sourceType) {
      const updateSourceType = () => {
        const keyword = sourceType.value === 'keyword';
        dialog.querySelector('[data-keyword-source-help]').hidden = !keyword;
        const expression = dialog.querySelector('[data-source-expression]');
        expression.hidden = keyword;
        expression.querySelector('textarea').disabled = keyword;
        dialog.querySelector('button[value="save"]').hidden = keyword;
        dialog.querySelector('.collection-enabled').hidden = keyword;
      };
      sourceType.addEventListener('change', updateSourceType);
      updateSourceType();
    }
    dialog.showModal();
  });
  dialog.addEventListener('click', event => {
    if (event.target.closest('[data-close-editor]')) dialog.close();
    if (event.target.closest('[data-show-backfill]')) {
      const section = dialog.querySelector('.collection-backfill-form');
      section.open = true;
      section.scrollIntoView({block: 'start', behavior: 'smooth'});
    }
    if (event.target.closest('[data-open-keyword-monitor]')) {
      const name = dialog.querySelector('input[name="label"]').value;
      selectTab(tabs.find(tab => tab.getAttribute('aria-controls') === 'terms'));
      dialog.replaceChildren(document.getElementById('add-query').content.cloneNode(true));
      dialog.querySelector('input[name="label"]').value = name;
      setupQueryBuilder();
      dialog.scrollTop = 0;
      dialog.querySelector('input[name="label"]').focus();
    }
  });
  dialog.addEventListener('close', () => stopPreview());
  function jump(row) {
    if (!row) return;
    const pane = document.getElementById(active).querySelector('.collection-sheet-scroll');
    const header = pane.querySelector('thead').getBoundingClientRect().height;
    const top = row.element.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop - header;
    pane.scrollTo({top: Math.max(0, top), behavior: 'instant'});
    jumpHighlight = {panel: active, top: pane.scrollTop, letter: row.letter};
    row.element.focus({preventScroll: true});
    setLetter(row.letter);
  }
  letters.forEach(button => button.addEventListener('click', () => jump(visible.find(row => row.letter === button.dataset.letter))));
  alphabet.querySelector('[data-jump-top]').addEventListener('click', () => jump(visible[0]));
  panels.forEach(panel => panel.querySelector('.collection-sheet-scroll')?.addEventListener('scroll', () => {
    if (panel.id !== active || ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      const pane = panel.querySelector('.collection-sheet-scroll');
      if (jumpHighlight?.panel === active && Math.abs(pane.scrollTop - jumpHighlight.top) < 1) {
        setLetter(jumpHighlight.letter); ticking = false; return;
      }
      jumpHighlight = null;
      const edge = pane.getBoundingClientRect().top + pane.querySelector('thead').getBoundingClientRect().height;
      const row = visible.find(item => item.element.getBoundingClientRect().bottom > edge + 2);
      setLetter(row?.letter);
      ticking = false;
    });
  }, {passive: true}));
  dimensions.forEach(select => select.addEventListener('change', filter));
  root.querySelector('#collection-reset-filters').addEventListener('click', () => {
    search.value = ''; removed.checked = false; dimensions.forEach(select => { select.value = ''; });
    filter();
  });
  search.addEventListener('input', filter);
  removed.addEventListener('change', () => selectTab(tabs.find(tab => tab.getAttribute('aria-controls') === active)));
  selectTab(tabs.find(tab => tab.getAttribute('aria-controls') === initial) || tabs[0]);
  const pendingBackfills = [...root.querySelectorAll('[data-backfill-run]')].filter(row => ['queued', 'running'].includes(row.dataset.status));
  if (pendingBackfills.length) {
    const poll = async () => {
      try {
        const states = await Promise.all(pendingBackfills.map(async row => {
          const response = await fetch(`/settings/collection/backfills/${row.dataset.backfillRun}`, {headers: {'Accept': 'application/json'}});
          if (!response.ok) throw new Error('Status unavailable');
          return response.json();
        }));
        if (states.some(state => !['queued', 'running'].includes(state.status))) { location.reload(); return; }
      } catch (_) {
        // A transient request failure does not imply the job failed or completed.
      }
      setTimeout(poll, 3000);
    };
    setTimeout(poll, 3000);
  }
})();
