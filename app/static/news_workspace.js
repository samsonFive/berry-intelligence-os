(function () {
  'use strict';
  var root = document.querySelector('[data-news-workspace]');
  if (!root) return;
  var zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  var tz = document.querySelector('[data-news-timezone]');
  var url = new URL(window.location.href);
  if (tz && zone && !url.searchParams.has('tz')) tz.value = zone;
  var filterDisclosure = document.querySelector('[data-news-filter-disclosure]');
  if (filterDisclosure && window.matchMedia('(max-width:750px)').matches) filterDisclosure.open = false;
  var filterForm = document.querySelector('.news-filters');
  if (filterForm) {
    var start = filterForm.querySelector('[name=start]'), end = filterForm.querySelector('[name=end]');
    function validateDates() {
      end.setCustomValidity(start.value && end.value && start.value > end.value ? 'Choose an end date on or after the start date.' : '');
    }
    start.addEventListener('input', validateDates);
    end.addEventListener('input', validateDates);
    filterForm.addEventListener('submit', function (event) {
      validateDates();
      if (!filterForm.reportValidity()) event.preventDefault();
    });
  }
  // Legacy item bookmarks open the shared reader, without collection on GET.
  if (root.dataset.initialStory && !url.searchParams.has('story')) {
    url.searchParams.set('story', root.dataset.initialStory);
    url.searchParams.delete('item');
    window.history.replaceState(window.history.state, '', url);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
  document.querySelectorAll('[data-news-local-time]').forEach(function (time) {
    var date = new Date(time.dateTime);
    if (!isNaN(date)) time.textContent = date.toLocaleString();
  });
  var button = document.querySelector('[data-news-refresh]'), status = document.querySelector('[data-news-refresh-status]');
  var timer;
  function poll() {
    fetch('/api/news/refresh', {credentials: 'same-origin'}).then(function (res) {
      if (!res.ok) throw new Error('Could not check refresh status.');
      return res.json();
    }).then(function (state) {
      if (state.status === 'queued' || state.status === 'running') {
        status.textContent = 'Checking public news sources…';
        timer = setTimeout(poll, 2500);
      } else {
        button.disabled = false;
        status.textContent = state.message || 'Refresh finished.';
        if (state.status === 'ready' || state.status === 'partial') {
          var link = document.createElement('a'); link.href = window.location.href;
          link.textContent = ' Show updated feed'; status.appendChild(link);
        }
      }
    }).catch(function (error) { button.disabled = false; status.textContent = error.message; });
  }
  if (button) button.addEventListener('click', function () {
    button.disabled = true; status.textContent = 'Starting news capture…';
    fetch('/api/news/refresh', {method: 'POST', credentials: 'same-origin'}).then(function (res) {
      if (!res.ok) throw new Error('News refresh could not start. Try again.');
      poll();
    }).catch(function (error) { button.disabled = false; status.textContent = error.message; });
  });
  window.addEventListener('pagehide', function () { clearTimeout(timer); });
})();
