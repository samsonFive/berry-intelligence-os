(function () {
  'use strict';
  const root = document.querySelector('#living-workspace'); if (!root) return;
  const $ = id => document.getElementById(id), token = () => crypto.randomUUID();
  const api = window.livingAPI;
  let inventory, page, items = {}, sources = {}, selected = new Set(), dirty = false, saving = false, timer, feedCards = [], incoming = [], createToken = token();
  let overviewStale=false,materialUpdatedAt='';
  const status = text => { $('lw-status').textContent = text; };
  function el(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; }
  function button(text, action, parent) { const e = el('button', text); e.type = 'button'; e.addEventListener('click', () => Promise.resolve().then(action).catch(error)); parent.append(e); return e; }
  function error(e) { status(e.message); }
  function recoveryKey() { return 'bios:living:recovery:' + page.id; }
  function changed() {
    dirty = true; status('Unsaved changes');renderOverview();
    try { localStorage.setItem(recoveryKey(), JSON.stringify(page)); } catch (_) {}
    clearTimeout(timer); timer = setTimeout(save, 900);
  }
  async function save() {
    if (!page || saving || !dirty) return;
    saving = true; const sent = JSON.stringify(page); status('Saving…');
    try {
      const result = await api('/api/workspaces/page/' + page.id, 'PUT', page);
      if (JSON.stringify(page) === sent) { page = result; dirty = false; localStorage.removeItem(recoveryKey()); status('Saved · revision ' + page.version);materialUpdatedAt=page.content_updated_at||page.updated_at;renderOverview(); }
      else { page.version = result.version; status('Saving newer edits…'); }
    } catch (e) { status('Save failed · ' + e.message + ' · Your draft is retained.'); }
    finally { saving = false; if (dirty && JSON.stringify(page) !== sent) timer = setTimeout(save, 900); }
  }
  function sidebar() {
    const nav = $('lw-pages'); nav.replaceChildren(); const query = $('lw-search').value.toLowerCase();
    inventory.pages.forEach(row => {
      if (query && !JSON.stringify(row).toLowerCase().includes(query)) return;
      const a = el('a', row.title); a.href = '/workspaces/' + row.id;
      let parent = row.parent_id, depth = 0, visited = new Set();
      while (parent && !visited.has(parent)) { visited.add(parent); depth++; parent = inventory.pages.find(p => p.id === parent)?.parent_id; }
      a.style.paddingLeft = (8 + depth * 14) + 'px'; if (page?.id === row.id) a.setAttribute('aria-current', 'page');
      nav.append(a);
    });
  }
  async function load(id) {
    if (dirty) await save(); if (dirty) throw Error('Save or recover your current edits before opening another page.');
    const data = await api('/api/workspaces/page/' + id); page = data.page;overviewLoadedSignature='';overviewStale=data.overview_stale;materialUpdatedAt=data.page_material_updated_at;
    items = Object.fromEntries(data.items.map(i => [i.id, i])); sources = Object.fromEntries(data.sources.map(s => [s.id, s]));
    $('lw-welcome').hidden = true; $('lw-editor').hidden = false; $('lw-title').value = page.title;requestAnimationFrame(()=>{$('lw-title').style.height='auto';$('lw-title').style.height=$('lw-title').scrollHeight+'px';});
    $('lw-export').href = '/api/workspaces/export/' + id; $('lw-json').href = '/api/workspaces/export/' + id + '?format=json';
    localStorage.setItem('bios:living:recent', id); sidebar(); render(); status('Saved · revision ' + page.version);
    $('lw-restore').hidden = !localStorage.getItem(recoveryKey());if(location.hash){try{document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView({block:'start'});}catch(_){}} await refreshFeed(true);
  }
  function chooseEntity(value) { return inventory.entities.find(e => e.id === value); }
  function entitySelect(value, onChange, parent, labelText) {
    const label = el('label', labelText), input = el('input'); input.setAttribute('list', 'lw-entity-options'); input.value = value || ''; label.append(input); parent.append(label);
    input.addEventListener('change', () => { if (input.value && !chooseEntity(input.value)) { input.setCustomValidity('Choose an exact entity ID from suggestions.'); input.reportValidity(); return; } input.setCustomValidity(''); onChange(input.value); }); return input;
  }
  function inputText(block, parent, field = 'text') {
    const input = el('textarea'); input.value = block[field] || ''; input.setAttribute('aria-label', block.type + ' ' + field); input.rows = Math.min(15, Math.max(2, input.value.split('\n').length)); input.addEventListener('input', () => { block[field] = input.value; changed(); }); parent.append(input);
  }
  function render() {
    const host = $('lw-blocks'); host.replaceChildren();
    page.blocks.forEach((block, index) => {
      const box = el('section', undefined, 'lw-block'); box.dataset.type = block.type; box.id = block.id;box.tabIndex=-1;
      const bar = el('div', undefined, 'lw-block-bar'), label = el('label'), check = el('input'); check.type = 'checkbox'; check.checked = selected.has(block.id); check.addEventListener('change', () => check.checked ? selected.add(block.id) : selected.delete(block.id)); label.append(check, document.createTextNode(block.type)); bar.append(label);
      function move(delta) { const next = index + delta; if (next < 0 || next >= page.blocks.length) return; [page.blocks[index], page.blocks[next]] = [page.blocks[next], page.blocks[index]]; changed(); render(); document.getElementById(block.id)?.querySelector('button')?.focus(); }
      button('↑', () => move(-1), bar).setAttribute('aria-label', 'Move block up'); button('↓', () => move(1), bar).setAttribute('aria-label', 'Move block down');
      button('Remove placement', () => { page.blocks.splice(index, 1); changed(); render(); }, bar); box.append(bar);
      const item = items[block.item_id], source = item && sources[item.source_id];
      if(block.authored){inputText(block,box);const a=el('a','Analyst-authored · unverified · open knowledge item');a.href='/workspaces/evidence/'+block.item_id;box.append(a);}
      else if (item && source) {
        box.append(el('p', item.nature.replaceAll('_', ' ') + ' · ' + item.verification_state + (item.withdrawn ? ' · WITHDRAWN' : ''), 'lw-eyebrow'));
        if (item.quote) box.append(el('blockquote', item.quote));
        if (item.text) box.append(el('p', item.text)); if (item.note) box.append(el('p', 'Analyst note: ' + item.note));
        const a = el('a', source.title + ' · ' + source.publisher + ' · ' + (source.published_date || 'Date unknown')); a.href = '/workspaces/evidence/' + item.id; box.append(a);
        const controls = el('div', undefined, 'lw-item-controls'); box.append(controls);
        button('Edit statement / note', () => editItem(item), controls); button(item.withdrawn ? 'Restore interpretation' : 'Withdraw interpretation', async () => { const result = await api('/api/workspaces/item/' + item.id, 'PATCH', {version: item.version, withdrawn: !item.withdrawn}); items[item.id] = result; render(); }, controls);
        button('Place on another page', () => placeElsewhere(item), controls);
        const review = el('a', 'Review evidence'); review.href = '/review/' + (item.review_evidence_id||item.id); controls.append(review);
        if (item.locator.state === 'unresolved') box.append(el('p', item.locator.reason, 'lw-muted'));
        if (block.type === 'article') {
          const details = el('details'), summary = el('summary', 'Read captured article · ' + source.availability.replaceAll('_', ' ')), prose = el('div', source.text || 'Full text unavailable. Open the original source.', 'lw-source');
          prose.tabIndex=0;prose.setAttribute('aria-label','Captured article text');prose.dataset.lwSource = ''; prose.dataset.sourceId = source.id; prose.dataset.articleId = source.article_id;
          details.append(summary, prose); box.append(details);
          if (/^https?:\/\//.test(source.url)) { const link = el('a', 'Open original source'); link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; details.append(link); }
        }
        box.append(el('p', 'Page commentary (does not alter shared evidence)', 'lw-muted')); inputText(block, box);
      } else if (block.type === 'table') {
        const table = el('table', undefined, 'lw-table'); (block.rows || [['Company', 'Source statement', 'Status'], ['', '', '']]).forEach((row, r) => {
          const tr = el('tr'); row.forEach((value, c) => { const td = el('td'), input = el('input'); input.value = value; input.setAttribute('aria-label', `Row ${r+1}, column ${c+1}`); input.addEventListener('input', () => { block.rows[r][c] = input.value; changed(); }); td.append(input); tr.append(td); }); table.append(tr);
        }); box.append(table); button('+ Row', () => { block.rows.push(block.rows[0].map(() => '')); changed(); render(); }, box); button('+ Column', () => { block.rows.forEach(row => row.push('')); changed(); render(); }, box);
      } else if (block.type === 'entity') {
        entitySelect(block.entity_id, id => { block.entity_id = id; changed(); render(); }, box, 'Linked company / variety / technology / topic');
        const entity = chooseEntity(block.entity_id); if (entity) { const link = el('a', entity.name + (entity.identity_state ? ' · unresolved identity' : '')); link.href = entity.identity_state ? '/workspaces?entity=' + entity.id : '/entities/' + entity.type + '/' + entity.id; box.append(link); } inputText(block, box);
      } else if (block.type === 'page') {
        const select = el('select'); select.append(el('option', 'Choose page')); inventory.pages.forEach(p => { const option = el('option', p.title); option.value = p.id; select.append(option); }); select.value = block.page_id || ''; select.addEventListener('change', () => { block.page_id = select.value; changed(); render(); }); box.append(select); if (block.page_id) { const a = el('a', 'Open linked page'); a.href = '/workspaces/' + block.page_id; box.append(a); }
      } else if (block.type === 'map') { drawMap(box); }
      else if (block.type === 'feed') { box.append(el('p', 'Living feed · incoming coverage is shown alongside this document. Feature an item to add it to the curated page.')); button('Configure feed', configureFeed, box); }
      else {
        if (block.type === 'checklist') { const check = el('input'); check.type = 'checkbox'; check.checked = !!block.checked; check.setAttribute('aria-label', 'Completed'); check.addEventListener('change', () => { block.checked = check.checked; changed(); }); box.append(check); }
        inputText(block, box);
        if (block.type === 'briefing') {
          box.append(el('p', block.method + ' · generated ' + block.generated_at, 'lw-muted'));if(block.generation_notice)box.append(el('p',block.generation_notice,'lw-muted'));
          (block.citations || []).forEach(ref => { const a = el('a', '[' + ref.number + '] ' + ref.title); a.href = '/workspaces/evidence/' + ref.item_id; box.append(a, el('br')); });
          const stale = (block.source_versions || []).some(ref => items[ref.id]?.version !== ref.version);
          if (stale) box.append(el('p', 'Referenced evidence changed. Generate a new block to compare; this draft is preserved.', 'lw-relation-label'));
        }
      }
      host.append(box);
    });
    renderOverview();
  }
  function formatDate(value) {return value?new Date(value).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):'Not generated yet';}
  function jumpLink(text,id) {
    const a=el('a',text);a.href='#'+id;a.addEventListener('click',event=>{const destination=document.getElementById(id);if(!destination)return;event.preventDefault();destination.scrollIntoView({behavior:'smooth',block:'start'});destination.focus({preventScroll:true});history.replaceState(null,'','#'+id);});return a;
  }
  function overviewSignature() {return JSON.stringify({title:page.title,blocks:page.blocks.filter(b=>!['briefing','feed','map'].includes(b.type)),items:Object.values(items).map(i=>[i.id,i.version])});}
  let overviewLoadedSignature='';
  function renderOverview() {
    if(!page)return;
    const overview=page.overview,signature=overviewSignature();if(!overviewLoadedSignature)overviewLoadedSignature=signature;
    const latestMaterial=[materialUpdatedAt||page.content_updated_at||page.updated_at,...Object.values(items).map(i=>i.updated_at||'')].sort().at(-1);$('lw-page-updated').textContent='Page updated · '+formatDate(latestMaterial)+(dirty?' · unsaved edits':'');
    $('lw-summary-date').textContent='Last generated · '+formatDate(overview?.generated_at);
    $('lw-summary-regenerate').textContent=overview?'Regenerate AI summary':'Generate AI summary';
    $('lw-summary-freshness').textContent=overview?(overviewStale||signature!==overviewLoadedSignature?'Page material has changed since this summary. Regenerate when you are ready.':'Summary reflects the saved material at generation time. Updates are always manual.'):'Compile a source-linked overview of this page. Your full research document stays below.';
    const body=$('lw-summary-body');body.replaceChildren();
    if(overview){
      body.append(el('p',overview.method==='deterministic cited digest'?'Evidence digest · AI model was not used':('AI-assisted overview · '+(overview.model||'configured model')),'lw-eyebrow'));
      if(overview.generation_notice)body.append(el('p',overview.generation_notice,'lw-muted'));
      const refs=Object.fromEntries((overview.citations||[]).map(ref=>[ref.number,ref]));
      const lines=overview.text.split('\n');
      lines.forEach(line=>{if(!line.trim())return;const heading=/^(#{1,3})\s+/.exec(line),node=el(heading?'h3':'p');const text=heading?line.slice(heading[0].length):line;let offset=0;
        for(const match of text.matchAll(/\[(\d+)\]/g)){node.append(document.createTextNode(text.slice(offset,match.index)));const ref=refs[match[1]];if(ref){const block=page.blocks.find(b=>b.item_id===ref.item_id);const a=block?jumpLink(match[0],block.id):el('a',match[0]);if(!block)a.href='/workspaces/evidence/'+ref.item_id;a.title=ref.title;node.append(a);}else node.append(document.createTextNode(match[0]));offset=match.index+match[0].length;}node.append(document.createTextNode(text.slice(offset)));body.append(node);
      });
    }else body.append(el('p','No summary has been generated yet. Switch to Contents & excerpts to explore the page immediately.','lw-muted'));
    const contents=$('lw-contents');contents.replaceChildren();const table=el('table',undefined,'lw-contents-table'),head=el('tr');['Section','Key excerpt'].forEach(text=>head.append(el('th',text)));table.append(head);
    let section='';page.blocks.forEach((block,index)=>{const item=items[block.item_id],source=item&&sources[item.source_id];let title=block.type==='heading'?block.text:(source?.title||chooseEntity(block.entity_id)?.name||inventory?.pages.find(p=>p.id===block.page_id)?.title||({map:'Relationship map',feed:'Incoming coverage',table:'Comparison table',briefing:'Cited briefing',note:'Analyst note',hypothesis:'Analyst hypothesis',callout:'Context & scope'})[block.type]||block.type);
      if(block.type==='heading')section=block.text;let excerpt=item?.text||item?.quote||block.text||(block.type==='article'?source?.text:'')||'';if(block.type==='table')excerpt=(block.rows||[]).slice(0,3).map(row=>row.join(' · ')).join(' / ');if(block.type==='map')excerpt='Source-stated relationships and labeled analyst hypotheses, with evidence and history.';if(block.type==='feed')excerpt=page.feed.paused?'Feed paused. Configure the page interests to receive coverage.':'Matching incoming coverage; featuring an article adds it to the curated page.';
      if(!excerpt&&!item&&!['table','map','feed','entity','page'].includes(block.type))return;
      const row=el('tr'),cell=el('td');cell.append(jumpLink((title||'Untitled section').slice(0,140),block.id),el('small',block.type+(item?' · '+item.nature.replaceAll('_',' ')+' · '+item.verification_state:'')));if(section&&block.type!=='heading')cell.append(el('small','In '+section));row.append(cell,el('td',String(excerpt).replace(/\s+/g,' ').slice(0,260)+(excerpt.length>260?'…':'')));table.append(row);
    });contents.append(table);if(!page.blocks.length)contents.append(el('p','Add a block or capture an article to begin.'));
  }
  const overviewTabs=[$('lw-summary-tab'),$('lw-contents-tab')];
  function selectOverview(index,focus=false){overviewTabs.forEach((tab,i)=>{tab.setAttribute('aria-selected',String(i===index));tab.tabIndex=i===index?0:-1;$(tab.getAttribute('aria-controls')).hidden=i!==index;});if(focus)overviewTabs[index].focus();}
  overviewTabs.forEach((tab,index)=>{tab.onclick=()=>selectOverview(index);tab.onkeydown=event=>{if(['ArrowRight','ArrowLeft','Home','End'].includes(event.key)){event.preventDefault();selectOverview(event.key==='Home'?0:event.key==='End'?1:1-index,true);}};});
  let overviewToken=token();
  $('lw-summary-regenerate').onclick=()=>{if(!page)return;const content=modal('Regenerate page overview'),label=el('label','Use configured AI model (sends curated passages, statements and notes to the configured provider)'),model=el('input');model.type='checkbox';model.checked=true;label.append(model);content.append(label,el('p','Generates from the curated page only. Incoming feed cards are excluded. Existing page sections remain unchanged. Without a connected model, a clearly labeled evidence digest is available.'));button('Compile page summary',async()=>{await save();if(dirty)throw Error('Save current edits before generating a summary.');status('Compiling page overview…');const result=await api('/api/workspaces/generate/'+page.id,'POST',{version:page.version,selected:[],token:overviewToken,use_model:model.checked,style:'briefing',target:'overview'});overviewToken=token();page=result;overviewStale=false;overviewLoadedSignature=overviewSignature();$('lw-dialog').close();renderOverview();status('Summary saved · revision '+page.version);selectOverview(0);},content);};
  function modal(title) { $('lw-dialog-content').replaceChildren(el('h2', title)); $('lw-dialog').showModal(); return $('lw-dialog-content'); }
  function formInput(parent, title, value = '', multiline = false) { const label = el('label', title), input = el(multiline ? 'textarea' : 'input'); input.value = value; label.append(input); parent.append(label); return input; }
  async function editItem(item) {
    const content = modal('Edit interpretation · source quote stays preserved');
    content.append(el('blockquote', item.quote)); const text = formInput(content, 'Statement or interpretation', item.text, true), note = formInput(content, 'Analyst note', item.note, true), supporting=formInput(content,'Supporting capture IDs (comma separated)',(item.supporting_item_ids||[]).join(', ')); let relation=item.relation?structuredClone(item.relation):null;if(relation){entitySelect(relation.subject_id,id=>relation.subject_id=id,content,'From entity');entitySelect(relation.object_id,id=>relation.object_id=id,content,'To entity');const pred=el('select');inventory.predicates.forEach(p=>{const o=el('option',p.replaceAll('_',' '));o.value=p;pred.append(o);});pred.value=relation.predicate;pred.onchange=()=>relation.predicate=pred.value;content.append(pred);const scope=formInput(content,'Crop / program scope',relation.scope||'');scope.oninput=()=>relation.scope=scope.value;content.append(el('p',relation.nature+' · changing a hypothesis into a source statement requires a separate capture.'));}
    button('Save revision', async () => { const result = await api('/api/workspaces/item/' + item.id, 'PATCH', {version: item.version, text: text.value, note: note.value,supporting_item_ids:supporting.value.split(',').map(s=>s.trim()).filter(Boolean),...(relation?{relation}: {})}); items[item.id] = result; $('lw-dialog').close(); render(); }, content);
    button('View history', () => showHistory(item.id), content);
  }
  async function placeElsewhere(item) {
    const content = modal('Reuse this knowledge item'), select = el('select'); inventory.pages.forEach(p => { const o = el('option', p.title); o.value = p.id; select.append(o); }); content.append(select);
    button('Add shared reference', async () => { const other = (await api('/api/workspaces/page/' + select.value)).page; other.blocks.push({id: 'b-' + token(), type: item.kind === 'article' ? 'article' : 'evidence', item_id: item.id, text: ''}); await api('/api/workspaces/page/' + other.id, 'PUT', other); $('lw-dialog').close(); status('Shared reference added'); }, content);
  }
  async function showHistory(key) { const data = await api('/api/workspaces/history/' + key), content = modal('Revision history'); data.revisions.forEach(row => { const details = el('details'); details.append(el('summary', 'Revision ' + row.version + ' · ' + row.actor + ' · ' + row.at), el('pre', JSON.stringify(JSON.parse(row.body), null, 2))); content.append(details); }); }
  function drawMap(host) {
    let external=[];const map = el('div', undefined, 'lw-map'), filter = el('input'), hypotheses = el('input'), statusSelect = el('select'), typeSelect = el('select'); filter.placeholder = 'Search or focus a neighborhood'; filter.setAttribute('aria-label', 'Map entity search'); hypotheses.type = 'checkbox'; hypotheses.checked = true;
    const hlabel = el('label', 'Show analyst hypotheses'); hlabel.append(hypotheses); ['All review states', 'unverified', 'verified_primary', 'disputed'].forEach(v => { const o = el('option', v); o.value = v; statusSelect.append(o); }); statusSelect.setAttribute('aria-label', 'Verification filter');
    ['All entity types', ...new Set(inventory.entities.map(e => e.type))].forEach(v => { const o = el('option', v); o.value = v; typeSelect.append(o); }); typeSelect.setAttribute('aria-label', 'Entity type filter');
    const expandLabel=el('label','Include related knowledge from outside this page'),expand=el('input');expand.type='checkbox';expandLabel.append(expand);expand.addEventListener('change',async()=>{external=expand.checked?(await api('/api/workspaces/related/'+page.id)).items:[];update();});map.append(filter, hlabel, statusSelect, typeSelect, expandLabel, el('p', 'Legend: solid = source statement; dashed = analyst hypothesis. Review state is labeled on every edge.', 'lw-muted')); const drawing = el('div'); map.append(drawing); host.append(map);
    function update() {
      drawing.replaceChildren(); const relations = [...Object.values(items),...external].filter(i => i.relation && !i.withdrawn && (hypotheses.checked || i.nature !== 'analyst_hypothesis') && (statusSelect.selectedIndex === 0 || i.verification_state === statusSelect.value)).filter(i => {
        const nodes = [chooseEntity(i.relation.subject_id), chooseEntity(i.relation.object_id)].filter(Boolean);
        return (!filter.value || nodes.some(n => (n.name + ' ' + n.id).toLowerCase().includes(filter.value.toLowerCase()))) && (typeSelect.selectedIndex === 0 || nodes.some(n => n.type === typeSelect.value));
      });
      if (!relations.length) { drawing.append(el('p', 'No recorded relationships in this page scope. Use “Link relationship” on a source passage. Co-mentions create no edges.')); return; }
      const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg'); svg.setAttribute('viewBox', '0 0 600 ' + Math.max(150, relations.length * 100)); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', 'Page relationships. Equivalent interactive table follows.');
      const table = el('table'), head = el('tr'); ['From → to', 'Relationship / status', 'Evidence'].forEach(t => head.append(el('th', t))); table.append(head);
      relations.forEach((item, i) => {
        const rel = item.relation, from = chooseEntity(rel.subject_id), to = chooseEntity(rel.object_id), speculative = item.nature === 'analyst_hypothesis', y = 35 + i * 100;
        const label = (speculative ? 'Potential ' : '') + rel.predicate.replaceAll('_', ' ') + (speculative ? ' — analyst hypothesis' : ' — source statement') + ' · ' + item.verification_state+(item.outside_page?' · OUTSIDE PAGE':'');
        const line = document.createElementNS(ns, 'line'); for (const [k,v] of Object.entries({x1:90,y1:y,x2:510,y2:y,class:speculative?'hypothesis':''})) line.setAttribute(k,v); line.setAttribute('tabindex','0');line.setAttribute('role','button');line.setAttribute('aria-label',label);line.style.cursor='pointer';const inspect=()=>item.canonical?location.assign('/evidence/'+item.evidence_ids[0]):editItem(item);line.addEventListener('click',inspect);line.addEventListener('keydown',e=>{if(e.key==='Enter')inspect();});svg.append(line);
        [[90,from],[510,to]].forEach(([x,n]) => { const circle = document.createElementNS(ns,'circle'); circle.setAttribute('cx',x); circle.setAttribute('cy',y); circle.setAttribute('r',12); const anchor=document.createElementNS(ns,'a');anchor.setAttribute('href',n&&!n.identity_state?'/entities/'+n.type+'/'+n.id:'/workspaces?entity='+n?.id);anchor.append(circle);svg.append(anchor); const text = document.createElementNS(ns,'text'); text.setAttribute('x',x === 90 ? 5 : 430); text.setAttribute('y',y+24); text.textContent = n?.name || 'Unresolved entity'; svg.append(text); });
        const text = document.createElementNS(ns,'text'); text.setAttribute('x',110); text.setAttribute('y',y-12); text.textContent = label; svg.append(text);
        const tr = el('tr'), nodes = el('td'); [from,to].forEach((n,index) => { if (index) nodes.append(document.createTextNode(' → ')); const a = el('a', n?.name || 'Unresolved'); a.href = n && !n.identity_state ? '/entities/' + n.type + '/' + n.id : '/workspaces?entity=' + n?.id; nodes.append(a); }); const evidence = el('td'); button('Inspect passage, notes & history', () => item.canonical?location.assign('/evidence/'+item.evidence_ids[0]):editItem(item), evidence); tr.append(nodes,el('td',label + (rel.scope ? ' · ' + rel.scope : '')),evidence); table.append(tr);
      }); drawing.append(svg,table);
    }
    [filter,hypotheses,statusSelect,typeSelect].forEach(e => e.addEventListener('input',update)); update();
  }
  function configureFeed() {
    if (!page) return; const content = modal('Configure this page’s feed'), config = structuredClone(page.feed), fields = ['entity_ids','berry_ids','technology_ids','topic_ids','geography_ids','source_ids','languages','keywords'], inputs = {};
    content.append(el('p', 'Alternatives within each field. Choose whether active fields match ANY or ALL. Scope stays fixed until you save it.'));
    const mode = el('select'); ['any','all'].forEach(v => { const o = el('option',v.toUpperCase() + ' active fields'); o.value=v;mode.append(o); }); mode.value=config.mode;content.append(mode);
    const pauseLabel = el('label','Pause feed'), pause = el('input');pause.type='checkbox';pause.checked=!!config.paused;pauseLabel.append(pause);content.append(pauseLabel);
    fields.forEach(k=> { inputs[k]=formInput(content,k.replaceAll('_',' ') + ' (comma separated IDs or words)',(config[k]||[]).join(', ')); });
    const suggestions = [...new Set([...Object.values(items).flatMap(i=>i.entity_ids||[]),...page.blocks.map(b=>b.entity_id).filter(Boolean)])];
    button('Suggest entities from page',()=>{inputs.entity_ids.value=suggestions.join(', ');},content);
    button('Save feed scope',async()=>{fields.forEach(k=>config[k]=inputs[k].value.split(',').map(s=>s.trim()).filter(Boolean));config.mode=mode.value;config.paused=pause.checked;page.feed=config;changed();await save();if(!dirty){$('lw-dialog').close();await refreshFeed(true);}},content);
  }
  function showFeed(cards) {
    const host=$('lw-feed-cards');host.replaceChildren(); feedCards=cards;
    cards.forEach(card=>{const box=el('article',undefined,'lw-feed-card');box.append(el('h3',card.title),el('p',card.publisher+' · Published '+(card.published_date||'unknown')+' · Discovered '+(card.discovered_date||'unknown')),el('p',card.matches.join(' · ')));
      const read=el('a','Read');read.href='/intelligence/'+card.id;box.append(read);
      button('Feature article',async()=>{await save();if(dirty)throw Error('Save current edits first');await api('/api/workspaces/capture','POST',{token:token(),page_id:page.id,article_id:card.id,kind:'article'});await load(page.id);},box);
      button('Annotate',async()=>{const source=await api('/api/workspaces/source/'+card.id);window.openLivingCapture({article_id:card.id,source_id:source.id,quote:'',kind:'note',page_id:page.id});},box);
      button('Dismiss on this page',()=>{page.dismissed.push(card.id);changed();showFeed(feedCards.filter(c=>c.id!==card.id));},box);host.append(box);
    });
  }
  async function refreshFeed(explicit=false) {
    if(!page)return;
    try{const data=await api('/api/workspaces/feed/'+page.id);$('lw-feed-status').textContent=data.state==='paused'?'Feed paused':'Last successful update '+new Date(data.last_success).toLocaleTimeString();
      if(explicit){showFeed(data.items);$('lw-updates').hidden=true;}
      else if(JSON.stringify(data.items)!==JSON.stringify(feedCards)){incoming=data.items;$('lw-updates').hidden=false;$('lw-updates').textContent='Coverage changed · show updates';}
    }catch(e){$('lw-feed-status').textContent='Feed update failed · '+e.message;}
  }
  async function createPage(nested) {
    const content=modal(nested?'New nested page':'New research page'),title=formInput(content,'Page title'), label=el('label','Use starter layout'),starter=el('input');starter.type='checkbox';starter.checked=true;label.append(starter);content.append(label);
    button('Create page',async()=>{const created=await api('/api/workspaces','POST',{token:createToken,title:title.value,parent_id:nested?page?.id:null,starter:starter.checked});createToken=token();location.assign('/workspaces/'+created.id);},content);
  }
  $('lw-new').onclick=()=>createPage(false);$('lw-nested').onclick=()=>createPage(true);$('lw-search').oninput=sidebar;$('lw-save').onclick=save;
  $('lw-title').oninput=()=>{page.title=$('lw-title').value;$('lw-title').style.height='auto';$('lw-title').style.height=$('lw-title').scrollHeight+'px';changed();};$('lw-config').onclick=configureFeed;$('lw-refresh').onclick=()=>refreshFeed(true);$('lw-updates').onclick=()=>{showFeed(incoming);$('lw-updates').hidden=true;};
  $('lw-add').onclick=()=>{const type=$('lw-type').value;page.blocks.push({id:'b-'+token(),type,text:'',...(type==='table'?{rows:[['Company','Source statement','Status'],['','','']]}:{})});changed();render();};
  $('lw-history').onclick=()=>page&&showHistory(page.id);
  $('lw-restore').onclick=()=>{const restored=JSON.parse(localStorage.getItem(recoveryKey()));restored.version=page.version;page=restored;$('lw-title').value=page.title;changed();render();$('lw-restore').hidden=true;status('Recovery draft restored. Compare with history before saving.');clearTimeout(timer);};
  let generateToken=token();$('lw-generate').onclick=()=>{const content=modal('Generate from curated material'),modelLabel=el('label','Use configured model (sends selected passages, statements and notes to the configured provider)'),useModel=el('input');useModel.type='checkbox';modelLabel.append(useModel);content.append(modelLabel);const style=el('select');['briefing','landscape'].forEach(v=>{const o=el('option',v);o.value=v;style.append(o);});content.append(style);content.append(el('p','Incoming feed cards are excluded. A new editable block preserves the selected evidence versions and citations.'));button('Generate new block',async()=>{await save();if(dirty)throw Error('Save current changes first');status('Generating cited draft…');await api('/api/workspaces/generate/'+page.id,'POST',{version:page.version,selected:[...selected],token:generateToken,use_model:useModel.checked,style:style.value});generateToken=token();$('lw-dialog').close();await load(page.id);},content);};
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  document.addEventListener('bios:workspace-captured',async event=>{const update=event.detail.page.id===page?.id?event.detail.page:event.detail.from_page?.id===page?.id?event.detail.from_page:null;if(!update)return;if(update.version<page.version){status('Capture already saved; current page revision retained');return;}if(dirty){status('A capture was saved. Save your recovery draft and reload to compare the new page revision.');return;}page=update;const keep=new Set(page.blocks.map(b=>b.id));document.querySelectorAll('#lw-blocks > .lw-block').forEach(box=>{if(!keep.has(box.id))box.remove();});const item=event.detail.item;if(item){items[item.id]=item;const id=event.detail.block_id;if(id&&!document.getElementById(id)){const box=el('section',undefined,'lw-block');box.id=id;box.append(el('p','New capture · unverified','lw-eyebrow'),el('blockquote',item.quote||item.text||'Saved article'));const a=el('a','Open capture for detailed editing');a.href='/workspaces/evidence/'+item.id;box.append(a);$('lw-blocks').append(box);}}materialUpdatedAt=page.content_updated_at||page.updated_at;renderOverview();status('Capture saved · revision '+page.version+' · reader position preserved');});
  (async()=>{inventory=await api('/api/workspaces');const datalist=el('datalist');datalist.id='lw-entity-options';inventory.entities.forEach(e=>{const o=el('option',e.name+' · '+e.type+(e.identity_state?' · unresolved':''));o.value=e.id;datalist.append(o);});document.body.append(datalist);sidebar();
    const entity=new URLSearchParams(location.search).get('entity');if(entity){const data=await api('/api/workspaces/entity/'+encodeURIComponent(entity));const content=modal('Linked analyst material · unverified');data.items.forEach(i=>{const a=el('a',i.text||i.quote||i.kind);a.href='/workspaces/evidence/'+i.id;content.append(a,el('p',i.nature+' · '+i.verification_state));});}
    const id=root.dataset.pageId;if(id)await load(id);else status('Choose a page or create one.');
  })().catch(error);
  setInterval(()=>{if(!document.hidden)refreshFeed();},30000);
})();
