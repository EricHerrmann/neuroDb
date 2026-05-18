# NeuroAtlas Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone browser-based 2D atlas viewer at `tools/neuro-atlas/` where the user searches a neuroscience term and sees a pinpoint highlight on the correct atlas plate with zoom/pan.

**Architecture:** Pure HTML/CSS/vanilla JS, no build tools. Data-driven via `manifest.json` + one JSON file per plate. The app fetches all plate files on load, builds a search index in memory, and renders an SVG highlight overlay inside the same CSS-transformed container as the image so highlights stay locked at all zoom levels.

**Tech Stack:** HTML5, CSS3, vanilla JS (ES2020), SVG, `python3 -m http.server` to serve locally.

---

## File Map

| File | Responsibility |
|------|----------------|
| `tools/neuro-atlas/index.html` | App shell: header with search, three-column layout, DOM structure |
| `tools/neuro-atlas/styles.css` | Layout, dark theme, zoom controls, highlight animation |
| `tools/neuro-atlas/atlas.js` | All application logic: boot, data loading, search index, zoom/pan, SVG highlight, results |
| `tools/neuro-atlas/data/manifest.json` | Ordered list of plate IDs — only file edited when adding a plate |
| `tools/neuro-atlas/data/plates/brain-lobes.json` | Plate metadata + region coordinates for ATLAS Human Brain Lobes.png |
| `tools/neuro-atlas/data/plates/cns-1.json` | Lateral (A) + medial (B) labeled anatomy |
| `tools/neuro-atlas/data/plates/cns-2.json` | Same view pair as cns-1 (different page of same atlas figure) |
| `tools/neuro-atlas/data/plates/cns-3.json` | Dorsal (C) + ventral (D) views |
| `tools/neuro-atlas/data/plates/cns-4.json` | Same view pair as cns-3 |
| `tools/neuro-atlas/data/plates/neural-map-1.json` | DTI axial (A) + sagittal (B) tractography |
| `tools/neuro-atlas/data/plates/neural-map-2.json` | Same view pair as neural-map-1 |
| `tools/neuro-atlas/data/plates/neural-map-3.json` | DTI sagittal (C) + 3D planes diagram (D) |
| `tools/neuro-atlas/data/plates/brain-3d-quarters.json` | Same content as neural-map-3 |
| `tools/neuro-atlas/README.md` | How to run; how to add a new plate |

**Images are NOT copied.** They are referenced as `../../library/Neuroscience7thed/images/<filename>` from `index.html`.

---

## Task 1: Project Scaffold

**Files:**
- Create: `tools/neuro-atlas/index.html`
- Create: `tools/neuro-atlas/styles.css`
- Create: `tools/neuro-atlas/atlas.js`
- Create: `tools/neuro-atlas/README.md`

- [ ] **Step 1.1 — Create directory**

```bash
mkdir -p /home/oldha/projects/neuroDb/tools/neuro-atlas/data/plates
```

- [ ] **Step 1.2 — Write `index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NeuroAtlas Viewer</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header>
    <div class="logo">NeuroAtlas</div>
    <div class="search-container">
      <input type="text" id="search-input"
        placeholder="Search a brain structure..." autocomplete="off">
      <div id="autocomplete-dropdown" class="autocomplete-dropdown hidden"></div>
    </div>
  </header>
  <main>
    <aside id="sidebar">
      <div class="sidebar-header">PLATES</div>
      <ul id="plate-list"></ul>
    </aside>
    <div id="viewer-container">
      <div id="viewer-surface">
        <div id="viewer-inner">
          <img id="atlas-image" src="" alt="" draggable="false">
          <svg id="highlight-overlay"></svg>
        </div>
      </div>
      <div class="zoom-controls">
        <button id="zoom-out" title="Zoom out">−</button>
        <button id="zoom-in"  title="Zoom in">+</button>
        <button id="zoom-reset" title="Reset view">⟳</button>
      </div>
    </div>
    <aside id="results-panel">
      <div class="panel-header">RESULTS</div>
      <div id="results-content">
        <p class="empty-state">Search a term to highlight regions</p>
      </div>
    </aside>
  </main>
  <script src="atlas.js"></script>
</body>
</html>
```

- [ ] **Step 1.3 — Write `styles.css`**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: #0f172a;
  color: #e2e8f0;
  font-family: system-ui, -apple-system, sans-serif;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* ── Header ── */
header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  background: #0f172a;
  border-bottom: 1px solid #1e293b;
  flex-shrink: 0;
  z-index: 10;
}

.logo {
  font-size: 15px;
  font-weight: 700;
  color: #f8fafc;
  letter-spacing: 0.06em;
  white-space: nowrap;
}

.search-container {
  position: relative;
  flex: 1;
  max-width: 420px;
}

#search-input {
  width: 100%;
  padding: 7px 12px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
}
#search-input:focus { border-color: #3b82f6; }

.autocomplete-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0; right: 0;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  max-height: 260px;
  overflow-y: auto;
  z-index: 100;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}
.autocomplete-dropdown.hidden { display: none; }

.autocomplete-item {
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  color: #cbd5e1;
}
.autocomplete-item:hover,
.autocomplete-item.active { background: #334155; color: #f8fafc; }

/* ── Three-column body ── */
main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

aside {
  flex-shrink: 0;
  overflow-y: auto;
  background: #0f172a;
}

#sidebar {
  width: 160px;
  border-right: 1px solid #1e293b;
}

#results-panel {
  width: 190px;
  border-left: 1px solid #1e293b;
}

.sidebar-header, .panel-header {
  padding: 8px 12px;
  font-size: 10px;
  font-weight: 700;
  color: #475569;
  letter-spacing: 0.08em;
  border-bottom: 1px solid #1e293b;
  position: sticky;
  top: 0;
  background: #0f172a;
}

/* ── Sidebar plate list ── */
#plate-list { list-style: none; padding: 4px 0; }

#plate-list li {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px 8px 9px;
  font-size: 12px;
  cursor: pointer;
  color: #94a3b8;
  border-left: 3px solid transparent;
  line-height: 1.3;
}
#plate-list li:hover { background: #1e293b; color: #e2e8f0; }
#plate-list li.active { border-left-color: #3b82f6; color: #e2e8f0; background: #0f2744; }

.match-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #fbbf24;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
}
.has-match .match-dot { opacity: 1; }

/* ── Main viewer ── */
#viewer-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #020617;
}

#viewer-surface {
  width: 100%; height: 100%;
  overflow: hidden;
  cursor: grab;
}
#viewer-surface.dragging { cursor: grabbing; }

#viewer-inner {
  display: inline-block;
  position: relative;
  transform-origin: 0 0;
  user-select: none;
}

