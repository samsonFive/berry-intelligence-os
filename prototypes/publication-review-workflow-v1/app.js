(function () {
  "use strict";

  var FIX = window.PUBLICATION_REVIEW_FIXTURES;
  var ACTOR = FIX.meta.actor;
  var store = {
    drafts: structuredClone(FIX.drafts),
    filter: "all",
    selectedId: null,
    events: [],
    receipts: [],
    idempotency: new Map(),
    lastFocus: null,
    dialogMode: null
  };

  var el = {
    queue: document.getElementById("queue-list"),
    count: document.getElementById("pending-count"),
    filters: document.getElementById("filters"),
    workspace: document.getElementById("workspace"),
    receipt: document.getElementById("receipt"),
    backdrop: document.getElementById("backdrop"),
    dialog: document.getElementById("decision-dialog"),
    dialogTitle: document.getElementById("dialog-title"),
    dialogBody: document.getElementById("dialog-body"),
    toast: document.getElementById("toast-region"),
    live: document.getElementById("live")
  };

  function uid(prefix) {
    return prefix + "-" + Math.random().toString(36).slice(2, 9) + "-" + Date.now().toString(36);
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function announce(msg) {
    el.live.textContent = "";
    requestAnimationFrame(function () { el.live.textContent = msg; });
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function getDraft(id) {
    return store.drafts.find(function (d) { return d.draft_id === id; });
  }

  function qualityBadge(q) {
    if (q === "readable") return "ok";
    if (q === "transcript") return "info";
    if (q === "limited") return "warn";
    return "danger";
  }

  function matchesFilter(d) {
    if (store.filter === "all") return d.queue_state === "pending" || true;
    if (store.filter === "readable") return d.content_quality === "readable";
    if (store.filter === "transcript") return d.content_quality === "transcript";
    if (store.filter === "limited") return d.content_quality === "limited";
    if (store.filter === "problem") return d.content_quality === "problem" || (d.blocking_warnings && d.blocking_warnings.length);
    return true;
  }

  function pendingCount() {
    return store.drafts.filter(function (d) { return d.queue_state === "pending"; }).length;
  }

  function sortedVisible() {
    return store.drafts.filter(matchesFilter).slice().sort(function (a, b) {
      var ap = a.queue_state === "pending" ? 0 : 1;
      var bp = b.queue_state === "pending" ? 0 : 1;
      if (ap !== bp) return ap - bp;
      return (a.needs_attention_rank || 99) - (b.needs_attention_rank || 99);
    });
  }

  function renderFilters() {
    el.filters.innerHTML = FIX.filters.map(function (f) {
      return '<button type="button" class="chip-btn" data-filter="' + f.id + '" aria-pressed="' + (store.filter === f.id) + '">' +
        escapeHtml(f.label) + "</button>";
    }).join("");
    el.filters.querySelectorAll("[data-filter]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        store.filter = btn.getAttribute("data-filter");
        render();
        announce("Filter " + btn.textContent);
      });
    });
  }

  function renderQueue() {
    el.count.textContent = String(pendingCount());
    var rows = sortedVisible();
    if (!rows.length) {
      el.queue.innerHTML = '<p class="meta">No drafts match this filter.</p>';
      return;
    }
    if (!store.selectedId || !rows.some(function (d) { return d.draft_id === store.selectedId; })) {
      store.selectedId = rows[0].draft_id;
    }
    el.queue.innerHTML = rows.map(function (d) {
      var selected = d.draft_id === store.selectedId ? " is-selected" : "";
      var attention = (d.attention_reasons && d.attention_reasons.length) ? " is-attention" : "";
      var handled = d.queue_state !== "pending" ? " is-handled" : "";
      var badges = '<span class="badge ' + qualityBadge(d.content_quality) + '">' + escapeHtml(d.content_quality_label) + "</span>";
      if (d.duplicate && d.duplicate.status === "probable") badges += '<span class="badge warn">Probable duplicate</span>';
      if (d.entity_match.status === "missing") badges += '<span class="badge warn">Missing entity</span>';
      if (d.publication_date_confidence === "low" || d.publication_date_confidence === "none") badges += '<span class="badge warn">Uncertain date</span>';
      if (d.blocking_warnings && d.blocking_warnings.length) badges += '<span class="badge danger">Blocking</span>';
      if (d.queue_state !== "pending") badges += '<span class="badge pending">' + escapeHtml(d.queue_state) + "</span>";
      return (
        '<button type="button" class="queue-item' + selected + attention + handled + '" data-draft-id="' + d.draft_id + '" aria-current="' + (selected ? "true" : "false") + '">' +
          '<div class="queue-topline"><span class="source">' + escapeHtml(d.source_name) + "</span>" +
          '<span class="meta">Cap ' + escapeHtml((d.captured_at || "").slice(0, 10) || "—") + "</span></div>" +
          "<strong>" + escapeHtml(d.headline) + "</strong>" +
          '<div class="meta">Published ' + escapeHtml(d.publication_date || "unknown") +
          " · confidence " + escapeHtml(d.publication_date_confidence) + "</div>" +
          '<div class="badges">' + badges + "</div>" +
        "</button>"
      );
    }).join("");
    el.queue.querySelectorAll("[data-draft-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        store.selectedId = btn.getAttribute("data-draft-id");
        renderWorkspace();
        el.queue.querySelectorAll("[data-draft-id]").forEach(function (b) {
          var on = b === btn;
          b.classList.toggle("is-selected", on);
          b.setAttribute("aria-current", on ? "true" : "false");
        });
        announce("Selected draft");
      });
    });
  }

  function warnHtml(list) {
    if (!list || !list.length) return "<p class=\"meta\">None</p>";
    return "<ul class=\"warn-list\">" + list.map(function (w) {
      var cls = w.level === "block" ? " block-level" : "";
      return "<li class=\"" + cls + "\">[" + escapeHtml(w.level) + "] " + escapeHtml(w.message) +
        (w.level === "warn" ? " <em>(warning — not an automatic blocker)</em>" : "") +
        (w.level === "block" ? " <em>(contractual blocker)</em>" : "") +
        "</li>";
    }).join("") + "</ul>";
  }

  function renderWorkspace() {
    var d = getDraft(store.selectedId);
    if (!d) {
      el.workspace.innerHTML = '<p class="workspace-empty">Select a draft from the queue.</p>';
      return;
    }
    var entityHtml = d.entity_match.status === "matched"
      ? d.entity_match.entities.map(function (e) { return escapeHtml(e.name) + " (" + escapeHtml(e.type) + ")"; }).join(", ")
      : "No entity match proposed";
    var dupHtml = d.duplicate
      ? '<div class="dup-card" role="status"><strong>Probable duplicate</strong> of ' +
        escapeHtml(d.duplicate.candidate_title) + " (" + escapeHtml(d.duplicate.candidate_id) +
        ") · similarity " + escapeHtml(String(d.duplicate.similarity)) +
        ". Warning only — does not auto-block approval.</div>"
      : '<p class="meta">No duplicate candidates flagged.</p>';
    var bodyHtml = d.body_text
      ? '<pre class="body-copy">' + escapeHtml(d.body_text) + "</pre>"
      : '<p class="limited" role="status">' + escapeHtml(d.limited_explanation || "No usable body.") + "</p>";
    var limitedHtml = d.limited_explanation
      ? '<p class="limited" role="status">' + escapeHtml(d.limited_explanation) + "</p>"
      : "";
    var historyHtml = (d.review_history && d.review_history.length)
      ? "<ul class=\"history-list\">" + d.review_history.map(function (h) {
          return "<li>" + escapeHtml(h.at) + " · " + escapeHtml(h.actor) + " · <strong>" +
            escapeHtml(h.action) + "</strong>" + (h.note ? " — " + escapeHtml(h.note) : "") +
            (h.resulting_publication_id ? " → " + escapeHtml(h.resulting_publication_id) : "") + "</li>";
        }).join("") + "</ul>"
      : '<p class="meta">No prior review events.</p>';
    var provHtml = "<ol class=\"prov-list\">" + d.provenance_chain.map(function (p) {
      return "<li><strong>" + escapeHtml(p.step) + "</strong> · " + escapeHtml(p.at) + " — " + escapeHtml(p.detail) + "</li>";
    }).join("") + "</ol>";

    var canApprove = d.queue_state === "pending" && !(d.blocking_warnings && d.blocking_warnings.length);
    var disabledNote = "";
    if (d.queue_state !== "pending") disabledNote = "This draft is already handled (" + d.queue_state + "). Further approval is idempotent / blocked.";
    if (d.blocking_warnings && d.blocking_warnings.length) disabledNote = "Contractual blockers prevent approval until resolved.";

    el.workspace.innerHTML =
      '<header class="panel-head"><div><p class="eyebrow">Review workspace</p><h2 id="workspace-title">' + escapeHtml(d.headline) +
      '</h2><p class="meta">Fixture state: ' + escapeHtml(d.fixture_state) + " · version " + d.version + "</p></div>" +
      '<span class="badge ' + qualityBadge(d.content_quality) + '">' + escapeHtml(d.content_quality_label) + "</span></header>" +

      '<section class="block" aria-label="Source metadata">' +
        "<h3>Original source metadata</h3>" +
        '<dl class="dl">' +
        "<dt>Source</dt><dd>" + escapeHtml(d.source_name) + "</dd>" +
        "<dt>Source URL</dt><dd>" + (d.source_url ? '<a href="' + escapeHtml(d.source_url) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(d.source_url) + "</a>" : "<em>Missing</em>") + "</dd>" +
        "<dt>Source type</dt><dd>" + escapeHtml(d.source_type) + "</dd>" +
        "<dt>Published</dt><dd>" + escapeHtml(d.publication_date || "unknown") + " · confidence " + escapeHtml(d.publication_date_confidence) + "</dd>" +
        "<dt>Discovered</dt><dd>" + escapeHtml(d.discovered_at) + "</dd>" +
        "<dt>Captured</dt><dd>" + escapeHtml(d.captured_at) + "</dd>" +
        "<dt>Acquisition</dt><dd>" + escapeHtml(d.acquisition_outcome) + "</dd>" +
        "</dl></section>" +

      '<section class="block" aria-label="Readable content">' +
        "<h3>" + (d.body_kind === "transcript" ? "Transcript" : "Extracted readable body") + "</h3>" +
        limitedHtml + bodyHtml +
      "</section>" +

      '<section class="block" aria-label="Entities and duplicates">' +
        "<h3>Proposed entities &amp; duplicates</h3>" +
        "<p><strong>Entity match:</strong> " + entityHtml + "</p>" + dupHtml +
      "</section>" +

      '<section class="block" aria-label="Warnings">' +
        "<h3>Provenance warnings</h3>" + warnHtml(d.provenance_warnings) +
        "<h3>Blocking warnings</h3>" + warnHtml(d.blocking_warnings) +
      "</section>" +

      '<section class="block" aria-label="Provenance chain">' +
        "<h3>Complete provenance chain</h3>" + provHtml +
      "</section>" +

      '<section class="block" aria-label="Review history">' +
        "<h3>Review history</h3>" + historyHtml +
      "</section>" +

      '<section class="block" aria-label="Publication decisions">' +
        "<h3>Publication decisions</h3>" +
        '<p class="decision-note"><strong>Approve publication</strong> means publication approval only — not Evidence approval. This prototype does not create trusted Evidence or call production mutations.</p>' +
        '<p class="no-bulk">Bulk approval is not available.</p>' +
        (disabledNote ? '<p class="limited" role="status">' + escapeHtml(disabledNote) + "</p>" : "") +
        '<div class="decisions" role="group" aria-label="Decision actions">' +
          '<button type="button" class="decision-btn primary" data-decision="approve_publication"' + (canApprove ? "" : " disabled") + ">Approve publication</button>" +
          '<button type="button" class="decision-btn danger" data-decision="reject"' + (d.queue_state === "pending" ? "" : " disabled") + ">Reject</button>" +
          '<button type="button" class="decision-btn" data-decision="defer"' + (d.queue_state === "pending" ? "" : " disabled") + ">Defer</button>" +
          '<button type="button" class="decision-btn warn" data-decision="request_correction"' + (d.queue_state === "pending" ? "" : " disabled") + ">Request correction</button>" +
        "</div>" +
      "</section>";

    el.workspace.querySelectorAll("[data-decision]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openDialog(btn.getAttribute("data-decision"), d);
      });
    });
  }

  function openDialog(mode, draft) {
    store.dialogMode = mode;
    store.lastFocus = document.activeElement;
    var titles = {
      approve_publication: "Confirm publication approval",
      reject: "Reject publication draft",
      defer: "Defer publication draft",
      request_correction: "Request correction"
    };
    el.dialogTitle.textContent = titles[mode] || "Decision";
    var html = "";
    if (mode === "approve_publication") {
      html =
        '<p>You are recording a <strong>publication approval</strong> for:</p>' +
        "<p><strong>" + escapeHtml(draft.headline) + "</strong></p>" +
        '<p class="meta">This is not Evidence approval. Prototype only — no production mutation, no trusted Evidence created.</p>' +
        (draft.provenance_warnings && draft.provenance_warnings.length
          ? '<p class="limited" role="status">Non-blocking warnings are present and remain visible. They do not prevent this confirmation unless listed as contractual blockers.</p>'
          : "") +
        '<div class="dialog-actions">' +
        '<button type="button" class="btn" data-cancel>Cancel</button>' +
        '<button type="button" class="btn primary" data-confirm>Confirm approve publication</button></div>';
    } else if (mode === "reject" || mode === "request_correction") {
      var reasons = mode === "reject" ? FIX.rejection_reasons : FIX.correction_reasons;
      html =
        "<p>" + (mode === "reject" ? "Rejection" : "Correction request") + " requires a reason.</p>" +
        '<label>Reason<select id="decision-reason" required>' +
        reasons.map(function (r) { return '<option value="' + r.id + '">' + escapeHtml(r.label) + "</option>"; }).join("") +
        "</select></label>" +
        '<label>Notes (optional)<textarea id="decision-notes" rows="3"></textarea></label>' +
        '<div class="dialog-actions">' +
        '<button type="button" class="btn" data-cancel>Cancel</button>' +
        '<button type="button" class="btn ' + (mode === "reject" ? "danger" : "warn") + '" data-confirm>Confirm</button></div>';
    } else {
      html =
        "<p>Defer hides this draft from today's active triage without rejecting it. The draft file remains.</p>" +
        '<label>Notes (optional)<textarea id="decision-notes" rows="3"></textarea></label>' +
        '<div class="dialog-actions">' +
        '<button type="button" class="btn" data-cancel>Cancel</button>' +
        '<button type="button" class="btn primary" data-confirm>Confirm defer</button></div>';
    }
    el.dialogBody.innerHTML = html;
    el.backdrop.hidden = false;
    el.backdrop.classList.add("open");
    el.dialog.classList.add("open");
    el.dialog.setAttribute("aria-hidden", "false");
    var closeBtn = document.getElementById("dialog-close");
    closeBtn.focus();
    el.dialogBody.querySelector("[data-cancel]").addEventListener("click", closeDialog);
    el.dialogBody.querySelector("[data-confirm]").addEventListener("click", function () {
      applyDecision(mode, draft);
    });
    announce(titles[mode] + " dialog opened");
  }

  function closeDialog() {
    el.dialog.classList.remove("open");
    el.dialog.setAttribute("aria-hidden", "true");
    el.backdrop.classList.remove("open");
    el.backdrop.hidden = true;
    store.dialogMode = null;
    if (store.lastFocus && document.contains(store.lastFocus)) store.lastFocus.focus();
    announce("Dialog closed");
  }

  function showToast(message) {
    el.toast.innerHTML = "";
    var toast = document.createElement("div");
    toast.className = "toast";
    toast.setAttribute("role", "status");
    toast.innerHTML = "<span>" + escapeHtml(message) + '</span><button type="button">Dismiss</button>';
    toast.querySelector("button").addEventListener("click", function () { el.toast.innerHTML = ""; });
    el.toast.appendChild(toast);
    setTimeout(function () { if (el.toast.contains(toast)) el.toast.innerHTML = ""; }, 6000);
  }

  function showReceipt(receipt) {
    el.receipt.classList.add("open");
    el.receipt.innerHTML =
      "<strong>Success receipt</strong>" +
      "<div>Decision: " + escapeHtml(receipt.action) + "</div>" +
      "<div>Actor: " + escapeHtml(receipt.actor_id) + "</div>" +
      "<div>Time: " + escapeHtml(receipt.timestamp) + "</div>" +
      "<div>Source draft: " + escapeHtml(receipt.draft_id) + "</div>" +
      (receipt.resulting_publication_id
        ? "<div>Resulting publication id: " + escapeHtml(receipt.resulting_publication_id) + " <em>(prototype label only)</em></div>"
        : "<div>No publication artifact created for this decision.</div>") +
      "<div class=\"meta\">No false undo — architecture uses compensating/corrective events, not erase.</div>";
    el.receipt.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function applyDecision(mode, draft) {
    var reasonEl = document.getElementById("decision-reason");
    var notesEl = document.getElementById("decision-notes");
    var reason = reasonEl ? reasonEl.value : null;
    var notes = notesEl ? notesEl.value.trim() : "";

    if ((mode === "reject" || mode === "request_correction") && !reason) {
      announce("Reason required");
      if (reasonEl) reasonEl.focus();
      return;
    }

    // Concurrent / already handled
    if (draft.expected_version_conflict_if_acted || draft.queue_state !== "pending") {
      closeDialog();
      showToast("Stale or concurrent review: another operator already handled this draft. No duplicate effect.");
      announce("Concurrent review — idempotent no-op");
      render();
      return;
    }

    // Contractual blockers on approve
    if (mode === "approve_publication" && draft.blocking_warnings && draft.blocking_warnings.length) {
      closeDialog();
      showToast("Approval blocked by contractual validation.");
      announce("Approval blocked");
      return;
    }

    var idemKey = mode + ":" + draft.draft_id + ":" + draft.version;
    if (store.idempotency.has(idemKey)) {
      closeDialog();
      showToast("Duplicate click ignored — idempotent result already recorded.");
      announce("Idempotent duplicate click");
      showReceipt(store.idempotency.get(idemKey));
      return;
    }

    var resultingPub = null;
    var nextState = draft.queue_state;
    if (mode === "approve_publication") {
      nextState = "approved";
      resultingPub = "proto-pub-" + draft.draft_id;
    } else if (mode === "reject") {
      nextState = "rejected";
    } else if (mode === "defer") {
      nextState = "deferred";
    } else if (mode === "request_correction") {
      nextState = "correction_requested";
    }

    draft.queue_state = nextState;
    draft.version += 1;
    var event = {
      event_id: uid("evt"),
      draft_id: draft.draft_id,
      actor_id: ACTOR.actor_id,
      action: mode,
      reason: reason,
      notes: notes || null,
      prior_state: "pending",
      resulting_state: nextState,
      resulting_publication_id: resultingPub,
      timestamp: nowIso(),
      prototype_only: true
    };
    store.events.unshift(event);
    draft.review_history = draft.review_history || [];
    draft.review_history.push({
      at: event.timestamp,
      actor: event.actor_id,
      action: mode,
      note: notes || reason || null,
      resulting_publication_id: resultingPub
    });

    var receipt = {
      action: mode,
      actor_id: ACTOR.actor_id,
      timestamp: event.timestamp,
      draft_id: draft.draft_id,
      resulting_publication_id: resultingPub
    };
    store.receipts.unshift(receipt);
    store.idempotency.set(idemKey, receipt);

    closeDialog();
    showReceipt(receipt);
    showToast("Decision recorded in prototype memory only.");
    announce("Decision " + mode + " recorded");
    render();
  }

  function focusableIn(container) {
    return Array.prototype.slice.call(
      container.querySelectorAll('a[href],button:not([disabled]),textarea,input,select,[tabindex]:not([tabindex="-1"])')
    );
  }

  document.getElementById("dialog-close").addEventListener("click", closeDialog);
  el.backdrop.addEventListener("click", closeDialog);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && store.dialogMode) {
      e.preventDefault();
      closeDialog();
      return;
    }
    if (store.dialogMode && e.key === "Tab") {
      var nodes = focusableIn(el.dialog);
      if (!nodes.length) return;
      var first = nodes[0];
      var last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
      return;
    }
    var tag = (e.target && e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    var rows = sortedVisible();
    var idx = rows.findIndex(function (d) { return d.draft_id === store.selectedId; });
    if (e.key === "j") {
      var next = rows[Math.min(rows.length - 1, Math.max(0, idx) + 1)];
      if (next) { store.selectedId = next.draft_id; render(); }
      e.preventDefault();
    } else if (e.key === "k") {
      var prev = rows[Math.max(0, idx - 1)];
      if (prev) { store.selectedId = prev.draft_id; render(); }
      e.preventDefault();
    } else if (e.key === "a") {
      var d = getDraft(store.selectedId);
      if (d && d.queue_state === "pending") openDialog("approve_publication", d);
      e.preventDefault();
    } else if (e.key === "r") {
      var dr = getDraft(store.selectedId);
      if (dr && dr.queue_state === "pending") openDialog("reject", dr);
      e.preventDefault();
    } else if (e.key === "x") {
      var dx = getDraft(store.selectedId);
      if (dx && dx.queue_state === "pending") openDialog("defer", dx);
      e.preventDefault();
    } else if (e.key === "c") {
      var dc = getDraft(store.selectedId);
      if (dc && dc.queue_state === "pending") openDialog("request_correction", dc);
      e.preventDefault();
    }
  });

  document.getElementById("reset-demo").addEventListener("click", function () {
    store.drafts = structuredClone(FIX.drafts);
    store.events = [];
    store.receipts = [];
    store.idempotency.clear();
    store.selectedId = null;
    el.receipt.classList.remove("open");
    el.receipt.innerHTML = "";
    el.toast.innerHTML = "";
    render();
    announce("Demo state reset");
  });

  function render() {
    renderFilters();
    renderQueue();
    renderWorkspace();
  }

  render();
})();
