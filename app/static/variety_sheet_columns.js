/* Shared sheet interaction: stable column identities and account-backed layouts. */
(async () => {
 const root=document.querySelector('.variety-sheet-shell');if(!root)return;
 const durable=root.dataset.savedViews==='1';
 const empty=()=>({revision:0,widths:{},order:[],hidden:[],filters:{}});
 async function read(key){if(!durable)return empty();const r=await fetch('/api/varieties/view-state/'+key,{cache:'no-store'});if(!r.ok)throw Error('Saved layout unavailable');return r.json();}
 async function write(key,state){if(!durable)return state;const r=await fetch('/api/varieties/view-state/'+key,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)});const data=await r.json();if(!r.ok)throw Error(data.detail||'Layout not saved');return data;}
 const hash=text=>{let h=2166136261;for(const c of text){h^=c.charCodeAt(0);h=Math.imul(h,16777619);}return (h>>>0).toString(36);};
 for(const table of root.querySelectorAll('table')){
  const head=table.tHead;if(!head||head.rows.length!==1)continue;
  const headers=Array.from(head.rows[0].cells);if(headers.length<2||headers.length>30)continue;
  const titles=headers.map(h=>h.dataset.columnLabel||h.textContent.replace(/\s+/g,' ').trim());
  const catalog=table.classList.contains('variety-table');
  const view=catalog?'catalog':location.pathname.includes('/compare')?'compare':location.pathname.includes('/coverage')?'coverage':location.pathname.includes('/regions')?'regions':location.pathname.includes('/entities/variety/')?'profile':'varieties';
  const key=view+'-'+hash(titles.join('|'));
  const ids=titles.map((title,i)=>'c'+i+'-'+hash(title));
  const defaults=Object.fromEntries(headers.map((h,i)=>[ids[i],Math.max(48,Math.min(1200,Math.round(h.getBoundingClientRect().width)||160))]));
  const pinned=ids.slice(0,catalog?2:1);
  let state=empty(),saveChain=Promise.resolve();
  const toolbar=document.createElement('div');toolbar.className='vs-sheet-tools';
  const menu=document.createElement('details');menu.className='vs-column-menu';const summary=document.createElement('summary');summary.textContent='Columns';menu.append(summary);
  const choices=document.createElement('div');menu.append(choices);
  const reset=document.createElement('button');reset.type='button';reset.textContent='Reset columns';
  const status=document.createElement('span');status.setAttribute('role','status');status.textContent='Loading saved columns…';toolbar.append(menu,reset,status);
  const scroll=table.closest('.company-table-scroll,.table-wrap,.variety-source-table-wrap');(scroll||table).before(toolbar);
  try{state=await read(key);status.textContent=state.revision?'Saved columns restored':'Default columns';}catch(e){status.textContent=e.message+' · changes stay in this page';}
  let order=[...pinned,...(state.order||[]).filter(id=>ids.includes(id)&&!pinned.includes(id)),...ids.filter(id=>!pinned.includes(id)&&!(state.order||[]).includes(id))];
  let hidden=new Set((state.hidden||[]).filter(id=>ids.includes(id)&&!pinned.includes(id)));
  let widths={...defaults,...Object.fromEntries(Object.entries(state.widths||{}).filter(([id,w])=>ids.includes(id)&&Number.isInteger(w)&&w>=48&&w<=1200))};
  const rows=Array.from(table.rows).map(row=>({row,cells:Array.from(row.cells)}));
  rows.forEach(({cells})=>{if(cells.length===ids.length)cells.forEach((cell,i)=>cell.dataset.vsColumn=ids[i]);});
  table.querySelectorAll(':scope > colgroup').forEach(group=>group.remove());const colgroup=document.createElement('colgroup');table.prepend(colgroup);table.classList.add('vs-adjustable');
  let lastOrder='',lastOffsets='';
  function apply(){
   const visible=order.filter(id=>!hidden.has(id)),orderKey=visible.join('|'),offsetKey=pinned.slice(0,-1).map(id=>widths[id]).join('|');
   const sameOrder=lastOrder===orderKey;
   if(!sameOrder)colgroup.replaceChildren(...visible.map(()=>document.createElement('col')));
   Array.from(colgroup.children).forEach((col,i)=>{col.style.width=widths[visible[i]]+'px';});
   table.style.width=visible.reduce((n,id)=>n+widths[id],0)+'px';table.style.minWidth='0';table.style.tableLayout='fixed';
   headers.forEach((h,i)=>h.querySelector('[role="separator"]')?.setAttribute('aria-valuenow',String(widths[ids[i]])));
   choices.querySelectorAll('input[type=number]').forEach(input=>{if(input!==document.activeElement)input.value=String(widths[input.dataset.columnId]);});
   if(sameOrder&&lastOffsets===offsetKey)return;
   lastOrder=orderKey;lastOffsets=offsetKey;
   rows.forEach(({row,cells})=>{
    if(cells.length!==ids.length){if(cells.length===1)cells[0].colSpan=visible.length;return;}
    const desired=visible.map(id=>cells[ids.indexOf(id)]);if(row.cells.length!==desired.length||desired.some((cell,i)=>row.cells[i]!==cell))row.replaceChildren(...desired);
    let left=0;
    for(const id of visible){const cell=cells[ids.indexOf(id)];cell.style.width='auto';cell.style.display='table-cell';cell.style.left=pinned.includes(id)?left+'px':'auto';cell.style.position=pinned.includes(id)?'sticky':'';cell.style.zIndex=pinned.includes(id)?(row.parentElement.tagName==='THEAD'?'6':'2'):'';if(pinned.includes(id))left+=widths[id];}
   });
   headers.forEach((h,i)=>h.querySelector('[role="separator"]')?.setAttribute('aria-valuenow',String(widths[ids[i]])));
  }
  function remember(){
   const snapshot={revision:state.revision,widths:{...widths},order:[...order],hidden:[...hidden],filters:state.filters||{}};status.textContent=durable?'Saving columns…':'Columns changed · this page only';
   saveChain=saveChain.then(async()=>{snapshot.revision=state.revision;try{state=await write(key,snapshot);status.textContent=durable?'Columns saved for your account':'Columns changed · this page only';}catch(e){status.textContent=e.message;}});
  }
  function move(id,to){const from=order.indexOf(id);if(pinned.includes(id)||to<pinned.length||to>=order.length)return;order.splice(from,1);order.splice(to,0,id);apply();renderChoices();remember();}
  function renderChoices(){choices.replaceChildren();for(const id of order){const i=ids.indexOf(id),row=document.createElement('div'),label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=!hidden.has(id);check.disabled=pinned.includes(id);check.setAttribute('aria-label','Show '+titles[i]+' column');check.onchange=()=>{check.checked?hidden.delete(id):hidden.add(id);apply();remember();};label.append(check,document.createTextNode(titles[i]));const size=document.createElement('input');size.type='number';size.min='48';size.max='1200';size.step='10';size.value=String(widths[id]);size.dataset.columnId=id;size.setAttribute('aria-label','Width of '+titles[i]+' column');size.onchange=()=>{widths[id]=Math.max(48,Math.min(1200,Math.round(Number(size.value)||defaults[id])));apply();remember();};row.append(label,size);for(const [delta,symbol] of [[-1,'↑'],[1,'↓']]){const b=document.createElement('button');b.type='button';b.textContent=symbol;b.setAttribute('aria-label','Move '+titles[i]+' '+(delta<0?'left':'right'));b.disabled=pinned.includes(id)||order.indexOf(id)+delta<pinned.length||order.indexOf(id)+delta>=order.length;b.onclick=()=>move(id,order.indexOf(id)+delta);row.append(b);}choices.append(row);}}
  headers.forEach((header,i)=>{
   const id=ids[i];header.classList.add('vs-column-header');
   const grip=document.createElement('button');grip.type='button';grip.className='vs-column-grip';grip.textContent='⠿';grip.setAttribute('aria-label','Move '+titles[i]+' column');grip.title='Drag to reorder; Alt + Left/Right moves a column';grip.disabled=pinned.includes(id);
   grip.onkeydown=e=>{if(e.altKey&&['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();move(id,order.indexOf(id)+(e.key==='ArrowRight'?1:-1));}};
   grip.onpointerdown=e=>{if(e.button!==0||pinned.includes(id))return;e.preventDefault();grip.setPointerCapture(e.pointerId);let target=null;grip.onpointermove=m=>{root.querySelectorAll('.vs-column-drop').forEach(el=>el.classList.remove('vs-column-drop'));const cell=document.elementFromPoint(m.clientX,m.clientY)?.closest('th[data-vs-column]');target=cell&&head.contains(cell)?cell.dataset.vsColumn:null;if(target&&!pinned.includes(target))cell.classList.add('vs-column-drop');};const end=()=>{grip.onpointermove=null;root.querySelectorAll('.vs-column-drop').forEach(el=>el.classList.remove('vs-column-drop'));if(target)move(id,order.indexOf(target));};grip.onpointerup=end;grip.onpointercancel=()=>{grip.onpointermove=null;};};
   const handle=document.createElement('span');handle.className='vs-column-resize';handle.tabIndex=0;handle.setAttribute('role','separator');handle.setAttribute('aria-orientation','vertical');handle.setAttribute('aria-label','Resize '+titles[i]+' column');handle.setAttribute('aria-valuemin','48');handle.setAttribute('aria-valuemax','1200');handle.title='Drag to resize; Left/Right adjusts width';
   function setWidth(value){widths[id]=Math.max(48,Math.min(1200,Math.round(value)));apply();}
   handle.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();handle.setPointerCapture(e.pointerId);const x=e.clientX,start=widths[id];document.body.classList.add('vs-column-resizing');handle.onpointermove=m=>setWidth(start+m.clientX-x);const end=()=>{handle.onpointermove=null;document.body.classList.remove('vs-column-resizing');remember();};handle.onpointerup=end;handle.onlostpointercapture=end;handle.onpointercancel=end;};
   handle.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home'].includes(e.key))return;e.preventDefault();setWidth(e.key==='Home'?defaults[id]:widths[id]+(e.key==='ArrowRight'?1:-1)*(e.shiftKey?50:10));remember();};header.append(grip,handle);
  });
  reset.onclick=()=>{order=[...ids];hidden.clear();widths={...defaults};apply();renderChoices();remember();};apply();renderChoices();
 }
 // Filters are a separate saved view, so column layouts survive Reset filters.
 const filters=root.querySelector('form[aria-label="Filter varieties"]');
 if(durable&&filters){
  const key='catalog-filters';let state;try{state=await read(key);}catch(_){return;}
  const names=Array.from(filters.elements).map(e=>e.name).filter(Boolean);
  const current=Object.fromEntries(Array.from(new FormData(filters)).filter(([k,v])=>names.includes(k)&&typeof v==='string'));
  const explicit=names.some(name=>new URLSearchParams(location.search).has(name));
  if(!explicit&&Object.values(state.filters||{}).some(v=>v)&&!new URLSearchParams(location.search).has('reset_view')){location.replace(location.pathname+'?'+new URLSearchParams(state.filters));return;}
  async function saveFilters(values){state=await write(key,{...state,filters:values});}
  if(explicit){try{await saveFilters(current);}catch(_){}}
  filters.addEventListener('submit',async e=>{e.preventDefault();try{await saveFilters(Object.fromEntries(new FormData(filters)));}catch(_){}filters.submit();});
  const reset=Array.from(filters.querySelectorAll('a')).find(a=>a.textContent.trim()==='Reset');reset?.addEventListener('click',async e=>{e.preventDefault();try{await saveFilters({});}catch(_){}location.assign(reset.href+'&reset_view=1');});
 }
})();
