(function () {
  "use strict";
  document.querySelectorAll("[data-landscape-picker]").forEach(function (picker) {
    var search = picker.querySelector("[data-landscape-search]");
    search.addEventListener("input", function () {
      var query = search.value.toLocaleLowerCase().trim();
      picker.querySelectorAll("[data-landscape-option]").forEach(function (row) {
        row.hidden = !(row.dataset.search || row.textContent).toLocaleLowerCase().includes(query);
      });
    });
  });
}());
