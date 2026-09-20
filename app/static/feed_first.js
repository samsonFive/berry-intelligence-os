(function () {
  const root = document.querySelector("[data-feed-first]");
  if (!root) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function csrfSafe() {
    return true;
  }

  async function postJSON(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error("request failed");
    }
    return response.json();
  }

  function setPressed(button, on) {
    button.setAttribute("aria-pressed", on ? "true" : "false");
  }

  function renderStatements(statements) {
    const box = root.querySelector("[data-statement-list]");
    if (!box) return;
    if (!statements || !statements.length) {
      box.innerHTML = "<p class=\"bos-note\">No supported statements yet.</p>";
      return;
    }
    box.innerHTML = statements
      .map(function (row) {
        const removed = row.statement_state === "removed";
        return (
          '<article class="bos-statement" data-statement-id="' +
          row.id +
          '" data-statement-state="' +
          escapeHtml(row.statement_state || "") +
          '" data-importance="' +
          escapeHtml(row.importance_state || "") +
          '">' +
          "<p>" +
          escapeHtml(row.statement_text) +
          "</p>" +
          '<p class="bos-meta">' +
          escapeHtml(row.confidence || "") +
          " · " +
          escapeHtml(row.importance_state || "normal") +
          (removed ? " · removed" : "") +
          " · " +
          escapeHtml((row.supporting_passages || [])[0] || "") +
          "</p>" +
          '<div class="bos-actions">' +
          '<button type="button" class="bos-btn" data-statement-action="important">Important</button>' +
          '<button type="button" class="bos-btn" data-statement-action="demote">Demote</button>' +
          '<button type="button" class="bos-btn" data-statement-action="remove">Remove</button>' +
          '<button type="button" class="bos-btn" data-statement-action="restore">Restore</button>' +
          "</div></article>"
        );
      })
      .join("");
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showLoader(on) {
    const loader = root.querySelector("[data-growth-loader]");
    if (!loader) return;
    loader.hidden = !on;
  }

  function markStatementReviewed(article, statement) {
    if (!article || !statement) return;
    const wasReviewed = article.getAttribute("data-reviewed") === "true";
    article.setAttribute("data-reviewed", "true");
    article.setAttribute("data-statement-state", statement.statement_state || "");
    article.setAttribute("data-importance", statement.importance_state || "");
    const label = article.querySelector("[data-review-label]");
    if (label) label.textContent = "Reviewed";
    const status = article.querySelector("[data-statement-status]");
    if (status) {
      const edits = (statement.analyst_edit_history || []).length;
      status.textContent =
        (statement.statement_state || "") +
        " · " +
        (statement.importance_state || "normal") +
        (edits ? " · " + edits + " edit(s)" : "");
    }
    if (!wasReviewed) {
      const reviewed = root.querySelector("[data-reviewed-count]");
      const remaining = root.querySelector("[data-remaining-count]");
      const progress = root.querySelector("[data-gate-progress] progress");
      if (reviewed) reviewed.textContent = String(Number(reviewed.textContent || 0) + 1);
      if (remaining) remaining.textContent = String(Math.max(0, Number(remaining.textContent || 0) - 1));
      if (progress) progress.value = Number(progress.value || 0) + 1;
    }
  }

  root.addEventListener("click", function (event) {
    const react = event.target.closest("[data-react]");
    if (react && csrfSafe()) {
      event.preventDefault();
      const itemId = react.getAttribute("data-item-id");
      let action = react.getAttribute("data-react");
      if (react.getAttribute("aria-pressed") === "true" && action !== "save") {
        action = "clear_reaction";
      }
      if (action === "thumbs_up") showLoader(true);
      if (action === "clear_reaction" || action === "thumbs_down") {
        renderStatements([]);
      }
      const previous = {
        up: react.getAttribute("aria-pressed"),
      };
      postJSON("/api/feed-first/react", { item_id: itemId, action: action })
        .then(function (data) {
          const up = root.querySelector('[data-react="thumbs_up"][data-item-id="' + itemId + '"]');
          const down = root.querySelector('[data-react="thumbs_down"][data-item-id="' + itemId + '"]');
          const save = root.querySelector('[data-react="save"][data-item-id="' + itemId + '"]');
          if (up) setPressed(up, data.decision.reaction === "up");
          if (down) setPressed(down, data.decision.reaction === "down");
          if (save) setPressed(save, Boolean(data.decision.saved));
          renderStatements(data.statements || []);
          const card = root.querySelector('[data-feed-card="' + itemId + '"]');
          if (card && data.decision.reaction === "down" && !reduced) {
            card.style.opacity = "0.35";
          } else if (card) {
            card.style.opacity = "1";
          }
        })
        .catch(function () {
          showLoader(false);
          if (previous.up != null) react.setAttribute("aria-pressed", previous.up);
        })
        .finally(function () {
          window.setTimeout(function () {
            showLoader(false);
          }, reduced ? 0 : 400);
        });
      return;
    }

    const statement = event.target.closest("[data-statement-action]");
    if (statement) {
      const article = statement.closest("[data-statement-id]");
      if (!article) return;
      postJSON("/api/feed-first/statement", {
        statement_id: article.getAttribute("data-statement-id"),
        action: statement.getAttribute("data-statement-action"),
      }).then(function (data) {
        if (!data.statement) return;
        markStatementReviewed(article, data.statement);
      }).catch(function () {
        const status = article.querySelector("[data-statement-status]");
        if (status) status.textContent = "Action failed. Try again.";
      });
    }
  });

  root.addEventListener("submit", function (event) {
    const form = event.target.closest("[data-statement-edit]");
    if (!form) return;
    event.preventDefault();
    const id = form.getAttribute("data-statement-edit");
    const text = (form.querySelector("textarea") || {}).value || "";
    postJSON("/api/feed-first/statement", {
      statement_id: id,
      action: "edit",
      text: text,
    }).then(function (data) {
      if (!data.statement) return;
      markStatementReviewed(form.closest("[data-statement-id]"), data.statement);
    }).catch(function () {
      const status = form.querySelector("[data-statement-status]");
      if (status) status.textContent = "Edit failed. Try again.";
    });
  });

  root.addEventListener("change", function (event) {
    const tier = event.target.closest("[data-tier-select]");
    if (!tier) return;
    postJSON("/api/feed-first/tier", {
      entity_id: tier.getAttribute("data-tier-select"),
      tier: tier.value,
    });
  });

  const readerRoot = root.querySelector("[data-reader-root]");
  const readerPanel = root.querySelector("[data-reader-panel]");
  const viewportShell = root.querySelector("[data-viewport-shell]");
  const readerReopen = root.querySelector(".bos-reader-reopen");

  function setReaderCollapsed(collapsed) {
    if (!readerRoot || !readerPanel || !viewportShell) return;
    viewportShell.classList.toggle("is-reader-collapsed", collapsed);
    readerPanel.hidden = collapsed;
    root.querySelectorAll("[data-reader-toggle]").forEach(function (button) {
      button.setAttribute("aria-expanded", collapsed ? "false" : "true");
    });
    if (readerReopen) readerReopen.hidden = !collapsed;
    if (collapsed && readerReopen) {
      readerReopen.focus();
    } else if (!collapsed) {
      readerRoot.focus();
    }
  }

  root.addEventListener("click", function (event) {
    const toggle = event.target.closest("[data-reader-toggle]");
    if (!toggle) return;
    event.preventDefault();
    setReaderCollapsed(!viewportShell || !viewportShell.classList.contains("is-reader-collapsed"));
  });

  if (readerRoot && readerRoot.getAttribute("data-item-id")) {
    postJSON("/api/feed-first/capture", { item_id: readerRoot.getAttribute("data-item-id") })
      .then(function (data) {
        const body = root.querySelector("[data-reader-body]");
        if (!body || !data.passages || !data.passages.length) return;
        if (data.availability === "blocked" || data.availability === "error") return;
        body.innerHTML = data.passages
          .map(function (passage) {
            return "<p>" + escapeHtml(passage) + "</p>";
          })
          .join("");
        if (data.availability !== "full") {
          body.innerHTML +=
            '<p class="bos-note">' + escapeHtml(data.availability || "partial") + " — this is not claimed as the full article.</p>";
        }
        if (data.content_kind === "pdf") {
          body.innerHTML =
            '<p class="bos-note">PDF source fidelity — extracted text only. This is not claimed as the full document.</p>' +
            body.innerHTML;
        }
        if (data.images && data.images.length) {
          renderGallery(data.images);
        }
      })
      .catch(function () {
        return;
      });
  }

  function renderGallery(images) {
    const gallery = root.querySelector("[data-gallery]");
    if (!gallery || !images || !images.length) return;
    const slides = gallery.querySelectorAll("[data-gallery-slide]");
    if (!slides.length) {
      gallery.innerHTML = images
        .map(function (image, index) {
          return (
            '<figure class="bos-gallery-slide"' +
            (index ? " hidden" : "") +
            ' data-gallery-slide><img src="' +
            escapeHtml(image.url || "") +
            '" alt="' +
            escapeHtml(image.alt || "Article image " + (index + 1)) +
            '"></figure>'
          );
        })
        .join("");
      if (images.length > 1) {
        gallery.innerHTML +=
          '<div class="bos-actions"><button type="button" class="bos-btn" data-gallery-prev aria-label="Previous image">Previous image</button><button type="button" class="bos-btn" data-gallery-next aria-label="Next image">Next image</button><span class="bos-note" data-gallery-status>1 / ' +
          images.length +
          "</span></div>";
      }
    }
  }

  function stepGallery(delta) {
    const gallery = root.querySelector("[data-gallery]");
    if (!gallery) return;
    const slides = Array.prototype.slice.call(gallery.querySelectorAll("[data-gallery-slide]"));
    if (slides.length < 2) return;
    let index = slides.findIndex(function (slide) {
      return !slide.hidden;
    });
    if (index < 0) index = 0;
    slides[index].hidden = true;
    index = (index + delta + slides.length) % slides.length;
    slides[index].hidden = false;
    const status = gallery.querySelector("[data-gallery-status]");
    if (status) status.textContent = index + 1 + " / " + slides.length;
  }

  root.addEventListener("click", function (event) {
    if (event.target.closest("[data-gallery-next]")) {
      event.preventDefault();
      stepGallery(1);
      return;
    }
    if (event.target.closest("[data-gallery-prev]")) {
      event.preventDefault();
      stepGallery(-1);
      return;
    }
    const mode = event.target.closest("[data-reader-mode]");
    if (!mode) return;
    const chosen = mode.getAttribute("data-reader-mode");
    const body = root.querySelector("[data-reader-body]");
    const live = root.querySelector("[data-live-page]");
    if (chosen === "live_page" && live) {
      live.hidden = false;
      if (body) body.hidden = true;
    } else {
      if (live) live.hidden = true;
      if (body) body.hidden = false;
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.target.matches("input, textarea, select")) return;
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const key = event.key;
    if (key === "j" || key === "ArrowRight") {
      const next = root.querySelector("[data-next-item]");
      if (next && next.href) {
        event.preventDefault();
        window.location.href = next.href;
      }
    }
    if (key === "k" || key === "ArrowLeft") {
      const prev = root.querySelector("[data-prev-item]");
      if (prev && prev.href) {
        event.preventDefault();
        window.location.href = prev.href;
      }
    }
    if (key === "Escape") {
      const reader = root.querySelector("[data-reader-root]");
      const close = root.querySelector("[data-close-reader]");
      if (reader && close && close.href) {
        event.preventDefault();
        window.location.href = close.href;
      }
    }
    if (key === "u" || key === "d" || key === "s") {
      event.preventDefault();
      const itemId = (root.querySelector("[data-reader-root]") || {}).getAttribute
        ? root.querySelector("[data-reader-root]").getAttribute("data-item-id")
        : "";
      const action = key === "u" ? "thumbs_up" : key === "d" ? "thumbs_down" : "save";
      const button = root.querySelector('[data-react="' + action + '"][data-item-id="' + itemId + '"]');
      if (button) button.click();
    }
  });
})();
