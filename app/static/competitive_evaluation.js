(() => {
  const form=document.getElementById('ce-scope');
  form?.addEventListener('submit',event=>{
    event.preventDefault();const data=new FormData(form),params=new URLSearchParams();
    for(const [key,value] of data)if(key!=='companies'&&value)params.set(key,value);
    params.set('companies',data.getAll('companies').join(','));location.search=params.toString();
  });
  const raw=document.getElementById('ce-plot-data');if(!raw)return;
  const rows=JSON.parse(raw.textContent),x=document.getElementById('ce-x'),y=document.getElementById('ce-y');
  const context=document.getElementById('ce-cohort'),target=document.getElementById('ce-plot');
  x.value='marketer.supply_months';y.value='access-model';
  const cohortFields=['peer_role','berry_id','destination_scope','origin_scope','period_start','period_end','use_system','rubric_version'];
  const cohort=a=>JSON.stringify(cohortFields.map(k=>a[k]));
  const scope=a=>JSON.stringify(['entity_id','program_or_variety',...cohortFields].map(k=>a[k]));
  function candidates(){
    const points=[];
    if(x.value==='access-model'||y.value==='access-model'){
      if(x.value===y.value)return points;
      const numeric=x.value==='access-model'?y.value:x.value;
      for(const a of rows.filter(a=>a.capability_id===numeric&&Number.isInteger(a.rating))){
        for(const model of a.access_models||[])points.push({a,b:a,x:x.value==='access-model'?model.value:a.rating,
          y:y.value==='access-model'?model.value:a.rating,category:model});
      }
    }else{
      for(const a of rows.filter(a=>a.capability_id===x.value&&Number.isInteger(a.rating))){
        for(const b of rows.filter(b=>b.capability_id===y.value&&Number.isInteger(b.rating)&&scope(a)===scope(b))){
          points.push({a,b,x:a.rating,y:b.rating});
        }
      }
    }
    return points;
  }
  function render(reset=false){
    const all=candidates(),contexts=[...new Set(all.map(p=>cohort(p.a)))];
    if(reset){const previous=context.value;context.replaceChildren(...contexts.map(value=>{const node=document.createElement('option');node.value=value;node.textContent=JSON.parse(value).join(' · ');return node;}));if(contexts.includes(previous))context.value=previous;}
    const points=all.filter(p=>cohort(p.a)===context.value),ns='http://www.w3.org/2000/svg';
    const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 600 600');
    svg.setAttribute('role','img');svg.setAttribute('aria-label',x.value+' versus '+y.value+'; '+points.length+' compatible points');svg.classList.add('ce-plot-svg');
    const categories=[...new Set(points.filter(p=>p.category).map(p=>p.category.value))].sort();
    const position=value=>typeof value==='number'?value*90:90+categories.indexOf(value)*360/Math.max(1,categories.length-1);
    for(let n=1;n<=5;n++)for(const [px,py] of [[n*90,550],[25,530-n*90]]){
      const t=document.createElementNS(ns,'text');t.setAttribute('x',px);t.setAttribute('y',py);t.textContent=n;svg.append(t);
    }
    for(const point of points){
      const c=document.createElementNS(ns,'circle');c.setAttribute('cx',position(point.x));c.setAttribute('cy',530-position(point.y));
      c.setAttribute('r',8);c.setAttribute('fill',point.category?'white':'#2c6a4d');c.setAttribute('stroke','#2c6a4d');
      const title=document.createElementNS(ns,'title');title.textContent=(point.a.entity_name||point.a.entity_id)+': '+point.x+' / '+point.y+'; '+point.a.status+'; '+(point.category?.claim_status||point.a.confidence);c.append(title);svg.append(c);
    }
    const note=document.createElement('p');note.textContent=points.length?
      points.length+' compatible points. Categorical positions are unordered; outlined markers retain their source claim status.':
      'No compatible observed pairs in this scope. Unknown values are not plotted at zero. Select different axes or inspect the matrix.';
    const list=document.createElement('ul');
    for(const point of points){const li=document.createElement('li');li.textContent=(point.a.entity_name||point.a.entity_id)+': '+point.x+' / '+point.y+'; '+point.a.program_or_variety+'; '+point.a.status+'; '+(point.category?.claim_status||point.a.confidence);list.append(li);}
    const legend=document.createElement('p');if(categories.length)legend.textContent='Unordered access categories: '+categories.join(' · ');
    target.replaceChildren(svg,note,list,legend);
  }
  x.addEventListener('change',()=>render(true));y.addEventListener('change',()=>render(true));context.addEventListener('change',()=>render());render(true);
})();
