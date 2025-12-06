const root = document.documentElement;
root.classList.add("page-loading");
window.addEventListener("load", () => {
  root.classList.remove("page-loading");
});

document.addEventListener("DOMContentLoaded", () => {

  const links = document.querySelectorAll("a.btn, .nav-links a");
  const loading = createLoader();

  links.forEach((link) => {
    link.addEventListener("click", () => {
      const href = link.getAttribute("href");
      if (href?.startsWith("#")) return;
      
      loading.show();
      
      // For graph pages, keep loading visible until page fully loads
      if (href?.includes("/graph")) {
        // Don't auto-hide for graph pages - let the page hide it
      } else {
        setTimeout(() => loading.hide(), 1200);
      }
    });
  });

  enhanceMatrixHover();
  hideLoadingWhenGraphReady();
});

function hideLoadingWhenGraphReady() {
  // Check if we're on a graph page
  const graphContainer = document.getElementById('mynetwork');
  if (!graphContainer) return;
  
  // Hide loading when page is fully loaded and graph is drawn
  const hideLoading = () => {
    const loader = document.querySelector(".loading");
    if (loader) {
      setTimeout(() => {
        loader.style.display = "none";
      }, 500);
    }
  };
  
  // Method 1: Listen for window load
  if (document.readyState === 'complete') {
    hideLoading();
  } else {
    window.addEventListener('load', hideLoading);
  }
  
  // Method 2: Check for network object (PyVis creates this)
  const checkNetwork = setInterval(() => {
    if (typeof network !== 'undefined' && network) {
      try {
        network.on('stabilizationIterationsDone', hideLoading);
        clearInterval(checkNetwork);
      } catch (e) {
        // Continue checking
      }
    }
  }, 100);
  
  // Fallback: Force hide after 3 seconds
  setTimeout(hideLoading, 3000);
}

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
