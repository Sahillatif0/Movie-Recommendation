document.addEventListener("DOMContentLoaded", () => {
  const links = document.querySelectorAll("a.btn, .nav-links a");
  const loading = createLoader();

  links.forEach((link) => {
    link.addEventListener("click", () => {
      if (link.getAttribute("href")?.startsWith("#")) return;
      loading.show();
      setTimeout(() => loading.hide(), 1200);
    });
  });

  enhanceMatrixHover();
});

function createLoader() {
  let el = document.querySelector(".loading");
  if (!el) {
    el = document.createElement("div");
    el.className = "loading";
    el.innerHTML = '<div class="spinner"></div>';
    document.body.appendChild(el);
  }
  return {
    show: () => (el.style.display = "flex"),
    hide: () => (el.style.display = "none"),
  };
}

function enhanceMatrixHover() {
  const table = document.querySelector(".table-wrapper table");
  if (!table) return;

  const headerCells = table.querySelectorAll("thead th");
  const bodyRows = table.querySelectorAll("tbody tr");

  const clear = () => {
    table.querySelectorAll(".row-hot, .col-hot, .is-hot").forEach((cell) => {
      cell.classList.remove("row-hot", "col-hot", "is-hot");
    });
  };

  table.querySelectorAll("tbody td").forEach((cell) => {
    cell.addEventListener("mouseenter", () => {
      clear();
      const colIndex = cell.cellIndex; // includes row header
      const row = cell.parentElement;
      row.classList.add("row-hot");

      bodyRows.forEach((r) => {
        const target = r.children[colIndex];
        if (target) target.classList.add("col-hot");
      });
      const header = headerCells[colIndex];
      if (header) header.classList.add("col-hot");
      cell.classList.add("is-hot");
    });
  });

  table.addEventListener("mouseleave", clear);
}
