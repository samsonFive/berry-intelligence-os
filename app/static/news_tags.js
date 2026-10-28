(function () {
  'use strict';
  var panel = document.querySelector('[data-tags-panel]');
  if (!panel) return;
  var form = panel.closest('form'), status = panel.querySelector('[data-tag-status]');
  function post(path, body) {
    return fetch('/api/news/tags' + path, {method:'POST', credentials:'same-origin',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(body || {})}).then(function (res) {
      if (!res.ok) return res.json().then(function (data) {throw new Error(data.detail || 'Could not save tags.');});
      return res.json();
    });
  }
  function selected() {return Array.from(panel.querySelectorAll('[name=tag_choice]:checked')).map(function (el) {return el.value;});}
  function save(tags, mode) {return panel.dataset.canSave === '1' ? post('/preferences', {tags:tags, mode:mode || panel.querySelector('[name=tag_mode]').value}) : Promise.resolve();}
  function navigate(href, tags) {
    save(tags).then(function () {window.location.assign(href);}).catch(function (e) {status.textContent=e.message;});
  }
  panel.querySelector('[data-tag-search]').addEventListener('input', function (event) {
    var query = event.target.value.toLocaleLowerCase();
    panel.querySelectorAll('.news-tag-chip').forEach(function (chip) {chip.hidden = !chip.textContent.toLocaleLowerCase().includes(query);});
  });
  form.addEventListener('change', function (event) {
    if (event.target.matches('[name=tag_choice], [name=tag_mode]')) form.requestSubmit();
  });
  var submitting = false;
  form.addEventListener('submit', function (event) {
    if (submitting || !form.checkValidity()) return;
    event.preventDefault();
    save(selected()).then(function () {submitting=true; form.requestSubmit();}).catch(function (e) {status.textContent=e.message;});
  });
  document.querySelectorAll('[data-clear-tags]').forEach(function (link) {
    link.addEventListener('click', function (event) {event.preventDefault(); navigate(link.href, []);});
  });
  document.querySelectorAll('[data-select-tag]').forEach(function (link) {
    link.addEventListener('click', function (event) {event.preventDefault(); navigate(link.href, Array.from(new Set(selected().concat([link.dataset.selectTag]))));});
  });
  // Explicit URL state wins over the remembered selection, including an empty tag=.
  var url = new URL(window.location.href);
  if (url.searchParams.has('tag') || url.searchParams.has('topic') || url.searchParams.has('tag_choice')) {
    save(selected()).catch(function (e) {status.textContent=e.message;});
  }
  var dialog = document.querySelector('[data-tag-dialog]'), add = panel.querySelector('[data-add-tag]');
  function normalize(value) {return value.normalize('NFKC').trim().replace(/\s+/g,' ').toLocaleLowerCase();}
  if (add) {
    add.addEventListener('click', function () {dialog.showModal(); dialog.querySelector('[name=name]').focus();});
    dialog.querySelector('[name=name]').addEventListener('input', function (event) {
      var name=normalize(event.target.value), matches=dialog.querySelector('[data-tag-matches]');
      matches.textContent='';
      panel.querySelectorAll('.news-tag-chip').forEach(function (chip) {
        if (name && normalize(chip.textContent).includes(name)) matches.textContent += chip.textContent.trim() + ' · ';
      });
    });
    dialog.querySelector('[data-create-tag]').addEventListener('click', function (event) {
      event.preventDefault();
      var input=dialog.querySelector('[name=name]');
      if (!input.reportValidity()) return;
      var button=this; button.disabled=true;
      post('', {name:input.value, description:dialog.querySelector('[name=description]').value}).then(function (data) {
        if (!Array.from(panel.querySelectorAll('[name=tag_choice]')).some(function (el) {return el.value===data.tag.id;})) {
          var label=document.createElement('label'); label.className='news-tag-chip';
          var checkbox=document.createElement('input'); checkbox.type='checkbox'; checkbox.name='tag_choice'; checkbox.value=data.tag.id;
          var text=document.createElement('span'); text.textContent=data.tag.name; label.append(checkbox,text);
          panel.querySelector('[data-tag-chips]').appendChild(label);
        }
        dialog.close(); status.textContent='Tag available. Classifying stored articles…'; poll();
      }).catch(function (e) {dialog.querySelector('[data-tag-create-status]').textContent=e.message;}).finally(function () {button.disabled=false;});
    });
  }
  document.querySelectorAll('[data-article-tag]').forEach(function (button) {
    button.addEventListener('click', function () {
      var message=button.closest('details').querySelector('[data-assignment-status]'); button.disabled=true;
      post('/assignment', {article:button.dataset.articleTag, tag:button.dataset.tagId, action:button.dataset.tagAction}).then(function () {
        message.textContent='Correction saved.'; window.location.reload();
      }).catch(function (e) {message.textContent=e.message; button.disabled=false;});
    });
  });
  document.querySelectorAll('[data-tag-explanations]').forEach(function (details) {
    details.addEventListener('toggle', function () {
      if (!details.open || details.dataset.loaded) return;
      fetch('/api/news/tags/explanations/'+encodeURIComponent(details.dataset.tagExplanations), {credentials:'same-origin'}).then(function (res) {if (!res.ok) throw new Error('Explanations unavailable.'); return res.json();}).then(function (data) {
        details.querySelector('[data-tag-explanation-text]').textContent=data.assignments.map(function (a) {return a.name+' · '+a.origin+': '+a.rationale;}).join(' — ') || 'No classified assignments yet.';
        details.dataset.loaded='1';
      }).catch(function (e) {details.querySelector('[data-tag-explanation-text]').textContent=e.message;});
    });
  });
  var manage=panel.querySelector('[data-manage-tags]'), definition=document.querySelector('[data-tag-definition-dialog]');
  if (manage) {
    var chooser=definition.querySelector('[data-definition-id]');
    function loadDefinition() {
      var option=chooser.selectedOptions[0];
      definition.querySelector('[data-definition-name]').value=option.dataset.name;
      definition.querySelector('[data-definition-description]').value=option.dataset.description;
    }
    manage.addEventListener('click',function () {loadDefinition(); definition.showModal();});
    chooser.addEventListener('change',loadDefinition);
    definition.querySelector('[data-save-definition]').addEventListener('click', function (event) {
      event.preventDefault();
      var name=definition.querySelector('[data-definition-name]'); if (!name.reportValidity()) return;
      post('/definition',{id:chooser.value,name:name.value,description:definition.querySelector('[data-definition-description]').value}).then(function () {window.location.reload();}).catch(function (e) {definition.querySelector('[data-definition-status]').textContent=e.message;});
    });
  }
  var deadline;
  function poll() {
    if (!deadline) deadline=Date.now()+600000;
    setTimeout(function () {
      fetch('/api/news/tags/status', {credentials:'same-origin', cache:'no-store'}).then(function (res) {if (!res.ok) throw new Error('Could not check classification.'); return res.json();}).then(function (state) {
        status.textContent = state.status === 'ready' ? 'Stored article classification complete. Reload to show updated assignments.' :
          (state.error || 'Classifying stored articles: '+state.processed+' / '+state.total+'. Results may be incomplete.');
        if (state.status==='ready') {
          var link=document.createElement('a'); link.href=window.location.href; link.textContent=' Show updated news'; status.appendChild(link);
        } else if (state.status!=='failed' && Date.now()<deadline) poll();
      }).catch(function (e) {status.textContent=e.message+' Use Recheck stored articles to retry.';});
    }, 2000);
  }
  function recheck() {post('/classify').then(function () {status.textContent='Classifying stored articles…'; deadline=undefined; poll();}).catch(function (e) {status.textContent=e.message;});}
  var retry=panel.querySelector('[data-retry-tags]');
  if (retry) retry.addEventListener('click', recheck);
  if (retry && status.dataset.jobStatus==='pending') recheck();
  else if (status.dataset.jobStatus==='running' || status.dataset.jobStatus==='queued') poll();
}());
