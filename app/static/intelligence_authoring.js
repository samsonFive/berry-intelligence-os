(function () {
  'use strict';
  var catalogNode = document.getElementById('authoring-reference-catalog');
  if (!catalogNode) return;
  var catalog;
  try { catalog = JSON.parse(catalogNode.textContent); } catch (_) { return; }
  document.querySelectorAll('[data-reference-field]').forEach(function (section) {
    var field = section.querySelector('.reference-manual input');
    var chosen = section.querySelector('.reference-selected');
    var choices = section.querySelector('.reference-choices');
    var search = choices.querySelector('input');
    var results = choices.querySelector('.reference-results');
    var count = choices.querySelector('.reference-count');
    var rows = catalog[section.dataset.referenceField] || [];
    function tokens() { return field.value.split(',').map(function (id) { return id.trim(); }).filter(Boolean); }
    function resolve(id) { return rows.find(function (row) { return row.id === id || (section.dataset.referenceField === 'strategic_question_ids' && row.label.toLowerCase() === id.toLowerCase()); }); }
    function change(id, focusId) {
      var selected = tokens();
      if (selected.includes(id)) selected = selected.filter(function (value) { return value !== id; });
      else selected.push(id);
      field.value = selected.join(', ');
      field.dispatchEvent(new Event('change', {bubbles: true}));
      var target = focusId ? Array.from(results.children).find(function (el) { return el.dataset.referenceId === focusId; }) : choices.querySelector('summary');
      if (target) target.focus();
    }
    function render() {
      var selected = tokens();
      chosen.replaceChildren();
      if (!selected.length) { var empty = document.createElement('span'); empty.textContent = 'None selected'; chosen.append(empty); }
      selected.forEach(function (id, index) {
        var row = resolve(id), button = document.createElement('button');
        var label = row ? row.label : 'Unresolved reference ' + (index + 1);
        button.type = 'button'; button.textContent = label + ' ×';
        button.setAttribute('aria-label', 'Remove ' + label);
        button.addEventListener('click', function () { change(id); }); chosen.append(button);
      });
      var query = search.value.trim().toLowerCase();
      var matching = rows.filter(function (row) { return (row.label + ' ' + row.detail + ' ' + row.id).toLowerCase().includes(query); });
      results.replaceChildren();
      matching.slice(0, 30).forEach(function (row) {
        var button = document.createElement('button'), label = document.createElement('span'), detail = document.createElement('small');
        button.type = 'button'; label.textContent = row.label; detail.textContent = row.detail;
        button.dataset.referenceId = row.id;
        button.setAttribute('aria-pressed', String(selected.some(function (id) { var resolved = resolve(id); return resolved && resolved.id === row.id; })));
        button.append(label, detail);
        button.addEventListener('click', function () {
          var existing = selected.find(function (id) { var resolved = resolve(id); return resolved && resolved.id === row.id; });
          change(existing || row.id, row.id);
        }); results.append(button);
      });
      count.textContent = matching.length ? 'Showing ' + Math.min(matching.length, 30) + ' of ' + matching.length + ' matches. Refine your search to see others.' : 'No matching records. Existing selections are kept.';
    }
    chosen.hidden = false; choices.hidden = false;
    search.addEventListener('input', render); field.addEventListener('change', render); field.addEventListener('input', render);
    search.addEventListener('keydown', function (event) { if (event.key === 'Enter') event.preventDefault(); });
    render();
  });
}());
