# Manual Test Plan — TeX Ingest (Knowledge Library)

## Purpose
Verify that an operator can extract an arXiv TeX tarball into the Knowledge Library,
select the resulting project folder, acquire it, and get section-anchored searchable full
text — covering the real server/DB wiring and browser workflow that automated tests do not.

## Prerequisites
1. **Automated tests pass.** Run `uv run pytest tests/ -q`.
   Pass criteria: no new failures beyond those already tracked in `docs/testLog.md`.
2. Streamlit/API server running against the local DuckDB.
3. A real arXiv source tarball downloaded (e.g., from an `e-print` link).

## Steps
1. Extract the tarball into `knowledge_library_files/<paper_name>/` (so the folder holds
   `main.tex`, any `\input` children, and a `.bbl`).
2. In the Knowledge Library picker, confirm `<paper_name>` appears as a TeX project
   (kind = `tex_project`), distinct from loose PDF/HTML files.
3. Approve a target paper, then acquire it using the project folder as the source.
4. Wait for the background job to complete (status leaves `pending`).

## Expected Results
- The paper's full-text status becomes populated; `text_source` is `tex_pylatexenc`.
- Semantic search over the paper returns chunks anchored by section label (e.g., `Methods`,
  `Results`, `References`), not page numbers.
- Inline math appears as raw LaTeX in retrieved chunk text.
- Re-acquiring the same project does not duplicate chunks (chunk count stable).

## Pass/Fail
PASS when all Expected Results hold and no new automated-test failures were introduced.
