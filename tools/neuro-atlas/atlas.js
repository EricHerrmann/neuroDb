// ─── State ────────────────────────────────────────────────────────────────────
const state = {
  plates: [],
  activePlateId: null,
  searchTerm: '',
  activeMatch: null,
  zoom: 1,
  panX: 0,
  panY: 0,
  isDragging: false,
  dragStartX: 0,
  dragStartY: 0,
  dragStartPanX: 0,
  dragStartPanY: 0,
};

// ─── Search index ─────────────────────────────────────────────────────────────
const searchIndex = new Map();

function buildSearchIndex() {
  searchIndex.clear();
  for (const plate of state.plates) {
    for (const region of plate.regions) {
      const key = region.term.toLowerCase();
      if (!searchIndex.has(key)) searchIndex.set(key, []);
      searchIndex.get(key).push({ plateId: plate.id, region });
    }
  }
}

// ─── Boot ─────────────────────────────────────────────────────────────────────
async function init() {
  try {
    const manifest = await fetch('data/manifest.json').then(r => {
      if (!r.ok) throw new Error(`manifest fetch failed: ${r.status}`);
      return r.json();
    });
    const results = await Promise.all(
      manifest.plates.map(id =>
        fetch(`data/plates/${id}.json`)
          .then(r => r.ok ? r.json() : Promise.reject(new Error(`${r.status}`)))
          .catch(err => { console.warn(`Skipping plate "${id}": ${err.message}`); return null; })
      )
    );
    state.plates = results.filter(Boolean);
    buildSearchIndex();
    renderSidebar();
    initPan();
    initZoomButtons();
    initSearch();
    if (state.plates.length > 0) setActivePlate(state.plates[0].id);
  } catch (err) {
    const p = document.createElement('p');
    p.className = 'error-state';
    p.textContent = `Could not load atlas data: ${err.message}`;
    document.getElementById('viewer-container').replaceChildren(p);
  }
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
function renderSidebar() {
  const list = document.getElementById('plate-list');
  list.innerHTML = '';
  for (const plate of state.plates) {
    const li = document.createElement('li');
    li.dataset.plateId = plate.id;
    const dot = document.createElement('span');
    dot.className = 'match-dot';
    const name = document.createElement('span');
    name.className = 'plate-name';
    name.textContent = plate.displayName;
    li.append(dot, name);
    li.addEventListener('click', () => onSidebarClick(plate.id));
    list.appendChild(li);
  }
}

function onSidebarClick(plateId) {
  setActivePlate(plateId);
  if (state.searchTerm) {
    const matches = searchIndex.get(state.searchTerm) || [];
    const match = matches.find(m => m.plateId === plateId);
    if (match) {
      showHighlightWithZoom(plateId, match.region);
    } else {
      clearHighlight();
    }
  }
}

function updateSidebarActive() {
  document.querySelectorAll('#plate-list li').forEach(li => {
    li.classList.toggle('active', li.dataset.plateId === state.activePlateId);
  });
}

function updateSidebarMatchDots() {
  const matchingIds = new Set(
    (searchIndex.get(state.searchTerm) || []).map(m => m.plateId)
  );
  document.querySelectorAll('#plate-list li').forEach(li => {
    li.classList.toggle('has-match', matchingIds.has(li.dataset.plateId));
  });
}

// ─── Placeholder stubs (filled in Tasks 4–7) ─────────────────────────────────
function setActivePlate(plateId) {
  const plate = state.plates.find(p => p.id === plateId);
  if (!plate) return;
  state.activePlateId = plateId;
  clearHighlight();
  const img = document.getElementById('atlas-image');
  img.alt = plate.displayName;
  img.src = `../../library/Neuroscience7thed/images/${encodeURIComponent(plate.filename)}`;
  img.onload = () => {
    updateHighlightOverlaySize();
    resetZoomPan();
  };
  img.onerror = () => {
    img.alt = `[Image not found: ${plate.filename}]`;
  };
  updateSidebarActive();
}

// ─── Viewer helpers ───────────────────────────────────────────────────────────
function updateHighlightOverlaySize() {
  const img = document.getElementById('atlas-image');
  const svg = document.getElementById('highlight-overlay');
  svg.setAttribute('width', img.naturalWidth);
  svg.setAttribute('height', img.naturalHeight);
  svg.setAttribute('viewBox', `0 0 ${img.naturalWidth} ${img.naturalHeight}`);
}

function resetZoomPan() {
  const surface = document.getElementById('viewer-surface');
  const img = document.getElementById('atlas-image');
  if (!img.naturalWidth) return;
  const scaleX = surface.clientWidth / img.naturalWidth;
  const scaleY = surface.clientHeight / img.naturalHeight;
  state.zoom = Math.min(scaleX, scaleY, 1);
  state.panX = (surface.clientWidth - img.naturalWidth * state.zoom) / 2;
  state.panY = (surface.clientHeight - img.naturalHeight * state.zoom) / 2;
  applyTransform();
}

function applyTransform() {
  const inner = document.getElementById('viewer-inner');
  inner.style.transform =
    `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
}

function initPan() {
  const surface = document.getElementById('viewer-surface');

  surface.addEventListener('mousedown', e => {
    if (e.button !== 0) return;
    state.isDragging = true;
    state.dragStartX = e.clientX;
    state.dragStartY = e.clientY;
    state.dragStartPanX = state.panX;
    state.dragStartPanY = state.panY;
    surface.classList.add('dragging');
    e.preventDefault();
  });

  window.addEventListener('mousemove', e => {
    if (!state.isDragging) return;
    state.panX = state.dragStartPanX + (e.clientX - state.dragStartX);
    state.panY = state.dragStartPanY + (e.clientY - state.dragStartY);
    applyTransform();
  });

  window.addEventListener('mouseup', () => {
    state.isDragging = false;
    surface.classList.remove('dragging');
  });

  surface.addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    zoomAt(factor, e.clientX, e.clientY);
  }, { passive: false });
}

function zoomAt(factor, clientX, clientY) {
  const surface = document.getElementById('viewer-surface');
  const rect = surface.getBoundingClientRect();
  const mouseX = clientX - rect.left;
  const mouseY = clientY - rect.top;
  const imgX = (mouseX - state.panX) / state.zoom;
  const imgY = (mouseY - state.panY) / state.zoom;
  const newZoom = Math.min(8, Math.max(0.5, state.zoom * factor));
  state.panX = mouseX - imgX * newZoom;
  state.panY = mouseY - imgY * newZoom;
  state.zoom = newZoom;
  applyTransform();
}

function initZoomButtons() {
  document.getElementById('zoom-in').addEventListener('click', () => {
    const surface = document.getElementById('viewer-surface');
    const rect = surface.getBoundingClientRect();
    zoomAt(1.25, rect.left + rect.width / 2, rect.top + rect.height / 2);
  });
  document.getElementById('zoom-out').addEventListener('click', () => {
    const surface = document.getElementById('viewer-surface');
    const rect = surface.getBoundingClientRect();
    zoomAt(0.8, rect.left + rect.width / 2, rect.top + rect.height / 2);
  });
  document.getElementById('zoom-reset').addEventListener('click', resetZoomPan);
}
function initSearch() {}
function clearHighlight() {
  document.getElementById('highlight-overlay').innerHTML = '';
  state.activeMatch = null;
}
function showHighlight(region) {
  const img = document.getElementById('atlas-image');
  const svg = document.getElementById('highlight-overlay');
  const cx = (region.cx / 100) * img.naturalWidth;
  const cy = (region.cy / 100) * img.naturalHeight;
  const r  = (region.r  / 100) * img.naturalWidth;
  svg.innerHTML = `
    <circle class="highlight-circle" cx="${cx}" cy="${cy}" r="${r}"/>
    <text class="highlight-label"
          x="${cx}" y="${cy - r - 8}"
          text-anchor="middle">${region.label}</text>
  `;
}

function showHighlightWithZoom(plateId, region) {
  const doRender = () => {
    showHighlight(region);
    state.activeMatch = { plateId, region };
    const img = document.getElementById('atlas-image');
    const surface = document.getElementById('viewer-surface');
    const cx_px = (region.cx / 100) * img.naturalWidth;
    const cy_px = (region.cy / 100) * img.naturalHeight;
    state.zoom = 2.5;
    state.panX = surface.clientWidth  / 2 - cx_px * state.zoom;
    state.panY = surface.clientHeight / 2 - cy_px * state.zoom;
    applyTransform();
  };

  if (state.activePlateId !== plateId) {
    setActivePlate(plateId);
    const img = document.getElementById('atlas-image');
    const prev = img.onload;
    img.onload = () => { if (prev) prev(); doRender(); };
  } else {
    const img = document.getElementById('atlas-image');
    if (img.complete && img.naturalWidth > 0) doRender();
    else img.onload = () => { updateHighlightOverlaySize(); resetZoomPan(); doRender(); };
  }
}

// ─── Bootstrap ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
