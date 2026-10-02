(function () {
  // Delegation also covers a Reader fragment loaded after page entry.
  document.addEventListener("click", async function (event) {
    const button = event.target.closest("[data-reader-statement-action]");
    if (!button) return;
    const section = button.closest("[data-reader-statement]");
    const status = section.querySelector(".statement-reader-status");
    const action = button.dataset.readerStatementAction;
    const buttons = Array.from(section.querySelectorAll("button"));
    buttons.forEach(function (control) { control.disabled = true; });
    status.textContent = "Saving decision…";
    try {
      const response = await fetch("/api/feed-first/statement", {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json"}, body: JSON.stringify({statement_id: section.dataset.readerStatement, action: action})});
      const data = await response.json();
      if (!response.ok || !data.statement) throw new Error(data.detail || "Could not save this decision. Try again.");
      const labels = {trusted_analyst: "Confirmed statement", rejected: "Rejected statement", removed: "Removed statement"};
      section.querySelector("[data-reader-statement-state]").textContent = labels[data.statement.statement_state] || "Decision saved";
      buttons.forEach(function (control) { control.remove(); });
      if (data.statement.statement_state === "trusted_analyst") {
        const retract = document.createElement("button");
        retract.type = "button"; retract.className = "outline-button";
        retract.dataset.readerStatementAction = "retract"; retract.textContent = "Remove statement from profiles";
        status.before(retract);
      }
      status.textContent = action === "retract" ? "Statement removed from profiles. Its linked reviewed fact and source remain unchanged." : "Decision saved. Source text and review history are retained.";
      status.tabIndex = -1; status.focus({preventScroll: true});
      document.dispatchEvent(new CustomEvent("bios:statement-updated", {detail: data.statement}));
    } catch (error) {
      status.textContent = error.message;
      buttons.forEach(function (control) { control.disabled = false; });
    }
  });
})();
