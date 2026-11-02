(() => {
  'use strict';
  const root = document.querySelector('[data-research-sheet]');
  if (!root) return;
  const model = JSON.parse(document.getElementById('research-sheet-data').textContent);
  const headers = [...model.headers, ...model.extra_headers];
  const grid = root.querySelector('[data-grid]');
  const filters = root.querySelector('[data-filters]');
  const message = root.querySelector('[data-message]');
  const selected = new Set();
  let visible = [], columns = headers.map((_, i) => i).slice(0, 14), anchor = null, focus = null, dragging = false;
  const el = (tag, text, className) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; };
  const mode = () => root.querySelector('[data-mode]').value;
  const includeHeaders = () => root.querySelector('[data-headers]').checked;
  const letter = n => String.fromCharCode(65 + n);
  const value = (row, col) => {
    if (col === 10 && mode() === 'proposals' && row.can_fill) return row.proposal;
    if (col < 14) return row.original[col] ?? '';
    return [row.role, row.status + (row.issue ? ' · ' + row.issue : ''), row.sources.join('\n'), row.baseline, row.leads, row.closeout][col - 14] ?? '';
  };
  const literal = value => {
    const text = String(value ?? '');
    return /^\s*[=+@]/.test(text) || (/^\s*-/.test(text) && !/^\s*-\d+(\.\d+)?\s*$/.test(text)) ? "'" + text : text;
  };
  const tsv = matrix => matrix.map(row => row.map(value => {
    const text = literal(value);
    return /[\t\r\n"]/.test(text) ? '"' + text.replaceAll('"', '""') + '"' : text;
  }).join('\t')).join('\r\n');
  const escape = text => String(text ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
  const htmlTable = matrix => '<table>' + matrix.map(row => '<tr>' + row.map(cell => '<td style="mso-number-format:\'\\@\'">' + escape(literal(cell)).replaceAll('\n', '<br>') + '</td>').join('') + '</tr>').join('') + '</table>';
  async function copy(matrix, notice) {
    const text = tsv(matrix);
    try {
      if (navigator.clipboard?.write && window.ClipboardItem) {
        await navigator.clipboard.write([new ClipboardItem({'text/plain': new Blob([text], {type:'text/plain'}), 'text/html':new Blob([htmlTable(matrix)], {type:'text/html'})})]);
      } else if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
      else {
        const area = el('textarea'); area.value = text; area.style.position = 'fixed'; area.style.opacity = '0'; document.body.append(area); area.select();
        if (!document.execCommand('copy')) throw new Error('Clipboard unavailable');
        area.remove();
      }
      message.textContent = notice;
    } catch (_) { message.textContent = 'Clipboard access was blocked. Select cells and press Ctrl/Cmd+C, or download the row-mapped TSV.'; }
  }
  function rectangle() {
    if (!anchor || !focus) return null;
    return {r0:Math.min(anchor.r, focus.r), r1:Math.max(anchor.r, focus.r), c0:Math.min(anchor.c, focus.c), c1:Math.max(anchor.c, focus.c)};
  }
  function address(rows, cols) {
    if (!rows.length || !cols.length || cols.some(c => c >= 14)) return '';
    if (rows.some((row, i) => i && row.row !== rows[i-1].row + 1) || cols.some((col, i) => i && col !== cols[i-1] + 1)) return '';
    return letter(cols[0]) + rows[0].row + ':' + letter(cols.at(-1)) + rows.at(-1).row;
  }
  function matrix(rows, cols, withHeaders) { return [...(withHeaders ? [cols.map(c => headers[c])] : []), ...rows.map(row => cols.map(col => value(row,col)))]; }
  function cellSelection() {
    const rect = rectangle();
    if (!rect) return null;
    const rows = visible.slice(rect.r0, rect.r1 + 1), cols = columns.slice(rect.c0, rect.c1 + 1);
    return {rows, cols, matrix:matrix(rows,cols,includeHeaders()), address:includeHeaders() ? '' : address(rows,cols)};
  }
  function updateSelection() {
    const rect = rectangle();
    grid.querySelectorAll('td[data-r]').forEach(cell => {
      const inside = rect && +cell.dataset.r >= rect.r0 && +cell.dataset.r <= rect.r1 && +cell.dataset.c >= rect.c0 && +cell.dataset.c <= rect.c1;
      cell.classList.toggle('is-selected', Boolean(inside)); cell.setAttribute('aria-selected', Boolean(inside));
    });
    root.querySelector('[data-copy-cells]').disabled = !rect;
    root.querySelector('[data-copy-rows]').disabled = selected.size === 0;
    root.querySelector('[data-copy-roles]').disabled = selected.size === 0;
    const current = cellSelection();
    root.querySelector('[data-selection]').textContent = visible.length + ' matching rows · ' + selected.size + ' checked' + (current ? ' · ' + current.rows.length + ' × ' + current.cols.length + ' cells selected. ' + (current.address ? 'Paste into ' + current.address + ' in the starting sheet.' : 'This selection is compacted or includes research columns/headers; paste into a separate range.') : ' · Choose cells or check rows to copy.');
  }
  function choose(r,c,extend=false,moveFocus=false) {
    message.textContent = '';
    r = Math.max(0, Math.min(visible.length-1,r)); c = Math.max(0,Math.min(columns.length-1,c));
    if (!extend || !anchor) anchor = {r,c}; focus = {r,c}; updateSelection();
    if (moveFocus) { const cell = grid.querySelector(`td[data-r="${r}"][data-c="${c}"]`); if (cell) {cell.tabIndex=0;cell.focus({preventScroll:true});cell.scrollIntoView({block:'nearest',inline:'nearest'});} }
  }
  function inspect(row) {
    const body = root.querySelector('[data-evidence-body]'); body.replaceChildren();
    body.append(el('h3','Original row ' + row.row + ' · ' + (row.original[8] || row.original[1])));
    body.append(el('p',row.summary),el('p','Commercial proposal (unreviewed): ' + (row.proposal || 'No sourced contact available.')));
    if (row.role) body.append(el('p',row.role));
    if (row.leads) body.append(el('p','Rights / programme leads — supply unverified: '+row.leads));
    if (row.closeout) body.append(el('p',row.closeout));
    body.append(el('p',row.status + ' · ' + row.baseline));
    if (row.issue) body.append(el('p','Needs verification: ' + row.issue));
    if (row.review_notes.length) body.append(el('p','Photo transcription: ' + row.review_notes.join('; ')));
    if (row.aliases.length) body.append(el('p','Proposed aliases: ' + row.aliases.join(' · ')));
    const list = el('ul');
    row.sources.forEach(url => {if (!/^https?:\/\//i.test(url)) return; const item=el('li'),a=el('a',url);a.href=url;a.target='_blank';a.rel='noopener noreferrer';item.append(a);list.append(item);});body.append(list);
    if (row.href?.startsWith('/entities/')) {const a=el('a','Open full variety profile →');a.href=row.href+'#imported-research';body.append(a);}
    root.querySelector('[data-evidence]').open=true;
  }
  function render(reset=true) {
    message.textContent = '';
    if (reset) {selected.clear();anchor=null;focus=null;root.querySelector('[data-blocks]').hidden=true;}
    const data = new FormData(filters), words=String(data.get('q') || '').toLowerCase().split(/\s+/).filter(Boolean), crop=data.get('crop'), isolate=data.get('isolate'), baseline=data.get('baseline');
    const from=Number(data.get('from')) || 2, to=Number(data.get('to')) || Infinity;
    visible=model.rows.filter(row => row.row>=from && row.row<=to && (!crop || row.original[0]===crop) && (!baseline || row.baseline===baseline) && words.every(w=>row.search.includes(w)) && (isolate==='all' || isolate==='missing'&&row.missing_role || isolate==='fillable'&&row.can_fill || isolate==='unresolved'&&row.missing_role&&!row.can_fill || isolate==='leads'&&row.missing_role&&!row.can_fill&&row.leads || isolate==='no-leads'&&row.missing_role&&!row.can_fill&&!row.leads || isolate==='issues'&&(row.issue||row.review_notes.length)));
    grid.replaceChildren();grid.setAttribute('aria-rowcount',visible.length+1);grid.setAttribute('aria-colcount',columns.length+1);
    const head=el('thead'),hr=el('tr'),corner=el('th','Source row','sheet-row-number');hr.append(corner);
    columns.forEach(col=>{const th=el('th');th.scope='col';th.append(el('small',col<14 ? letter(col) : 'RESEARCH'),el('span',headers[col]));hr.append(th);});head.append(hr);grid.append(head);
    const body=el('tbody');
    visible.forEach((row,r)=>{
      const tr=el('tr');tr.classList.toggle('is-row-selected',selected.has(row.row));const gutter=el('th',undefined,'sheet-row-number');gutter.scope='row';
      const check=el('input');check.type='checkbox';check.checked=selected.has(row.row);check.setAttribute('aria-label','Select original row '+row.row);
      check.addEventListener('change',()=>{check.checked ? selected.add(row.row):selected.delete(row.row);tr.classList.toggle('is-row-selected',check.checked);root.querySelector('[data-blocks]').hidden=true;updateSelection();});
      const details=el('button',String(row.row)+(row.issue||row.review_notes.length?' !':''));details.type='button';details.title='Inspect row '+row.row+' sources and review notes';details.addEventListener('click',()=>inspect(row));gutter.append(check,details);tr.append(gutter);
      columns.forEach((col,c)=>{const td=el('td');td.dataset.r=r;td.dataset.c=c;td.tabIndex=-1;td.setAttribute('role','gridcell');td.dataset.proposal=String(col===10&&mode()==='proposals'&&row.can_fill);td.append(el('div',String(value(row,col))));td.title=String(value(row,col))+(td.dataset.proposal==='true'?' · Unreviewed research proposal':'');tr.append(td);});body.append(tr);
    });
    if (!visible.length) {const tr=el('tr'),td=el('td','No matching original rows. Clear a filter or change the row range.');td.colSpan=columns.length+1;tr.append(td);body.append(tr);}
    grid.append(body);updateSelection();
  }
  grid.addEventListener('mousedown',event=>{const cell=event.target.closest('td[data-r]');if(!cell||event.button!==0)return;event.preventDefault();dragging=true;choose(+cell.dataset.r,+cell.dataset.c,event.shiftKey,true);});
  grid.addEventListener('mouseover',event=>{if(!dragging)return;const cell=event.target.closest('td[data-r]');if(cell)choose(+cell.dataset.r,+cell.dataset.c,true);});
  document.addEventListener('mouseup',()=>{dragging=false;});
  grid.addEventListener('keydown',event=>{
    if (!focus) return;
    const delta={ArrowUp:[-1,0],ArrowDown:[1,0],ArrowLeft:[0,-1],ArrowRight:[0,1]}[event.key];
    if(delta){event.preventDefault();choose(focus.r+delta[0],focus.c+delta[1],event.shiftKey,true);}
    if(event.key==='Escape'){anchor=null;focus=null;updateSelection();}
  });
  grid.addEventListener('copy',event=>{const current=cellSelection();if(!current)return;event.preventDefault();event.clipboardData.setData('text/plain',tsv(current.matrix));event.clipboardData.setData('text/html',htmlTable(current.matrix));message.textContent=current.address?'Copied. Paste into '+current.address+'.':'Copied the selected cells as a compact table.';});
  root.querySelector('[data-copy-cells]').addEventListener('click',()=>{const current=cellSelection();if(current)copy(current.matrix,current.address?'Copied. Paste into '+current.address+'.':'Copied selected cells. Filtered selections are compacted.');});
  root.querySelector('[data-copy-rows]').addEventListener('click',()=>{const rows=visible.filter(r=>selected.has(r.row)),dest=includeHeaders()?'':address(rows,columns);copy(matrix(rows,columns,includeHeaders()),dest?'Copied. Paste into '+dest+'.':'Copied '+rows.length+' selected records as a compact table; use original row numbers to align them.');});
  root.querySelector('[data-select-all]').addEventListener('click',()=>{visible.forEach(r=>selected.add(r.row));render(false);});
  root.querySelector('[data-clear-selection]').addEventListener('click',()=>{selected.clear();anchor=null;focus=null;root.querySelector('[data-blocks]').hidden=true;render(false);});
  root.querySelector('[data-copy-roles]').addEventListener('click',()=>{
    const rows=visible.filter(r=>selected.has(r.row)),blocks=[];
    rows.forEach(row=>{let block=blocks.at(-1);if(!block||row.row!==block.at(-1).row+1){block=[];blocks.push(block);}block.push(row);});
    const buttons=root.querySelector('[data-block-buttons]');buttons.replaceChildren();
    blocks.forEach(block=>{const dest=address(block,[10]),button=el('button','Copy '+dest);button.type='button';button.addEventListener('click',()=>copy(matrix(block,[10],false),'Copied '+block.length+' Commercial Entity cells. Paste into '+dest+'; no header included.'));buttons.append(button);});root.querySelector('[data-blocks]').hidden=false;
  });
  function choices() {
    const body=root.querySelector('[data-column-choices]');body.replaceChildren();
    headers.forEach((header,col)=>{const label=el('label'),check=el('input');check.type='checkbox';check.checked=columns.includes(col);check.addEventListener('change',()=>{if(check.checked)columns.push(col);else if(columns.length>1)columns=columns.filter(n=>n!==col);else{check.checked=true;return;}columns.sort((a,b)=>a-b);root.querySelector('[data-preset]').value='custom';anchor=null;focus=null;render(false);});label.append(check,document.createTextNode((col<14?letter(col)+' · ':'')+header));body.append(label);});
  }
  root.querySelector('[data-preset]').addEventListener('change',event=>{if(event.target.value==='custom')return;columns=event.target.value==='roles'?[8,10,14,15,16,18,19]:event.target.value==='all'?headers.map((_,i)=>i):headers.slice(0,14).map((_,i)=>i);anchor=null;focus=null;choices();render(false);});
  root.querySelector('[data-mode]').addEventListener('change',()=>{anchor=null;focus=null;root.querySelector('[data-blocks]').hidden=true;render(false);});
  root.querySelector('[data-headers]').addEventListener('change',updateSelection);
  filters.addEventListener('submit',event=>event.preventDefault());filters.addEventListener('input',()=>{message.textContent='';render();});
  root.querySelector('[data-clear]').addEventListener('click',()=>{filters.reset();render();});
  root.querySelector('[data-download]').addEventListener('click',()=>{
    const extras=[15,16,18,19].filter(col=>!columns.includes(col)),cols=[...columns,...extras];
    const data=[['Source row',...cols.map(c=>headers[c])],...visible.map(row=>[row.row,...cols.map(c=>value(row,c))])];
    const blob=new Blob(['\uFEFF'+tsv(data)],{type:'text/tab-separated-values;charset=utf-8'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='patent-research-row-map.tsv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    message.textContent='Downloaded '+visible.length+' records with original row numbers, review status and sources.';
  });
  choices();render();
})();
