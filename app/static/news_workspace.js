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
  var refreshDeadline;
  function poll() {
    fetch('/api/news/refresh', {credentials: 'same-origin', cache: 'no-store'}).then(function (res) {
      if (!res.ok) throw new Error('Could not check refresh status.');
      return res.json();
    }).then(function (state) {
      if (!state.status || state.status === 'queued' || state.status === 'running') {
        if (Date.now() > refreshDeadline) {
          button.disabled = false;
          status.textContent = 'News is taking longer than expected. Try refreshing again.';
          return;
        }
        status.textContent = 'Checking public news sources…';
        timer = setTimeout(poll, 2500);
      } else {
        button.disabled = false;
        status.textContent = state.message || 'Refresh finished.';
        if (state.status === 'ready' || state.status === 'partial') {
          status.textContent = 'Showing updated news…';
          var latest = new URL(window.location.href);
          latest.searchParams.delete('page');
          latest.searchParams.delete('story');
          latest.searchParams.delete('item');
          latest.searchParams.delete('refresh');
          window.location.replace(latest.toString());
        }
      }
    }).catch(function (error) { button.disabled = false; status.textContent = error.message; });
  }
  function beginRefresh() {
    if (!button || button.disabled) return;
    refreshDeadline = Date.now() + 600000;
    button.disabled = true; status.textContent = 'Starting news capture…';
    fetch('/api/news/refresh', {method: 'POST', credentials: 'same-origin'}).then(function (res) {
      if (!res.ok) throw new Error('News refresh could not start. Try again.');
      poll();
    }).catch(function (error) { button.disabled = false; status.textContent = error.message; });
  }
  if (button) button.addEventListener('click', beginRefresh);
  // Clicking News is itself an explicit request for fresh news. Consume its
  // URL marker before the final reload so it cannot start a refresh loop.
  if (button && ['1', 'true', 'latest'].indexOf(url.searchParams.get('refresh')) !== -1) {
    url.searchParams.delete('refresh');
    window.history.replaceState(window.history.state, '', url);
    beginRefresh();
  }
  var imagesButton = document.querySelector('[data-news-images]'), imagesTimer;
  function pollImages() {
    fetch('/api/news/images', {credentials: 'same-origin'}).then(function (response) {
      if (!response.ok) throw new Error('Could not check article images.');
      return response.json();
    }).then(function (state) {
      if (state.status === 'queued' || state.status === 'running') {
        imagesTimer = setTimeout(pollImages, 2500);
      } else {
        imagesButton.disabled = false;
        status.textContent = state.message || 'Article images checked.';
        if (state.status === 'ready') {
          // Updating the grid through a reload would discard the open Reader.
          var link = document.createElement('a'); link.href = window.location.href;
          link.textContent = ' Show updated images'; status.appendChild(link);
        }
      }
    }).catch(function (error) { imagesButton.disabled = false; status.textContent = error.message; });
  }
  if (imagesButton) imagesButton.addEventListener('click', function () {
    imagesButton.disabled = true; status.textContent = 'Checking article images…';
    fetch('/api/news/images' + window.location.search, {method: 'POST', credentials: 'same-origin'}).then(function (response) {
      if (!response.ok) throw new Error('Article images could not be checked. Try again.');
      pollImages();
    }).catch(function (error) { imagesButton.disabled = false; status.textContent = error.message; });
  });
  // Background collection updates stored News. Observe completion without
  // triggering collection, and update an idle first page without a click.
  var backgroundTimer, filtersEdited = false, leaving = false;
  if (filterForm) filterForm.addEventListener('input', function () { filtersEdited = true; });
  function checkBackground() {
    if (leaving) return;
    backgroundTimer = setTimeout(checkBackground, 60000);
    var current = new URL(window.location.href);
    if (document.hidden || filtersEdited || (button && button.disabled) ||
        current.searchParams.has('story') || current.searchParams.has('item') ||
        Number(current.searchParams.get('page') || 1) > 1 || document.querySelector('.offcanvas.show')) return;
    fetch('/api/news/refresh', {credentials: 'same-origin', cache: 'no-store'}).then(function (response) {
      if (!response.ok) return null;
      return response.json();
    }).then(function (state) {
      if (!leaving && !document.hidden && !filtersEdited && state &&
          ['ready', 'partial'].indexOf(state.status) !== -1 && state.completed_at &&
          state.completed_at !== root.dataset.newsCompleted &&
          !new URL(window.location.href).searchParams.has('story') && !document.querySelector('.offcanvas.show')) {
        window.location.reload();
      }
    }).catch(function () { /* A status outage does not interrupt reading. */ });
  }
  backgroundTimer = setTimeout(checkBackground, 60000);
  window.addEventListener('pagehide', function () { leaving = true; clearTimeout(timer); clearTimeout(imagesTimer); clearTimeout(backgroundTimer); });
})();
