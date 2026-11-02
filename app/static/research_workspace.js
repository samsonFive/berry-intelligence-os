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
  var partial = document.createElement('section');
  partial.className = 'rd-panel';
  partial.hidden = true;
  partial.setAttribute('aria-label', 'Sources arriving');
  result.before(partial);
  function showProgress(event) {
    if (event.stage === 'capture') {
      status.textContent = 'Captured ' + event.captured + ' of ' + event.capture_total + ' sources. Matches below may change as more arrive.';
    } else if (event.stage === 'search') {
      status.textContent = 'Completed ' + event.searches_completed + ' searches; checking ' + event.candidates + ' candidate sources.';
    } else if (event.stage === 'provider') {
      status.textContent = 'Completed ' + event.providers_completed + ' provider checks. Saved intelligence remains available below.';
    }
    if (!event.items || !event.items.length) return;
    partial.replaceChildren();
    var heading = document.createElement('h2');
    heading.textContent = 'Sources arriving · unreviewed';
    partial.append(heading);
    event.items.slice(0, 20).forEach(function (item) {
      var url;
      try { url = new URL(item.source_url); } catch (_) { return; }
      if (url.protocol !== 'https:' && url.protocol !== 'http:') return;
      var card = document.createElement('article');
      var link = document.createElement('a');
      link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.textContent = item.title || url.hostname;
      var metadata = document.createElement('p');
      metadata.textContent = [item.published_date || 'Date unknown', item.relevance || 'Candidate', item.capture_status || '', item.passage_locator || ''].join(' · ');
      card.append(link, metadata);
      if (item.passage) {
        var excerpt = document.createElement('p');
        excerpt.textContent = String(item.passage).slice(0, 900);
        card.append(excerpt);
      }
      partial.append(card);
    });
    partial.hidden = false;
  }
  button.addEventListener('click', async function () {
    if (button.disabled) return;
    button.disabled = true;
    partial.hidden = true;
    status.textContent = 'Checking configured web sources. Your saved intelligence remains available below.';
    try {
      var response = await fetch(result.dataset.liveEndpoint, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'Accept': 'application/x-ndjson'},
        body: JSON.stringify({scope: JSON.parse(result.dataset.scope), first_content_ms: Number(result.dataset.firstContentMs || 0)})
      });
      if (!response.ok || !response.body) throw new Error('research failed');
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '', complete = false;
      function consume(line) {
        if (!line.trim()) return;
        var event = JSON.parse(line);
        if (event.type === 'error') throw new Error('research failed');
        if (event.type === 'progress') showProgress(event);
        if (event.type === 'complete') {
          result.innerHTML = event.html;
          partial.hidden = true;
          complete = true;
          var outcome = result.querySelector('[data-live-status]');
          status.textContent = outcome ? outcome.textContent : 'Source check finished. Review the results below.';
        }
      }
      while (true) {
        var chunk = await reader.read();
        buffer += decoder.decode(chunk.value || new Uint8Array(), {stream: !chunk.done});
        var lines = buffer.split('\n'); buffer = lines.pop();
        lines.forEach(consume);
        if (chunk.done) break;
      }
      if (buffer.trim()) consume(buffer);
      if (!complete) throw new Error('incomplete research stream');
    } catch (_) {
      status.textContent = 'The source check could not finish. Arriving sources are provisional; saved intelligence remains available. You can explicitly try again.';
    } finally {
      button.disabled = false;
      button.textContent = 'Check latest sources again';
    }
  });
}());
