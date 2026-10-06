(function () {
  "use strict";
  function selectTeaching(panel, index) {
    panel.querySelectorAll("[data-teaching-select]").forEach(function (item) {
      item.setAttribute("aria-pressed", String(item.dataset.teachingSelect === index));
    });
    panel.querySelectorAll("[data-teaching-detail]").forEach(function (item) {
      item.hidden = item.dataset.teachingDetail !== index;
    });
  }
  document.querySelectorAll("[data-teaching-explorer]").forEach(function (panel) {
    panel.dataset.enhanced = "true";
    selectTeaching(panel, "0");
  });
  document.addEventListener("click", function (event) {
    var teaching = event.target.closest("[data-teaching-select]");
    if (teaching) {
      selectTeaching(teaching.closest("[data-teaching-explorer]"), teaching.dataset.teachingSelect);
      return;
    }
    var button = event.target.closest("[data-cane-habit]");
    if (!button) return;
    var panel = button.closest("[data-cane-calendar]"), first = button.dataset.caneHabit === "primocane";
    panel.querySelectorAll("[data-cane-habit]").forEach(function (item) { item.setAttribute("aria-pressed", String(item === button)); });
    panel.querySelector("[data-cane-first-fruit]").toggleAttribute("hidden", !first);
    panel.querySelector("[data-cane-first-label]").textContent = first ? "May fruit on first-year canes" : "First-year growth";
    panel.querySelector("[data-cane-second-label]").textContent = first ? "A second crop depends on pruning and region" : "Second-year fruiting";
    panel.querySelector("[data-cane-explanation]").textContent = first ? "Primocane-fruiting types can bear fruit in the cane’s first year. Retaining part of the cane can allow a second-year crop; not every region or production system uses both crops." : "Floricane-fruiting types grow a cane in its first year and bear fruit on that cane in its second year.";
  });
})();
