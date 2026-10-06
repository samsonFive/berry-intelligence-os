(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const escape = value => String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeURL = value => { try { const u = new URL(value); return ['http:','https:'].includes(u.protocol) && !u.username && !u.password ? u.href : ''; } catch { return ''; } };
  const label = berry => ({'berry-blueberry':'Blueberry','berry-raspberry':'Raspberry','berry-strawberry':'Strawberry','berry-blackberry':'Blackberry'}[berry] || berry);
  const date = value => value ? new Date(value + 'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) : 'Date unknown';
  let records = [], countries = [], current = null, filtered = [], trust = 'unreviewed', query = '', selectedCompany = '', timer, gridScroll = 0, readerCollapsed = true;
  let companyRecords=[], activeCompany='company-costa-group-holdings', companyTab='overview';
  const profiles=window.buildEntityProfiles({getCompanies:()=>companyRecords,getQuery:()=>query,refresh:()=>render(),escape,safeURL});
  const companyLists=new Map(), listStorageKey='berry-design-company-lists-v1';
  let listFilter='', editingList='', membershipCompany='', memberQuery='', listOpener=null;
  try{const data=JSON.parse(localStorage.getItem(listStorageKey)||'{}');if(data.version===1&&Array.isArray(data.lists))for(const l of data.lists){if(l&&typeof l.id==='string'&&typeof l.name==='string'&&l.name.trim())companyLists.set(l.id,{id:l.id,name:l.name.trim().slice(0,60),members:new Set(Array.isArray(l.members)?l.members.filter(id=>typeof id==='string'):[]),archived:l.archived===true});}}catch{}
  const activeLists=()=>[...companyLists.values()].filter(l=>!l.archived).sort((a,b)=>a.name.localeCompare(b.name));
  const listsFor=id=>activeLists().filter(l=>l.members.has(id));
  function saveLists(){try{localStorage.setItem(listStorageKey,JSON.stringify({version:1,lists:[...companyLists.values()].map(l=>({...l,members:[...l.members]}))}));return true;}catch{toast('Lists updated for this session. Browser storage is unavailable.');return false;}}
  let companyLetter='', favoritesOnly=false, tierFilter='';
  const preferenceKey='berry-design-entity-preferences-v1', entityPreferences=new Map();
  const tierNames={tier1:'Tier 1',tier2:'Tier 2',tier3:'Tier 3'};
  try{const savedPrefs=JSON.parse(localStorage.getItem(preferenceKey)||'{}');if(savedPrefs.version===1)for(const [id,p] of Object.entries(savedPrefs.companies||{})){if(p&&typeof p==='object')entityPreferences.set(id,{favorite:p.favorite===true,tier:Object.hasOwn(tierNames,p.tier)?p.tier:''});}}catch{}
  const entityPreference=id=>entityPreferences.get(id)||{favorite:false,tier:''};
  const companyMatches=id=>(!listFilter||companyLists.get(listFilter)?.members.has(id))&&(!favoritesOnly||entityPreference(id).favorite)&&(!tierFilter||(tierFilter==='untiered'?!entityPreference(id).tier:entityPreference(id).tier===tierFilter));
  function saveEntityPreferences(){try{localStorage.setItem(preferenceKey,JSON.stringify({version:1,companies:Object.fromEntries(entityPreferences)}));return true;}catch{toast('Updated for this session. Browser storage is unavailable.');return false;}}
  function restoreMarkFocus(id,control,inProfile){const host=inProfile?$('#company-profile'):$('#company-rows');const target=host.querySelector(`[${control}="${CSS.escape(id)}"]`);(target||$('#favorites-filter')).focus({preventScroll:true});}
  function preferenceControls(c){const p=entityPreference(c.id);return `<div class="entity-mark-controls"><button data-favorite="${escape(c.id)}" aria-pressed="${p.favorite}" aria-label="${p.favorite?'Remove':'Add'} ${escape(c.name)} ${p.favorite?'from':'to'} favorites">${p.favorite?'★':'☆'}</button><select data-entity-tier="${escape(c.id)}" aria-label="Tier for ${escape(c.name)}"><option value="">Untiered</option>${Object.entries(tierNames).map(([v,n])=>`<option value="${v}" ${p.tier===v?'selected':''}>${n}</option>`).join('')}</select><button data-company-lists="${escape(c.id)}" aria-label="Manage watch lists for ${escape(c.name)}">Lists${listsFor(c.id).length?' '+listsFor(c.id).length:''}</button></div>`;}
  function preferenceBadges(c){const p=entityPreference(c.id);return `${p.favorite?'<span class="preference-badge">★ Favorite</span>':''}${p.tier?`<span class="preference-badge">${tierNames[p.tier]}</span>`:''}${listsFor(c.id).map(l=>`<button class="list-badge" data-filter-list="${escape(l.id)}" title="Filter by watch list: ${escape(l.name)}">${escape(l.name)}</button>`).join('')}`;}
  let dateFrom='', dateTo='', datePreset='all';
  const localISO=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const berries = new Set(), selectedCountries = new Set(), saved = new Set(), reactions = new Map();
  const regionExplorer=window.createRegionExplorer({getScope:()=>({countries:[...selectedCountries],berries:[...berries],companyMatches,selectedCompany}),refresh:()=>render(),escape,safeURL});
  function articleImage(r, reader=false) {
    const original = safeURL(r.image);
    const illustrative = !original && /^images\/[a-z-]+\.png$/.test(r.illustration || '');
    const src = original || (illustrative ? r.illustration : '');
    if (!src) return '';
    return `<figure class="${reader?'reader-figure':'story-figure'}"><img src="${escape(src)}" alt="${illustrative?'Illustrative berry agriculture image generated for this design preview':'Article preview'}" loading="${reader?'eager':'lazy'}" width="${reader?'900':'240'}" height="${reader?'500':'180'}" referrerpolicy="no-referrer">${illustrative?`<figcaption>${reader?'Illustrative image · generated for the design preview':'Illustration'}</figcaption>`:''}</figure>`;
  }
  function storyActions(r) {
    return `<div class="story-actions">${trust==='unreviewed'?`<button data-reaction="up" data-item-id="${escape(r.id)}" aria-pressed="${reactions.get(r.id)==='up'}" aria-label="Mark ${escape(r.title)} useful in preview">👍 <span>Useful</span></button><button data-reaction="down" data-item-id="${escape(r.id)}" aria-pressed="${reactions.get(r.id)==='down'}" aria-label="Mark ${escape(r.title)} not relevant in preview">👎</button>`:''}<button data-save="${escape(r.id)}" aria-pressed="${saved.has(r.id)}">${saved.has(r.id)?'✓ Saved':'＋ Save'}</button><button class="read-story" data-open="${escape(r.id)}">${current===r.id&&!readerCollapsed?'Reading':'Read story'} <span aria-hidden="true">↗</span></button></div>`;
  }
  function storyContext(r) {
    return `<div class="story-context">${r.companies.length?`<p class="preview-companies"><strong>Companies</strong> ${r.companies.map(c=>`${escape(c.name)} ${preferenceBadges(c)}`).join(' · ')}</p>`:''}<details class="preview-details"><summary>More context</summary><p><strong>Coverage</strong> ${escape(r.countries.map(c=>c.name).join(' · ') || 'Geography not tagged')}</p>${r.analysis?`<p class="preview-interpretation"><strong>Stored interpretation</strong> ${escape(r.analysis)}</p>`:''}</details></div>`;
  }
  function setReaderCollapsed(collapsed, returnFocus=false) {
    if (!collapsed && readerCollapsed) gridScroll = window.scrollY;
    readerCollapsed = collapsed;
    $('#workspace').classList.add('reader-collapsed');
    $('#workspace').classList.toggle('reader-open',!collapsed);
    $('#workspace').classList.remove('focus-reader','reader-wide');
    $('#reader-expand').setAttribute('aria-pressed','false');
    $('#reader-expand').setAttribute('aria-label','Expand Reader');
    $('#reader-toggle').setAttribute('aria-expanded',String(!collapsed));
    $('#reader-toggle').textContent = collapsed ? 'Open Reader' : 'Close Reader';
    render();
    if (collapsed) {
      window.scrollTo({top:gridScroll,behavior:'instant'});
      if(returnFocus) $(`.story[data-id="${CSS.escape(current || '')}"] .story-open`)?.focus({preventScroll:true});
    } else {
      $('#reader-collapse').focus({preventScroll:true});
    }
  }
  function toast(message) { $('#toast').textContent = message; $('#toast').classList.add('show'); clearTimeout(timer); timer=setTimeout(() => $('#toast').classList.remove('show'),3600); }
  function scopeRows() {
    return records.filter(r => ((!favoritesOnly&&!tierFilter&&!listFilter)||r.companies.some(c=>companyMatches(c.id))) && (!berries.size || r.berries.some(b => berries.has(b))) && (!selectedCountries.size || r.countries.some(c => selectedCountries.has(c.id))) && (!selectedCompany || r.companies.some(c => c.id === selectedCompany)) && (!query || [r.title,r.summary,r.source,...r.companies.map(c => c.name)].join(' ').toLowerCase().includes(query)) && (!dateFrom || (r.date && r.date>=dateFrom)) && (!dateTo || (r.date && r.date<=dateTo)));
  }
  function render() {
    $('#favorites-filter').setAttribute('aria-pressed',String(favoritesOnly));$('#favorites-filter').textContent=favoritesOnly?'★ Favorites only':'☆ Favorites only';$('#tier-filter').value=tierFilter;
    if(listFilter&&(!companyLists.has(listFilter)||companyLists.get(listFilter).archived))listFilter='';
    $('#watch-list-filter').innerHTML='<option value="">All companies</option>'+activeLists().map(l=>`<option value="${escape(l.id)}">${escape(l.name)} (${l.members.size})</option>`).join('');$('#watch-list-filter').value=listFilter;
    const scoped = scopeRows();
    $('#trusted-count').textContent = scoped.filter(r => r.facts.length).length;
    $('#raw-count').textContent = scoped.length;
    filtered = scoped.filter(r => trust === 'unreviewed' || r.facts.length);
    filtered.sort((a,b) => (b.date||'').localeCompare(a.date||'') || a.title.localeCompare(b.title));
    $('#date-label').textContent=datePreset==='all'?'All dates':datePreset==='7'?'Past 7 days':datePreset==='30'?'Past 30 days':datePreset==='ytd'?'Year to date':`${dateFrom || 'Any date'} – ${dateTo || 'Any date'}`;
    $$('[data-date-preset]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.datePreset===datePreset)));
    if (!filtered.some(r => r.id === current)) current = filtered[0]?.id || null;
    $('#feed-count').textContent = filtered.length;
    $('#reader-toggle').disabled = !filtered.length;
    const companyName = records.flatMap(r => r.companies).find(c => c.id === selectedCompany)?.name;
    $('#scope-chips').innerHTML = companyName ? `<button data-clear-company aria-label="Clear company filter">${escape(companyName)} ×</button>` : '';
    $('#feed-description').textContent = trust === 'trusted' ? 'Sources supporting active canonical facts' : 'Raw source view · human review remains separate';
    $('#sample-count').textContent = filtered.length + ' in sample';
    $('#country-label').textContent = selectedCountries.size ? [...selectedCountries].map(id => countries.find(c => c.id===id)?.name || id).join(', ') : 'All countries';
    if (selectedCountries.size > 2) $('#country-label').textContent = selectedCountries.size + ' countries';
    $$('[data-berry]').forEach(b => b.setAttribute('aria-pressed',String(b.dataset.berry ? berries.has(b.dataset.berry) : !berries.size)));
    $$('[data-trust]').forEach(b => b.setAttribute('aria-pressed',String(b.dataset.trust===trust)));
    $$('#country-options input').forEach(input => { input.checked = selectedCountries.has(input.value); });
    $('#stories').innerHTML = filtered.length ? filtered.map(r => `<article class="story ${r.id===current?'selected':''}" data-id="${escape(r.id)}"><div class="story-source"><span>${escape(r.source)}</span><time datetime="${escape(r.date)}">${escape(date(r.date))}</time></div><div class="story-main">${articleImage(r)}<div class="story-copy"><h3><button class="story-open" data-open="${escape(r.id)}" aria-pressed="${r.id===current}">${escape(r.title)}</button></h3><p class="story-excerpt">${escape(r.summary)}</p><div class="story-tags">${r.berries.map(b => `<span class="berry-label"><i class="berry-dot ${escape(b.replace('berry-',''))}"></i>${escape(label(b))}</span>`).join('')}<span>·</span><span>${escape(r.countries[0]?.name || 'Geography not tagged')}</span>${r.countries.length>1?`<span>+${r.countries.length-1}</span>`:''}</div></div></div>${storyContext(r)}${storyActions(r)}</article>`).join('') : '<div class="empty"><h3>No records in this scope.</h3><p>This curated sample has no matching content. This historical sample may have no articles in a recent date range. Try All dates or clear filters; missing coverage is not evidence of no market activity.</p><button data-reset>Clear filters</button></div>';
    renderReader();renderMapSummary();if(document.documentElement.dataset.view==='companies')renderCompanies();
    $$('#map [data-country]').forEach(path => { path.classList.toggle('selected', selectedCountries.has(path.dataset.country));path.classList.toggle('in-scope',filtered.some(r=>r.countries.some(c=>c.id===path.dataset.country)));path.classList.toggle('in-story',records.find(r=>r.id===current)?.countries.some(c=>c.id===path.dataset.country)) ;path.setAttribute('aria-pressed',String(selectedCountries.has(path.dataset.country))); });
    regionExplorer.render();
  }
  function readerText(text,chunk=false){
    const sentences=typeof Intl.Segmenter==='function'?[...new Intl.Segmenter('en',{granularity:'sentence'}).segment(String(text||''))].map(x=>x.segment.trim()).filter(Boolean):[String(text||'')];
    return chunk&&sentences.length>1&&String(text).length>230?`<ul class="reader-context-points">${sentences.map(sentence=>`<li>${escape(sentence)}</li>`).join('')}</ul>`:`<p>${escape(text)}</p>`;
  }
  let readerMode='article';
  const articleBodies=new Map();
  function readerArticle(r){
    if(readerCollapsed)return '';
    const body=articleBodies.get(r.id);
    if(!body){articleBodies.set(r.id,{state:'loading'});fetch('/__reader/article?id='+encodeURIComponent(r.id)).then(response=>{if(!response.ok)throw Error();return response.json();}).then(data=>{articleBodies.set(r.id,data);if(current===r.id&&readerMode==='article')renderReader();}).catch(()=>{articleBodies.set(r.id,{state:'unavailable'});if(current===r.id&&readerMode==='article')renderReader();});}
    if(!body||body.state==='loading')return '<div class="article-loading" role="status">Loading article…</div>';
    if(body.state!=='available'||!Array.isArray(body.paragraphs)||!body.paragraphs.length)return `<section class="article-unavailable"><h3>Article unavailable here</h3><p>This publisher's article could not be loaded into the Reader. You can open the original separately or read the brief.</p><div>${safeURL(r.url)?`<a href="${escape(safeURL(r.url))}" target="_blank" rel="noopener noreferrer">Open original article ↗</a>`:''}<button data-reader-mode="brief">Read brief</button><button data-retry-article="${escape(r.id)}">Try again</button></div></section>`;
    return `<article class="original-article-text" aria-label="Article text"><div class="article-byline"><strong>Article</strong><span>${body.author?escape(body.author)+' · ':''}${escape(r.source)}</span></div>${body.paragraphs.map(p=>`<p>${escape(p)}</p>`).join('')}</article>`;
  }
  function readerActionIcon(name){
    const paths={up:'<path d="M7 10v11H3V10zM7 10l4-7c.5-.9 2-.5 2 1v5h5.5a2 2 0 0 1 2 2.4l-1.3 7a3 3 0 0 1-3 2.6H7"/>',down:'<path d="M7 14V3H3v11zM7 14l4 7c.5.9 2 .5 2-1v-5h5.5a2 2 0 0 0 2-2.4l-1.3-7a3 3 0 0 0-3-2.6H7"/>',save:'<path d="M4 3h13l4 4v14H3V3z"/><path d="M7 3v6h10V3M7 21v-8h10v8"/><path d="M14 5v2"/>',original:'<path d="M5 4h16v15a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8h2zM5 8v11"/><path d="M9 8h8M9 11h8M9 15h3M15 15h2M9 18h3M15 18h2"/>'};
    return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name]}</svg>`;
  }
  function readerActionTooltip(id,text){return `<span class="reader-action-tooltip" role="tooltip" id="${id}">${escape(text)}</span>`;}
  function renderReader() {
    const r = records.find(r => r.id===current);
    if (!r) { $('#reader').innerHTML='<div class="empty"><h3>Choose a story to investigate.</h3><p>Adjust the scope to see available source records.</p></div>';$('#companies').innerHTML='<p class="context-footnote">Company connections appear with a selected story.</p>';return; }
    const url = safeURL(r.url), reaction = reactions.get(r.id);
    $('#reader').innerHTML = `
      <div class="reader-source"><span class="source-tile">${escape(r.source.split(' ').map(s=>s[0]).join('').slice(0,3))}</span><span><strong>${escape(r.source)}</strong>Published ${escape(date(r.date))}</span></div>
      <h2 class="reader-headline">${escape(r.title)}</h2>
      <div class="reader-tags"><span class="tag ${trust==='trusted'?'trusted':'raw'}">${trust==='trusted'?'Reviewed statements linked':'Unreviewed'}</span>${r.berries.map(b=>`<span class="tag">${escape(label(b))}</span>`).join('')}</div>
      <div class="reader-actions reader-icon-actions" role="group" aria-label="Article actions">${trust==='unreviewed'?`<button class="reader-icon-action" data-reaction="up" aria-pressed="${reaction==='up'}" aria-label="Useful" aria-describedby="reader-useful-tip">${readerActionIcon('up')}${readerActionTooltip('reader-useful-tip','Mark this article as useful')}</button><button class="reader-icon-action" data-reaction="down" aria-pressed="${reaction==='down'}" aria-label="Not relevant" aria-describedby="reader-not-relevant-tip">${readerActionIcon('down')}${readerActionTooltip('reader-not-relevant-tip','Mark this article as not relevant')}</button>`:''}<button class="reader-icon-action" id="save-story" aria-pressed="${saved.has(r.id)}" aria-label="${saved.has(r.id)?'Unsave story':'Save story'}" aria-describedby="reader-save-tip">${readerActionIcon('save')}${readerActionTooltip('reader-save-tip',saved.has(r.id)?'Remove story from saved items':'Save this story')}</button>${url?`<a class="reader-icon-action reader-original-action" href="${escape(url)}" target="_blank" rel="noopener noreferrer" aria-label="Read original article (opens in a new tab)" aria-describedby="reader-original-tip">${readerActionIcon('original')}${readerActionTooltip('reader-original-tip','Read original article · opens in a new tab')}</a>`:''}</div>
      <div class="reader-view-switch" role="group" aria-label="Reader view"><button data-reader-mode="article" aria-pressed="${readerMode==='article'}">Article</button><button data-reader-mode="brief" aria-pressed="${readerMode==='brief'}">Brief</button></div>
      ${readerMode==='article'?readerArticle(r):`      <section class="article-summary reader-summary-block"><div class="reader-section-heading"><h3>Article summary</h3></div><p class="reader-deck">${escape(r.summary)}</p></section>
      ${articleImage(r,true)}
      ${r.facts.length?`<section class="reader-section reader-escalated"><div class="reader-section-heading"><h3>Key statements</h3><span class="reader-record-count">${r.facts.length} linked ${r.facts.length===1?'statement':'statements'}</span></div>${r.facts.map(f=>`<div class="${f.classification==='claim'?'claim-box':'fact-box'}"><div class="statement-heading"><strong>${escape(f.classification).toUpperCase()}</strong>${f.classification==='claim'?'<span>Reported claim · not independently verified</span>':''}</div><p>${escape(f.text)}</p></div>`).join('')}</section>`:''}
      ${r.companies.length?`<section class="reader-section reader-related"><div class="reader-section-heading"><h3>Companies in this story</h3><span class="reader-record-count">${r.companies.length}</span></div><div class="reader-company-cards">${r.companies.map(c=>`<div class="reader-company-card"><a href="http://127.0.0.1:18321/entities/company/${encodeURIComponent(c.id)}" target="_blank" rel="noopener">${escape(c.name)} <span aria-hidden="true">↗</span></a><div class="reader-company-marks">${preferenceBadges(c)}</div><button class="reader-list-edit" data-company-lists="${escape(c.id)}" aria-label="Manage watch lists for ${escape(c.name)}">Edit lists</button></div>`).join('')}</div></section>`:''}
      <div class="reader-supporting-notes">${r.analysis?`<details class="reader-coverage-note"><summary>About this coverage</summary><div class="coverage-note-body"><p class="coverage-note-label">An interpretation of the coverage, not a verified fact.</p>${readerText(r.analysis,true)}</div></details>`:''}<details class="reader-source-details"><summary>Source details</summary><div class="coverage-note-body"><p>${escape(r.source)} · Published ${escape(date(r.date))}</p>${!r.facts.length?'<p>No reviewed statements linked in this preview.</p>':''}${url?`<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">Read original source ↗</a>`:''}<details class="reader-record-reference"><summary>Record reference</summary><p>${escape(r.id)}</p></details></div></details></div>`}`;
    $('#companies').innerHTML = r.companies.length ? r.companies.slice(0,5).map(c => `<div class="company-row"><span class="company-monogram">${escape(c.name.split(' ').map(s=>s[0]).join('').slice(0,2))}</span><div><a href="http://127.0.0.1:18321/entities/company/${encodeURIComponent(c.id)}" target="_blank" rel="noopener">${escape(c.name)}</a><small>Linked in this source</small></div><span class="arrow">↗</span></div>`).join('') : '<p class="context-footnote">No company entity is linked to this source.</p>';
  }
  function renderCompanies() {
    const country=$('#company-country').value, role=$('#company-role').value;
    const initial=c=>{const first=c.name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').charAt(0).toUpperCase();return /^[A-Z]$/.test(first)?first:'#';};
    const scoped=companyRecords.filter(c=>companyMatches(c.id)&&(!berries.size||c.berries.some(b=>berries.has(b)))&&(!country||c.country===country)&&(!role||c.roles.includes(role))&&(!query||[c.name,...c.aliases,c.description].join(' ').toLowerCase().includes(query))).sort((a,b)=>a.name.localeCompare(b.name));
    const available=new Set(scoped.map(initial));
    $('#company-alphabet').innerHTML=['','ABCDEFGHIJKLMNOPQRSTUVWXYZ#'.split('')].flat().map(letter=>`<button data-letter="${letter}" aria-pressed="${companyLetter===letter}" ${letter&&!available.has(letter)?'disabled':''}>${letter||'All'}</button>`).join('');
    const list=scoped.filter(c=>!companyLetter||initial(c)===companyLetter);
    if(!list.some(c=>c.id===activeCompany))activeCompany=list[0]?.id;
    $('#company-total').textContent=`${list.length} of ${companyRecords.length} companies${companyLetter?' · '+companyLetter:''}`;
    const oldScroll=$('#company-rows').scrollTop;
    $('#company-rows').innerHTML=list.length?list.map(c=>`<div class="entity-row ${activeCompany===c.id?'is-selected':''}"><button class="entity-name" data-entity="${escape(c.id)}" aria-pressed="${activeCompany===c.id}">${profiles.logo(c)}<span><strong>${escape(c.name)}</strong><small>${escape(c.roles.slice(0,3).map(r=>r.replaceAll('_',' ')).join(' · ')||'Roles not recorded')}</small><span class="entity-berries">${c.berries.map(b=>`<i class="berry-dot ${escape(b.replace('berry-',''))}" title="${escape(label(b))}"></i><span>${escape(label(b))}</span>`).join('')}</span></span></button><span class="entity-country">${escape(c.country)}</span><span class="entity-evidence">${c.evidence_count}<small>linked records</small></span>${preferenceControls(c)}</div>`).join(''):'<div class="empty"><h3>No matching companies.</h3><p>Adjust the alphabet, watch list, favorite, tier, berry, country, role or search filters.</p><button data-clear-company-filters>Clear company filters</button></div>';
    $('#company-rows').scrollTop=oldScroll;
    const c=companyRecords.find(c=>c.id===activeCompany);
    if(!c){$('#company-profile').innerHTML='<div class="empty">Select a company to open its profile.</div>';return;}
    const stories=records.filter(r=>r.companies.some(x=>x.id===c.id));
    const rels=c.relationships;
    const sourceLinks=ids=>(ids||[]).slice(0,2).map(id=>`<a href="http://127.0.0.1:18321/evidence/${encodeURIComponent(id)}" target="_blank" rel="noopener">Source ↗</a>`).join(' ');
    let body='';
    if(companyTab==='overview')body=`<section class="company-section"><h3>Company overview <span>Entity metadata</span></h3><p class="company-description">${escape(c.description||'No description recorded.')}</p><dl class="company-metadata"><div><dt>Recorded country</dt><dd>${escape(c.country)}</dd></div><div><dt>Headquarters</dt><dd>${escape(c.headquarters)}</dd></div></dl><div class="company-role-tags">${c.roles.map(r=>`<span>${escape(r.replaceAll('_',' '))}</span>`).join('')}</div></section><section class="company-section"><h3>Stored statements <span>${c.facts.length} active records</span></h3>${c.facts.length?c.facts.slice(0,3).map(f=>`<article class="company-statement"><span class="tag ${f.classification==='claim'?'raw':'trusted'}">${escape(f.classification||'Unclassified')}</span><p>${escape(f.statement)}</p><div>${sourceLinks(f.evidence_ids)}</div></article>`).join(''):'<p class="company-gap">No active statements linked in the published entity record.</p>'}</section><section class="company-section"><h3>Connections <span>${rels.length} active relationships</span></h3>${rels.slice(0,3).map(r=>`<div class="relationship-line"><strong>${escape(r.subject)}</strong><span>${escape(r.predicate.replaceAll('_',' '))} →</span><strong>${escape(r.object)}</strong></div>`).join('')||'<p class="company-gap">No active relationships linked.</p>'}<button class="company-inline" data-company-tab="connections">View all connections →</button></section>`;
    if(companyTab==='news')body=`<section class="company-section"><h3>Related news <span>${stories.length} in this design sample</span></h3><p class="company-gap">The preview includes a small historical sample. The full dossier contains the published source inventory.</p>${stories.map(r=>`<article class="company-news">${articleImage(r)}<div><small>${escape(r.source)} · ${escape(date(r.date))}</small><h3><button data-company-news="${escape(r.id)}">${escape(r.title)}</button></h3><p>${escape(r.summary)}</p></div></article>`).join('')||'<p class="company-gap">No matching articles in this preview. This does not mean the company has no news.</p>'}</section>`;
    if(companyTab==='connections')body=`<section class="company-section"><h3>Relationship register <span>Stored links, not inferred</span></h3>${rels.map(r=>`<article class="relationship-record"><div class="relationship-line"><strong>${escape(r.subject)}</strong><span>${escape(r.predicate.replaceAll('_',' '))} →</span><strong>${escape(r.object)}</strong></div><div>${sourceLinks(r.evidence_ids)}</div></article>`).join('')||'<p class="company-gap">No active relationships linked to this entity.</p>'}</section>`;
    if(companyTab==='people')body=profiles.companyPeopleMarkup();
    $('#company-profile').innerHTML=`<header class="company-profile-header"><span class="eyebrow">COMPANY DOSSIER · ${escape(c.status)}</span><div class="company-title">${profiles.logo(c,true)}<h2>${escape(c.name)}</h2></div><p>${c.berries.map(b=>`<span class="tag">${escape(label(b))}</span>`).join('')}<span class="company-country-label">${escape(c.country)}</span></p><div class="profile-preferences"><span>Your company marks</span>${preferenceControls(c)}</div><div class="company-profile-actions"><button data-edit-company="${escape(c.id)}">Edit details & logo</button><button data-company-news="">View company news →</button><a href="http://127.0.0.1:18321/entities/company/${encodeURIComponent(c.id)}" target="_blank" rel="noopener">Full existing dossier ↗</a></div></header><nav class="company-tabs" aria-label="Company sections">${['overview','news','people','connections'].map(t=>`<button data-company-tab="${t}" aria-pressed="${t===companyTab}">${t[0].toUpperCase()+t.slice(1)}${t==='news'?` <span>${stories.length}</span>`:''}</button>`).join('')}</nav><div class="company-profile-body">${companyTab==='overview'?profiles.companyDetails(c)+regionExplorer.companyMarkup(c):''}${body}<p class="company-provenance">Published repository snapshot · Metadata, facts and claims retain their separate roles. Source-link counts describe records, not confidence.</p></div>`;
    if(companyTab==='people')profiles.renderPeople(c.id);
  }
  function renderListMembers() {
    const l=companyLists.get(editingList);if(!l||!$('#list-member-rows'))return;
    const rows=companyRecords.filter(c=>!memberQuery||[c.name,...c.aliases].join(' ').toLowerCase().includes(memberQuery)).sort((a,b)=>Number(l.members.has(b.id))-Number(l.members.has(a.id))||a.name.localeCompare(b.name));
    $('#list-member-rows').innerHTML=rows.length?rows.map(c=>`<label><input type="checkbox" data-list-member="${escape(c.id)}" ${l.members.has(c.id)?'checked':''}><span>${escape(c.name)}<small>${escape(c.country)}</small></span></label>`).join(''):'<p class="company-gap">No companies match this search.</p>';
  }
  function renderListDialog() {
    const lists=activeLists();
    if(!lists.some(l=>l.id===editingList))editingList=lists[0]?.id||'';
    const target=companyRecords.find(c=>c.id===membershipCompany)||records.flatMap(r=>r.companies).find(c=>c.id===membershipCompany);
    const create=`<form id="create-list-form"><label for="new-list-name">New watch list</label><div><input id="new-list-name" maxlength="60" required placeholder="e.g. Genetics partnerships" autocomplete="off"><button type="submit">${membershipCompany?'Create & add company':'Create list'}</button></div></form><p id="list-error" role="alert"></p>`;
    if(membershipCompany){
      $('#watch-list-body').innerHTML=`<h3 class="membership-title">Lists for ${escape(target?.name||membershipCompany)}</h3><p class="company-gap">Select any number of lists. Changes save immediately.</p><div class="membership-options">${lists.length?lists.map(l=>`<label><input type="checkbox" data-company-list="${escape(l.id)}" ${l.members.has(membershipCompany)?'checked':''}><span>${escape(l.name)}</span><small>${l.members.size} ${l.members.size===1?'company':'companies'}</small></label>`).join(''):'<p class="company-gap">No watch lists yet. Create your first list below.</p>'}</div>${create}<button class="company-inline" id="all-lists-manage">Manage all lists →</button>`;
      return;
    }
    const l=companyLists.get(editingList), archived=[...companyLists.values()].filter(x=>x.archived);
    $('#watch-list-body').innerHTML=`<div class="watch-list-layout"><section class="watch-list-inventory"><h3>Your watch lists</h3>${lists.map(x=>`<button data-edit-list="${escape(x.id)}" aria-pressed="${x.id===editingList}"><span>${escape(x.name)}</span><small>${x.members.size} ${x.members.size===1?'company':'companies'}</small></button>`).join('')||'<p class="company-gap">Create a list to group companies you want to watch together.</p>'}${create}${archived.length?`<details class="archived-lists"><summary>Archived lists (${archived.length})</summary>${archived.map(x=>`<div><span>${escape(x.name)}</span><button data-restore-list="${escape(x.id)}">Restore</button></div>`).join('')}</details>`:''}</section><section class="watch-list-editor">${l?`<form id="rename-list-form"><label for="edit-list-name">List name</label><div><input id="edit-list-name" value="${escape(l.name)}" maxlength="60" required><button type="submit">Rename</button></div></form><div class="list-editor-actions"><button data-view-list="${escape(l.id)}">View companies →</button><button data-archive-list="${escape(l.id)}">Archive list</button></div><label class="member-search">Add or remove companies · members first<input id="list-member-search" type="search" value="${escape(memberQuery)}" placeholder="Search names or aliases"></label><div id="list-member-rows"></div>`:'<div class="empty"><h3>Build a focused watch.</h3><p>A company can belong to several lists. Favorites and tiers remain independent.</p></div>'}</section></div>`;
    renderListMembers();
  }
  function openLists(companyId,opener) {
    membershipCompany=companyId||'';memberQuery='';listOpener={element:opener,companyId,profile:!!opener.closest('#company-profile'),reader:!!opener.closest('#reader')};renderListDialog();$('#watch-lists').showModal();
  }
  function validListName(raw,except='') {
    const name=raw.trim().replace(/\s+/g,' ');
    if(!name||name.length>60){$('#list-error').textContent='Use a list name between 1 and 60 characters.';return '';}
    if([...companyLists.values()].some(l=>l.id!==except&&l.name.toLowerCase()===name.toLowerCase())){$('#list-error').textContent='A list with this name already exists. Check archived lists too.';return '';}
    return name;
  }
  function renderMapSummary() {
    window.renderMarketStatistics({countries:[...selectedCountries],berries:[...berries],countryNames:countries});
    const counts = new Map();
    filtered.forEach(r => r.countries.forEach(c => counts.set(c.id,(counts.get(c.id)||0)+1)));
    const tagged=filtered.filter(r=>r.countries.length).length;
    $('#map-coverage').textContent=tagged+' mapped stories · '+(filtered.length-tagged)+' without geographic tags in this sample';
    const params=new URLSearchParams();if(berries.size)params.set('berry',[...berries].join(','));if(selectedCountries.size)params.set('countries',[...selectedCountries].join(','));$('#existing-explorer').href='http://127.0.0.1:18321/explorer?'+params;
    const rows = countries.filter(c=>counts.has(c.id)).sort((a,b)=>counts.get(b.id)-counts.get(a.id)).slice(0,4);
    const max = Math.max(1,...counts.values());
    $('#geography-summary').innerHTML = rows.length ? rows.map(c=>`<button class="geo-row" data-geo="${escape(c.id)}" aria-label="${escape(c.name)}, ${counts.get(c.id)} source records. Toggle country selection."><span>${escape(c.name)}</span><span class="bar"><i style="width:${counts.get(c.id)/max*100}%"></i></span><b>${counts.get(c.id)}</b></button>`).join('') : '<p class="context-footnote">No tagged geography in this scope.</p>';
  }
  function reset() {listFilter='';favoritesOnly=false;tierFilter='';companyLetter='';berries.clear();selectedCountries.clear();query='';selectedCompany='';$('#search').value='';dateFrom='';dateTo='';datePreset='all';$('#date-from').value='';$('#date-to').value='';$('#date-error').textContent='';render();}
  function toggleCountry(id) {selectedCountries.has(id)?selectedCountries.delete(id):selectedCountries.add(id);render();}
  function openStory(id,focus=false) {readerMode='article';current=id;if(readerCollapsed)setReaderCollapsed(false);else render();$('#reader').scrollTop=0;if(focus && matchMedia('(max-width:720px)').matches) $('.reader-panel').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});}
  function move(step) {if(!filtered.length)return;const index=filtered.findIndex(r=>r.id===current);openStory(filtered[(index+step+filtered.length)%filtered.length].id);}
  document.addEventListener('click',event=>{
    const b=event.target.closest('button');if(!b)return;
    if(b.id==='manage-watch-lists')openLists('',b);
    if(b.dataset.companyLists)openLists(b.dataset.companyLists,b);
    if(b.id==='all-lists-manage'){membershipCompany='';renderListDialog();}
    if(b.dataset.editList){editingList=b.dataset.editList;memberQuery='';renderListDialog();$('#edit-list-name').focus();}
    if(b.dataset.filterList){listFilter=b.dataset.filterList;companyLetter='';render();}
    if(b.dataset.viewList){listFilter=b.dataset.viewList;companyLetter='';$('#watch-lists').close();$('.primary-nav [data-view=companies]').click();}
    if(b.dataset.archiveList){const l=companyLists.get(b.dataset.archiveList);if(l){l.archived=true;if(listFilter===l.id)listFilter='';saveLists();render();renderListDialog();toast('List archived. Restore it from Manage lists.');}}
    if(b.dataset.restoreList){const l=companyLists.get(b.dataset.restoreList);if(l){l.archived=false;editingList=l.id;saveLists();render();renderListDialog();}}
    if(b.hasAttribute('data-letter')){companyLetter=b.dataset.letter;renderCompanies();$('#company-rows').scrollTop=0;$(`#company-alphabet [data-letter="${CSS.escape(companyLetter)}"]`)?.focus({preventScroll:true});}
    if(b.dataset.favorite){const inProfile=!!b.closest('#company-profile'),id=b.dataset.favorite,p=entityPreference(id);entityPreferences.set(id,{...p,favorite:!p.favorite});const persisted=saveEntityPreferences();render();restoreMarkFocus(id,'data-favorite',inProfile);if(persisted)toast('Company favorite updated in this browser. Tier is unchanged.');}
    if(b.id==='favorites-filter'){favoritesOnly=!favoritesOnly;companyLetter='';render();}
    if(b.dataset.datePreset){datePreset=b.dataset.datePreset;const today=new Date();dateTo=datePreset==='all'?'':localISO(today);const start=new Date(today);if(datePreset==='ytd')start.setMonth(0,1);else if(datePreset!=='all')start.setDate(start.getDate()-Number(datePreset)+1);dateFrom=datePreset==='all'?'':localISO(start);$('#date-from').value=dateFrom;$('#date-to').value=dateTo;$('#date-error').textContent='';$('#date-picker').open=false;render();}
    if(b.dataset.theme){document.documentElement.dataset.theme=b.dataset.theme;$$('[data-theme]').filter(x=>x.tagName==='BUTTON').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));$('#direction-note').innerHTML=b.dataset.theme==='daylight'?'<strong>Daylight</strong><br>Crisp surfaces. Calm color. Space for the work.':'<strong>Glasshouse</strong><br>Layered light. Berry color. A living workspace.';}
    if(b.dataset.view){const view=b.dataset.view;const placeholder=view==='companies'?'Search companies and aliases':view==='people'?'Search people, roles and companies':'Search this workspace';$('#search').placeholder=placeholder;$('#search').setAttribute('aria-label',placeholder);document.documentElement.dataset.view=view;$('#workspace').classList.remove('focus-reader','reader-wide');$('#reader-expand').setAttribute('aria-pressed','false');$$('.primary-nav [data-view]').forEach(x=>{x.dataset.view===(view==='people'?'companies':view)?x.setAttribute('aria-current','page'):x.removeAttribute('aria-current');});$$('.entity-sections [data-view]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.view===view)));$('#workspace-title').textContent=({news:'News, in focus.',companies:'Entities / Companies',people:'Entities / People',explore:'Map Explorer'})[view];render();}
    if(b.dataset.entity){activeCompany=b.dataset.entity;companyTab='overview';renderCompanies();if(matchMedia('(max-width:900px)').matches)$('#company-profile').scrollIntoView({block:'start'});}
    if(b.dataset.companyTab){companyTab=b.dataset.companyTab;renderCompanies();}
    if(b.id==='company-clear'||b.hasAttribute('data-clear-company-filters')){listFilter='';companyLetter='';favoritesOnly=false;tierFilter='';$('#company-country').value='';$('#company-role').value='';query='';$('#search').value='';berries.clear();render();}
    if(b.hasAttribute('data-company-news')){$('#search').placeholder='Search this workspace';$('#search').setAttribute('aria-label','Search stories, companies and summaries');selectedCompany=activeCompany;query='';$('#search').value='';selectedCountries.clear();trust='unreviewed';document.documentElement.dataset.view='news';$('#workspace-title').textContent='News, in focus.';$$('.primary-nav [data-view]').forEach(x=>x.dataset.view==='news'?x.setAttribute('aria-current','page'):x.removeAttribute('aria-current'));if(b.dataset.companyNews){readerMode='article';current=b.dataset.companyNews;setReaderCollapsed(false);}else{setReaderCollapsed(true);} }
    if(b.hasAttribute('data-berry')){const v=b.dataset.berry;if(!v)berries.clear();else berries.has(v)?berries.delete(v):berries.add(v);render();}
    if(b.dataset.trust){trust=b.dataset.trust;render();}
    if(b.dataset.open)openStory(b.dataset.open,true);
    if(b.dataset.geo)toggleCountry(b.dataset.geo);
    if(b.dataset.company){selectedCompany=b.dataset.company;$('#entity-dialog').close();query='';$('#search').value='';render();toast('Company filter applied. Reset clears the scope.');}
    if(b.dataset.readerMode){readerMode=b.dataset.readerMode;renderReader();$('#reader').scrollTop=0;$(`.reader-view-switch [data-reader-mode="${readerMode}"]`)?.focus({preventScroll:true});}
    if(b.dataset.retryArticle){articleBodies.delete(b.dataset.retryArticle);renderReader();}
    if(b.dataset.reaction){const readerAction=!!b.closest('.reader-icon-actions'),action=b.dataset.reaction;const itemId=b.dataset.itemId||current;reactions.get(itemId)===b.dataset.reaction?reactions.delete(itemId):reactions.set(itemId,b.dataset.reaction);render();toast('Feedback updated in this preview.');if(readerAction)$(`#reader .reader-icon-action[data-reaction="${action}"]`)?.focus({preventScroll:true});}
    if(b.id==='save-story'||b.dataset.save){const itemId=b.dataset.save||current;saved.has(itemId)?saved.delete(itemId):saved.add(itemId);render();toast(saved.has(itemId)?'Saved in this preview.':'Removed from preview saves.');if(b.id==='save-story')$('#save-story')?.focus({preventScroll:true});}
    if(b.hasAttribute('data-reset')||b.id==='reset')reset();
    if(b.hasAttribute('data-clear-company')){selectedCompany='';render();}
    if(b.id==='clear-countries'||b.id==='map-reset'){selectedCountries.clear();render();}
    if(b.id==='reader-next')move(1);
    if(b.id==='reader-collapse')setReaderCollapsed(true,true);
    if(b.id==='reader-toggle')setReaderCollapsed(!readerCollapsed,true);
    if(b.id==='reader-back'){$('#workspace').classList.remove('focus-reader','reader-wide');$('.feed-panel').scrollIntoView({block:'start'});}
    if(b.id==='reader-expand'){const on=$('#workspace').classList.toggle('reader-wide');b.setAttribute('aria-pressed',String(on));b.setAttribute('aria-label',on?'Restore workspace':'Expand Reader');}
    if(b.id==='mission-open')$('#mission').showModal();
    if(b.id==='entities-open')$('#entity-dialog').showModal();
    if(b.id==='about-open'||b.id==='about-footer')$('#about').showModal();
    if(b.hasAttribute('data-close'))b.closest('dialog').close();
  });
  $('#watch-lists').addEventListener('close',()=>{const o=listOpener;if(!o)return;const host=o.profile?$('#company-profile'):o.reader?$('#reader'):$('#company-rows');const target=o.element?.isConnected?o.element:o.companyId?host.querySelector(`[data-company-lists="${CSS.escape(o.companyId)}"]`):null;(target||$('#manage-watch-lists')).focus({preventScroll:true});});
  $('#watch-list-body').addEventListener('submit',e=>{e.preventDefault();if(e.target.id==='create-list-form'){const name=validListName($('#new-list-name').value);if(!name)return;const id='list-'+crypto.randomUUID();companyLists.set(id,{id,name,members:new Set(membershipCompany?[membershipCompany]:[]),archived:false});editingList=id;const persisted=saveLists();render();renderListDialog();if(persisted)toast(membershipCompany?'List created and company added.':'Watch list created.');}else if(e.target.id==='rename-list-form'){const name=validListName($('#edit-list-name').value,editingList);if(!name)return;companyLists.get(editingList).name=name;saveLists();render();renderListDialog();}});
  $('#watch-list-body').addEventListener('input',e=>{if(e.target.id==='list-member-search'){memberQuery=e.target.value.trim().toLowerCase();renderListMembers();}});
  $('#watch-list-body').addEventListener('change',e=>{let l,id,selector;if(e.target.dataset.companyList){l=companyLists.get(e.target.dataset.companyList);id=membershipCompany;selector=`[data-company-list="${CSS.escape(l.id)}"]`;}else if(e.target.dataset.listMember){l=companyLists.get(editingList);id=e.target.dataset.listMember;selector=`[data-list-member="${CSS.escape(id)}"]`;}if(!l||!id)return;e.target.checked?l.members.add(id):l.members.delete(id);saveLists();render();renderListDialog();$('#watch-list-body').querySelector(selector)?.focus({preventScroll:true});});
  $('#watch-list-filter').addEventListener('change',e=>{listFilter=e.target.value;companyLetter='';render();});
  $('#tier-filter').addEventListener('change',e=>{tierFilter=e.target.value;companyLetter='';render();});
  document.addEventListener('change',e=>{if(!e.target.matches('[data-entity-tier]'))return;const inProfile=!!e.target.closest('#company-profile'),id=e.target.dataset.entityTier,tier=e.target.value;if(tier&&!Object.hasOwn(tierNames,tier))return;entityPreferences.set(id,{...entityPreference(id),tier});const persisted=saveEntityPreferences();render();restoreMarkFocus(id,'data-entity-tier',inProfile);if(persisted)toast('Company tier updated in this browser. Favorite is unchanged.');});
  $('#search').addEventListener('input',e=>{companyLetter='';query=e.target.value.trim().toLowerCase();render();});
  $('#date-form').addEventListener('submit',e=>{e.preventDefault();const from=$('#date-from').value,to=$('#date-to').value;if(from&&to&&from>to){$('#date-error').textContent='The start date must be on or before the end date.';return;}dateFrom=from;dateTo=to;datePreset=from||to?'custom':'all';$('#date-error').textContent='';$('#date-picker').open=false;render();});
  $('#date-picker').addEventListener('toggle',()=>{if($('#date-picker').open)$('#country-picker').open=false;});
  $('#country-picker').addEventListener('toggle',()=>{if($('#country-picker').open)$('#date-picker').open=false;});
  $('#density').addEventListener('change',e=>{document.documentElement.dataset.density=e.target.value;});
  $('#country-options').addEventListener('change',e=>{if(e.target.matches('input'))toggleCountry(e.target.value);});
  document.addEventListener('keydown',e=>{if(document.documentElement.dataset.workspace)return;if(e.target.closest('input,select,textarea,dialog')||e.ctrlKey||e.metaKey||e.altKey)return;if(['companies','people'].includes(document.documentElement.dataset.view) && ['j','k','Escape'].includes(e.key))return;if(e.key==='Escape' && !readerCollapsed){e.preventDefault();setReaderCollapsed(true,true);}else if(e.key==='/'){e.preventDefault();$('#search').focus();}else if(e.key.toLowerCase()==='j'){e.preventDefault();move(1);}else if(e.key.toLowerCase()==='k'){e.preventDefault();move(-1);}});
  function drawMap(data){
    const byISO=new Map(countries.map(c=>[c.iso,c]));
    function ringPath(ring){return ring.map(([lon,lat],i)=>`${!i||Math.abs(lon-ring[i-1][0])>180?'M':'L'}${((lon+180)*1000/360).toFixed(1)},${((90-lat)*500/180).toFixed(1)}`).join(' ')+'Z';}
    for(const f of data.features){const c=byISO.get(f.properties['ISO3166-1-Alpha-2']);const path=document.createElementNS('http://www.w3.org/2000/svg','path');const polys=f.geometry.type==='MultiPolygon'?f.geometry.coordinates:[f.geometry.coordinates];path.setAttribute('d',polys.flatMap(p=>p.map(ringPath)).join(' '));path.setAttribute('fill-rule','evenodd');path.setAttribute('class','country'+(c&&records.some(r=>r.countries.some(g=>g.id===c.id))?' has-content':''));if(c){path.dataset.country=c.id;path.setAttribute('role','button');path.setAttribute('tabindex','0');path.setAttribute('aria-label','Filter '+c.name);path.setAttribute('aria-pressed','false');path.addEventListener('click',()=>toggleCountry(c.id));path.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();toggleCountry(c.id);}});}const title=document.createElementNS('http://www.w3.org/2000/svg','title');title.textContent=c?c.name+' · select country':f.properties.name;path.append(title);$('#map').append(path);}
  }
  window.addEventListener('keydown',e=>{if(e.key!=='Escape')return;const actions=$('.reader-icon-actions');const visible=actions&&[...actions.querySelectorAll('.reader-action-tooltip')].some(t=>getComputedStyle(t).visibility==='visible');if(visible){e.preventDefault();e.stopImmediatePropagation();actions.classList.add('tooltips-dismissed');}},true);
  document.addEventListener('pointerout',e=>{if(e.target.closest?.('.reader-icon-action')&&!e.target.closest('.reader-icon-action').contains(e.relatedTarget))$('.reader-icon-actions')?.classList.remove('tooltips-dismissed');});
  document.addEventListener('focusout',e=>{if(e.target.matches?.('.reader-icon-action'))$('.reader-icon-actions')?.classList.remove('tooltips-dismissed');});
  // Render outside the translucent header so fixed positioning uses the viewport.
  const moreDisclosure=$('.more-nav'), moreMenu=$('#more-workspaces'), moreTrigger=$('#more-trigger');
  document.body.append(moreMenu);
  function closeMore(returnFocus=false){moreDisclosure.open=false;moreMenu.hidden=true;moreTrigger.setAttribute('aria-expanded','false');if(returnFocus)moreTrigger.focus({preventScroll:true});}
  function positionMore(){if(!moreDisclosure.open)return;const rect=moreTrigger.getBoundingClientRect(),height=document.documentElement.clientHeight;if(rect.bottom<0||rect.top>height){closeMore();return;}const top=Math.max(12,Math.min(rect.bottom+10,height-150));moreMenu.style.top=top+'px';moreMenu.style.maxHeight=Math.max(120,height-top-12)+'px';}
  moreDisclosure.addEventListener('toggle',()=>{moreMenu.hidden=!moreDisclosure.open;moreTrigger.setAttribute('aria-expanded',String(moreDisclosure.open));if(moreDisclosure.open){positionMore();moreMenu.querySelector('a').focus({preventScroll:true});}});
  $('#close-more').addEventListener('click',()=>closeMore(true));
  document.addEventListener('click',e=>{if(moreDisclosure.open&&!moreMenu.contains(e.target)&&!moreDisclosure.contains(e.target))closeMore();});
  window.addEventListener('keydown',e=>{if(e.key==='Escape'&&moreDisclosure.open){e.preventDefault();e.stopImmediatePropagation();closeMore(true);}},true);
  window.addEventListener('resize',positionMore);window.addEventListener('scroll',positionMore,{passive:true});
  moreMenu.addEventListener('click',e=>{if(e.target.closest('a'))closeMore();});
  fetch('companies.json').then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{companyRecords=data.companies;$('#company-country').innerHTML='<option value="">All recorded countries</option>'+[...new Set(companyRecords.map(c=>c.country))].sort().map(c=>`<option>${escape(c)}</option>`).join('');$('#company-role').innerHTML='<option value="">All roles</option>'+[...new Set(companyRecords.flatMap(c=>c.roles))].sort().map(r=>`<option value="${escape(r)}">${escape(r.replaceAll('_',' '))}</option>`).join('');renderCompanies();}).catch(()=>{$('#company-rows').innerHTML='<p class="empty">Company records could not load. Reload the preview to retry.</p>';});
  $('#company-country').addEventListener('change',renderCompanies);$('#company-role').addEventListener('change',renderCompanies);
  Promise.all([fetch('content.json').then(r=>{if(!r.ok)throw Error();return r.json();}),regionExplorer.ready]).then(([data,regionCatalog])=>{
    records=data.records.sort((a,b)=>(b.date||'').localeCompare(a.date||'')||a.title.localeCompare(b.title));countries=[...new Map([...regionCatalog.countries,...records.flatMap(r=>r.countries)].map(c=>[c.id,c])).values()].sort((a,b)=>a.name.localeCompare(b.name));
    $('#country-options').innerHTML=countries.map(c=>`<label><input type="checkbox" value="${escape(c.id)}">${escape(c.name)}</label>`).join('');
    const companies=[...new Map(records.flatMap(r=>r.companies).map(c=>[c.id,c])).values()].sort((a,b)=>a.name.localeCompare(b.name));
    $('#entity-list').innerHTML=companies.map(c=>`<div><button data-company="${escape(c.id)}">${escape(c.name)}</button><a href="http://127.0.0.1:18321/entities/company/${encodeURIComponent(c.id)}" target="_blank" rel="noopener" aria-label="Open ${escape(c.name)} profile">↗</a></div>`).join('');
    render();return fetch('countries.geojson');
  }).then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{drawMap(data);render();}).catch(()=>{if(!records.length)$('#stories').innerHTML='<div class="empty"><h3>The sample could not load.</h3><p>Reload this local preview to retry.</p></div>';else $('.map-note').textContent='Map unavailable. Use the country selector above.';});
})();
