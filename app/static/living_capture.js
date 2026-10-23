(function () {
  'use strict';
  async function api(path, method='GET', payload, options={}) {
    const response = await fetch(path, {...options, method, credentials:'same-origin', headers:payload?{'Content-Type':'application/json'}:{}, body:payload?JSON.stringify(payload):undefined});
    if (response.redirected || response.status===401) throw Error('Your session needs attention. Sign in, then retry; input is preserved.');
    if (!response.headers.get('content-type')?.includes('application/json')) throw Error('The server returned an error ('+response.status+'). Retry; your input is preserved.');
    const data = await response.json(); if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'The workspace could not save this request.');return data;
  }
  window.livingAPI=api;
  const el=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;},token=()=>crypto.randomUUID();
  const panel=el('section');panel.className='lw-capture';panel.hidden=true;panel.setAttribute('aria-label','Save selected material');
  const actions=el('div'), status=el('div');status.className='lw-capture-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');panel.append(actions,status);document.body.append(panel);
  let snapshot=null,pending=null,result=null,form=null,unsaved=false,inventory=null,panelHost=document.body,saving=false,varietyBusy=false;
  const shortcutKeys={'Research & Learn':'a','Quick save':'q','Capture fact':'f','Link relationship':'k','Add note':'n','Choose destination':'d','Open workspace':'o','Close':'escape','Change destination':'d','Undo placement':'u','Retry save':'t','Return to editor':'e','Save / embed article':'q','Variety workspace':'v'};
  window.livingRememberPage=id=>{try{let ids=JSON.parse(localStorage.getItem('bios:living:recent-pages')||'[]');if(!Array.isArray(ids))ids=[];localStorage.setItem('bios:living:recent-pages',JSON.stringify([id,...ids.filter(value=>value!==id)].slice(0,8)));localStorage.setItem('bios:living:recent',id);}catch(_){}};
  function say(text){status.textContent=text;}
  function setShortcut(b,key){b.querySelector('kbd')?.remove();b.dataset.lwKey=key;b.setAttribute('aria-keyshortcuts',key==='escape'?'Escape':key.toUpperCase());b.append(el('kbd',key==='escape'?'Esc':key.toUpperCase()));}
  function button(text,fn,parent=actions){const b=el('button',text);b.type='button';if(shortcutKeys[text])setShortcut(b,shortcutKeys[text]);b.addEventListener('pointerdown',e=>{if(!form)e.preventDefault();});b.addEventListener('click',()=>Promise.resolve().then(fn).catch(e=>say('Failed · '+e.message+' Retry keeps the original input.')));parent.append(b);return b;}
  function rememberSelection(){
    const selection=window.getSelection();if(!selection||selection.isCollapsed||!selection.rangeCount)return;
    const range=selection.getRangeAt(0),element=range.startContainer.nodeType===1?range.startContainer:range.startContainer.parentElement;
    if(element.closest('input,textarea,select,form,[contenteditable=true],.lw-capture,.learn-provenance'))return;
    const reader=element.closest('[data-lw-source],[data-personal-reader],[data-intel-reader]');if(!reader)return;
    const end=range.endContainer.nodeType===1?range.endContainer:range.endContainer.parentElement;if(!reader.contains(end))return;
    const text=String(selection);if(!text.trim())return;
    if(unsaved)return;panelHost=element.closest('.offcanvas.show')||document.body;panelHost.append(panel);
    const prefix=range.cloneRange();prefix.selectNodeContents(reader);prefix.setEnd(range.startContainer,range.startOffset);
    const articleId=reader.dataset.articleId||reader.dataset.itemId||document.querySelector('#v2ReaderBody [data-item-id]')?.dataset.itemId||location.pathname.match(/\/intelligence\/([^/]+)/)?.[1];if(!articleId)return;
    snapshot={article_id:articleId,source_id:reader.dataset.sourceId||undefined,quote:text,locator:{start:prefix.toString().length},page_id:document.querySelector('#living-workspace')?.dataset.pageId||localStorage.getItem('bios:living:recent')||undefined};
    if(!form){pending=null;result=null;showActions();}
  }
  function showActions(){panel.hidden=false;actions.replaceChildren();const learn=document.querySelector('.learn-context-selection');if(learn)learn.hidden=true;say(snapshot?.quote?'Selected text preserved · '+snapshot.quote.length+' characters':'Save readable article to a research page');
    const berries=el('div');berries.className='lw-berry-destinations';berries.append(el('span','Save to berry workspace'));
    [['Blueberry','b'],['Blackberry','l'],['Raspberry','r'],['Strawberry','s']].forEach(([name,key])=>{const b=button(name,()=>{snapshot.page_id='wp-berry-'+name.toLowerCase();pending=null;return save(snapshot.kind==='article'?'article':'evidence');},berries);setShortcut(b,key);});actions.append(berries);
    button('Research & Learn',()=>document.querySelector('.learn-context-selection button')?.click());button('Quick save',()=>save(snapshot.kind==='article'?'article':'evidence'));button('Capture fact',()=>editor('statement'));button('Link relationship',()=>editor('relationship'));button('Add note',()=>editor('note'));button('Variety workspace',saveVariety);button('Choose destination',destination);button('Open workspace',async()=>{if(!result)await save(snapshot.kind==='article'?'article':'evidence');if(result)location.assign('/workspaces/'+result.page.id);});button('Close',close);
    showRecentDestinations();
  }
  async function showRecentDestinations(){
    const original=snapshot,anchor=el('div');anchor.className='lw-recent-destinations';actions.append(anchor);
    try{const data=await getInventory();if(snapshot!==original||!anchor.isConnected||form||result)return;
      let recent=[];try{recent=JSON.parse(localStorage.getItem('bios:living:recent-pages')||'[]');}catch(_){}if(!Array.isArray(recent))recent=[];
      const last=localStorage.getItem('bios:living:recent');const ids=[...new Set([last,...recent,...data.pages.slice().sort((a,b)=>(b.updated_at||'').localeCompare(a.updated_at||'')).map(p=>p.id)].filter(Boolean))];
      const pages=ids.map(id=>data.pages.find(p=>p.id===id)).filter(Boolean).slice(0,3);if(!pages.length)return;
      anchor.append(el('span','Recent workspaces'));
      pages.forEach((page,index)=>{const b=button(page.title,()=>{snapshot.page_id=page.id;pending=null;return save(snapshot.kind==='article'?'article':'evidence');},anchor);setShortcut(b,String(index+1));b.title='Save selection to '+page.title;});
    }catch(_){anchor.remove();}
  }
  const varietyCreateToken=token();
  async function saveVariety(){
    if(varietyBusy||saving||form)return;varietyBusy=true;
    try{const data=await getInventory();let page=data.pages.find(p=>p.title.trim().toLowerCase()==='variety workspace');
      if(!page)page=await api('/api/workspaces','POST',{title:'Variety workspace',parent_id:null,starter:false,token:varietyCreateToken});
      snapshot.page_id=page.id;pending=null;await save(snapshot.kind==='article'?'article':'evidence');
    }finally{varietyBusy=false;}
  }
  function close(){if(unsaved){say('Unsaved input is preserved. Save it or use Discard input to close.');return;}panel.hidden=true;form?.remove();form=null;window.getSelection()?.removeAllRanges();}
  function field(label,value='',multiline=false){const wrapper=el('label',label),input=el(multiline?'textarea':'input');input.value=value;wrapper.append(input);form.append(wrapper);input.addEventListener('input',()=>{unsaved=true;pending=null;});return input;}
  async function getInventory(){inventory=await api('/api/workspaces');return inventory;}
  async function save(kind,extra={}){
    if(!snapshot)throw Error('Select a passage in an article first.');
    if(saving)return;saving=true;
    if(!pending)pending={...structuredClone(snapshot),kind,token:token(),...extra};
    say('Saving…');
    try{result=await api('/api/workspaces/capture','POST',pending);unsaved=false;form?.remove();form=null;window.livingRememberPage(result.page.id);actions.replaceChildren();
      say('Saved to '+result.page.title+' · unverified');button('Open workspace',()=>location.assign('/workspaces/'+result.page.id));button('Change destination',destination);button('Undo placement',undo);button('Close',close);document.dispatchEvent(new CustomEvent('bios:workspace-captured',{detail:result}));
    }catch(e){say('Save failed · '+e.message);actions.replaceChildren();button('Retry save',()=>save(kind,extra));button('Return to editor',()=>{pending=null;if(form){say('Adjust your preserved input, then save the capture.');form.querySelector('textarea,input')?.focus();}else editor(kind);});button('Close',close);throw e;}finally{saving=false;}
  }
  async function undo(){if(!result)return;const current=(await api('/api/workspaces/page/'+result.page.id)).page;current.blocks=current.blocks.filter(b=>b.id!==result.block_id);const updated=await api('/api/workspaces/page/'+current.id,'PUT',current);say('Placement removed. Shared knowledge and source history remain available.');result=null;pending=null;showActions();say('Placement removed. Shared knowledge and source history remain available.');document.dispatchEvent(new CustomEvent('bios:workspace-captured',{detail:{page:updated}}));}
  async function destination(){
    await getInventory();const previousForm=form,previousUnsaved=unsaved;previousForm?.remove();form=el('div');form.className='lw-capture-form';panel.append(form);panel.hidden=false;const restore=()=>{form.remove();form=previousForm;unsaved=previousUnsaved;if(form)panel.append(form);};
    const label=el('label','Destination'),select=el('select');label.append(select);form.append(label);const inbox=el('option','Capture inbox');inbox.value='wp-inbox';select.append(inbox);
    inventory.pages.filter(p=>p.id!=='wp-inbox').forEach(p=>{const o=el('option',p.title);o.value=p.id;select.append(o);});select.value=snapshot.page_id||'wp-inbox';
    const title=field('Or create a page (leave empty to use selection)'),nested=el('input'),nestedLabel=el('label','Create nested beneath selected page');nested.type='checkbox';nestedLabel.append(nested);form.append(nestedLabel);
    const createToken=token();button('Use destination',async()=>{
      let id=select.value;if(title.value.trim()){const p=await api('/api/workspaces','POST',{title:title.value,parent_id:nested.checked&&id!=='wp-inbox'?id:null,starter:false,token:createToken});id=p.id;}
      if(result){const target=(await api('/api/workspaces/page/'+id)).page;const origin=(await api('/api/workspaces/page/'+result.page.id)).page;const moved=await api('/api/workspaces/move','POST',{token:token(),from_page:result.page.id,to_page:id,block_id:result.block_id,from_version:origin.version,to_version:target.version});result.page=moved.page;result.page.id=id;say('Capture moved to '+target.title);document.dispatchEvent(new CustomEvent('bios:workspace-captured',{detail:{page:moved.page,from_page:moved.from_page}}));}
      snapshot.page_id=id;pending=null;window.livingRememberPage(id);restore();if(!result&&!form)showActions();
    },form);button('Cancel destination',restore,form);
  }
  async function editor(kind){
    if(form&&unsaved){say('Save or discard your current input before changing capture type.');return;}await getInventory();panel.hidden=false;form?.remove();form=el('div');form.className='lw-capture-form';panel.append(form);form.append(el('blockquote',snapshot.quote));
    const text=field(kind==='note'?'Analyst interpretation / question':'Editable statement',kind==='statement'?snapshot.quote:'',true),note=field('Analyst note','',true),entities=field('Associated entities (canonical IDs, comma separated)');
    const options=el('datalist');options.id='lw-capture-entities';inventory.entities.forEach(e=>{const o=el('option',e.name+' · '+e.type+' · '+(e.aliases||[]).join(', '));o.value=e.id;options.append(o);});form.append(options);entities.setAttribute('list',options.id);
    button('Use source entity suggestions',async()=>{const data=await api('/api/workspaces/source/'+snapshot.article_id);entities.value=(data.entity_ids||[]).join(', ');say('Source associations suggested. Co-mentions do not establish relationships.');},form);
    button('Create unresolved entity stub',async()=>{const name=field('New entity name'),type=field('Type: company, variety, technology or topic','company');button('Save unresolved identity',async()=>{const row=await api('/api/workspaces/entity','POST',{name:name.value,type:type.value});entities.value+=(entities.value?', ':'')+row.id;say('Unresolved identity saved. No automatic name merge.');},form);},form);
    let subject,target,predicate,nature,scope;
    if(kind==='relationship'){
      subject=field('From entity ID');target=field('To entity ID');[subject,target].forEach(e=>e.setAttribute('list',options.id));
      const label=el('label','Direction: From → To; typed relationship');predicate=el('select');inventory.predicates.forEach(p=>{const o=el('option',p.replaceAll('_',' '));o.value=p;predicate.append(o);});label.append(predicate);form.append(label);
      const nlabel=el('label','Nature');nature=el('select');[['source_statement','Source-stated relationship (unverified)'],['analyst_hypothesis','Potential relationship — analyst hypothesis']].forEach(([value,label])=>{const o=el('option',label);o.value=value;nature.append(o);});nlabel.append(nature);form.append(nlabel);scope=field('Crop / program scope');
    }
    unsaved=true;text.focus();say('Exact source quote is preserved separately. Save enters the knowledge base as unverified.');
    button('Save capture',()=>save(kind,{text:text.value,note:note.value,entity_ids:entities.value.split(',').map(v=>v.trim()).filter(Boolean),...(kind==='relationship'?{relation:{subject_id:subject.value,object_id:target.value,predicate:predicate.value,nature:nature.value,scope:scope.value}}:{})}),form);
    button('Discard input',()=>{unsaved=false;pending=null;form.remove();form=null;showActions();},form);
  }
  window.openLivingCapture=data=>{if(unsaved){say('Save or discard the current capture before opening another.');return;}panelHost=document.body;panelHost.append(panel);snapshot=structuredClone(data);pending=null;result=null;showActions();if(data.kind==='note')editor('note');};
  document.addEventListener('keydown',event=>{
    if(panel.hidden||!snapshot||saving||varietyBusy||event.repeat||event.ctrlKey||event.metaKey||event.altKey||event.isComposing)return;
    if(event.target.closest('input,textarea,select,[contenteditable=true]'))return;
    const match=Array.from(panel.querySelectorAll('button[data-lw-key]')).find(b=>b.dataset.lwKey===event.key.toLowerCase()&&!b.disabled&&b.offsetParent!==null);
    if(!match)return;event.preventDefault();event.stopImmediatePropagation();match.click();
  },true);
  document.addEventListener('mouseup',event=>{if(!panel.contains(event.target))rememberSelection();});document.addEventListener('touchend',()=>setTimeout(rememberSelection,150),{passive:true});document.addEventListener('keyup',event=>{if(['Shift','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))rememberSelection();if(event.key==='Escape'&&!unsaved)close();});
  document.addEventListener('selectionchange',()=>{if(window.getSelection()?.toString()&&!panel.contains(document.activeElement))rememberSelection();});
  // Keep the original Research/Learn control and put capture on the same menu.
  const observer=new MutationObserver(()=>{
    const learn=document.querySelector('.learn-context-selection');if(learn&&!learn.querySelector('[data-lw-shortcut]')){const b=el('button','Save to workspace');b.type='button';b.dataset.lwShortcut='';b.addEventListener('pointerdown',e=>e.preventDefault());b.addEventListener('click',()=>{rememberSelection();learn.hidden=true;if(snapshot)showActions();});learn.append(b);}
    document.querySelectorAll('[data-personal-reader],[data-intel-reader]').forEach(reader=>{if(reader.querySelector('[data-lw-save-article]'))return;const b=el('button','Save full article to workspace');b.type='button';b.dataset.lwSaveArticle='';b.className='lw-save-article';b.addEventListener('click',()=>{if(unsaved){say('Save or discard your current input first.');return;}panelHost=reader.closest('.offcanvas.show')||document.body;panelHost.append(panel);const id=reader.dataset.itemId||location.pathname.match(/\/intelligence\/([^/]+)/)?.[1];if(!id)return;snapshot={article_id:id,kind:'article',quote:'',page_id:localStorage.getItem('bios:living:recent')||undefined};pending=null;result=null;showActions();actions.replaceChildren();button('Save / embed article',()=>save('article'));button('Choose destination',destination);button('Close',close);});(reader.querySelector('.personal-reader-toolbar')||reader.querySelector('header')||reader).append(b);});
  });observer.observe(document.body,{childList:true,subtree:true});
  document.querySelectorAll('[data-lw-entity-material]').forEach(async host=>{const id=location.pathname.split('/').filter(Boolean).pop();try{const data=await api('/api/workspaces/entity/'+encodeURIComponent(id)),list=host.querySelector('[data-lw-entity-items]');data.items.slice(0,12).forEach(item=>{const a=el('a',(item.text||item.quote||item.kind).slice(0,160)+' · '+item.nature.replaceAll('_',' ')+' · '+item.verification_state);a.href='/workspaces/evidence/'+item.id;const p=el('p');p.append(a);list.append(p);});}catch(_){}});
  window.addEventListener('beforeunload',event=>{if(unsaved){event.preventDefault();event.returnValue='';}});
})();
