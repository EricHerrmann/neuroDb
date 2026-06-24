# Manual Test Plan - Knowledge Library Remove References

## Scope

Verify that Knowledge Library removal honors user intent. Removing an unreferenced
paper deletes it. Removing a referenced paper explains why deletion is blocked and
offers explicit choices to delete dependent references or move them to another paper.
Legacy soft-removed papers can be restored to pending review or permanently
deleted from the Removed filter.

## Prerequisites

1. Run `uv run pytest tests/ -q`. Pass: no new failures beyond those already
   tracked in `docs/testLog.md`.
2. Start the backend:
   `uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`
3. Start the frontend:
   `cd frontend && npm run dev`
4. Open the Vite URL and navigate to Knowledge Library.

## T1 - Unreferenced Remove Deletes The Paper

1. Queue or locate a pending Knowledge Library paper with no claims, notes,
   evidence links, dataset links, grouping links, or plan steps. Full-text chunks
   or staged full-text review may exist; these are paper-owned artifacts, not
   external references.
2. Click Remove.
3. Refresh the Knowledge Library.
4. Attempt to queue the same DOI/title again from Tutor.

Pass: the item disappears because it was deleted, and re-queue creates a normal
queued source rather than reporting `already_exists`.

## T2 - Referenced Remove Explains The Block

1. Locate a paper that is referenced by at least one external dependent record,
   such as a claim, evidence link, study note, dataset-paper link, grouping link,
   or plan step.
2. Click Remove.

Pass: the paper is not silently hidden. The UI shows a clear rationale that the
paper is referenced elsewhere, lists reference counts by type, and presents
explicit actions: delete references and remove, or replace references with another
paper ID.

## T3 - Delete References And Remove

1. From the blocker message in T2, choose Delete references and remove.
2. Confirm the action.
3. Refresh the Knowledge Library.
4. Query or inspect the dependent surfaces that previously referenced the paper.

Pass: the paper is gone, dependent references are removed or detached according to
their type, Chroma summary/chunks are removed when present, and no stale DOI/title
dedupe collision remains.

## T4 - Replace References And Remove

1. Create or locate a correct replacement paper in the Knowledge Library.
2. On the blocked paper, enter the replacement paper ID and choose Replace
   references and remove.
3. Refresh relevant dependent surfaces.

Pass: paper-level references now point to the replacement paper, artifacts that
belonged only to the old paper are removed, and the stale paper is deleted.

## T5 - Restore Legacy Removed Paper

1. Set the Knowledge Library status filter to Removed.
2. Locate a legacy soft-removed paper.
3. Confirm that both Restore and Delete actions are visible.
4. Click Restore.
5. Switch the status filter to Pending.

Pass: the paper is visible as a pending source again and can be reviewed,
approved, rejected, or removed through the normal workflow.

## Results

| Case | Status | Notes |
|---|---|---|
| T1 - Unreferenced remove deletes | Pending | |
| T2 - Referenced remove explains block | Pending | |
| T3 - Delete references and remove | Pending | |
| T4 - Replace references and remove | Pending | |
| T5 - Restore legacy removed paper | Pending | |
