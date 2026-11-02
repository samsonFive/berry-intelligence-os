(() => {
 const dialog=document.querySelector('[data-entity-research]');
 if(!dialog)return;
 const frame=dialog.querySelector('[data-entity-research-frame]');
 function load(topic='breeder technical sheets trials awards news patents'){
  const query=[dialog.dataset.targetName,dialog.dataset.targetBerry,topic].filter(Boolean).join(' ');
  frame.src='/varieties/research?'+new URLSearchParams({entity_id:dialog.dataset.targetId||'',q:query});
 }
 document.querySelector('[data-open-entity-research]')?.addEventListener('click',()=>{if(!frame.getAttribute('src'))load();dialog.showModal();});
 dialog.querySelector('[data-close-entity-research]').addEventListener('click',()=>dialog.close());
 dialog.querySelectorAll('[data-research-topic]').forEach(button=>button.addEventListener('click',()=>load(button.dataset.researchTopic)));
})();
