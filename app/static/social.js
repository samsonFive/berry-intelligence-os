(() => {
  'use strict';
  const root=document.querySelector('[data-social]'); if(!root) return;
  const records=[...root.querySelectorAll('[data-social-record]')];
  function drill(ids,label,save=true,clear=false) {
    const selection=new Set(ids);
    records.forEach(r=>{r.hidden=!clear && !selection.has(r.dataset.socialRecord);});
    root.querySelector('[data-drill-title]').textContent=label+' · '+(clear?records.length:ids.length)+' posts';
    if(save){const u=new URL(location.href); if(!clear)u.searchParams.set('drill',ids.length?ids.join(','):'none');else u.searchParams.delete('drill');history.replaceState(history.state,'',u);}
  }
  root.querySelectorAll('[data-social-drill]').forEach(button=>button.addEventListener('click',()=>{
    const ids=JSON.parse(button.dataset.socialDrill);drill(ids,button.textContent.trim());
    root.querySelector('#social-records').scrollIntoView({behavior:'instant',block:'start'});
    root.querySelector('[data-drill-title]').setAttribute('tabindex','-1');root.querySelector('[data-drill-title]').focus();
  }));
  root.querySelectorAll('[data-social-drill][role="button"]').forEach(control=>control.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();control.dispatchEvent(new MouseEvent('click',{bubbles:true}));}}));
  root.querySelector('[data-clear-drill]').addEventListener('click',()=>drill([],'Posts',true,true));
  const saved=new URL(location.href).searchParams.get('drill'); if(saved)drill(saved.split(',').filter(id=>records.some(r=>r.dataset.socialRecord===id)),'Selected posts',false);
  root.querySelectorAll('[data-sort]').forEach(button=>button.addEventListener('click',()=>{
    const body=button.closest('table').querySelector('tbody'); const index=Number(button.dataset.sort);const asc=button.getAttribute('aria-sort')!=='ascending';
    [...body.rows].sort((a,b)=>{const x=a.cells[index].dataset.sortValue||a.cells[index].textContent.trim(),y=b.cells[index].dataset.sortValue||b.cells[index].textContent.trim();return (button.hasAttribute('data-numeric')?Number(x)-Number(y):x.localeCompare(y))*(asc?1:-1);}).forEach(row=>body.appendChild(row));
    button.setAttribute('aria-sort',asc?'ascending':'descending');button.closest('th').setAttribute('aria-sort',asc?'ascending':'descending');
  }));
  const cloud=root.querySelector('[data-cloud-mode]');if(cloud)cloud.addEventListener('change',()=>{
    root.querySelectorAll('[data-cloud-phrase]').forEach(b=>{b.classList.toggle('positive',cloud.value==='sentiment'&&Number(b.dataset.positive)>Number(b.dataset.negative));b.classList.toggle('negative',cloud.value==='sentiment'&&Number(b.dataset.negative)>Number(b.dataset.positive));});
    root.querySelector('[data-cloud-note]').textContent=cloud.value==='rising'?'Not enough comparable data to show rising topics. Showing frequency.':'Select a word to see matching posts.';
  });
  async function post(path,payload) {
    const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),credentials:'same-origin'});
    const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Intake validation failed');return result;
  }
  const status=root.querySelector('[data-intake-status]');
  root.querySelector('[data-manual-capture]').addEventListener('submit',async event=>{
    event.preventDefault();const p=Object.fromEntries(new FormData(event.target));p.language_basis='analyst supplied';p.attribution='Analyst captured public source reference';
    try{status.textContent='Validating capture…';const r=await post('/api/social/manual',p);status.textContent='Saved '+r.ids.length+' post. Choose Saved by you to see it.';}catch(e){status.textContent=e.message;}
  });
  root.querySelector('[data-social-import]').addEventListener('submit',async event=>{
    event.preventDefault();try{status.textContent='Validating import…';const r=await post('/api/social/import',JSON.parse(new FormData(event.target).get('payload')));status.textContent='Uploaded '+r.ids.length+' posts. Choose Uploaded data to see them.';}catch(e){status.textContent=e.message;}
  });
  document.addEventListener('error',event=>{
    const img=event.target;
    if(!img.matches?.('[data-social-reader-image]'))return;
    const note=document.createElement('small');note.textContent='Image unavailable · open original';img.replaceWith(note);
  },true);
  document.addEventListener('click',async event=>{
    const imageButton=event.target.closest('[data-social-image]');
    if(imageButton){
      const image=document.createElement('img');image.alt='Original source '+(imageButton.dataset.kind||'image');
      image.referrerPolicy='no-referrer';image.loading='lazy';
      const status=document.createElement('small');status.setAttribute('role','status');status.textContent='Loading source image…';
      image.addEventListener('load',()=>{status.textContent='Source image';imageButton.hidden=true;});
      image.addEventListener('error',()=>{image.remove();status.textContent='Image unavailable · open Source';imageButton.disabled=true;});
      imageButton.disabled=true;imageButton.after(image,status);image.src=imageButton.dataset.socialImage;return;
    }
    const b=event.target.closest('[data-social-handoff]');if(!b)return;const s=b.parentElement.querySelector('[data-handoff-status]');
    try{const r=await post('/api/social/'+encodeURIComponent(b.dataset.socialHandoff)+'/handoff',{});const a=document.createElement('a');a.href=r.review_url;a.textContent='Open existing publication review →';s.replaceChildren(a);}catch(e){s.textContent=e.message;}
  });
})();
