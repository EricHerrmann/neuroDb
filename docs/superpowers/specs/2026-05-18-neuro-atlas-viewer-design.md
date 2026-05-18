# NeuroAtlas Viewer — Design Spec

**Date:** 2026-05-18
**Status:** Approved
**Location:** `neuroDb/tools/neuro-atlas/`

## Purpose

A standalone, offline-capable browser tool for neuroscience reference while learning. The user searches a neuroscience term and sees a pinpoint highlight on the relevant atlas plate. Designed to grow incrementally as new atlas images are acquired — adding a plate requires no code changes.

## Scope

- Single-page HTML/CSS/JS app, no build tools, no server-side code
- Covers the 9 existing atlas plates in `library/Neuroscience7thed/images/`
- Pinpoint region mapping for all labeled structures visible across those plates (~80–100 entries)
- Zoom, pan, search, highlight
- Out of scope: user annotations, persistence, backend, authentication

## File Structure

```
tools/neuro-atlas/
  index.html          — app shell and layout
  atlas.js            — all application logic
  styles.css          — layout, theming, animations
  data/
    manifest.json     — ordered list of plate IDs to load
    plates/
      brain-lobes.json
      neural-map-1.json
      neural-map-2.json
      neural-map-3.json
      cns-1.json
      cns-2.json
      cns-3.json
      cns-4.json
      brain-3d-quarters.json
  README.md           — how to run; how to add plates
```

Images are referenced as `../../library/Neuroscience7thed/images/<filename>` relative to `index.html`. No copying or symlinking required.

## Running

```bash
cd tools/neuro-atlas
python3 -m http.server 8080
# open http://localhost:8080
```

## Data Schema

### `manifest.json`

The only file that needs editing when a new plate is added.

```json
{
  "plates": ["brain-lobes", "neural-map-1", "neural-map-2", "neural-map-3",
             "cns-1", "cns-2", "cns-3", "cns-4", "brain-3d-quarters"]
}
```

### `data/plates/<id>.json`

One file per plate. Self-contained — owns its metadata and all region definitions.

```json
{
  "id": "brain-lobes",
  "filename": "ATLAS Human Brain Lobes.png",
  "displayName": "Human Brain Lobes",
  "category": "lobes",
  "regions": [
    {
      "term": "frontal lobe",
      "cx": 28.4,
      "cy": 35.1,
      "r": 11.0,
      "label": "Frontal lobe"
    }
  ]
}
```

**Field definitions:**
- `cx`, `cy` — center of the highlighted region as percentage of image natural width/height (0–100). Resolution-independent.
- `r` — highlight circle radius as percentage of image natural width.
- `term` — lowercase search key. Must match exactly what users will type. A region entry with `"term": "frontal lobe"` is found by searches for "frontal", "lobe", "frontal lobe".
- `label` — display string shown in the tooltip on hover.

A single term may appear in multiple plate files. The search index unions all matches across all plates.

## Application Boot Sequence

1. Fetch `data/manifest.json`
2. Fetch all plate JSON files listed in manifest in parallel (`Promise.all`)
3. Build search index: `Map<term, Array<{plateId, region}>>` — one pass over all loaded plates
4. Render sidebar plate list in manifest order
5. Display first plate as active, fit to viewer

## Layout

Three-column layout, full viewport height.

```
┌──────────────────────────────────────────────────────────┐
│  NeuroAtlas    🔍 [search input________________]         │
├─────────────┬────────────────────────────┬───────────────┤
│ PLATES      │                            │ RESULTS       │
│ (sidebar)   │   <active plate image>     │ (info panel)  │
│             │   <SVG highlight overlay>  │               │
│ scrollable  │   zoom/pan surface         │               │
│ list of     │                            │ shows matched │
│ all plates  │   [−] [+] [⟳] controls    │ term + other  │
│             │                            │ plates        │
└─────────────┴────────────────────────────┴───────────────┘
```

