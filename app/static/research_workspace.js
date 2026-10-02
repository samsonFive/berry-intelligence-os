(function () {
  'use strict';
  document.querySelectorAll('[data-research-example]').forEach(function (button) {
    button.addEventListener('click', function () {
      var field = document.getElementById('rd-question');
      if (field) { field.value = button.dataset.researchExample || ''; field.focus(); }
    });
  });
  var result = document.getElementById('rd-result');
  var button = document.getElementById('rd-run-live');
  var status = document.getElementById('rd-capture-status');
  if (!result || !button) return;
  button.addEventListener('click', function () {
    if (button.disabled) return;
    button.disabled = true;
    status.textContent = 'Checking configured web sources. Your saved intelligence remains available below.';
    fetch(result.dataset.liveEndpoint, {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({scope: JSON.parse(result.dataset.scope), first_content_ms: Number(result.dataset.firstContentMs || 0)})
    }).then(function (response) {
      if (!response.ok) throw new Error('research failed');
      return response.text();
    }).then(function (html) {
      result.innerHTML = html;
      var outcome = result.querySelector('[data-live-status]');
      status.textContent = outcome ? outcome.textContent : 'Source check finished. Review the results below.';
    }).catch(function () {
      status.textContent = 'The source check could not finish. Your saved intelligence remains available; you can try again.';
    }).finally(function () {
      button.disabled = false;
      button.textContent = 'Check latest sources again';
    });
  });
}());
