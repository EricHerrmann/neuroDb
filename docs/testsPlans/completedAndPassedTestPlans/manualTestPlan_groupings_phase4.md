# Manual Test Plan — Groupings Phase 4 (Consumer Migration)

**Status:** Complete — T1-T7 passed and signed off 2026-06-04
**Date created:** 2026-06-02
**Design spec:** `docs/superpowers/specs/2026-06-01-unified-groupings-taxonomy-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-06-02-groupings-phase4-consumer-migration.md`
**Result:** Complete and passed. T1-T7 signed off by user on 2026-06-04.

---

## Prerequisites
- [x] Run the automated backend suite: `uv run pytest tests/ -q`. Pass criterion: no new failures beyond those already tracked in `docs/testLog.md`.
- [x] Run the automated frontend suite: `cd frontend && npm test`. Pass criterion: all frontend test files pass.
- [x] Run the frontend production build: `cd frontend && npm run build`. Pass criterion: TypeScript and Vite build complete without errors.
- [x] Start the backend: `uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`.
- [x] Start the frontend: `cd frontend && npm run dev` (Vite proxies `/api` to port 8001).

## T1 — Tutor paper tagging writes grouping links
- [x] Open the Tutor workflow and ask for a cited paper recommendation on a topic that is not already queued.
- [x] Confirm the queued source appears in Knowledge Library with its title and topic context.
- [x] In the Research panel, confirm the related active topic grouping appears in the topic filter or hierarchy.
- [x] Pass: paper tagging is visible through the grouping-powered UI; no legacy topic-table-only behavior is required.

## T2 — Grouping bundles feed local context
- [x] Create or select a topic grouping with a linked approved paper, study note, and dataset packet.
- [x] Ask Tutor for local context for that topic in contextual mode.
- [x] Pass: the answer or context summary reflects the grouping's linked papers, notes, and datasets.

## T3 — Knowledge Library preserves paper grouping links
- [x] Queue or select a pending paper that has topic grouping links.
- [x] Approve it in Knowledge Library.
- [x] Refresh Research and confirm the linked topic grouping still appears for the paper/topic workflow.
- [x] Pass: approval does not drop paper grouping links, including on DuckDB-backed runtime.

## T4 — Study Log resolves topic and concept anchors from groupings
- [x] Create study notes anchored to a topic grouping and a concept grouping.
- [x] Open Study Log and search for each note.
- [x] Pass: both notes appear with the expected anchor labels; deleting a note removes it from the visible list without leaving stale grouping behavior.

## T5 — Question delete cleans grouping links (LOG-064)
- [x] Create a question that receives pending topic/concept suggestions.
- [x] Delete the question from the Research panel.
- [x] Query or inspect the question list and grouping suggestions.
- [x] Pass: the question is gone; no dangling question links remain; proposed groupings attached only to that question are removed.

## T6 — Topic hierarchy collapses independently (LOG-065)
- [x] In Research, expand the Topic hierarchy with at least two top-level topics that have children.
- [x] Collapse one top-level topic.
- [x] Pass: only that topic's children hide; the other topic's children remain visible. Re-expanding restores only the collapsed branch.

## T7 — Question suggestions refresh after create (LOG-066)
- [x] Create a new research question expected to receive topic/concept suggestions.
- [x] Stay on the Research panel without manually refreshing the browser.
- [x] Pass: suggestion chips appear after the create flow refreshes query state; a manual page reload is not required.
