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
        return (
          '<article class="bos-statement" data-statement-id="' +
          row.id +
          '">' +
          "<p>" +
          escapeHtml(row.statement_text) +
          "</p>" +
          '<p class="bos-meta">' +
          escapeHtml(row.confidence || "") +
          " · " +
          escapeHtml((row.supporting_passages || [])[0] || "") +
          "</p>" +
          '<div class="bos-actions">' +
          '<button type="button" class="bos-btn" data-statement-action="important">Important</button>' +
          '<button type="button" class="bos-btn" data-statement-action="demote">Demote</button>' +
          '<button type="button" class="bos-btn" data-statement-action="remove">Remove</button>' +
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
      postJSON("/api/feed-first/react", { item_id: itemId, action: action })
        .then(function (data) {
          const up = root.querySelector('[data-react="thumbs_up"][data-item-id="' + itemId + '"]');
          const down = root.querySelector('[data-react="thumbs_down"][data-item-id="' + itemId + '"]');
          if (up) setPressed(up, data.decision.reaction === "up");
          if (down) setPressed(down, data.decision.reaction === "down");
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
        if (data.statement && data.statement.statement_state === "removed") {
          article.remove();
        }
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

  document.addEventListener("keydown", function (event) {
    if (event.target.matches("input, textarea, select")) return;
    if (event.key === "j" || event.key === "ArrowRight") {
      const next = root.querySelector("[data-next-item]");
      if (next && next.href) window.location.href = next.href;
    }
    if (event.key === "k" || event.key === "ArrowLeft") {
      const prev = root.querySelector("[data-prev-item]");
      if (prev && prev.href) window.location.href = prev.href;
    }
    if (event.key === "Escape") {
      const close = root.querySelector("[data-close-reader]");
      if (close && close.href) window.location.href = close.href;
    }
    if (event.key === "u" || event.key === "d") {
      const itemId = (root.querySelector("[data-reader-root]") || {}).getAttribute
        ? root.querySelector("[data-reader-root]").getAttribute("data-item-id")
        : "";
      const action = event.key === "u" ? "thumbs_up" : "thumbs_down";
      const button = root.querySelector('[data-react="' + action + '"][data-item-id="' + itemId + '"]');
      if (button) button.click();
    }
  });
})();
