# Manual Test Plan — Groupings Phase 3b (UI)

## Prerequisites
- [ ] Run the automated suites:
  - Backend: `uv run pytest tests/ -q` — pass criterion: no new failures beyond `docs/testLog.md`.
  - Frontend: `cd frontend && npm test` — all suites pass.
- [ ] Start the backend: `uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`.
- [ ] Start the frontend: `cd frontend && npm run dev` (Vite proxies `/api` to port 8001).

## T1 — Topic filter is populated from the groupings endpoint
- [ ] Open the Research panel.
- [ ] Expected: the topic filter bar shows active topic groupings (network tab shows `GET /api/research/groupings?type=topic&status=active`, not a `/api/sql/execute` call).
- [ ] Click a topic → the question list filters; clicking a parent topic also returns child-tagged questions (rollup).

## T2 — Proposed ("new") suggestion chips
- [ ] Create a question that yields a proposed grouping (a general term not yet in the taxonomy).
- [ ] Expected: a pending chip shows a small "new" badge.
- [ ] Click ✓ → the chip becomes a confirmed badge; the grouping now appears in the topic filter (it was activated).
- [ ] Create another proposed suggestion and click ✕ → the chip disappears and the proposed grouping is not added to the filter.

## T3 — Hierarchy curation
- [ ] In the Topic hierarchy view, confirm seeded parents (e.g. `plasticity`) show their children nested.
- [ ] Use a grouping's parent dropdown to set its parent → the view re-nests after the change.
- [ ] Attempt an invalid re-parent (e.g. assign a parent that already has a parent, or a grouping that has children) → an inline error message appears and the hierarchy is unchanged.
