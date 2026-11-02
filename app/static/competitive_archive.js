(() => {
  const button=document.getElementById('archive-refresh');
  button?.addEventListener('click',async()=>{
    const status=document.getElementById('archive-refresh-status'),y=scrollY;
    status.textContent='Refreshing…';button.disabled=true;
    try{
      const response=await fetch(location.href,{cache:'no-store',credentials:'same-origin'});
      if(!response.ok)throw Error('Coverage retrieval failed');
      const doc=new DOMParser().parseFromString(await response.text(),'text/html');
      if(!doc.getElementById('archive-results'))throw Error('Coverage result unavailable');
      for(const id of ['archive-results','archive-counts','archive-pagination']){
        const current=document.getElementById(id),next=doc.getElementById(id);
        if(current&&next)current.replaceWith(next);
      }
      document.dispatchEvent(new CustomEvent('bios:intelligence-updated'));
      scrollTo(0,y);status.textContent='Captured archive refreshed. Filters and reading position retained.';
    }catch(e){status.textContent='Retrieval failure. Existing results remain; retry refresh.';}
    finally{button.disabled=false;}
  });
})();
