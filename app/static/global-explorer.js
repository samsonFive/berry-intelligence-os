(() => {
  'use strict';
  const countries = JSON.parse(document.getElementById('gx-data').textContent);
  const byISO = new Map(countries.map(c => [c.iso, c]));
  const byID = new Map(countries.map(c => [c.id, c]));
  const field = document.getElementById('gx-countries');
  const selected = new Set(field.value.split(',').filter(Boolean));
  const form = document.getElementById('gx-query');
  const svg = document.getElementById('gx-map');
  const group = document.getElementById('gx-boundaries');
  const status = document.getElementById('gx-map-status');
  const NS = 'http://www.w3.org/2000/svg';
  const layer = form.elements.layer.value;
  function params() { const p = new URLSearchParams(new FormData(form)); p.delete('berry'); p.set('berry', berryValue()); return p; }
  function coverage(c) { return layer === 'news' ? c.count : c.region_count; }
  function paint() { group.querySelectorAll('[data-country]').forEach(el => { const c=byID.get(el.dataset.country); el.classList.toggle('has-coverage', coverage(c)>0); el.setAttribute('aria-label', c.name+', '+coverage(c)+(layer==='news'?' stories':' recorded locations')); }); }
  function berryValue() { return Array.from(document.querySelectorAll('[data-berry]:checked')).map(el => el.value).join(','); }
  form.addEventListener('keydown', event => event.stopPropagation());
  let scale = 1, tx = 0, ty = 0, drag = null, moved = false;
  let refreshTimer, revision = 0, previewID = null;
  function refresh() {
    clearTimeout(refreshTimer);
    const mine = ++revision;
    refreshTimer = setTimeout(async () => {
      const queryParams = params();
      status.textContent = 'Updating intelligence…';
      try {
        const response = await fetch('/explorer?' + queryParams);
        if (!response.ok) throw Error();
        const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
        if (mine !== revision) return;
        document.getElementById('gx-results').replaceWith(doc.getElementById('gx-results'));
        document.getElementById('gx-statistics').replaceWith(doc.getElementById('gx-statistics'));
        document.querySelector('[data-news-link]').href=doc.querySelector('[data-news-link]').href;
        document.dispatchEvent(new Event('bios:intelligence-updated'));
        const fresh = JSON.parse(doc.getElementById('gx-data').textContent);
        fresh.forEach(c => { byISO.set(c.iso,c); byID.set(c.id,c); });
        paint();
        document.dispatchEvent(new Event('bios:map-updated'));
        document.querySelectorAll('.gx-country-list input').forEach(el => { el.parentElement.querySelector('small').textContent = coverage(byID.get(el.value))+(layer==='news'?' stories':' locations'); });
        if (previewID) preview(byID.get(previewID));
        const story=new URLSearchParams(location.search).get('story'); if(story)queryParams.set('story',story);
        history.replaceState(history.state, '', '/explorer?' + queryParams);
        status.textContent = selected.size + ' countries selected · intelligence updated';
      } catch (error) { if (mine === revision) status.textContent = 'Unable to update intelligence. Apply scope to retry.'; }
    }, 200);
  }
  function preview(country, name) {
    previewID = country?.id || null;
    const panel = document.getElementById('gx-preview');
    panel.replaceChildren();
    function add(tag, text) { const el = document.createElement(tag); el.textContent = text; panel.append(el); return el; }
    add('h2', country ? country.name : name);
    if (!country) { add('p', 'No canonical country record is available. This boundary cannot yet scope evidence.'); return; }
    if (country.unavailable) add('p', 'No canonical Geography or published evidence is available for this country. You can select it to preserve an explicit empty scope.');
    add('p', `${coverage(country)} ${layer==='news'?'stories':'recorded locations'} · ${country.berries.join(', ') || 'No berry tags available'}`);
    if(layer!=='news'){ add('p','Recorded presence is not acreage or market share. News dates and review status do not apply to locations.'); }
    if(layer==='news')add('p', country.companies.length ? 'Companies mentioned: ' + country.companies.slice(0, 8).join(', ') : 'No companies linked to this evidence.');
    if (layer==='news' && !country.recent.length) add('p', 'No published intelligence for this country and berry. See the market context and region layers for separately recorded information.');
    if(layer==='news')country.recent.forEach(r => { const a = add('a', r.title + ' · ' + r.date); a.href = r.href; });
    const button = add('button', selected.has(country.id) ? 'Deselect country' : 'Select country');
    button.type = 'button'; button.className = 'bos-btn';
    button.onclick = () => { toggle(country.id); preview(country); };
  }
  function sync() {
    field.value = [...selected].join(',');
    document.querySelectorAll('.gx-country-list input').forEach(el => { el.checked = selected.has(el.value); });
    group.querySelectorAll('[data-country]').forEach(el => { const on = selected.has(el.dataset.country); el.classList.toggle('is-selected', on); el.setAttribute('aria-pressed', String(on)); });
    const chips = document.querySelector('.gx-chips'); chips.replaceChildren();
    if (!selected.size) chips.textContent = 'Global scope · select countries to focus';
    selected.forEach(id => { const b = document.createElement('button'); b.type = 'button'; b.className = 'gx-chip'; b.textContent = (byID.get(id)?.name || id) + ' ×'; b.setAttribute('aria-label', 'Deselect ' + (byID.get(id)?.name || id)); b.onclick = () => toggle(id); chips.append(b); });
    const queryParams = params();
    document.querySelector('[data-snapshot]').href = '/explorer/snapshot?' + queryParams;
    queryParams.set('countries',''); document.querySelector('[data-clear-countries]').href='/explorer?'+queryParams;
    document.querySelector('[data-all-berries]').setAttribute('aria-pressed', String(!berryValue()));
    status.textContent = `${selected.size} countries selected.`;
  }
  function toggle(id) { selected.has(id) ? selected.delete(id) : selected.add(id); sync(); refresh(); }
  document.querySelectorAll('[data-berry]').forEach(el => el.addEventListener('change', () => { sync(); refresh(); }));
  document.querySelector('[data-all-berries]').addEventListener('click', () => {
    document.querySelectorAll('[data-berry]').forEach(el => { el.checked = false; }); sync(); refresh();
  });
  form.addEventListener('change', e => { if (e.target.matches('.gx-country-list input')) toggle(e.target.value); });
  document.querySelectorAll('[data-remove]').forEach(b => { b.onclick = () => toggle(b.dataset.remove); });
  document.getElementById('gx-search').oninput = e => {
    document.querySelectorAll('[data-country-name]').forEach(el => { el.hidden = !el.dataset.countryName.includes(e.target.value.toLowerCase()); });
  };
  function transform() { group.setAttribute('transform', `translate(${tx} ${ty}) scale(${scale})`); }
  document.querySelectorAll('[data-zoom]').forEach(b => { b.onclick = () => {
    if (b.dataset.zoom === 'reset') { scale = 1; tx = ty = 0; }
    else { const next = Math.max(1, Math.min(6, scale * (b.dataset.zoom === 'in' ? 1.4 : 1/1.4))); tx = 500 - (500-tx)*next/scale; ty = 250 - (250-ty)*next/scale; scale = next; }
    transform();
  }; });
  svg.addEventListener('pointerdown', e => { drag = {x:e.clientX,y:e.clientY,tx,ty}; moved = false; });
  svg.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = (e.clientX-drag.x)*1000/svg.clientWidth, dy = (e.clientY-drag.y)*500/svg.clientHeight;
    if (Math.abs(dx)+Math.abs(dy)>5) { moved = true; tx = drag.tx+dx; ty = drag.ty+dy; transform(); }
  });
  window.addEventListener('pointerup', () => { drag = null; });
  svg.addEventListener('pointercancel', () => { drag = null; });
  function ringPath(ring) {
    // Split dateline jumps instead of drawing a polygon across the world.
    return ring.map(([lon, lat], i) => `${!i || Math.abs(lon-ring[i-1][0])>180 ? 'M' : 'L'}${((lon+180)*1000/360).toFixed(2)},${((90-lat)*500/180).toFixed(2)}`).join(' ')+' Z';
  }
  fetch('/static/countries.geojson').then(r => { if (!r.ok) throw Error(); return r.json(); }).then(data => {
    data.features.forEach(f => {
      const iso = f.properties['ISO3166-1-Alpha-2'];
      const c = byISO.get(iso);
      const path = document.createElementNS(NS, 'path');
      const polys = f.geometry.type === 'MultiPolygon' ? f.geometry.coordinates : [f.geometry.coordinates];
      path.setAttribute('d', polys.flatMap(p => p.map(ringPath)).join(' '));
      path.setAttribute('fill-rule', 'evenodd'); path.classList.add('gx-country');
      const title = document.createElementNS(NS, 'title'); title.textContent = f.properties.name; path.append(title);
      if (c) {
        path.dataset.country = c.id; path.setAttribute('tabindex', '0'); path.setAttribute('role','button');
        path.setAttribute('aria-label', c.name + ', ' + coverage(c) + (layer==='news'?' stories':' recorded locations'));
        path.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(c.id); preview(byID.get(c.id)); } });
      } else path.classList.add('gx-unavailable');
      path.addEventListener('pointerenter', () => { if (!drag) preview(byISO.get(iso), f.properties.name); });
      path.addEventListener('focus', () => preview(byISO.get(iso), f.properties.name));
      path.addEventListener('click', () => { if (moved) return; if (c) toggle(c.id); preview(byISO.get(iso), f.properties.name); });
      group.append(path);
    }); paint(); sync(); status.textContent = 'Country boundaries loaded. Select countries, then apply scope.';
  }).catch(() => { status.textContent = 'Map unavailable. Use the country selection list below.'; document.querySelector('.gx-country-picker').open = true; });
})();
