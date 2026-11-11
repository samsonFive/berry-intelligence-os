(() => {
  'use strict';
  const status = document.querySelector('[data-media-status]');
  async function send(url, payload) {
    const response = await fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const value = await response.json();
    if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'Media decision could not be saved');
    return value;
  }
  document.addEventListener('click', async event => {
    const refresh = event.target.closest('[data-media-refresh]');
    const button = event.target.closest('[data-media-save],[data-media-reject],[data-media-primary]');
    if (!refresh && !button) return;
    try {
      if (refresh) await send('/api/brand-media/reuse', {entity_id: refresh.dataset.mediaRefresh});
      else {
        const card = button.closest('[data-media-review]');
        const changes = button.hasAttribute('data-media-reject') ? {rejected: true} : button.hasAttribute('data-media-primary') ? {primary: true} : {
          kind: card.querySelector('[data-media-kind]').value, classification_basis: card.querySelector('[data-media-basis]').value
        };
        await send('/api/brand-media/' + card.dataset.mediaReview + '/decision', {changes, reviewer: card.querySelector('[data-media-reviewer]').value});
      }
      location.reload();
    } catch (error) { status.textContent = error.message; }
  });
  document.addEventListener('submit', async event => {
    const form = event.target.closest('[data-media-upload]');
    if (!form) return;
    event.preventDefault();
    try {
      const values = new FormData(form);
      const file = values.get('image');
      if (!file || !file.size || file.size > 2 * 1024 * 1024) throw new Error('Choose a raster image up to 2 MB');
      const content = await new Promise((resolve, reject) => {
        const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]); reader.onerror = reject; reader.readAsDataURL(file);
      });
      const metadata = {};
      ['entity_id','kind','source_kind','publisher','caption','attribution','authorization','classification_basis'].forEach(key => { metadata[key] = values.get(key); });
      metadata.source_page_url = values.get('source_page_url') || null;
      metadata.policy = {display: values.has('display'), cache: values.has('cache'), export: values.has('export'),
        source_url: values.get('policy_source_url'), basis: values.get('policy_basis'), checked_at: new Date().toISOString(),
        expires_at: values.get('expires_at') ? new Date(values.get('expires_at')).toISOString() : null};
      await send('/api/brand-media/upload', {metadata, content_base64: content});
      location.reload();
    } catch (error) { status.textContent = error.message; }
  });
})();