#atlas-image {
  display: block;
  max-width: none;
  user-select: none;
  -webkit-user-drag: none;
}

#highlight-overlay {
  position: absolute;
  top: 0; left: 0;
  pointer-events: none;
  overflow: visible;
}

.zoom-controls {
  position: absolute;
  bottom: 14px; right: 14px;
  display: flex;
  gap: 4px;
}
.zoom-controls button {
  width: 30px; height: 30px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #94a3b8;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}
.zoom-controls button:hover { background: #334155; color: #f8fafc; }

/* ── Results panel ── */
#results-content { padding: 12px; }

.empty-state { color: #475569; font-size: 12px; line-height: 1.5; }

.result-term {
  font-size: 13px;
  font-weight: 600;
  color: #fbbf24;
  margin-bottom: 10px;
  text-transform: capitalize;
}

.result-label {
  font-size: 10px;
  font-weight: 700;
  color: #475569;
  letter-spacing: 0.07em;
  margin-bottom: 6px;
}

.result-plates { list-style: none; }
.result-plates li {
  padding: 6px 8px;
  font-size: 12px;
  color: #94a3b8;
  cursor: pointer;
  border-radius: 4px;
  line-height: 1.3;
}
.result-plates li:hover { background: #1e293b; color: #e2e8f0; }
.result-plates li.current { color: #3b82f6; }

.no-match { color: #64748b; font-size: 12px; font-style: italic; }

/* ── Highlight animation ── */
@keyframes highlight-pulse {
  0%   { opacity: 0.9; }
  50%  { opacity: 0.4; }
  100% { opacity: 0.9; }
}

.highlight-circle {
  fill: none;
  stroke: #fbbf24;
  stroke-width: 2.5;
  animation: highlight-pulse 1.8s ease-in-out infinite;
}

.highlight-label {
  fill: #fbbf24;
  font-size: 13px;
  font-family: system-ui, sans-serif;
  font-weight: 600;
  paint-order: stroke fill;
  stroke: #0f172a;
  stroke-width: 3;
}

.error-state {
  color: #ef4444;
  font-size: 12px;
  padding: 24px;
}
```

- [ ] **Step 1.4 — Write `atlas.js` stub** (ensures the file exists and doesn't crash on load)

```javascript
// NeuroAtlas — loaded by index.html after DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  console.log('NeuroAtlas loading...');
});
```

- [ ] **Step 1.5 — Write `README.md`**

```markdown
# NeuroAtlas Viewer

Standalone browser-based atlas viewer for neuroscience study.

## Running

```bash
cd tools/neuro-atlas
python3 -m http.server 8080
# open http://localhost:8080
```

## Adding a New Plate

Three steps, no code changes required:

1. Place the image in `library/Neuroscience7thed/images/`
2. Create `data/plates/<id>.json`:

```json
{
  "id": "my-plate",
  "filename": "My Atlas Image.png",
  "displayName": "My Plate Name",
  "category": "custom",
  "regions": [
    { "term": "frontal lobe", "cx": 28.4, "cy": 35.1, "r": 11.0, "label": "Frontal lobe" }
  ]
}
```

3. Add the id to `data/manifest.json`:

```json
{ "plates": ["brain-lobes", "cns-1", ..., "my-plate"] }
```

## Region Coordinates

`cx`, `cy` = center of the region as **percentage** of image width/height (0–100).
`r` = highlight circle radius as percentage of image width.

To find coordinates: open the image in any viewer that shows pixel coordinates.
Find the center pixel of the labeled structure. Divide by image width/height.
```

- [ ] **Step 1.6 — Start the dev server and verify the scaffold loads**

```bash
cd /home/oldha/projects/neuroDb/tools/neuro-atlas
python3 -m http.server 8080
```

Open http://localhost:8080. Expected: dark page with "NeuroAtlas" in header, three empty columns, no JS errors in browser console.

- [ ] **Step 1.7 — Commit**

```bash
cd /home/oldha/projects/neuroDb
git add tools/neuro-atlas/
git commit -m "feat(neuro-atlas): scaffold — HTML shell, CSS layout, README"
```

---

## Task 2: Data Files

**Files:**
- Create: `tools/neuro-atlas/data/manifest.json`
- Create: `tools/neuro-atlas/data/plates/brain-lobes.json`
- Create: `tools/neuro-atlas/data/plates/cns-1.json`
- Create: `tools/neuro-atlas/data/plates/cns-2.json`
- Create: `tools/neuro-atlas/data/plates/cns-3.json`
- Create: `tools/neuro-atlas/data/plates/cns-4.json`
- Create: `tools/neuro-atlas/data/plates/neural-map-1.json`
- Create: `tools/neuro-atlas/data/plates/neural-map-2.json`
- Create: `tools/neuro-atlas/data/plates/neural-map-3.json`
- Create: `tools/neuro-atlas/data/plates/brain-3d-quarters.json`

> **Coordinate note:** `cx`/`cy` are percentages of image natural width/height. `r` is radius as % of width. Values are estimated from visual inspection — fine-tune by running the app, zooming in, and adjusting values in the JSON.

- [ ] **Step 2.1 — Write `data/manifest.json`**

```json
{
  "plates": [
    "brain-lobes",
    "cns-1",
    "cns-2",
    "cns-3",
    "cns-4",
    "neural-map-1",
    "neural-map-2",
    "neural-map-3",
    "brain-3d-quarters"
  ]
}
```

- [ ] **Step 2.2 — Write `data/plates/brain-lobes.json`**

Image: `ATLAS Human Brain Lobes.png` — lateral colored view (top half) and medial view (bottom half).

```json
{
  "id": "brain-lobes",
  "filename": "ATLAS Human Brain Lobes.png",
  "displayName": "Human Brain Lobes",
  "category": "lobes",
  "regions": [
    { "term": "frontal lobe",              "cx": 25.0, "cy": 22.0, "r": 10.0, "label": "Frontal lobe" },
    { "term": "central sulcus",            "cx": 46.0, "cy": 17.0, "r":  3.5, "label": "Central sulcus" },
    { "term": "parietal lobe",             "cx": 57.0, "cy": 19.0, "r":  9.0, "label": "Parietal lobe" },
    { "term": "lateral sulcus",            "cx": 41.0, "cy": 34.0, "r":  4.0, "label": "Lateral (Sylvian) fissure" },
    { "term": "temporal lobe",             "cx": 35.0, "cy": 37.0, "r":  9.0, "label": "Temporal lobe" },
    { "term": "preoccipital notch",        "cx": 66.0, "cy": 34.0, "r":  3.0, "label": "Preoccipital notch" },
    { "term": "occipital lobe",            "cx": 72.0, "cy": 26.0, "r":  8.0, "label": "Occipital lobe" },
    { "term": "cingulate gyrus",           "cx": 31.0, "cy": 63.0, "r":  4.0, "label": "Cingulate gyrus" },
    { "term": "cingulate sulcus",          "cx": 27.0, "cy": 60.0, "r":  3.0, "label": "Cingulate sulcus" },
    { "term": "parieto-occipital sulcus",  "cx": 60.0, "cy": 64.0, "r":  3.0, "label": "Parieto-occipital sulcus" }
  ]
}
```

- [ ] **Step 2.3 — Write `data/plates/cns-1.json`**

Image: `ATLAS Human CNS 1.png` — lateral view (A, top half) and medial view (B, bottom half) with detailed gyrus/sulcus labels.

```json
{
  "id": "cns-1",
  "filename": "ATLAS Human CNS 1.png",
  "displayName": "CNS Lateral & Medial",
  "category": "cns",
  "regions": [
    { "term": "superior frontal gyrus",    "cx": 30.0, "cy": 11.0, "r": 4.0, "label": "Superior frontal gyrus" },
    { "term": "superior frontal sulcus",   "cx": 32.0, "cy": 14.0, "r": 3.0, "label": "Superior frontal sulcus" },
    { "term": "middle frontal gyrus",      "cx": 28.0, "cy": 17.0, "r": 4.0, "label": "Middle frontal gyrus" },
    { "term": "inferior frontal gyrus",    "cx": 24.0, "cy": 21.0, "r": 4.0, "label": "Inferior frontal gyrus" },
    { "term": "inferior frontal sulcus",   "cx": 26.0, "cy": 24.0, "r": 3.0, "label": "Inferior frontal sulcus" },
    { "term": "precentral gyrus",          "cx": 35.0, "cy": 16.0, "r": 4.0, "label": "Precentral gyrus" },
    { "term": "central sulcus",            "cx": 43.0, "cy": 15.0, "r": 3.0, "label": "Central sulcus" },
    { "term": "superior parietal lobule",  "cx": 53.0, "cy": 14.0, "r": 4.0, "label": "Superior parietal lobule" },
    { "term": "intraparietal sulcus",      "cx": 50.0, "cy": 18.0, "r": 3.0, "label": "Intraparietal sulcus" },
    { "term": "postcentral sulcus",        "cx": 48.0, "cy": 21.0, "r": 3.0, "label": "Postcentral sulcus" },
    { "term": "postcentral gyrus",         "cx": 46.0, "cy": 19.0, "r": 3.5, "label": "Postcentral gyrus" },
    { "term": "angular gyrus",             "cx": 57.0, "cy": 26.0, "r": 4.0, "label": "Angular gyrus" },
    { "term": "supramarginal gyrus",       "cx": 52.0, "cy": 25.0, "r": 4.0, "label": "Supramarginal gyrus" },
    { "term": "lateral occipital gyri",    "cx": 64.0, "cy": 24.0, "r": 4.0, "label": "Lateral occipital gyri" },
    { "term": "superior temporal gyrus",   "cx": 38.0, "cy": 33.0, "r": 4.0, "label": "Superior temporal gyrus" },
    { "term": "superior temporal sulcus",  "cx": 38.0, "cy": 30.0, "r": 3.0, "label": "Superior temporal sulcus" },
    { "term": "middle temporal gyrus",     "cx": 38.0, "cy": 36.0, "r": 4.0, "label": "Middle temporal gyrus" },
    { "term": "inferior temporal gyrus",   "cx": 40.0, "cy": 40.0, "r": 4.0, "label": "Inferior temporal gyrus" },
    { "term": "inferior temporal sulcus",  "cx": 42.0, "cy": 37.0, "r": 3.0, "label": "Inferior temporal sulcus" },
    { "term": "lateral sulcus",            "cx": 38.0, "cy": 27.0, "r": 3.0, "label": "Lateral (Sylvian) fissure" },
    { "term": "cerebellar hemisphere",     "cx": 62.0, "cy": 40.0, "r": 5.0, "label": "Cerebellar hemisphere" },
    { "term": "preoccipital notch",        "cx": 65.0, "cy": 33.0, "r": 3.0, "label": "Preoccipital notch" },
    { "term": "cingulate sulcus",          "cx": 27.0, "cy": 58.0, "r": 3.0, "label": "Cingulate sulcus" },
    { "term": "cingulate gyrus",           "cx": 30.0, "cy": 61.0, "r": 4.0, "label": "Cingulate gyrus" },
    { "term": "genu of corpus callosum",   "cx": 35.0, "cy": 62.0, "r": 3.5, "label": "Genu of corpus callosum" },
    { "term": "corpus callosum",           "cx": 44.0, "cy": 64.0, "r": 4.0, "label": "Corpus callosum, body" },
    { "term": "splenium of corpus callosum","cx": 49.0,"cy": 64.0, "r": 3.5, "label": "Splenium of corpus callosum" },
    { "term": "lateral ventricle",         "cx": 37.0, "cy": 60.0, "r": 3.5, "label": "Lateral ventricle" },
    { "term": "fornix",                    "cx": 40.0, "cy": 64.0, "r": 3.0, "label": "Fornix" },
    { "term": "paracentral lobule",        "cx": 44.0, "cy": 61.0, "r": 4.0, "label": "Paracentral lobule" },
    { "term": "precuneus",                 "cx": 52.0, "cy": 63.0, "r": 4.0, "label": "Precuneus" },
    { "term": "cuneus",                    "cx": 62.0, "cy": 67.0, "r": 4.0, "label": "Cuneus" },
    { "term": "parieto-occipital sulcus",  "cx": 57.0, "cy": 66.0, "r": 3.0, "label": "Parieto-occipital sulcus" },
    { "term": "calcarine sulcus",          "cx": 63.0, "cy": 70.0, "r": 3.0, "label": "Calcarine sulcus" },
    { "term": "lingual gyrus",             "cx": 62.0, "cy": 74.0, "r": 4.0, "label": "Lingual gyrus" },
    { "term": "thalamus",                  "cx": 42.0, "cy": 67.0, "r": 4.0, "label": "Thalamus" },
    { "term": "hypothalamus",              "cx": 38.0, "cy": 69.0, "r": 3.0, "label": "Hypothalamus" },
    { "term": "optic chiasm",              "cx": 36.0, "cy": 71.0, "r": 3.0, "label": "Optic chiasm" },
    { "term": "midbrain",                  "cx": 44.0, "cy": 74.0, "r": 4.0, "label": "Midbrain" },
    { "term": "pons",                      "cx": 44.0, "cy": 79.0, "r": 4.0, "label": "Pons" },
    { "term": "fourth ventricle",          "cx": 48.0, "cy": 78.0, "r": 3.5, "label": "Fourth ventricle" },
    { "term": "medulla oblongata",         "cx": 43.0, "cy": 84.0, "r": 4.0, "label": "Medulla oblongata" },
    { "term": "parahippocampal gyrus",     "cx": 46.0, "cy": 79.0, "r": 4.0, "label": "Parahippocampal gyrus" },
    { "term": "rhinal sulcus",             "cx": 40.0, "cy": 78.0, "r": 3.0, "label": "Rhinal sulcus" },
    { "term": "gyrus rectus",              "cx": 32.0, "cy": 74.0, "r": 3.0, "label": "Gyrus rectus" }
  ]
}
```

- [ ] **Step 2.4 — Write `data/plates/cns-2.json`**

Same atlas views as cns-1 (different page export of the same figure set). Regions identical; coordinates may need minor adjustment once both are tested side-by-side.

```json
{
  "id": "cns-2",
  "filename": "ATLAS Human CNS 2.png",
  "displayName": "CNS Lateral & Medial II",
  "category": "cns",
  "regions": [
    { "term": "superior frontal gyrus",    "cx": 30.0, "cy": 11.0, "r": 4.0, "label": "Superior frontal gyrus" },
    { "term": "superior frontal sulcus",   "cx": 32.0, "cy": 14.0, "r": 3.0, "label": "Superior frontal sulcus" },
    { "term": "middle frontal gyrus",      "cx": 28.0, "cy": 17.0, "r": 4.0, "label": "Middle frontal gyrus" },
    { "term": "inferior frontal gyrus",    "cx": 24.0, "cy": 21.0, "r": 4.0, "label": "Inferior frontal gyrus" },
    { "term": "precentral gyrus",          "cx": 35.0, "cy": 16.0, "r": 4.0, "label": "Precentral gyrus" },
    { "term": "central sulcus",            "cx": 43.0, "cy": 15.0, "r": 3.0, "label": "Central sulcus" },
    { "term": "superior parietal lobule",  "cx": 53.0, "cy": 14.0, "r": 4.0, "label": "Superior parietal lobule" },
    { "term": "postcentral gyrus",         "cx": 46.0, "cy": 19.0, "r": 3.5, "label": "Postcentral gyrus" },
    { "term": "angular gyrus",             "cx": 57.0, "cy": 26.0, "r": 4.0, "label": "Angular gyrus" },
    { "term": "supramarginal gyrus",       "cx": 52.0, "cy": 25.0, "r": 4.0, "label": "Supramarginal gyrus" },
    { "term": "superior temporal gyrus",   "cx": 38.0, "cy": 33.0, "r": 4.0, "label": "Superior temporal gyrus" },
    { "term": "middle temporal gyrus",     "cx": 38.0, "cy": 36.0, "r": 4.0, "label": "Middle temporal gyrus" },
    { "term": "inferior temporal gyrus",   "cx": 40.0, "cy": 40.0, "r": 4.0, "label": "Inferior temporal gyrus" },
    { "term": "lateral sulcus",            "cx": 38.0, "cy": 27.0, "r": 3.0, "label": "Lateral (Sylvian) fissure" },
    { "term": "cerebellar hemisphere",     "cx": 62.0, "cy": 40.0, "r": 5.0, "label": "Cerebellar hemisphere" },
    { "term": "cingulate gyrus",           "cx": 30.0, "cy": 61.0, "r": 4.0, "label": "Cingulate gyrus" },
    { "term": "corpus callosum",           "cx": 44.0, "cy": 64.0, "r": 4.0, "label": "Corpus callosum, body" },
    { "term": "thalamus",                  "cx": 42.0, "cy": 67.0, "r": 4.0, "label": "Thalamus" },
    { "term": "midbrain",                  "cx": 44.0, "cy": 74.0, "r": 4.0, "label": "Midbrain" },
    { "term": "pons",                      "cx": 44.0, "cy": 79.0, "r": 4.0, "label": "Pons" },
    { "term": "medulla oblongata",         "cx": 43.0, "cy": 84.0, "r": 4.0, "label": "Medulla oblongata" }
  ]
}
```

- [ ] **Step 2.5 — Write `data/plates/cns-3.json`**

Image: `ATLAS Human CNS 3.png` — dorsal view (C, top half) and ventral view (D, bottom half).

```json
{
  "id": "cns-3",
  "filename": "ATLAS Human CNS 3.png",
  "displayName": "CNS Dorsal & Ventral",
  "category": "cns",
  "regions": [
    { "term": "supramarginal gyrus",       "cx": 62.0, "cy": 22.0, "r": 4.0, "label": "Supramarginal gyrus" },
    { "term": "angular gyrus",             "cx": 63.0, "cy": 27.0, "r": 4.0, "label": "Angular gyrus" },
    { "term": "postcentral sulcus",        "cx": 55.0, "cy": 20.0, "r": 3.0, "label": "Postcentral sulcus" },
    { "term": "central sulcus",            "cx": 48.0, "cy": 17.0, "r": 3.0, "label": "Central sulcus" },
    { "term": "precentral gyrus",          "cx": 41.0, "cy": 18.0, "r": 4.0, "label": "Precentral gyrus" },
    { "term": "precentral sulcus",         "cx": 37.0, "cy": 21.0, "r": 3.0, "label": "Precentral sulcus" },
    { "term": "superior frontal gyrus",    "cx": 32.0, "cy": 23.0, "r": 4.0, "label": "Superior frontal gyrus" },
    { "term": "longitudinal fissure",      "cx": 50.0, "cy": 20.0, "r": 3.0, "label": "Longitudinal fissure" },
    { "term": "superior parietal lobule",  "cx": 54.0, "cy": 26.0, "r": 4.0, "label": "Superior parietal lobule" },
    { "term": "intraparietal sulcus",      "cx": 57.0, "cy": 28.0, "r": 3.0, "label": "Intraparietal sulcus" },
    { "term": "postcentral gyrus",         "cx": 53.0, "cy": 22.0, "r": 4.0, "label": "Postcentral gyrus" },
    { "term": "lateral occipital gyri",    "cx": 65.0, "cy": 35.0, "r": 4.0, "label": "Lateral occipital gyri" },
    { "term": "middle frontal gyrus",      "cx": 30.0, "cy": 28.0, "r": 4.0, "label": "Middle frontal gyrus" },
    { "term": "optic chiasm",              "cx": 44.0, "cy": 70.0, "r": 3.5, "label": "Optic chiasm" },
    { "term": "orbital gyri",              "cx": 38.0, "cy": 67.0, "r": 4.0, "label": "Orbital gyri" },
    { "term": "olfactory tract",           "cx": 36.0, "cy": 65.0, "r": 3.0, "label": "Olfactory tract" },
    { "term": "olfactory bulb",            "cx": 35.0, "cy": 63.0, "r": 3.0, "label": "Olfactory bulb" },
    { "term": "gyrus rectus",              "cx": 40.0, "cy": 67.0, "r": 3.0, "label": "Gyrus rectus" },
    { "term": "uncus",                     "cx": 40.0, "cy": 72.0, "r": 3.0, "label": "Uncus" },
    { "term": "parahippocampal gyrus",     "cx": 38.0, "cy": 74.0, "r": 4.0, "label": "Parahippocampal gyrus" },
    { "term": "rhinal sulcus",             "cx": 36.0, "cy": 71.0, "r": 3.0, "label": "Rhinal sulcus" },
    { "term": "mammillary body",           "cx": 45.0, "cy": 72.0, "r": 3.0, "label": "Mammillary body" },
    { "term": "cerebral peduncle",         "cx": 46.0, "cy": 74.0, "r": 4.0, "label": "Cerebral peduncle" },
    { "term": "pons",                      "cx": 48.0, "cy": 77.0, "r": 5.0, "label": "Pons" },
    { "term": "medulla oblongata",         "cx": 48.0, "cy": 85.0, "r": 4.0, "label": "Medulla oblongata" },
    { "term": "inferior olive",            "cx": 46.0, "cy": 84.0, "r": 3.0, "label": "Inferior olive" },
    { "term": "medullary pyramid",         "cx": 48.0, "cy": 83.0, "r": 3.0, "label": "Medullary pyramid" },
    { "term": "cerebellar hemisphere",     "cx": 57.0, "cy": 80.0, "r": 6.0, "label": "Cerebellar hemisphere" },
    { "term": "inferior temporal gyrus",   "cx": 32.0, "cy": 63.0, "r": 4.0, "label": "Inferior temporal gyrus" },
    { "term": "occipitotemporal gyrus",    "cx": 32.0, "cy": 70.0, "r": 4.0, "label": "Occipitotemporal gyrus" },
    { "term": "collateral sulcus",         "cx": 37.0, "cy": 73.0, "r": 3.0, "label": "Collateral sulcus" },
    { "term": "trigeminal nerve",          "cx": 44.0, "cy": 80.0, "r": 3.0, "label": "Trigeminal nerve" },
    { "term": "facial nerve",              "cx": 42.0, "cy": 78.0, "r": 3.0, "label": "Facial nerve" }
  ]
}
```

- [ ] **Step 2.6 — Write `data/plates/cns-4.json`**

Same atlas views as cns-3. Regions shared; adjust coordinates if images differ.

```json
{
  "id": "cns-4",
  "filename": "ATLAS Human CNS 4.png",
  "displayName": "CNS Dorsal & Ventral II",
  "category": "cns",
  "regions": [
    { "term": "supramarginal gyrus",    "cx": 62.0, "cy": 22.0, "r": 4.0, "label": "Supramarginal gyrus" },
    { "term": "angular gyrus",          "cx": 63.0, "cy": 27.0, "r": 4.0, "label": "Angular gyrus" },
    { "term": "central sulcus",         "cx": 48.0, "cy": 17.0, "r": 3.0, "label": "Central sulcus" },
    { "term": "precentral gyrus",       "cx": 41.0, "cy": 18.0, "r": 4.0, "label": "Precentral gyrus" },
    { "term": "superior frontal gyrus", "cx": 32.0, "cy": 23.0, "r": 4.0, "label": "Superior frontal gyrus" },
    { "term": "postcentral gyrus",      "cx": 53.0, "cy": 22.0, "r": 4.0, "label": "Postcentral gyrus" },
    { "term": "optic chiasm",           "cx": 44.0, "cy": 70.0, "r": 3.5, "label": "Optic chiasm" },
    { "term": "pons",                   "cx": 48.0, "cy": 77.0, "r": 5.0, "label": "Pons" },
    { "term": "medulla oblongata",      "cx": 48.0, "cy": 85.0, "r": 4.0, "label": "Medulla oblongata" },
    { "term": "cerebellar hemisphere",  "cx": 57.0, "cy": 80.0, "r": 6.0, "label": "Cerebellar hemisphere" },
    { "term": "cerebral peduncle",      "cx": 46.0, "cy": 74.0, "r": 4.0, "label": "Cerebral peduncle" }
  ]
}
```

- [ ] **Step 2.7 — Write `data/plates/neural-map-1.json`**

Image: `ATLAS Brain Nueral Map 1.png` — DTI tractography, axial view (A, top half) and sagittal view (B, bottom half).

```json
{
  "id": "neural-map-1",
  "filename": "ATLAS Brain Nueral Map 1.png",
  "displayName": "White Matter Tracts I",
  "category": "tractography",
  "regions": [
    { "term": "corpus callosum",                     "cx": 50.0, "cy": 22.0, "r": 4.0, "label": "Corpus callosum, body" },
    { "term": "cingulum bundle",                     "cx": 43.0, "cy": 22.0, "r": 4.0, "label": "Cingulum bundle" },
    { "term": "corona radiata",                      "cx": 52.0, "cy": 18.0, "r": 4.0, "label": "Corona radiata, central" },
    { "term": "superior longitudinal fasciculus",    "cx": 60.0, "cy": 23.0, "r": 4.0, "label": "Superior longitudinal fasciculus" },
    { "term": "occipital association fibers",        "cx": 60.0, "cy": 33.0, "r": 4.0, "label": "Occipital association fibers" },
    { "term": "internal capsule",                    "cx": 46.0, "cy": 63.0, "r": 4.0, "label": "Internal capsule, posterior limb" },
    { "term": "anterior commissure",                 "cx": 43.0, "cy": 70.0, "r": 3.0, "label": "Anterior commissure" },
    { "term": "fornix",                              "cx": 40.0, "cy": 71.0, "r": 3.5, "label": "Fornix, column" },
    { "term": "uncinate fasciculus",                 "cx": 35.0, "cy": 71.0, "r": 4.0, "label": "Uncinate fasciculus" },
    { "term": "middle cerebellar peduncle",          "cx": 48.0, "cy": 81.0, "r": 4.0, "label": "Middle cerebellar peduncle" },
    { "term": "cerebral peduncle",                   "cx": 46.0, "cy": 76.0, "r": 4.0, "label": "Cerebral peduncle" },
    { "term": "inferior cerebellar peduncle",        "cx": 52.0, "cy": 85.0, "r": 4.0, "label": "Inferior cerebellar peduncle" },
    { "term": "medullary pyramid",                   "cx": 50.0, "cy": 88.0, "r": 3.0, "label": "Medullary pyramid" }
  ]
}
```

- [ ] **Step 2.8 — Write `data/plates/neural-map-2.json`**

Same DTI views as neural-map-1. Adjust coordinates if images differ after testing.

```json
{
  "id": "neural-map-2",
  "filename": "ATLAS Brain Nueral Map 2.png",
  "displayName": "White Matter Tracts II",
  "category": "tractography",
  "regions": [
    { "term": "corpus callosum",                  "cx": 50.0, "cy": 22.0, "r": 4.0, "label": "Corpus callosum, body" },
    { "term": "cingulum bundle",                  "cx": 43.0, "cy": 22.0, "r": 4.0, "label": "Cingulum bundle" },
    { "term": "corona radiata",                   "cx": 52.0, "cy": 18.0, "r": 4.0, "label": "Corona radiata, central" },
    { "term": "superior longitudinal fasciculus", "cx": 60.0, "cy": 23.0, "r": 4.0, "label": "Superior longitudinal fasciculus" },
    { "term": "internal capsule",                 "cx": 46.0, "cy": 63.0, "r": 4.0, "label": "Internal capsule, posterior limb" },
    { "term": "uncinate fasciculus",              "cx": 35.0, "cy": 71.0, "r": 4.0, "label": "Uncinate fasciculus" },
    { "term": "middle cerebellar peduncle",       "cx": 48.0, "cy": 81.0, "r": 4.0, "label": "Middle cerebellar peduncle" },
    { "term": "inferior cerebellar peduncle",     "cx": 52.0, "cy": 85.0, "r": 4.0, "label": "Inferior cerebellar peduncle" }
  ]
}
```

- [ ] **Step 2.9 — Write `data/plates/neural-map-3.json`**

Image: `ATLAS Brain Nueral Map 3.png` — DTI sagittal with left-side labels (C, top half) and 3D cutting planes diagram (D, bottom half).

```json
{
  "id": "neural-map-3",
  "filename": "ATLAS Brain Nueral Map 3.png",
  "displayName": "White Matter Tracts III",
  "category": "tractography",
  "regions": [
    { "term": "corona radiata",                   "cx": 47.0, "cy": 21.0, "r": 4.0, "label": "Corona radiata, central" },
    { "term": "internal capsule",                 "cx": 47.0, "cy": 26.0, "r": 4.0, "label": "Internal capsule" },
    { "term": "superior longitudinal fasciculus", "cx": 55.0, "cy": 22.0, "r": 4.0, "label": "Superior longitudinal fasciculus" },
    { "term": "inferior longitudinal fasciculus", "cx": 56.0, "cy": 30.0, "r": 4.0, "label": "Inferior longitudinal fasciculus" },
    { "term": "uncinate fasciculus",              "cx": 36.0, "cy": 27.0, "r": 4.0, "label": "Uncinate fasciculus" },
    { "term": "middle cerebellar peduncle",       "cx": 46.0, "cy": 38.0, "r": 4.0, "label": "Middle cerebellar peduncle" },
    { "term": "medullary pyramid",                "cx": 47.0, "cy": 41.0, "r": 3.0, "label": "Medullary pyramid" },
    { "term": "inferior cerebellar peduncle",     "cx": 49.0, "cy": 40.0, "r": 3.0, "label": "Inferior cerebellar peduncle" },
    { "term": "coronal plane",                    "cx": 42.0, "cy": 70.0, "r": 5.0, "label": "Coronal (frontal) plane" },
    { "term": "sagittal plane",                   "cx": 55.0, "cy": 62.0, "r": 5.0, "label": "Sagittal plane" },
    { "term": "horizontal plane",                 "cx": 60.0, "cy": 78.0, "r": 5.0, "label": "Horizontal (axial) plane" }
  ]
}
```

- [ ] **Step 2.10 — Write `data/plates/brain-3d-quarters.json`**

Image: `ATLAS Brain 3d quarters.png` — same DTI sagittal (C) and 3D planes (D) content as neural-map-3.

```json
{
  "id": "brain-3d-quarters",
  "filename": "ATLAS Brain 3d quarters.png",
  "displayName": "Brain 3D Planes",
  "category": "orientation",
  "regions": [
    { "term": "corona radiata",          "cx": 47.0, "cy": 21.0, "r": 4.0, "label": "Corona radiata, central" },
    { "term": "internal capsule",        "cx": 47.0, "cy": 26.0, "r": 4.0, "label": "Internal capsule" },
    { "term": "coronal plane",           "cx": 42.0, "cy": 70.0, "r": 5.0, "label": "Coronal (frontal) plane" },
    { "term": "sagittal plane",          "cx": 55.0, "cy": 62.0, "r": 5.0, "label": "Sagittal plane" },
    { "term": "horizontal plane",        "cx": 60.0, "cy": 78.0, "r": 5.0, "label": "Horizontal (axial) plane" },
    { "term": "middle cerebellar peduncle", "cx": 46.0, "cy": 38.0, "r": 4.0, "label": "Middle cerebellar peduncle" }
  ]
}
```

- [ ] **Step 2.11 — Validate JSON files parse correctly**

```bash
cd /home/oldha/projects/neuroDb/tools/neuro-atlas
python3 -c "
import json, pathlib
for f in pathlib.Path('data').rglob('*.json'):
    try:
        json.load(open(f))
        print(f'OK  {f}')
    except Exception as e:
        print(f'ERR {f}: {e}')
"
```

Expected: all files print `OK`.

- [ ] **Step 2.12 — Commit**

```bash
cd /home/oldha/projects/neuroDb
git add tools/neuro-atlas/data/
git commit -m "feat(neuro-atlas): add manifest and all 9 plate data files with region coordinates"
```

---

## Task 3: Boot Sequence, Search Index, Sidebar

**Files:**
- Modify: `tools/neuro-atlas/atlas.js` (replace stub with full implementation in stages, starting here)

- [ ] **Step 3.1 — Replace `atlas.js` with boot + search index + sidebar**

```javascript
// ─── State ────────────────────────────────────────────────────────────────────
const state = {
  plates: [],          // [{id, filename, displayName, category, regions}]
  activePlateId: null,
  searchTerm: '',
  activeMatch: null,   // {plateId, region} currently highlighted
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
// Map<termLower, [{plateId, region}]> — built once on boot
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
    document.getElementById('viewer-container').innerHTML =
      `<p class="error-state">Could not load atlas data: ${err.message}</p>`;
  }
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
function renderSidebar() {
  const list = document.getElementById('plate-list');
  list.innerHTML = '';
  for (const plate of state.plates) {
    const li = document.createElement('li');
    li.dataset.plateId = plate.id;
    li.innerHTML = `<span class="match-dot"></span><span class="plate-name">${plate.displayName}</span>`;
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
```

- [ ] **Step 3.2 — Verify sidebar renders**

With server running, reload http://localhost:8080. Expected: sidebar shows all 9 plate names. Console shows no errors. First plate name should appear highlighted (active state via stub).

- [ ] **Step 3.3 — Commit**

```bash
cd /home/oldha/projects/neuroDb
git add tools/neuro-atlas/atlas.js
git commit -m "feat(neuro-atlas): boot sequence, search index, sidebar rendering"
```

---

## Task 4: Main Viewer — Image Display and Plate Switching

**Files:**
- Modify: `tools/neuro-atlas/atlas.js` (replace `setActivePlate` stub)

- [ ] **Step 4.1 — Replace `setActivePlate` stub with full implementation**

Find the line `function setActivePlate(plateId) { state.activePlateId = plateId; updateSidebarActive(); }` and replace it with:

```javascript
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
```

Also add these two functions right after (before the stubs section):

```javascript
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
```

- [ ] **Step 4.2 — Verify image loads**

Reload http://localhost:8080. Expected: first plate image ("Human Brain Lobes") renders centered in the main viewer. Clicking other plates in the sidebar switches the image.

- [ ] **Step 4.3 — Commit**

```bash
cd /home/oldha/projects/neuroDb
git add tools/neuro-atlas/atlas.js
git commit -m "feat(neuro-atlas): plate switching and image display"
```

---

## Task 5: Zoom and Pan

**Files:**
- Modify: `tools/neuro-atlas/atlas.js` (replace `initPan` and `initZoomButtons` stubs)

- [ ] **Step 5.1 — Replace `initPan` stub**

Find `function initPan() {}` and replace with:

```javascript
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
```

- [ ] **Step 5.2 — Replace `initZoomButtons` stub**

Find `function initZoomButtons() {}` and replace with:

```javascript
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
```

- [ ] **Step 5.3 — Verify zoom and pan**

Reload. Expected:
- Mouse wheel over the image zooms centered on cursor
- Click + drag pans
- `[−]` / `[+]` step zoom centered on viewer
- `[⟳]` resets to fit-to-container

- [ ] **Step 5.4 — Commit**

```bash
cd /home/oldha/projects/neuroDb
git add tools/neuro-atlas/atlas.js
git commit -m "feat(neuro-atlas): zoom (wheel + buttons) and pan (drag)"
```

---

## Task 6: SVG Highlight Overlay

**Files:**
- Modify: `tools/neuro-atlas/atlas.js` (replace `clearHighlight` and `showHighlightWithZoom` stubs)

- [ ] **Step 6.1 — Replace `clearHighlight` stub**

Find `function clearHighlight() {}` and replace with:

```javascript
function clearHighlight() {
  document.getElementById('highlight-overlay').innerHTML = '';
  state.activeMatch = null;
}
```

- [ ] **Step 6.2 — Add `showHighlight` and replace `showHighlightWithZoom` stub**

Add `showHighlight` right after `clearHighlight`, then replace `function showHighlightWithZoom(plateId, region) {}`:

```javascript
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
    // zoom to frame the region
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
```

- [ ] **Step 6.3 — Test highlight manually**

In the browser console, run:

```javascript
const m = searchIndex.get('frontal lobe');
if (m) showHighlightWithZoom(m[0].plateId, m[0].region);
```

Expected: "Human Brain Lobes" plate activates (if not already), zooms to the frontal lobe area, gold pulsing circle appears with label "Frontal lobe".

- [ ] **Step 6.4 — Commit**

```bash
cd /home/oldha/projects/neuroDb
git add tools/neuro-atlas/atlas.js
git commit -m "feat(neuro-atlas): SVG highlight overlay with zoom-to-region"
```

---

## Task 7: Search Input, Autocomplete, Results Panel

**Files:**
- Modify: `tools/neuro-atlas/atlas.js` (replace `initSearch` stub; add search helpers and results panel functions)

- [ ] **Step 7.1 — Add search helpers and results panel functions** (insert before `initSearch` stub)

```javascript
// ─── Search helpers ───────────────────────────────────────────────────────────
function getAutocompleteSuggestions(query) {
  if (!query) return [];
  const q = query.toLowerCase();
  const scored = [];
  for (const [term] of searchIndex) {
    const pos = term.indexOf(q);
    if (pos !== -1) scored.push({ term, pos });
  }
  scored.sort((a, b) => a.pos - b.pos || a.term.localeCompare(b.term));
  return scored.slice(0, 10).map(s => s.term);
}

function selectTerm(term) {
  state.searchTerm = term.toLowerCase();
  updateSidebarMatchDots();
  const matches = searchIndex.get(state.searchTerm) || [];
  if (!matches.length) {
    clearHighlight();
    renderNoMatch(term);
    return;
  }
  showHighlightWithZoom(matches[0].plateId, matches[0].region);
  renderResults(term, matches);
}

// ─── Results panel ────────────────────────────────────────────────────────────
function clearResults() {
  document.getElementById('results-content').innerHTML =
    '<p class="empty-state">Search a term to highlight regions</p>';
}

function renderNoMatch(term) {
  document.getElementById('results-content').innerHTML =
    `<p class="no-match">No regions mapped for "${term}"</p>`;
}

function renderResults(term, matches) {
  const plateNames = Object.fromEntries(state.plates.map(p => [p.id, p.displayName]));
  const panel = document.getElementById('results-content');
  panel.innerHTML = `
    <div class="result-term">${term}</div>
    <div class="result-label">APPEARS IN</div>
    <ul class="result-plates">
      ${matches.map(m => `
        <li data-plate-id="${m.plateId}"
            class="${m.plateId === state.activePlateId ? 'current' : ''}">
          ${plateNames[m.plateId] || m.plateId}
        </li>`).join('')}
    </ul>
  `;
  panel.querySelectorAll('.result-plates li').forEach(li => {
    li.addEventListener('click', () => {
      const match = matches.find(m => m.plateId === li.dataset.plateId);
      if (match) {
        showHighlightWithZoom(match.plateId, match.region);
        // update current highlight in results list
        panel.querySelectorAll('.result-plates li')
          .forEach(el => el.classList.toggle('current', el === li));
      }
    });
  });
}
```

- [ ] **Step 7.2 — Replace `initSearch` stub**

Find `function initSearch() {}` and replace with:

```javascript
function initSearch() {
  const input = document.getElementById('search-input');
  const dropdown = document.getElementById('autocomplete-dropdown');
  let activeIdx = -1;

  input.addEventListener('input', () => {
    const q = input.value.trim();
    activeIdx = -1;
    if (!q) {
      dropdown.classList.add('hidden');
      state.searchTerm = '';
      clearHighlight();
      clearResults();
      updateSidebarMatchDots();
      return;
    }
    const suggestions = getAutocompleteSuggestions(q);
    if (!suggestions.length) { dropdown.classList.add('hidden'); return; }
    dropdown.innerHTML = suggestions
      .map(t => `<div class="autocomplete-item" data-term="${t}">${t}</div>`)
      .join('');
    dropdown.querySelectorAll('.autocomplete-item').forEach(el => {
      el.addEventListener('mousedown', e => {
        e.preventDefault();
        input.value = el.dataset.term;
        dropdown.classList.add('hidden');
        selectTerm(el.dataset.term);
      });
    });
    dropdown.classList.remove('hidden');
  });

  input.addEventListener('keydown', e => {
    const items = dropdown.querySelectorAll('.autocomplete-item');
    if (e.key === 'ArrowDown') {
      activeIdx = Math.min(activeIdx + 1, items.length - 1);
      items.forEach((el, i) => el.classList.toggle('active', i === activeIdx));
      e.preventDefault();
    } else if (e.key === 'ArrowUp') {
      activeIdx = Math.max(activeIdx - 1, -1);
      items.forEach((el, i) => el.classList.toggle('active', i === activeIdx));
      e.preventDefault();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0 && items[activeIdx]) {
        input.value = items[activeIdx].dataset.term;
        selectTerm(items[activeIdx].dataset.term);
      } else if (input.value.trim()) {
        selectTerm(input.value.trim());
      }
      dropdown.classList.add('hidden');
    } else if (e.key === 'Escape') {
      dropdown.classList.add('hidden');
      activeIdx = -1;
    }
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('.search-container')) dropdown.classList.add('hidden');
  });
}
```

- [ ] **Step 7.3 — Verify full search flow**

Reload. Type "frontal" in the search box. Expected:
1. Autocomplete dropdown shows suggestions including "frontal lobe"
2. Select "frontal lobe" — Brain Lobes plate activates, image zooms to frontal area, gold circle pulses with label
3. Results panel shows "frontal lobe" heading and lists plates containing it
4. Clicking a plate in results panel switches to that plate and shows the highlight
5. Sidebar shows gold dots next to plates that contain "frontal lobe"

- [ ] **Step 7.4 — Test keyboard navigation**

Type "cor" → press ArrowDown twice → press Enter. Expected: second autocomplete suggestion is selected and triggers the full search flow.

- [ ] **Step 7.5 — Test no-match case**

Type "zzz" + Enter. Expected: results panel shows `No regions mapped for "zzz"`, no highlight drawn.

- [ ] **Step 7.6 — Commit**

```bash
cd /home/oldha/projects/neuroDb
git add tools/neuro-atlas/atlas.js
git commit -m "feat(neuro-atlas): search, autocomplete, and results panel"
```

---

## Task 8: Final Verification and Coordinate Tuning

**Files:**
- Modify: any `data/plates/*.json` — fine-tune coordinates as needed

- [ ] **Step 8.1 — Run the full manual test checklist**

With server running at http://localhost:8080:

| Test | Expected |
|------|----------|
| Page load | All 9 plates in sidebar, first plate image visible, no console errors |
| Search "frontal lobe" | Brain Lobes + cns-1/cns-2 match; brain-lobes activates; gold circle appears near front of brain |
| Search "corpus callosum" | cns-1/neural-map-1/etc. match; highlight on correct region |
| Search "pons" | Multiple plates match; highlight points to brainstem |
| Click another plate in results panel | Switches plate, shows highlight on that plate's region |
| Click sidebar plate | Switches image; highlight from current search appears if that plate has a match |
| Mouse wheel zoom | Zooms centered on cursor; highlight stays locked to brain region |
| Drag pan | Image pans; highlight moves with image |
| Zoom reset | Image fits container |
| Search then clear | Clearing input removes highlight, removes gold dots, empties results |
| Search "xyz" | Shows "No regions mapped for 'xyz'" |

- [ ] **Step 8.2 — Tune any coordinates that are visibly off**

For each region where the highlight circle is noticeably away from the labeled structure:

1. Zoom in on that structure in the viewer
2. Note where the circle is vs. where it should be
3. Estimate the corrected `cx`/`cy` percentages
4. Edit the relevant `data/plates/<id>.json`
5. Reload (no server restart needed — JSON is re-fetched on page load)

- [ ] **Step 8.3 — Add `.superpowers/` to `.gitignore` if not already present**

```bash
cd /home/oldha/projects/neuroDb
grep -q '\.superpowers' .gitignore || echo '.superpowers/' >> .gitignore
```

- [ ] **Step 8.4 — Final commit**

```bash
cd /home/oldha/projects/neuroDb
git add tools/neuro-atlas/ .gitignore
git commit -m "feat(neuro-atlas): complete — atlas viewer with search, highlight, zoom/pan"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - ✅ Single-page HTML/CSS/JS, no build tools
  - ✅ All 9 plates in `data/plates/`, manifest-driven
  - ✅ Three-column layout (sidebar, viewer, results)
  - ✅ Zoom: wheel + buttons + reset
  - ✅ Pan: click+drag
  - ✅ SVG overlay inside transformed container — no recalculation on zoom
  - ✅ Search with autocomplete (up to 10 suggestions, prefix-ranked)
  - ✅ On select: switch plate, zoom to 2.5×, draw highlight, populate results
  - ✅ Results panel: term heading + clickable plate list
  - ✅ Sidebar gold dots for plates with match
  - ✅ Error handling: missing plate JSON skipped silently, missing image alt text, manifest failure shows error
  - ✅ Adding plates: manifest + one JSON file, no code change (README documents this)
  - ✅ Images referenced via relative path, not copied

- [x] **No placeholders** — all code is complete and executable

- [x] **Type consistency:**
  - `showHighlight(region)` — takes a `region` object, not `(plateId, region)`
  - `showHighlightWithZoom(plateId, region)` — takes both, handles plate switching
  - `state.activeMatch` stores `{plateId, region}`
  - `searchIndex` is `Map<string, [{plateId, region}]>` — consistent throughout
  - `updateHighlightOverlaySize()` and `resetZoomPan()` added in Task 4 before `applyTransform()` which they call — correct order
