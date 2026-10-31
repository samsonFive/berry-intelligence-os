(() => {
  for (const picker of document.querySelectorAll('[data-ce-entity-picker]')) {
    const search=picker.querySelector('[data-ce-entity-search]');
    const options=[...picker.querySelectorAll('.ce-entity-choice')];
    const picked=picker.querySelector('[data-ce-picked-entities]');
    const count=picker.querySelector('[data-ce-entity-count]');
    const normalize=text=>text.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase();
    const filter=()=>{
      const query=normalize(search.value.trim());let visible=0;
      for(const label of options){label.hidden=!normalize(label.dataset.ceSearch||label.textContent).includes(query);if(!label.hidden)visible++;}
      picker.querySelector('[data-ce-entity-empty]').hidden=visible>0;
    };
    const update=()=>{
      const selected=options.filter(label=>label.querySelector('input').checked);
      count.textContent=selected.length?selected.length+' selected':'All entities';
      picked.replaceChildren(...selected.map(label=>{
        const input=label.querySelector('input'),name=label.querySelector('[data-ce-entity-name]').textContent;
        const button=document.createElement('button');button.type='button';
        button.textContent=name+' ×';button.setAttribute('aria-label','Remove '+name);
        button.addEventListener('click',()=>{input.checked=false;input.dispatchEvent(new Event('change',{bubbles:true}));});
        return button;
      }));
    };
    search.addEventListener('input',filter);
    picker.addEventListener('change',update);
    picker.querySelector('[data-ce-entity-clear]').addEventListener('click',()=>{
      for(const label of options)label.querySelector('input').checked=false;
      picker.dispatchEvent(new Event('change',{bubbles:true}));
    });
    update();
  }
})();
