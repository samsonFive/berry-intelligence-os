(() => {
  'use strict';
  const dialog = document.getElementById('viewer-export-dialog');
  if (!dialog) return;
  document.querySelector('[data-open-export]')?.addEventListener('click', () => dialog.showModal());
  document.querySelectorAll('[data-select-stories]').forEach(button => button.addEventListener('click', () => {
    dialog.querySelectorAll('[name="story_ids"]').forEach(box => { box.checked = button.dataset.selectStories === 'all'; });
  }));
  const baseline = document.getElementById('vx-baseline-mode');
  const upload = dialog.querySelector('[data-baseline-upload]');
  const update = () => { upload.hidden = baseline.value !== 'upload'; };
  baseline.addEventListener('change', update);
  update();
  dialog.querySelector('.vx-form')?.addEventListener('submit', event => {
    const button = event.target.querySelector('.green-button');
    if (button) { button.disabled = true; button.textContent = 'Preparing research and available assets…'; }
  });
  if (typeof dialog.showModal === 'function') { dialog.close(); dialog.showModal(); }
  else dialog.setAttribute('open', '');
})();
