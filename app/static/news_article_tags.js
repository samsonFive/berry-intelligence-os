(function () {
  'use strict';
  var drawer = document.querySelector('[data-news-tag-drawer]');
  if (!drawer || !window.bootstrap) return;
  var state = JSON.parse(document.querySelector('[data-news-card-tags]').textContent);
  var rows = Array.from(drawer.querySelectorAll('[data-drawer-tag-row]'));
  var title = drawer.querySelector('[data-article-tag-title]');
  var reason = drawer.querySelector('[data-article-tag-reason]');
  var status = drawer.querySelector('[data-article-tag-status]');
  var search = drawer.querySelector('[data-article-tag-search]');
  var filter = drawer.querySelector('[data-filter-article-tag]');
  var sheet = bootstrap.Offcanvas.getOrCreateInstance(drawer);
  var article, selectedTag, sourceCard, trigger, assignments = [], changed = false, busy = false, requestVersion = 0;
  function rowFor(id) {return rows.find(function (row) {return row.dataset.drawerTagRow === id;});}
  function updateRows() {
    rows.forEach(function (row) {
      var id = row.dataset.drawerTagRow, assigned = (state[article] || []).includes(id);
      row.classList.toggle('is-assigned', assigned);
      row.classList.toggle('is-selected', id === selectedTag);
      var toggle = row.querySelector('[data-drawer-tag-toggle]');
      if (toggle) {
        toggle.setAttribute('aria-pressed', String(assigned));
        toggle.setAttribute('aria-label', (assigned ? 'Remove ' : 'Assign ') + row.dataset.tagName);
        toggle.textContent = assigned ? '✓ Assigned' : '+ Add';
      }
    });
  }
  function explain(id) {
    selectedTag = id;
    var row = rowFor(id), found = assignments.find(function (item) {return item.id === id;});
    title.textContent = row ? row.dataset.tagName : 'Article tags';
    reason.textContent = found ? found.origin + ' · ' + found.rationale :
      (id ? ((state[article] || []).includes(id) ? 'This assignment is retained from the source. Supporting text is not available yet.' : 'This tag is not currently assigned to this article.') : 'Select a tag below to inspect its supporting text, or add a tag to this article.');
    filter.hidden = !row;
    if (row) {
      var url = new URL(window.location.href);
      var panel = document.querySelector('[data-tags-panel]');
      var ids = panel ? Array.from(panel.querySelectorAll('[name=tag_choice]:checked')).map(function (input) {return input.value;}) : [];
      url.searchParams.set('tag', Array.from(new Set(ids.concat([id]))).join(','));
      ['tag_choice','topic','topic_choice','page','story','item'].forEach(function (key) {url.searchParams.delete(key);});
      filter.href = url.toString(); filter.dataset.selectTag = id;
    }
    updateRows();
  }
  function loadExplanations() {
    var version = ++requestVersion;
    return fetch('/api/news/tags/explanations/' + encodeURIComponent(article), {credentials:'same-origin', cache:'no-store'}).then(function (res) {
      if (!res.ok) throw new Error('Supporting text is unavailable. Try opening this panel again.');
      return res.json();
    }).then(function (data) {
      if (version !== requestVersion) return;
      assignments = data.assignments; explain(selectedTag);
    }).catch(function (error) {if (version === requestVersion) reason.textContent = error.message;});
  }
  function updateCard() {
    var container = sourceCard.querySelector('.news-article-tags');
    container.replaceChildren();
    var ids = state[article] || [];
    ids.slice(0,3).forEach(function (id) {
      var row = rowFor(id); if (!row) return;
      var button = document.createElement('button'); button.type = 'button'; button.className = 'news-tag-label';
      button.dataset.openArticleTags = article; button.dataset.tagId = id; button.dataset.tagName = row.dataset.tagName;
      button.setAttribute('aria-controls', 'newsTagDrawer');
      button.setAttribute('aria-label', row.dataset.tagName + ': explanation and edit tags');
      button.textContent = row.dataset.tagName; container.appendChild(button);
    });
    if (ids.length > 3) {
      var more = document.createElement('button'); more.type = 'button'; more.className = 'news-tag-label';
      more.dataset.openArticleTags = article; more.textContent = '+' + (ids.length - 3);
      more.setAttribute('aria-label','Show all article tags'); more.setAttribute('aria-controls','newsTagDrawer'); container.appendChild(more);
    }
  }
  function save(id, action) {
    if (busy) return;
    selectedTag = id;
    busy = true; status.textContent = 'Saving…';
    drawer.querySelectorAll('.news-tag-toggle,.news-tag-restore').forEach(function (button) {button.disabled = true;});
    fetch('/api/news/tags/assignment', {method:'POST', credentials:'same-origin',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({article:article,tag:id,action:action})}).then(function (res) {
      if (!res.ok) throw new Error('Could not save this tag. Try again.');
      return res.json();
    }).then(function (data) {
      state[article] = data.tags; changed = true; updateRows(); updateCard();
      status.textContent = action === 'automatic' ? 'Automatic assignment restored.' : 'Article tags saved.';
      return loadExplanations();
    }).catch(function (error) {status.textContent = error.message;}).finally(function () {
      busy = false; drawer.querySelectorAll('.news-tag-toggle,.news-tag-restore').forEach(function (button) {button.disabled = false;});
    });
  }
  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-open-article-tags]');
    if (!button) return;
    trigger = button; sourceCard = button.closest('[data-item-id]'); article = button.dataset.openArticleTags;
    selectedTag = button.dataset.tagId || ''; assignments = []; changed = false; status.textContent = ''; search.value = '';
    rows.forEach(function (row) {row.hidden = false;});
    drawer.querySelector('[data-article-tag-source]').textContent = sourceCard.querySelector('h2').textContent;
    explain(selectedTag); reason.textContent = selectedTag ? 'Loading supporting text…' : reason.textContent;
    sheet.show(); loadExplanations();
  });
  drawer.addEventListener('click', function (event) {
    var info = event.target.closest('[data-drawer-tag-info]');
    var toggle = event.target.closest('[data-drawer-tag-toggle]');
    var restore = event.target.closest('[data-drawer-tag-restore]');
    if (info) explain(info.dataset.drawerTagInfo);
    if (toggle) save(toggle.dataset.drawerTagToggle, toggle.getAttribute('aria-pressed') === 'true' ? 'remove' : 'add');
    if (restore) save(restore.dataset.drawerTagRestore, 'automatic');
  });
  search.addEventListener('input', function () {
    rows.forEach(function (row) {row.hidden = !row.dataset.tagName.toLocaleLowerCase().includes(search.value.toLocaleLowerCase());});
  });
  document.addEventListener('news:tag-created', function (event) {
    var tag = event.detail;
    if (rowFor(tag.id)) return;
    var row = document.createElement('div'); row.className = 'news-drawer-tag-row';
    row.dataset.drawerTagRow = tag.id; row.dataset.tagName = tag.name;
    var info = document.createElement('button'); info.type = 'button'; info.className = 'news-tag-label';
    info.dataset.drawerTagInfo = tag.id; info.textContent = tag.name; row.appendChild(info);
    if (drawer.dataset.canEdit === '1') {
      var toggle = document.createElement('button'); toggle.type = 'button'; toggle.className = 'news-tag-toggle';
      toggle.dataset.drawerTagToggle = tag.id; toggle.setAttribute('aria-pressed','false');
      toggle.setAttribute('aria-label','Assign '+tag.name); toggle.textContent = '+ Add'; row.appendChild(toggle);
      var restore = document.createElement('button'); restore.type = 'button'; restore.className = 'news-tag-restore';
      restore.dataset.drawerTagRestore = tag.id; restore.textContent = 'Restore automatic'; row.appendChild(restore);
    }
    drawer.querySelector('[data-article-tag-list]').appendChild(row); rows.push(row);
  });
  drawer.addEventListener('shown.bs.offcanvas', function () {if (!selectedTag) search.focus();});
  drawer.addEventListener('hide.bs.offcanvas', function (event) {if (busy) event.preventDefault();});
  drawer.addEventListener('hidden.bs.offcanvas', function () {
    requestVersion++;
    var active = document.querySelector('[data-tags-panel] [name=tag_choice]:checked');
    if (changed && active) {window.location.reload(); return;}
    if (trigger && trigger.isConnected) trigger.focus();
    else if (sourceCard) (sourceCard.querySelector('[data-add-article-tag]') || sourceCard).focus();
  });
}());
