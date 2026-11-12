(function () {
  'use strict';
  var opener = null;
  var sourceReturn = null;
  function galleryDialogs(dialog) {
    return Array.from(dialog.closest('[data-brand-gallery]').querySelectorAll('[data-brand-dialog]')).filter(function (item) { return !item.closest('[data-brand-card]').hidden; });
  }
  function open(dialog, trigger) {
    if (!dialog || typeof dialog.showModal !== 'function') return false;
    if (trigger) opener = trigger;
    var dialogs = galleryDialogs(dialog);
    dialog.querySelectorAll('[data-brand-step]').forEach(function (button) { button.hidden = dialogs.length < 2; });
    dialog.querySelector('[data-brand-position]').textContent = (dialogs.indexOf(dialog) + 1) + ' / ' + dialogs.length;
    dialog.showModal();
    dialog.querySelector('[data-brand-close]').focus({ preventScroll:true });
    return true;
  }
  function move(dialog, step) {
    var dialogs = galleryDialogs(dialog);
    if (dialogs.length < 2) return;
    var next = dialogs[(dialogs.indexOf(dialog) + step + dialogs.length) % dialogs.length];
    dialog.dataset.brandMoving = '1';
    dialog.close();
    open(next);
  }
  function hideBrokenImage(image) {
    if (image.hasAttribute('data-brand-logo-fallback')) {
      var mark = document.createElement('span');
      mark.className = image.dataset.brandLogoStyle === 'dossier' ? 'bos-monogram bos-entity-logo-fallback' : 'company-monogram company-large';
      mark.textContent = image.dataset.brandLogoFallback;
      mark.setAttribute('aria-hidden', 'true');
      image.replaceWith(mark);
      return;
    }
    var card = image.closest('[data-brand-card]');
    if (card) {
      card.hidden = true;
      var dialog = card.querySelector('[data-brand-dialog]');
      if (dialog && dialog.open) dialog.close();
      var gallery = card.closest('[data-brand-gallery]');
      if (!Array.from(gallery.querySelectorAll('[data-brand-card]')).some(function (item) { return !item.hidden; })) gallery.hidden = true;
    }
    var logo = image.closest('.brand-identity-logo');
    if (logo) logo.hidden = true;
  }
  document.addEventListener('error', function (event) { if (event.target.matches && event.target.matches('[data-brand-image],[data-brand-logo-fallback]')) hideBrokenImage(event.target); }, true);
  document.querySelectorAll('[data-brand-image],[data-brand-logo-fallback]').forEach(function (image) { if (image.complete && !image.naturalWidth) hideBrokenImage(image); });
  document.querySelectorAll('[data-brand-dialog]').forEach(function (dialog) {
    dialog.addEventListener('close', function () {
      if (dialog.dataset.brandMoving) { delete dialog.dataset.brandMoving; return; }
      if (sourceReturn) return;
      if (opener && opener.isConnected && !opener.closest('[hidden]')) opener.focus({ preventScroll:true });
    });
    dialog.addEventListener('keydown', function (event) {
      event.stopPropagation();
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); move(dialog, event.key === 'ArrowLeft' ? -1 : 1); }
    });
    dialog.addEventListener('click', function (event) { if (event.target === dialog) dialog.close(); });
  });
  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-brand-expand]');
    if (trigger && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      var dialog = document.getElementById(trigger.dataset.brandExpand);
      if (open(dialog, trigger)) { event.preventDefault(); event.stopPropagation(); }
      return;
    }
    var close = event.target.closest('[data-brand-close]');
    if (close) { close.closest('[data-brand-dialog]').close(); return; }
    var step = event.target.closest('[data-brand-step]');
    if (step) { move(step.closest('[data-brand-dialog]'), Number(step.dataset.brandStep)); return; }
    var source = event.target.closest('[data-brand-source]');
    if (source && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      sourceReturn = opener;
      source.closest('[data-brand-dialog]').close();
    }
  });
  var reader = document.getElementById('v2ReaderOffcanvas');
  if (reader) reader.addEventListener('hidden.bs.offcanvas', function () {
    if (sourceReturn && sourceReturn.isConnected) sourceReturn.focus({ preventScroll:true });
    sourceReturn = null;
  });
})();
