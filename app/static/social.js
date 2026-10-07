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
  const loadImage=img=>{if(img.dataset.socialSrc){img.src=img.dataset.socialSrc;delete img.dataset.socialSrc;}};
  const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){loadImage(entry.target);observer.unobserve(entry.target);}}),{rootMargin:'180px'});
  function initializeMedia(){
    document.querySelectorAll('[data-social-src]').forEach(img=>observer.observe(img));
    document.querySelectorAll('[data-social-carousel]:not([data-ready])').forEach(carousel=>{
      carousel.dataset.ready='true';const track=carousel.querySelector('.social-carousel-track');const slides=[...track.children];const controls=carousel.querySelector('.social-carousel-controls');
      if(slides.length<2)return;controls.hidden=false;
      const update=()=>{const index=Math.round(track.scrollLeft/track.clientWidth);carousel.querySelector('[data-slide-count]').textContent=(index+1)+' / '+slides.length;};
      track.addEventListener('scroll',update,{passive:true});update();
      carousel.querySelectorAll('[data-slide-step]').forEach(button=>button.addEventListener('click',()=>{
        const index=Math.max(0,Math.min(slides.length-1,Math.round(track.scrollLeft/track.clientWidth)+Number(button.dataset.slideStep)));
        slides[index].querySelectorAll('[data-social-src]').forEach(loadImage);track.scrollTo({left:index*track.clientWidth,behavior:'instant'});
      }));
    });
  }
  const lightbox=document.createElement('dialog');lightbox.className='social-lightbox';lightbox.setAttribute('aria-label','Original post image');
  lightbox.innerHTML='<button type="button" data-lightbox-close aria-label="Close image">×</button><button type="button" data-lightbox-prev aria-label="Previous image">‹</button><img alt="Original post image"><button type="button" data-lightbox-next aria-label="Next image">›</button><span role="status"></span>';
  document.body.append(lightbox);let images=[],imageIndex=0,opener;
  function showImage(index){imageIndex=(index+images.length)%images.length;const link=images[imageIndex];const img=lightbox.querySelector('img');img.src=link.href;img.alt=link.querySelector('img').alt;[images[(imageIndex+1)%images.length],images[(imageIndex+images.length-1)%images.length]].forEach(a=>a.querySelectorAll('[data-social-src]').forEach(loadImage));lightbox.querySelector('span').textContent=(imageIndex+1)+' / '+images.length;lightbox.querySelectorAll('[data-lightbox-prev],[data-lightbox-next]').forEach(b=>b.hidden=images.length<2);}
  lightbox.querySelector('[data-lightbox-close]').onclick=()=>lightbox.close();
  lightbox.querySelector('[data-lightbox-prev]').onclick=()=>showImage(imageIndex-1);
  lightbox.querySelector('[data-lightbox-next]').onclick=()=>showImage(imageIndex+1);
  lightbox.addEventListener('keydown',event=>{event.stopPropagation();if(event.key==='ArrowLeft')showImage(imageIndex-1);if(event.key==='ArrowRight')showImage(imageIndex+1);});
  lightbox.addEventListener('close',()=>opener?.focus());
  lightbox.addEventListener('click',event=>{if(event.target===lightbox)lightbox.close();});
  document.addEventListener('error',event=>{const img=event.target;if(img.matches?.('[data-social-lightbox] img')){img.alt='Image unavailable';img.closest('a').setAttribute('aria-label','Image unavailable');}if(img===lightbox.querySelector('img'))lightbox.querySelector('span').textContent='Image unavailable';},true);
  initializeMedia();new MutationObserver(initializeMedia).observe(document.body,{childList:true,subtree:true});
  document.addEventListener('click',async event=>{
    const expand=event.target.closest('[data-social-expand]');
    if(expand){const opened=expand.getAttribute('aria-expanded')!=='true';expand.setAttribute('aria-expanded',String(opened));expand.textContent=opened?'Less text':'Full post';document.getElementById(expand.getAttribute('aria-controls')).classList.toggle('social-text-expanded',opened);return;}
    const link=event.target.closest('[data-social-lightbox]');
    if(link){event.preventDefault();event.stopImmediatePropagation();opener=link;images=[...link.closest('[data-social-carousel]').querySelectorAll('[data-social-lightbox]')];showImage(images.indexOf(link));lightbox.showModal();return;}
    const b=event.target.closest('[data-social-handoff]');if(!b)return;const s=b.parentElement.querySelector('[data-handoff-status]');
    try{const r=await post('/api/social/'+encodeURIComponent(b.dataset.socialHandoff)+'/handoff',{});const a=document.createElement('a');a.href=r.review_url;a.textContent='Open existing publication review →';s.replaceChildren(a);}catch(e){s.textContent=e.message;}
  });
})();
