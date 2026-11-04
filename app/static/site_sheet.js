/* Site-wide read-only sheets. Research editors retain their governed edit controls. */
window.BerrySheetTools = function({table,toolbar,rows,headers,titles,ids,getFilters,setFilters}) {
 const body=table.tBodies[0], data=rows.filter(r=>r.row.parentElement===body&&r.cells.length===headers.length);
 const controls=document.createElement('div');controls.className='site-sheet-controls';toolbar.after(controls);
 const search=document.createElement('input');search.type='search';search.maxLength=400;search.placeholder='Search loaded rows';search.setAttribute('aria-label','Search loaded rows');
 const sort=document.createElement('select');sort.setAttribute('aria-label','Sort loaded rows');sort.add(new Option('Original order',''));
 titles.forEach((title,i)=>{if(!headers[i].querySelector('input')&&title!=='Select'&&title!=='Monitor')for(const dir of ['asc','desc'])sort.add(new Option(title+' · '+(dir==='asc'?'Ascending':'Descending'),ids[i]+'|'+dir));});
 const wrap=document.createElement('button');wrap.type='button';wrap.textContent='Wrap text';
 const count=document.createElement('span');count.setAttribute('role','status');
 const download=document.createElement('button');download.type='button';download.textContent='Export visible CSV';
 controls.append(search,sort,wrap,download,count);
 const initial=getFilters();search.value=initial.query||'';sort.value=initial.sort||'';
 let wrapped=initial.wrap==='1';
 const text=cell=>(cell.dataset.sortValue||cell.textContent).replace(/\s+/g,' ').trim();
 function apply(save=true){
  const [id,direction]=sort.value.split('|'),index=ids.indexOf(id),query=search.value.trim().toLocaleLowerCase();
  const ordered=index<0?[...data]:[...data].sort((a,b)=>text(a.cells[index]).localeCompare(text(b.cells[index]),undefined,{numeric:true,sensitivity:'base'})*(direction==='desc'?-1:1));
  ordered.forEach(r=>{r.row.hidden=!!query&&!r.cells.some(cell=>text(cell).toLocaleLowerCase().includes(query));body.append(r.row);});
  table.classList.toggle('site-sheet-wrap',wrapped);wrap.setAttribute('aria-pressed',String(wrapped));
  count.textContent=data.filter(r=>!r.row.hidden).length+' of '+data.length+' loaded rows';
  if(save)setFilters({query:search.value,sort:sort.value,wrap:wrapped?'1':'0'});
 }
 search.addEventListener('input',()=>apply(false));search.addEventListener('change',()=>apply());sort.onchange=()=>apply();wrap.onclick=()=>{wrapped=!wrapped;apply();};
 download.onclick=()=>{
  const csv=Array.from(table.rows).filter(row=>!row.hidden).map(row=>Array.from(row.cells).map(cell=>'"'+(row.parentElement===table.tHead?titles[ids.indexOf(cell.dataset.vsColumn)]:cell.textContent).replace(/\s+/g,' ').trim().replace(/^[=+@\-\t\r]/,"'").replace(/"/g,'""')+'"').join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='berry-sheet.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
 data.forEach(({cells})=>cells.forEach(cell=>{cell.tabIndex=0;cell.title=text(cell);cell.addEventListener('keydown',e=>{
  if(e.target!==cell||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
  const visible=Array.from(body.rows).filter(row=>!row.hidden),row=cell.parentElement,ci=Array.from(row.cells).indexOf(cell),ri=visible.indexOf(row);
  const next=e.key==='ArrowLeft'?row.cells[ci-1]:e.key==='ArrowRight'?row.cells[ci+1]:visible[ri+(e.key==='ArrowDown'?1:-1)]?.cells[ci];if(next){e.preventDefault();next.focus();}
 });}));
 apply(false);
};
(() => {
 const durable=document.currentScript.dataset.savedViews;
 for(const table of document.querySelectorAll('main table')){
  // These surfaces already own equivalent, richer column/editor controllers.
  if(table.closest('.variety-sheet-shell')||table.matches('.lw-research-grid,.ce-grid,[data-sheet-native]')||!table.tHead||table.tHead.rows.length!==1||!table.tBodies.length||table.tHead.rows[0].cells.length<2)continue;
  const scroll=table.closest('.company-table-scroll,.table-wrap,.gw-table-wrap,.variety-source-table-wrap')||document.createElement('div');
  if(!scroll.parentElement){table.before(scroll);scroll.append(table);}scroll.classList.add('site-sheet-scroll');
  const root=document.createElement('section');root.className='site-sheet-shell';root.dataset.savedViews=durable;scroll.before(root);root.append(scroll);table.classList.add('site-sheet');
  window.BerrySheet(root,true);
 }
})();
