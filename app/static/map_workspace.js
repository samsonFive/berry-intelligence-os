(() => {
  let letter='', search='', sort='name';
  function initial(name){const c=name.charAt(0).toUpperCase();return /^[A-Z]$/.test(c)?c:'#';}
  function render(){
    const section=document.querySelector('.gx-region-section'); if(!section)return;
    const rows=[...section.querySelectorAll('[data-region-row]')];
    rows.sort((a,b)=>a.dataset[sort].localeCompare(b.dataset[sort])||a.dataset.name.localeCompare(b.dataset.name));
    const body=section.querySelector('tbody'); let count=0;
    rows.forEach(row=>{body.append(row);row.hidden=!!((letter&&initial(row.dataset.name)!==letter)||(search&&!row.textContent.toLowerCase().includes(search)));if(!row.hidden)count++;});
    body.append(section.querySelector('[data-region-empty]'));
    section.querySelector('[data-region-empty]').hidden=count>0;
    section.querySelector('[data-region-count]').textContent=count;
    section.querySelectorAll('[data-region-letter]').forEach(button=>{button.setAttribute('aria-pressed',String(button.dataset.regionLetter===letter));button.disabled=!!button.dataset.regionLetter&&!rows.some(r=>initial(r.dataset.name)===button.dataset.regionLetter);});
    section.querySelectorAll('[data-region-sort]').forEach(button=>{button.closest('th').setAttribute('aria-sort',button.dataset.regionSort===sort?'ascending':'none');button.textContent=(button.dataset.regionSort==='name'?(document.querySelector('[name=layer]').value==='companies'?'Company':'Variety'):'Country / region')+(button.dataset.regionSort===sort?' ↓':'');});
  }
  document.addEventListener('click',event=>{if(event.target.closest('[data-focus-regions]')){document.querySelector('.gx-map-fold').open=false;const heading=document.querySelector('[data-region-heading]');heading.focus({preventScroll:true});heading.scrollIntoView({block:'start',behavior:'auto'});return;}const button=event.target.closest('[data-region-letter],[data-region-sort]');if(!button)return;if(button.hasAttribute('data-region-letter'))letter=button.dataset.regionLetter;else sort=button.dataset.regionSort;render();});
  document.addEventListener('input',event=>{if(event.target.matches('[data-region-search]')){search=event.target.value.toLowerCase();render();}});
  document.addEventListener('bios:map-updated',()=>{letter=search='';sort='name';render();});
  document.querySelector('[name=layer]')?.addEventListener('change',()=>{const form=document.getElementById('gx-query');form.querySelector('[name=activity]')?.remove();form.querySelector('[name=region_entity]')?.remove();form.requestSubmit();});
  render();
})();
