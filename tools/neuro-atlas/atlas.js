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
function setActivePlate(plateId) { state.activePlateId = plateId; updateSidebarActive(); }
function initPan() {}
function initZoomButtons() {}
function initSearch() {}
function clearHighlight() {}
function showHighlightWithZoom(plateId, region) {}

// ─── Bootstrap ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
