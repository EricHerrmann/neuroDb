# Manual Test Plan — Groupings Phase 4 (Consumer Migration)

**Status:** Pending manual verification
**Date created:** 2026-06-02
**Design spec:** `docs/superpowers/specs/2026-06-01-unified-groupings-taxonomy-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-06-02-groupings-phase4-consumer-migration.md`

---

## Prerequisites
- [ ] Run the automated backend suite: `uv run pytest tests/ -q`. Pass criterion: no new failures beyond those already tracked in `docs/testLog.md`.
- [ ] Run the automated frontend suite: `cd frontend && npm test`. Pass criterion: all frontend test files pass.
- [ ] Run the frontend production build: `cd frontend && npm run build`. Pass criterion: TypeScript and Vite build complete without errors.
- [ ] Start the backend: `uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`.
- [ ] Start the frontend: `cd frontend && npm run dev` (Vite proxies `/api` to port 8001).

## T1 — Tutor paper tagging writes grouping links
- [ ] Open the Tutor workflow and ask for a cited paper recommendation on a topic that is not already queued.
- [ ] Confirm the queued source appears in Knowledge Library with its title and topic context.
- [ ] In the Research panel, confirm the related active topic grouping appears in the topic filter or hierarchy.
- [ ] Pass: paper tagging is visible through the grouping-powered UI; no legacy topic-table-only behavior is required.

## T2 — Grouping bundles feed local context
- [ ] Create or select a topic grouping with a linked approved paper, study note, and dataset packet.
- [ ] Ask Tutor for local context for that topic in contextual mode.
- [ ] Pass: the answer or context summary reflects the grouping's linked papers, notes, and datasets.

## T3 — Knowledge Library preserves paper grouping links
- [ ] Queue or select a pending paper that has topic grouping links.
- [ ] Approve it in Knowledge Library.
- [ ] Refresh Research and confirm the linked topic grouping still appears for the paper/topic workflow.
- [ ] Pass: approval does not drop paper grouping links, including on DuckDB-backed runtime.

## T4 — Study Log resolves topic and concept anchors from groupings
- [ ] Create study notes anchored to a topic grouping and a concept grouping.
- [ ] Open Study Log and search for each note.
- [ ] Pass: both notes appear with the expected anchor labels; deleting a note removes it from the visible list without leaving stale grouping behavior.

## T5 — Question delete cleans grouping links (LOG-064)
- [ ] Create a question that receives pending topic/concept suggestions.
- [ ] Delete the question from the Research panel.
- [ ] Query or inspect the question list and grouping suggestions.
- [ ] Pass: the question is gone; no dangling question links remain; proposed groupings attached only to that question are removed.

## T6 — Topic hierarchy collapses independently (LOG-065)
- [ ] In Research, expand the Topic hierarchy with at least two top-level topics that have children.
- [ ] Collapse one top-level topic.
- [ ] Pass: only that topic's children hide; the other topic's children remain visible. Re-expanding restores only the collapsed branch.

## T7 — Question suggestions refresh after create (LOG-066)
- [ ] Create a new research question expected to receive topic/concept suggestions.
- [ ] Stay on the Research panel without manually refreshing the browser.
- [ ] Pass: suggestion chips appear after the create flow refreshes query state; a manual page reload is not required.