**Sidebar** (left, fixed width ~160px):
- Lists every plate from manifest by `displayName`
- Active plate is visually highlighted
- Plates containing the current search term show a gold indicator dot
- Clicking a plate switches the main viewer to that plate, preserving any active search highlight

**Main viewer** (center, flex-grows):
- Renders the active plate image
- SVG overlay element absolutely positioned over the image, same dimensions
- Zoom and pan via CSS `transform: scale() translate()` on an inner container
- Mouse wheel zooms centered on cursor; click+drag pans
- `[−]` / `[+]` buttons step zoom by 0.25×; `[⟳]` resets to fit-to-container
- Zoom range: 0.5× to 8×

**Results panel** (right, fixed width ~180px):
- Empty state: "Search a term to highlight regions"
- Active search: shows matched term as heading, then a list of all plates containing that term
- Each list item is clickable — switches to that plate and shows the highlight for that plate's region entry
- If no match: "No regions mapped for '[term]'"

## Search

- `<input>` in the header, live search on every keystroke (no debounce needed at this scale)
- Match algorithm: case-insensitive substring match against all region `term` keys in the search index
- Autocomplete dropdown: up to 10 suggestions, sorted by match position (prefix matches first)
- On selection:
  1. Switch active plate to the first plate in manifest order that contains a region for the selected term
  2. Animate zoom to frame the region: zoom to 2.5× centered on the region's `cx/cy`
  3. Draw and animate the SVG highlight
  4. Populate results panel

## Highlight Rendering

The image and a `<svg>` overlay are siblings inside the same transformed container, so CSS zoom/pan applies to both simultaneously — no highlight recalculation on pan or zoom.

The SVG uses a `viewBox` matching the image's natural pixel dimensions. On a match, a `<circle>` is placed at:

```
svgX = (cx / 100) * imageNaturalWidth
svgY = (cy / 100) * imageNaturalHeight
svgR = (r  / 100) * imageNaturalWidth
```

These are set once when a term is selected and remain correct at all zoom levels because the transform moves both image and SVG identically.

The circle uses a CSS `@keyframes` pulse animating `opacity` and `r` to create a glowing effect. `pointer-events: none` on the SVG so it never blocks pan/drag.

A `<text>` element inside the SVG shows the region `label` just above the circle.

## Adding a New Plate

Documented in `README.md`. Three steps, no code changes:

1. Place the image file in `library/Neuroscience7thed/images/`
2. Create `data/plates/<id>.json` with the plate's metadata and region definitions
3. Add `<id>` to the `plates` array in `data/manifest.json`

The app auto-loads all plates listed in manifest on next page load.

**Region coordinate workflow:** Open the image in any image viewer that shows pixel coordinates. Identify the center pixel of each labeled structure. Divide by the image's natural width/height to get `cx`/`cy` as percentages. Use a radius that visually encircles the label callout point.

## Color / Visual Style

- Dark background (`#0f172a`) matching the atlas plates' dark borders
- Gold highlight circle (`#fbbf24`) for visibility against both light and dark plate backgrounds
- Sidebar active state: left border accent in blue (`#3b82f6`)
- Term match indicator dot: gold (`#fbbf24`)
- Autocomplete dropdown: dark card with hover highlight

## Error Handling

- Missing plate JSON (404): log to console, skip that plate silently — remaining plates load normally
- Missing image (broken img): show placeholder with plate display name
- Empty manifest or fetch failure: show "Could not load atlas data" in main area

## Testing

No automated test suite for this tool. Manual verification:
- Load app, confirm all plates appear in sidebar
- Search "frontal lobe" → Brain Lobes plate activates, highlight appears, CNS plates listed in results panel
- Click a result plate → switches and shows highlight on that plate
- Zoom in/out via wheel and buttons → highlight stays locked to correct position
- Add a new plate file and manifest entry → plate appears without any other changes
