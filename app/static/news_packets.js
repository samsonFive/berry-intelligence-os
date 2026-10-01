(function () {
  "use strict";
  function localDate(value) {
    return value.getFullYear() + "-" + String(value.getMonth()+1).padStart(2,"0") + "-" + String(value.getDate()).padStart(2,"0");
  }
  document.querySelectorAll("[data-packet-time]").forEach(function (element) {
    element.textContent = new Intl.DateTimeFormat(undefined, {dateStyle:"medium",timeStyle:"short"}).format(new Date(element.dateTime));
  });
  document.querySelectorAll("[data-packet-start]").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelector('[name="start"]').value = button.dataset.packetGenerated ? localDate(new Date(button.dataset.packetGenerated)) : button.dataset.packetStart;
      if (button.dataset.packetEnd) document.querySelector('[name="end"]').value = button.dataset.packetEnd;
    });
  });
})();
