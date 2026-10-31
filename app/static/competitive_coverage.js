/* One captured archive panel shared by existing competitor/landscape surfaces. */
(() => {
  const path=location.pathname;
  if(!(/^\/(competitive-evaluation|competitors|landscapes|whitespace)(\/|$)/.test(path)||/^\/(entities\/(company|brand|breeding_program|retailer)|pulse\/company|workspaces)(\/|$)/.test(path)))return;
  const main=document.getElementById('digest-main');if(!main)return;
  const panel=document.createElement('details');panel.className='ce-archive-panel';panel.id='captured-coverage';
  const summary=document.createElement('summary');summary.textContent='Captured coverage · full archive';
  const p=document.createElement('p');p.textContent='Company matches use ANY selected company. Destination markets require explicit assignments; origins and headquarters remain separate.';
  const link=document.createElement('a');link.textContent='Open full archive';
  const compare=document.createElement('a');compare.href='/competitive-evaluation';compare.textContent='Open scoped capability comparison';
  const iframe=document.createElement('iframe');iframe.title='Scoped captured coverage';iframe.loading='lazy';
  const css=document.createElement('link');css.rel='stylesheet';css.href='/static/competitive_evaluation.css';document.head.append(css);
  panel.append(summary,p,link,document.createTextNode(' · '),compare,iframe);main.append(panel);
  let loaded='';
  function scope(){
    const src=new URL(location.href),q=new URLSearchParams(),ids=new Set();
    const canonical=/^(company|brand|program|breeding_program|variety|technology|retailer)-/;
    for(const key of ['companies','company_ids','ids','company','company_choice','entity','entity_id','selected','selected_company','focus','retailer']){
      for(const value of src.searchParams.getAll(key))for(const id of value.split(','))if(canonical.test(id))ids.add(id);
    }
    const match=path.match(/\/(?:company|brand|breeding_program|retailer)\/((?:company|brand|program|breeding_program|retailer)-[^/]+)/);
    if(match)ids.add(decodeURIComponent(match[1]));
    let defaults={};
    const bundle=document.getElementById('landscape-bundle');
    if(bundle){try{defaults=JSON.parse(bundle.textContent).filters||{};}catch(e){/* Explicit controls remain available. */}}
    const comparison=document.getElementById('ce-coverage-context');
    if(comparison){try{defaults={...defaults,...JSON.parse(comparison.textContent)};}catch(e){/* Keep URL scope. */}}
    if(!ids.size){for(const id of defaults.companies||[])ids.add(id);if(canonical.test(defaults.focus||''))ids.add(defaults.focus);}
    if(ids.size)q.set('companies',[...ids].join(','));
    let berry=src.searchParams.get('berry')||src.searchParams.get('crop')||defaults.berry||'';
    const b=path.match(/\/berries\/(blueberry|strawberry|raspberry|blackberry)/);if(b)berry=b[1];
    if(['blueberry','strawberry','raspberry','blackberry'].includes(berry))berry='berry-'+berry;
    if(/^berry-(blueberry|strawberry|raspberry|blackberry)$/.test(berry))q.set('berry',berry);
    // A generic country/region selection may describe origins, trials or rights.
    // Only an explicit canonical destination can narrow this feed automatically.
    const destination=src.searchParams.get('destination_market')||src.searchParams.get('destination')||defaults.destination_market||'';
    if(destination.startsWith('geography-'))q.set('destination',destination);
    return q;
  }
  function update(){const q=scope();link.href='/coverage/archive?'+q;compare.href='/competitive-evaluation?'+q;const url='/coverage/archive?'+q+'&embedded=1';if(panel.open&&loaded!==url){iframe.src=url;loaded=url;}}
  panel.addEventListener('toggle',update);window.addEventListener('popstate',update);window.addEventListener('bios:coverage-scope-changed',update);document.addEventListener('change',()=>setTimeout(update,0));update();
})();
