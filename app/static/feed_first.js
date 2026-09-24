(function () {
  const root = document.querySelector("[data-feed-first]");
  if (!root) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const viewportShell = root.querySelector("[data-viewport-shell]");
  const readerPanel = root.querySelector("[data-reader-panel]");
  let readerRequest = 0;
  let lastReaderTrigger = null;

  function readerItemFromUrl(value) {
    try {
      return new URL(value, window.location.href).searchParams.get("item") || "";
    } catch (error) {
      return "";
    }
  }

  function selectFeedCard(itemId) {
    root.querySelectorAll("[data-feed-card]").forEach(function (card) {
      card.classList.toggle("is-selected", card.dataset.feedCard === itemId);
    });
  }

  function clearFeedReader(scrollY) {
    if (!readerPanel || !viewportShell) return;
    ++readerRequest;
    readerPanel.innerHTML = "";
    viewportShell.classList.remove("has-reader");
    selectFeedCard("");
    if (lastReaderTrigger && lastReaderTrigger.isConnected) {
      lastReaderTrigger.focus({ preventScroll: true });
    }
    if (Number.isFinite(scrollY)) {
      window.requestAnimationFrame(function () {
        window.scrollTo({ top: scrollY, behavior: "auto" });
      });
    }
  }

  async function openFeedReader(href, trigger, options) {
    if (!readerPanel || !viewportShell) {
      window.location.assign(href);
      return;
    }
    const target = new URL(href, window.location.href);
    const itemId = readerItemFromUrl(target);
    if (!itemId) return;
    const fromHistory = options && options.fromHistory;
    const savedScroll = Number(
      (fromHistory && window.history.state && window.history.state.feedScrollY) ||
        window.scrollY
    );
    lastReaderTrigger = trigger || lastReaderTrigger;
    if (!fromHistory) {
      const current = Object.assign({}, window.history.state || {}, { feedScrollY: savedScroll });
      window.history.replaceState(current, "", window.location.href);
      window.history.pushState(
        { feedFirstReader: true, feedScrollY: savedScroll, itemId: itemId },
        "",
        target
      );
    }
    viewportShell.classList.add("has-reader");
    selectFeedCard(itemId);
    readerPanel.innerHTML = '<div class="bos-reader" aria-busy="true"><p class="bos-note">Loading reader…</p></div>';
    if (window.matchMedia("(max-width: 1100px)").matches) {
      readerPanel.scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" });
    }
    const request = ++readerRequest;
    try {
      const response = await fetch(target, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "feed-first-reader" },
      });
      if (!response.ok) throw new Error("reader unavailable");
      const documentCopy = new DOMParser().parseFromString(await response.text(), "text/html");
      const nextPanel = documentCopy.querySelector("[data-reader-panel]");
      if (!nextPanel || request !== readerRequest) return;
      readerPanel.innerHTML = nextPanel.innerHTML;
      selectFeedCard(itemId);
      const heading = readerPanel.querySelector(".bos-reader h2");
      if (heading) {
        heading.setAttribute("tabindex", "-1");
        heading.focus({ preventScroll: true });
      }
    } catch (error) {
      if (request !== readerRequest) return;
      window.location.assign(target);
    }
  }

  if (readerPanel) {
    root.addEventListener("click", function (event) {
      const close = event.target.closest("a[data-close-reader]");
      if (close && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
        event.preventDefault();
        const state = window.history.state || {};
        if (state.feedFirstReader) {
          window.history.back();
        } else {
          window.history.replaceState(
            { feedScrollY: 0 },
            "",
            new URL(close.href, window.location.href)
          );
          clearFeedReader(0);
        }
        return;
      }
      const opener = event.target.closest("a[data-open-feed-reader]");
      if (
        !opener ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey ||
        event.button !== 0
      ) {
        return;
      }
      event.preventDefault();
      openFeedReader(opener.href, opener);
    });

    window.addEventListener("popstate", function (event) {
      const itemId = readerItemFromUrl(window.location.href);
      if (itemId) {
        openFeedReader(window.location.href, null, { fromHistory: true });
      } else {
        const scrollY = Number(event.state && event.state.feedScrollY);
        clearFeedReader(Number.isFinite(scrollY) ? scrollY : 0);
      }
    });
  }

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
        const pending = row.statement_state === "pending_confirmation";
        const trusted = row.statement_state === "trusted_analyst";
        return (
          '<article class="bos-statement" data-statement-id="' +
          escapeHtml(row.id) +
          '" data-statement-state="' +
          escapeHtml(row.statement_state || "") +
          '" data-importance="' +
          escapeHtml(row.importance_state || "") +
          ((row.support_locators || [])[0]
            ? '" data-support-paragraph="' +
              escapeHtml((row.support_locators || [])[0].paragraph_index) +
              '" data-support-start="' +
              escapeHtml((row.support_locators || [])[0].start_offset) +
              '" data-support-end="' +
              escapeHtml((row.support_locators || [])[0].end_offset) +
              '" data-support-exact="' +
              escapeHtml((row.support_locators || [])[0].exact) +
              ""
            : "") +
          '" tabindex="0">' +
          '<label><input type="checkbox" data-claim-select> Select claim</label>' +
          '<form data-statement-edit="' +
          escapeHtml(row.id) +
          '">' +
          '<textarea name="text">' +
          escapeHtml(row.statement_text) +
          "</textarea>" +
          '<div class="bos-actions"><button class="bos-btn" type="submit">Save edit</button>' +
          (pending
            ? '<button type="button" class="bos-btn is-primary" data-statement-action="confirm">Confirm</button><button type="button" class="bos-btn" data-statement-action="reject">Reject</button>'
            : "") +
          (trusted
            ? '<button type="button" class="bos-btn" data-statement-action="retract">Retract</button>'
            : "") +
          "</div></form>" +
          '<p class="bos-meta">' +
          escapeHtml(row.confidence || "") +
          " · " +
          escapeHtml((row.statement_state || "").replaceAll("_", " ")) +
          " · " +
          escapeHtml((row.supporting_passages || [])[0] || "") +
          "</p></article>"
        );
      })
      .join("");
    applyEvidenceHighlights(statements);
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

  function applyEvidenceHighlights(statements) {
    const body = root.querySelector("[data-reader-body]");
    if (!body) return;
    body.querySelectorAll("[data-evidence-passage]").forEach(function (paragraph) {
      if (!paragraph.dataset.originalText) paragraph.dataset.originalText = paragraph.textContent;
      paragraph.textContent = paragraph.dataset.originalText;
    });
    (statements || []).forEach(function (row) {
      (row.support_locators || []).forEach(function (locator) {
        if (locator.medium !== "article_paragraph") return;
        const paragraph = body.querySelector(
          '[data-evidence-passage="' + String(locator.paragraph_index) + '"]'
        );
        if (!paragraph || paragraph.querySelector("mark")) return;
        const text = paragraph.textContent || "";
        const start = Number(locator.start_offset);
        const end = Number(locator.end_offset);
        if (start < 0 || end <= start || text.slice(start, end) !== locator.exact) return;
        paragraph.textContent = "";
        paragraph.append(document.createTextNode(text.slice(0, start)));
        const mark = document.createElement("mark");
        mark.className = "bos-evidence-highlight";
        mark.dataset.claimId = row.id;
        mark.tabIndex = 0;
        mark.textContent = text.slice(start, end);
        paragraph.append(mark);
        paragraph.append(document.createTextNode(text.slice(end)));
      });
    });
  }

  function focusClaim(statementId) {
    root.querySelectorAll(".bos-evidence-highlight").forEach(function (mark) {
      mark.classList.toggle("is-focused", mark.dataset.claimId === statementId);
    });
    const card = root.querySelector('[data-statement-id="' + CSS.escape(statementId) + '"]');
    if (card) {
      card.focus();
      card.scrollIntoView({ block: "nearest", behavior: reduced ? "auto" : "smooth" });
    }
  }

  function statementRowsFromDom() {
    return Array.prototype.slice.call(root.querySelectorAll("[data-statement-id]")).map(function (card) {
      const hasLocator = card.dataset.supportParagraph !== undefined;
      return {
        id: card.dataset.statementId,
        support_locators: hasLocator
          ? [
              {
                medium: "article_paragraph",
                paragraph_index: Number(card.dataset.supportParagraph),
                start_offset: Number(card.dataset.supportStart),
                end_offset: Number(card.dataset.supportEnd),
                exact: card.dataset.supportExact || "",
              },
            ]
          : [],
      };
    });
  }

  applyEvidenceHighlights(statementRowsFromDom());

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
      return;
    }

    const highlight = event.target.closest(".bos-evidence-highlight");
    if (highlight) {
      focusClaim(highlight.dataset.claimId || "");
      return;
    }

    const claimCard = event.target.closest("[data-statement-id]");
    if (claimCard && !event.target.closest("button, textarea, input, a")) {
      focusClaim(claimCard.dataset.statementId || "");
      return;
    }

    const batchAction =
      event.target.closest("[data-confirm-selected]") ||
      event.target.closest("[data-reject-selected]") ||
      event.target.closest("[data-confirm-all]");
    if (batchAction) {
      let cards = Array.prototype.slice.call(
        root.querySelectorAll('[data-statement-state="pending_confirmation"]')
      );
      if (!batchAction.matches("[data-confirm-all]")) {
        cards = cards.filter(function (card) {
          const checkbox = card.querySelector("[data-claim-select]");
          return checkbox && checkbox.checked;
        });
      } else if (!window.confirm("Confirm every pending claim in this reader?")) {
        return;
      }
      const action = batchAction.matches("[data-reject-selected]") ? "reject" : "confirm";
      postJSON("/api/feed-first/statement", {
        statement_ids: cards.map(function (card) {
          return card.dataset.statementId;
        }),
        action: action,
      }).then(function () {
        window.location.reload();
      });
      return;
    }

    const gap = event.target.closest("[data-launch-gap-research]");
    if (gap) {
      const status = root.querySelector("[data-research-status]");
      if (status) status.textContent = "Searching the bounded existing corpus…";
      postJSON("/api/entity-dossier/research", {
        entity_id: root.dataset.entityId,
        question_id: gap.dataset.launchGapResearch,
      })
        .then(function (data) {
          if (status) {
            status.textContent = data.proposal
              ? "Proposal ready for analyst review."
              : "Search completed with no evidence. This was not marked not publicly disclosed.";
          }
          window.location.reload();
        })
        .catch(function () {
          if (status) status.textContent = "Research failed; no claim was created.";
        });
      return;
    }

    const proposalAction = event.target.closest("[data-proposal-action]");
    if (proposalAction) {
      const proposal = proposalAction.closest("[data-proposal-id]");
      const editor = proposal ? proposal.querySelector("[data-proposal-edit]") : null;
      postJSON("/api/entity-dossier/proposal", {
        proposal_id: proposal ? proposal.dataset.proposalId : "",
        action: proposalAction.dataset.proposalAction,
        text: editor ? editor.value : "",
      }).then(function () {
        window.location.reload();
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
  if (readerRoot && readerRoot.getAttribute("data-item-id")) {
    postJSON("/api/feed-first/capture", { item_id: readerRoot.getAttribute("data-item-id") })
      .then(function (data) {
        const body = root.querySelector("[data-reader-body]");
        if (!body || !data.passages || !data.passages.length) return;
        if (data.availability === "blocked" || data.availability === "error") return;
        body.innerHTML = data.passages
          .map(function (passage, index) {
            return (
              '<p data-evidence-passage="' +
              index +
              '">' +
              escapeHtml(passage) +
              "</p>"
            );
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
        applyEvidenceHighlights(statementRowsFromDom());
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
    if (key === "Escape") {
      const close = root.querySelector("[data-close-reader]");
      if (close && close.href) {
        event.preventDefault();
        close.click();
      }
      return;
    }
    if (key === "j" || key === "ArrowRight") {
      const next = root.querySelector("[data-next-item]");
      if (next && next.href) {
        event.preventDefault();
        next.click();
      }
    }
    if (key === "k" || key === "ArrowLeft") {
      const prev = root.querySelector("[data-prev-item]");
      if (prev && prev.href) {
        event.preventDefault();
        prev.click();
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
