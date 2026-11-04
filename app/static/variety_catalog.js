document.querySelectorAll('[data-catalog-add]').forEach(button => {
  button.addEventListener('click', () => {
    const container = document.querySelector('[data-catalog-table="' + button.dataset.catalogAdd + '"]');
    const row = container.lastElementChild.cloneNode(true);
    const index = container.children.length;
    row.querySelector('legend').textContent = 'New entry';
    row.querySelectorAll('input, textarea, select').forEach(input => {
      if (input.type === 'checkbox') { input.checked = false; input.value = String(index); }
      else if (input.type !== 'hidden') input.value = input.tagName === 'SELECT' ? 'text' : '';
    });
    container.appendChild(row);
    row.querySelector('input:not([type="hidden"])').focus();
  });
});
