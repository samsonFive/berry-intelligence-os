(function () {
  "use strict";

  var frame = document.getElementById("preview-frame");
  var live = document.getElementById("live");
  var backdrop = document.getElementById("backdrop");
  var drawer = document.getElementById("drawer");
  var toastRegion = document.getElementById("toast-region");
  var lastFocus = null;

  function announce(msg) {
    live.textContent = "";
    requestAnimationFrame(function () { live.textContent = msg; });
  }

  document.querySelectorAll("[data-viewport]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var width = btn.getAttribute("data-viewport");
      frame.setAttribute("data-width", width);
      document.querySelectorAll("[data-viewport]").forEach(function (b) {
        b.setAttribute("aria-pressed", b === btn ? "true" : "false");
      });
      announce("Preview width set to " + width);
    });
  });

  document.querySelectorAll(".filter-bar .chip-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".filter-bar .chip-btn").forEach(function (b) {
        b.setAttribute("aria-pressed", b === btn ? "true" : "false");
      });
      var active = document.querySelector(".active-chip");
      if (active) {
        active.childNodes[0].textContent = "Active: " + btn.textContent + " ";
      }
      announce("Filter " + btn.textContent);
    });
  });

  document.querySelectorAll(".chips .chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      chip.parentElement.querySelectorAll(".chip").forEach(function (c) {
        c.setAttribute("aria-checked", c === chip ? "true" : "false");
      });
      announce("Reason " + chip.textContent);
    });
  });

  function openDrawer() {
    lastFocus = document.activeElement;
    backdrop.hidden = false;
    backdrop.classList.add("open");
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    document.getElementById("drawer-close").focus();
    announce("Reader drawer opened");
  }

  function closeDrawer() {
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    backdrop.classList.remove("open");
    backdrop.hidden = true;
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
    announce("Reader drawer closed");
  }

  function showToast() {
    toastRegion.innerHTML = "";
    var toast = document.createElement("div");
    toast.className = "toast";
    toast.setAttribute("role", "status");
    toast.innerHTML = "<span>Excluded from trusted feed. Provenance retained.</span><button type=\"button\">Undo</button>";
    var undo = toast.querySelector("button");
    undo.addEventListener("click", function () {
      toastRegion.innerHTML = "";
      announce("Undo applied");
      if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
    });
    toastRegion.appendChild(toast);
    undo.focus();
    announce("Undo toast shown");
    setTimeout(function () {
      if (toastRegion.contains(toast)) toastRegion.innerHTML = "";
    }, 7000);
  }

  var open1 = document.getElementById("open-drawer-demo");
  var open2 = document.getElementById("open-drawer-demo-2");
  if (open1) open1.addEventListener("click", openDrawer);
  if (open2) open2.addEventListener("click", openDrawer);
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  backdrop.addEventListener("click", closeDrawer);
  document.getElementById("show-toast-demo").addEventListener("click", function () {
    lastFocus = document.activeElement;
    showToast();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && drawer.classList.contains("open")) {
      closeDrawer();
      e.preventDefault();
    }
  });

  // Current-nav highlight on scroll
  var links = Array.prototype.slice.call(document.querySelectorAll(".rail-nav a[href^='#']"));
  var sections = links.map(function (a) {
    return document.querySelector(a.getAttribute("href"));
  }).filter(Boolean);

  function syncNav() {
    var y = window.scrollY + 120;
    var current = sections[0];
    sections.forEach(function (sec) {
      if (sec.offsetTop <= y) current = sec;
    });
    links.forEach(function (a) {
      a.setAttribute("aria-current", a.getAttribute("href") === "#" + current.id ? "page" : null);
      if (a.getAttribute("href") !== "#" + current.id) a.removeAttribute("aria-current");
      else a.setAttribute("aria-current", "page");
    });
  }
  window.addEventListener("scroll", syncNav, { passive: true });
  syncNav();
})();
