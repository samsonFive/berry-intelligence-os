/* Local navigation only: no fetching, saving or review changes. */
document.querySelectorAll('[data-company-source-varieties]').forEach(function (section) {
  var tools = section.querySelector('[data-source-tools]');
  if (!tools) return;
  var search = section.querySelector('[data-source-search]');
  var berry = section.querySelector('[data-source-berry]');
  var rows = Array.from(section.querySelectorAll('[data-source-row]'));
  var letter = '';
  function update() {
    var term = search.value.trim().toLocaleLowerCase();
    var count = 0;
    rows.forEach(function (row) {
      row.hidden = (letter && row.dataset.letter !== letter) ||
        (berry.value && row.dataset.berry !== berry.value) ||
        (term && !row.dataset.search.toLocaleLowerCase().includes(term));
      if (!row.hidden) count += 1;
    });
    section.querySelector('[data-source-count]').textContent = count + ' of ' + rows.length + ' names shown';
    section.querySelector('[data-source-empty]').hidden = count > 0;
    tools.querySelectorAll('[data-source-letter]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.sourceLetter === letter));
    });
  }
  search.addEventListener('input', update);
  berry.addEventListener('change', update);
  tools.addEventListener('click', function (event) {
    var button = event.target.closest('[data-source-letter], [data-source-reset]');
    if (!button) return;
    if (button.hasAttribute('data-source-reset')) {
      search.value = ''; berry.value = ''; letter = '';
    } else letter = button.dataset.sourceLetter;
    update();
  });
  tools.hidden = false;
  update();
});
