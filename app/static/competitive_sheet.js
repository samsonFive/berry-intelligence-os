/* Sheet presentation only. Assessment changes retain the existing guarded forms. */
(() => {
  const sheet = document.querySelector('.ce-sheet');
  if (!sheet) return;
  const dialog = document.getElementById('ce-row-dialog');
  const body = dialog.querySelector('[data-ce-dialog-body]');
  const rows = [...sheet.querySelectorAll('[data-ce-row]')];
  let active = null;
  let returnFocus = null;
  let home = null;
  let next = null;
  let detail = null;
  const select = row => {
    active?.classList.remove('ce-row-selected');
    active = row;
    active.classList.add('ce-row-selected');
  };
  const restore = () => {
    if (!detail) return;
    home.insertBefore(detail, next);
    detail.open = false;
    detail = null;
    returnFocus?.focus();
  };
  const open = (row, trigger) => {
    if (dialog.open || typeof dialog.showModal !== 'function') return;
    select(row);
    detail = row.querySelector('.ce-row-details');
    home = detail.parentNode;
    next = detail.nextSibling;
    returnFocus = trigger;
    document.getElementById('ce-row-dialog-title').textContent = row.getAttribute('aria-label');
    detail.open = true;
    body.replaceChildren(detail);
    dialog.showModal();
    dialog.querySelector('[data-ce-close-row]').focus();
  };
  if (typeof dialog.showModal === 'function') {
    sheet.classList.add('ce-sheet-ready');
    for (const row of rows) {
      const button = row.querySelector('[data-ce-open-row]');
      button.hidden = false;
      button.addEventListener('click', () => open(row, button));
      row.addEventListener('click', () => select(row));
      row.addEventListener('dblclick', event => {
        if (!event.target.closest('a,button,input,select,textarea,details')) open(row, row);
      });
      row.addEventListener('keydown', event => {
        if (event.target !== row) return;
        if (event.key === 'Enter') {
          event.preventDefault(); open(row, row);
        } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          const target = rows[rows.indexOf(row) + (event.key === 'ArrowDown' ? 1 : -1)];
          if (target) { select(target); target.focus(); }
        }
      });
    }
    dialog.querySelector('[data-ce-close-row]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', restore);
    dialog.addEventListener('click', event => {
      // The shared Reader must open outside the modal's top layer.
      if (event.target.closest('[data-open-reader]')) { dialog.close(); restore(); }
    });
  }
  const menu = sheet.querySelector('[data-ce-columns]');
  if (menu) {
    menu.hidden = false;
    menu.querySelectorAll('input[type=checkbox]').forEach(input => input.addEventListener('change', () => {
      sheet.querySelectorAll('[data-ce-col]').forEach(cell => {
        if (cell.dataset.ceCol === input.value) cell.classList.toggle('ce-column-hidden', !input.checked);
      });
    }));
    menu.querySelector('[data-ce-density]').addEventListener('change', event => {
      sheet.classList.toggle('ce-comfortable', event.target.value === 'comfortable');
    });
  }
  const filters = sheet.querySelector('.ce-filter-panel');
  const columns = sheet.querySelector('.ce-column-menu');
  for (const panel of [filters, columns].filter(Boolean)) {
    panel.addEventListener('keydown', event => {
      if (event.key === 'Escape') { panel.open = false; panel.querySelector('summary').focus(); }
    });
  }
  document.addEventListener('click', event => {
    for (const panel of [filters, columns].filter(Boolean)) {
      if (panel.open && !panel.contains(event.target)) panel.open = false;
    }
  });
})();
