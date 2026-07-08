# Manual Test Plan — Clickable Knowledge Library Citations

## Prerequisites
1. Run `uv run pytest tests/ -q`. Pass criteria: no new failures beyond those already tracked in `docs/testLog.md`.
2. Build/serve the frontend against the local API with an approved Knowledge Library paper that has an ID visible in the panel.

## Cases
- **CK1 — Clickable citation navigates + focuses.** In Tutor chat, ask a question that cites a Knowledge Library paper. Expected: the citation renders as a link; clicking it switches to the Knowledge Library panel, scrolls the referenced card into view, and briefly highlights it. No full-page reload.
- **CK2 — Visible ID.** Each Knowledge Library card shows its numeric ID (matching the ID the agent cites).
- **CK3 — Hidden-by-filter recovery.** Set the status filter to a value that hides the target paper, then click a citation for that paper. Expected: filter resets to All and the card is shown + highlighted.
- **CK4 — Link safety.** Confirm non-library links in chat still open in a new tab, and no citation link points outside `/knowledge-library`.
