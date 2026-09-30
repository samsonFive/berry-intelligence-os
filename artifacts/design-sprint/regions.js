window.createRegionExplorer = ({getScope, refresh, escape, safeURL}) => {
  const $ = s => document.querySelector(s);
  const key = 'berry-design-regions-v1';
  let catalog, overrides = {}, layer = 'news', editing = '', opener, tableLetter = '', tableQuery = '', tableSort = 'name';
  try { const saved=JSON.parse(localStorage.getItem(key)||'{}'); if(saved.version===1 && saved.overrides && typeof saved.overrides==='object')overrides=saved.overrides; } catch {}
  const ready = fetch('region-catalog.json').then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{catalog=data;return data;});
  const rows = () => catalog ? [...catalog.regions.filter(r=>!Object.hasOwn(overrides,r.id)),...Object.values(overrides).filter(r=>r&&typeof r==='object'&&r.id&&r.entity_id&&r.country_id)] : [];
  const entity = id => catalog?.entities.find(e=>e.id===id);
  const country = id => catalog?.countries.find(c=>c.id===id)?.name || id;
  const entityRows = id => rows().filter(r=>r.entity_id===id);
  const status = row => row.origin || 'User entry';
  function persist() {try{localStorage.setItem(key,JSON.stringify({version:1,overrides}));$('#region-message').textContent='Saved in this browser preview. Production records are unchanged.';}catch{$('#region-message').textContent='Saved for this session only; browser storage is unavailable.';}}
  function render() {
    if(!catalog)return;
    const scope=getScope();
    const visible=rows().filter(r=>{
      const e=entity(r.entity_id);
      return e && e.kind===(layer==='varieties'?'variety':'company') && (!scope.countries.length||scope.countries.includes(r.country_id)) && (!scope.berries.length||e.berries.some(b=>scope.berries.includes(b))) && (e.kind!=='company'||scope.companyMatches(e.id)) && (!scope.selectedCompany||e.kind!=='company'||scope.selectedCompany===e.id);
    });
    $('.map-panel').dataset.layer=layer;
    $('.map-panel h2').textContent=({news:'Global news coverage',varieties:'Variety growing regions',companies:'Company operating regions'})[layer];
    $('.map-caption').textContent=layer==='news'?'SOURCE COVERAGE':layer==='varieties'?'GROWING REGIONS':'OPERATING REGIONS';
    $('.map-note').textContent=layer==='news'?'Select countries on the map to scope the news. Berry, country and review filters carry between News and Map Explorer.':'Select countries to filter regions. Berry selections apply; news dates and review status do not change recorded locations.';
    $('#map-region-results').hidden=layer==='news';
    for(const id of ['map-coverage','geography-summary'])$('#'+id).hidden=layer!=='news';
    document.querySelectorAll('#map [data-country]').forEach(p=>{const matches=visible.filter(r=>r.country_id===p.dataset.country);p.classList.toggle('region-present',layer!=='news'&&matches.length>0);p.querySelector('title').textContent=country(p.dataset.country)+(layer==='news'?' · select country':` · ${matches.length} region entries in this scope`);});
    if(layer==='news')return;
    const initial = r => {const c=entity(r.entity_id).name.charAt(0).toUpperCase();return /^[A-Z]$/.test(c)?c:'#';};
    const initials=new Set(visible.map(initial));
    const matches=visible.filter(r=>(!tableLetter||initial(r)===tableLetter)&&(!tableQuery||[entity(r.entity_id).name,country(r.country_id),r.region,r.activity].join(' ').toLowerCase().includes(tableQuery)));
    matches.sort((a,b)=>{const av=tableSort==='country'?country(a.country_id):entity(a.entity_id).name,bv=tableSort==='country'?country(b.country_id):entity(b.entity_id).name;return av.localeCompare(bv)||entity(a.entity_id).name.localeCompare(entity(b.entity_id).name)||country(a.country_id).localeCompare(country(b.country_id));});
    $('#map-region-results').innerHTML=`<header class="region-table-heading"><div><span class="eyebrow">${layer==='companies'?'COMPANY FOOTPRINT':'VARIETY FOOTPRINT'}</span><h2>${layer==='companies'?'Company operating regions':'Variety growing regions'}</h2><p>${matches.length} of ${visible.length} region entries · ${new Set(matches.map(r=>r.entity_id)).size} ${layer==='companies'?'companies':'varieties'}</p></div><label class="region-table-search">Find in this table<input id="region-table-query" type="search" value="${escape(tableQuery)}" placeholder="Name, country or activity"></label></header><nav class="region-alphabet" aria-label="Region table name initial"><button data-region-letter="" aria-pressed="${!tableLetter}">All</button>${'ABCDEFGHIJKLMNOPQRSTUVWXYZ#'.split('').map(l=>`<button data-region-letter="${l}" aria-label="Names starting with ${l}" aria-pressed="${tableLetter===l}" ${initials.has(l)?'':'disabled'}>${l}</button>`).join('')}</nav><div class="region-table-scroll" tabindex="0" aria-label="Region entries table; scroll for more rows"><table class="region-table"><thead><tr><th scope="col" aria-sort="${tableSort==='name'?'ascending':'none'}"><button data-region-sort="name">${layer==='companies'?'Company':'Variety'} ${tableSort==='name'?'↓':''}</button></th><th scope="col" aria-sort="${tableSort==='country'?'ascending':'none'}"><button data-region-sort="country">Country / region ${tableSort==='country'?'↓':''}</button></th><th scope="col">Activity</th><th scope="col">Basis</th><th scope="col">As of</th><th scope="col">Actions</th></tr></thead><tbody>${matches.map(r=>`<tr><th scope="row"><button data-region-open="${escape(r.entity_id)}">${escape(entity(r.entity_id).name)}</button></th><td>${escape(country(r.country_id))}${r.region?`<small>${escape(r.region)}</small>`:''}</td><td>${escape(r.activity)}</td><td><span class="region-origin">${escape(status(r))}</span></td><td class="region-date">${escape(r.date||'Not recorded')}</td><td class="region-row-actions">${safeURL(r.source_url)?`<a href="${escape(safeURL(r.source_url))}" target="_blank" rel="noopener" aria-label="Source for ${escape(entity(r.entity_id).name)} in ${escape(country(r.country_id))}">Source ↗</a>`:'<span>No source</span>'}<button data-region-open="${escape(r.entity_id)}" aria-label="Edit regions for ${escape(entity(r.entity_id).name)}">Edit</button></td></tr>`).join('')||`<tr><td colspan="6" class="region-table-empty">${visible.length?'No rows match this table filter. Choose All or clear the search.':'No regions recorded in this scope yet. Add a region or check existing sources; missing coverage does not mean no activity.'}</td></tr>`}</tbody></table></div><details class="region-table-notes"><summary>Map scope and source notes</summary><p>Country and berry selections apply${layer==='companies'?'; company favorites, tiers and lists also apply':''}. News dates and review filters do not. Alphabet and search narrow this table only; the map keeps the full selected geographic scope.</p><p>Country shading indicates recorded presence, not acreage or market share. Subregions are labeled notes until boundaries are available. News suggestions and user entries are not confirmed statements.</p></details>`;
  }
  function list() {
    const id=$('#region-entity').value,e=entity(id);
    $('#region-editor-title').textContent=e?.kind==='variety'?'Growing regions':'Operating regions';
    const kinds=e?.kind==='variety'?['Commercial growing','Trial','Announced planting','Historical growing','Growing (unspecified)']:['Operations (unspecified)','Growing','Breeding / research','Packing / processing','Sales / distribution','Headquarters'];
    $('#region-activity').innerHTML=kinds.map(k=>`<option>${escape(k)}</option>`).join('');
    $('#region-existing').innerHTML=entityRows(id).map(r=>`<article><div><strong>${escape(country(r.country_id))}${r.region?' · '+escape(r.region):''}</strong><p>${escape(r.activity)} · ${escape(status(r))} · ${escape(r.date||'Date not recorded')}</p><p>${escape(r.note)}</p>${safeURL(r.source_url)?`<a href="${escape(safeURL(r.source_url))}" target="_blank" rel="noopener">Supporting source ↗</a>`:''}</div><button type="button" data-region-edit="${escape(r.id)}">Edit</button><button type="button" data-region-remove="${escape(r.id)}">Remove</button></article>`).join('')||'<p>No regions recorded yet. Add a place below; a news mention, selling market or headquarters alone does not establish a growing region.</p>';
    const sources=catalog.sources.filter(s=>s.entity_ids.includes(id));
    $('#region-source-record').innerHTML='<option value="">Manual entry / paste a source link</option>'+sources.map(s=>`<option value="${escape(s.id)}">${escape(s.kind+' · '+(s.classification?s.classification+' · ':'')+s.label.slice(0,140))}</option>`).join('');
    $('#region-record-link').href=`http://127.0.0.1:18321/entities/${e?.kind}/${encodeURIComponent(id)}`;
  }
  function clearForm(){editing='';$('#region-form').reset();$('#region-save').textContent='Add region';}
  function chooseKind(kind,id){$('#region-kind').value=kind;$('#region-entity').innerHTML=catalog.entities.filter(e=>e.kind===kind).map(e=>`<option value="${escape(e.id)}">${escape(e.name)}</option>`).join('');if(id)$('#region-entity').value=id;clearForm();list();}
  function open(id,trigger){if(!catalog)return;opener=trigger;chooseKind(entity(id)?.kind||(layer==='companies'?'company':'variety'),id);$('#region-message').textContent='Preview edits stay in this browser. Linked news and statements can support an entry; they do not automatically confirm it.';$('#region-editor').showModal();}
  $('#map-layer').addEventListener('change',e=>{layer=e.target.value;tableLetter='';tableQuery='';render();});
  $('#region-kind').addEventListener('change',e=>chooseKind(e.target.value));
  $('#region-entity').addEventListener('change',()=>{clearForm();list();});
  $('#region-source-record').addEventListener('change',e=>{const source=catalog.sources.find(s=>s.id===e.target.value);if(source){$('#region-source-url').value=source.url;$('#region-origin').value=source.kind==='News'?'News suggestion':'Statement-linked entry';$('#region-note').value=source.label;}});
  document.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.hasAttribute('data-region-letter')){tableLetter=b.dataset.regionLetter;render();$('#map-region-results [data-region-letter=\"'+tableLetter+'\"]')?.focus({preventScroll:true});}
    if(b.dataset.regionSort){tableSort=b.dataset.regionSort;render();$('#map-region-results [data-region-sort=\"'+tableSort+'\"]')?.focus({preventScroll:true});}
    if(b.id==='manage-map-regions'||b.hasAttribute('data-region-open'))open(b.dataset.regionOpen,b);
    if(b.id==='region-close'){$('#region-editor').close();opener?.focus();}
    if(b.dataset.regionEdit){const r=rows().find(x=>x.id===b.dataset.regionEdit);if(!r)return;editing=r.id;$('#region-country').value=r.country_id;$('#region-subregion').value=r.region;$('#region-activity').value=r.activity;$('#region-date').value=r.date;$('#region-note').value=r.note;$('#region-source-url').value=r.source_url;$('#region-source-record').value=r.source_id||'';$('#region-origin').value=['News suggestion','Statement-linked entry'].includes(r.origin)?r.origin:'User entry';$('#region-save').textContent='Save changes';}
    if(b.dataset.regionRemove){overrides[b.dataset.regionRemove]=null;persist();clearForm();list();refresh();}
    if(b.id==='region-new'){clearForm();list();}
  });
  document.addEventListener('input',e=>{if(e.target.id==='region-table-query'){const pos=e.target.selectionStart;tableQuery=e.target.value.toLowerCase();render();const input=$('#region-table-query');input.focus({preventScroll:true});input.setSelectionRange(pos,pos);}});
  $('#region-form').addEventListener('submit',e=>{
    e.preventDefault();const source=$('#region-source-url').value.trim();if(source&&!safeURL(source)){$('#region-message').textContent='Use a complete http or https source link.';return;}
    const id=editing||'preview-region-'+crypto.randomUUID();
    overrides[id]={id,entity_id:$('#region-entity').value,country_id:$('#region-country').value,region:$('#region-subregion').value.trim().slice(0,120),activity:$('#region-activity').value,date:$('#region-date').value,note:$('#region-note').value.trim().slice(0,1500),source_url:safeURL(source),source_id:$('#region-source-record').value,origin:$('#region-origin').value,edited_on:new Date().toISOString()};
    persist();clearForm();list();refresh();
  });
  ready.then(()=>{$('#region-country').innerHTML=catalog.countries.map(c=>`<option value="${escape(c.id)}">${escape(c.name)}</option>`).join('');$('#manage-map-regions').disabled=false;refresh();}).catch(()=>{$('#map-region-results').hidden=false;$('#map-region-results').textContent='Region data could not load. Reload to retry.';});
  return {ready,render,companyMarkup:c=>`<section class="company-section"><h3>Operating regions <span>${entityRows(c.id).length} recorded</span></h3><p class="company-gap">${escape(entityRows(c.id).map(r=>country(r.country_id)+' · '+r.activity).join('; ')||'No operating regions recorded yet.')}</p><button data-region-open="${escape(c.id)}">Edit operating regions</button></section>`};
};
