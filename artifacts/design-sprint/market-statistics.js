(() => {
  'use strict';
  const host = document.querySelector('#market-statistics');
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names = {'berry-blueberry':'Blueberry','berry-strawberry':'Strawberry','berry-raspberry':'Raspberry','berry-blackberry':'Blackberry'};
  let dataset, failed = false, scope = {countries:[], berries:[], countryNames:[]};
  window.renderMarketStatistics = next => {
    scope = next;
    const heading = '<header class="market-heading"><div><span class="eyebrow">MARKET CONTEXT</span><h2>Market statistics</h2></div><span class="market-year">Annual figures · 2025</span></header>';
    if (!dataset) {host.innerHTML=heading+'<p>'+(failed?'Statistics could not load. Reload this preview to retry.':'Loading public statistics…')+'</p>';return;}
    const groups = dataset.groups.filter(g=>(!scope.countries.length||scope.countries.includes(g.country_id))&&(!scope.berries.length||scope.berries.includes(g.berry_id)));
    const countryIds = scope.countries.length ? scope.countries : [...new Set(dataset.groups.map(g=>g.country_id))];
    const berryIds = scope.berries.length ? scope.berries : Object.keys(names);
    const missing = countryIds.map(id=>{
      const absent = berryIds.filter(b=>!dataset.groups.some(g=>g.country_id===id&&g.berry_id===b));
      const name = scope.countryNames.find(c=>c.id===id)?.name || dataset.groups.find(g=>g.country_id===id)?.country || id;
      return absent.length ? `${name}: ${absent.map(b=>names[b]||b).join(', ')}` : '';
    }).filter(Boolean);
    host.innerHTML = heading + '<p class="market-scope">Country and berry selections apply. News dates and company filters do not change these annual figures.</p>' +
      '<div class="market-stat-grid">' + groups.map(g=>`<article class="market-country"><header><h3>${escape(g.country)}</h3><span>${escape(g.period)}</span></header><p class="market-commodity">${escape(g.commodity)}</p><dl>${g.metrics.map(m=>`<div><dt>${escape(m.label)}</dt><dd>${escape(m.display)} <span>${escape(m.unit)}</span></dd><p>${escape(m.change)}</p></div>`).join('')}</dl><footer><a href="${escape(g.source_url)}" target="_blank" rel="noopener">${escape(g.publisher)} · source ↗</a><span>Published ${escape(g.released_on)}</span></footer><details><summary>What these figures cover</summary><p>${escape(g.note)}</p><p>${escape(g.source_title)} · Checked ${escape(dataset.checked_on)}</p></details></article>`).join('') + '</div>' +
      (!groups.length ? '<div class="market-empty"><h3>No statistics added for this selection yet</h3><p>This is a coverage gap, not zero production or trade.</p></div>' : '') +
      `<div class="market-availability"><strong>Initial dataset</strong><span>Blueberries in the United States and Peru. Other countries and berries still need research; these are not global totals.</span>${missing.length?`<details><summary>Missing from this selection</summary><p>${escape(missing.join(' · '))}</p></details>`:''}</div>`;
  };
  fetch('market-statistics.json').then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{dataset=data;window.renderMarketStatistics(scope);}).catch(()=>{failed=true;window.renderMarketStatistics(scope);});
})();
