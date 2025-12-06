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
  initBlendControls();
  setupGraphDrilldown();
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

function initBlendControls() {
  const slider = document.querySelector("[data-blend-slider]");
  const values = document.querySelector("[data-blend-values]");
  if (!slider || !values) return;

  const primaryLabel = values.dataset.primaryLabel || "Primary mix";
  const primaryTarget = values.querySelector("[data-primary-share]");
  const secondaryTarget = values.querySelector("[data-secondary-share]");
  const blendToggle = document.querySelector('input[name="blend_enabled"]');
  const algoChecks = Array.from(document.querySelectorAll('input[name="algorithms"]'));

  const render = () => {
    const raw = parseInt(slider.value || "0", 10);
    const clamped = Math.max(0, Math.min(raw, 100));
    const primaryShare = 100 - clamped;
    const secondaryShare = clamped;
    if (primaryTarget) {
      primaryTarget.textContent = `${primaryLabel} · ${primaryShare}%`;
    }
    if (secondaryTarget) {
      secondaryTarget.textContent = `Secondary mix · ${secondaryShare}%`;
    }
  };

  const syncInteractivity = () => {
    const selected = algoChecks.filter((checkbox) => checkbox.checked).length;
    const allowBlend = selected >= 2;
    slider.disabled = !allowBlend;
    if (blendToggle) {
      blendToggle.disabled = !allowBlend;
      if (!allowBlend) {
        blendToggle.checked = false;
      }
    }
    render();
  };

  const syncCardState = (checkbox) => {
    const card = checkbox.closest('.algo-card');
    if (card) {
      card.classList.toggle('is-selected', checkbox.checked);
    }
  };

  algoChecks.forEach((checkbox) => {
    syncCardState(checkbox);
    checkbox.addEventListener("change", () => {
      syncCardState(checkbox);
      syncInteractivity();
    });
  });

  syncInteractivity();

  slider.addEventListener("input", render);
}

function setupGraphDrilldown() {
  const graphContainer = document.getElementById("mynetwork");
  if (!graphContainer) return;

  const modal = createNodeModal();
  if (!modal) return;

  const attach = () => {
    if (typeof network === "undefined" || !network) {
      return false;
    }
    network.on("click", (params) => {
      const nodeId = params?.nodes?.[0];
      if (!nodeId) {
        modal.hide();
        return;
      }
      modal.showLoading();
      fetch(`/api/node/${encodeURIComponent(nodeId)}`)
        .then((res) => {
          if (!res.ok) throw new Error("failed");
          return res.json();
        })
        .then((data) => modal.render(data))
        .catch(() => modal.showError("Unable to load node insights."));
    });
    return true;
  };

  if (!attach()) {
    const timer = setInterval(() => {
      if (attach()) {
        clearInterval(timer);
      }
    }, 250);
  }
}

function createNodeModal() {
  let wrapper = document.querySelector("[data-node-modal]");
  if (!wrapper) {
    wrapper = document.createElement("div");
    wrapper.className = "node-modal";
    wrapper.dataset.nodeModal = "1";
    wrapper.innerHTML = `
      <div class="node-modal-panel">
        <button class="node-modal-close" type="button" aria-label="Close insight" data-close-node-modal>×</button>
        <div data-node-modal-body class="node-modal-body"></div>
      </div>`;
    document.body.appendChild(wrapper);
  }

  const body = wrapper.querySelector("[data-node-modal-body]");
  const close = () => wrapper.classList.remove("is-visible");
  wrapper.addEventListener("click", (event) => {
    if (event.target === wrapper || event.target.closest("[data-close-node-modal]")) {
      close();
    }
  });

  const renderProfile = (profile) => {
    const isUser = profile.type === "user";
    const header = isUser
      ? `<h3>User ${profile.id}</h3>`
      : `<h3>${profile.title}</h3><p class="node-subtitle">Movie ${profile.id}</p>`;

    const stats = `
      <div class="node-stat-grid">
        <div>
          <span>${profile.degree || 0}</span>
          <p>Connections</p>
        </div>
        <div>
          <span>${(profile.avg_rating || 0).toFixed(2)}</span>
          <p>${isUser ? "Avg rating" : "Avg score"}</p>
        </div>
      </div>`;

    const favorites = (profile.top_movies || [])
      .map((movie) => `
        <li>
          <strong>${movie.title}</strong>
          <span>${movie.rating.toFixed(2)}</span>
        </li>`)
      .join("") || "<li>No favorites tracked.</li>";

    const neighbors = (profile.similar_users || profile.watchers || [])
      .map((item) => {
        if (profile.similar_users) {
          const shared = (item.shared_titles || []).join(", ");
          return `<li><strong>User ${item.user_id}</strong><span>${item.overlap} shared · ${shared || "No shared titles"}</span></li>`;
        }
        return `<li><strong>User ${item.user_id}</strong><span>Rated ${item.rating.toFixed(2)}</span></li>`;
      })
      .join("") || "<li>No overlaps yet.</li>";

    const related = (profile.related_movies || [])
      .map((item) => `<li><strong>${item.title}</strong><span>${item.overlap} shared viewers</span></li>`)
      .join("");

    body.innerHTML = `
      <div class="node-pill">${isUser ? "User" : "Movie"} node</div>
      ${header}
      ${stats}
      <section>
        <p class="node-section-label">${isUser ? "Top favorites" : "Most engaged viewers"}</p>
        <ul class="node-modal-list">${isUser ? favorites : neighbors}</ul>
      </section>
      <section>
        <p class="node-section-label">${isUser ? "Closest neighbors" : "Related titles"}</p>
        <ul class="node-modal-list">${isUser ? neighbors : (related || "<li>No related titles in this sample.</li>")}</ul>
      </section>`;
  };

  return {
    showLoading() {
      body.innerHTML = "<p class=\"node-loading\">Loading node insights...</p>";
      wrapper.classList.add("is-visible");
    },
    showError(message) {
      body.innerHTML = `<p class="node-error">${message}</p>`;
      wrapper.classList.add("is-visible");
    },
    render(profile) {
      renderProfile(profile);
      wrapper.classList.add("is-visible");
    },
    hide: close,
  };
}
