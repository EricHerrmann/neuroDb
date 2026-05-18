# NeuroAtlas Viewer

Standalone browser-based atlas viewer for neuroscience study.

## Running

```
cd tools/neuro-atlas
python3 -m http.server 8080
# open http://localhost:8080
```

## Adding a New Plate

Three steps, no code changes required:

1. Place the image in `library/Neuroscience7thed/images/`
2. Create `data/plates/<id>.json` with this structure:
   - id, filename, displayName, category, regions array
   - Each region: term (search key), cx (% of width), cy (% of height), r (radius as % of width), label
3. Add the id to `data/manifest.json`'s plates array

## Region Coordinates

`cx`, `cy` = center of the region as percentage of image width/height (0–100).
`r` = highlight circle radius as percentage of image width.

To find coordinates: open the image in any viewer that shows pixel coordinates. Find the center pixel of the labeled structure. Divide by image width/height.
