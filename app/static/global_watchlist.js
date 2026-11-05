(() => {
  const savedNav = document.querySelector('.gw-saved-landscapes nav');
  const savedActive = savedNav?.querySelector('[aria-current]');
  if (savedActive) savedNav.scrollLeft += savedActive.getBoundingClientRect().left - savedNav.getBoundingClientRect().left;
  const form = document.getElementById('gw-compare');
  if (!form) return;
  const boxes = [...document.querySelectorAll('.gw-select')];
  const button = document.getElementById('gw-compare-button');
  const status = document.getElementById('gw-selection-status');
  function update() {
    const selected = boxes.filter(box => box.checked);
    document.getElementById('gw-compare-ids').value = selected.map(box => box.value).join(',');
    button.disabled = selected.length < 2;
    button.textContent = `Compare selected (${selected.length} / 4)`;
    boxes.forEach(box => { box.disabled = selected.length >= 4 && !box.checked; });
    status.textContent = selected.length === 4 ? 'Four selected. Deselect one to choose another.' : '';
  }
  boxes.forEach(box => box.addEventListener('change', update));
  update();
})();
