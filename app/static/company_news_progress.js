document.querySelectorAll('[data-company-news-progress]').forEach(function(root){
  var initial=Number(root.dataset.initialFinished||0), initialState=root.querySelector('[data-news-progress-state]').textContent.trim(), stopped=false;
  function poll(){
    if(stopped)return;
    fetch(root.dataset.companyNewsProgress,{credentials:'same-origin',headers:{Accept:'application/json'},cache:'no-store'}).then(function(response){if(!response.ok)throw new Error('unavailable');return response.json();}).then(function(job){
      root.querySelector('[data-news-progress-label]').textContent=job.finished+' of '+job.total+' companies researched';
      root.querySelector('[data-news-progress-state]').textContent=String(job.state||'draft').replaceAll('_',' ');
      root.querySelector('[data-news-progress-message]').textContent=job.message||'';
      root.querySelectorAll('[data-news-active-only]').forEach(function(node){node.hidden=!['running','queued'].includes(job.state);});
      root.querySelectorAll('[data-news-pending-only]').forEach(function(node){node.hidden=['running','queued'].includes(job.state)||job.finished>=job.total;});
      if(job.finished>initial||(['running','queued'].includes(initialState)&&!['running','queued'].includes(job.state)))root.querySelector('[data-news-new-findings]').hidden=false;
      if(['running','queued'].includes(job.state)||job.worker_active)setTimeout(poll,4000);else stopped=true;
    }).catch(function(){root.querySelector('[data-news-progress-message]').textContent='Progress is temporarily unavailable. Your saved findings remain available; reload to reconnect.';stopped=true;});
  }
  poll();
});
