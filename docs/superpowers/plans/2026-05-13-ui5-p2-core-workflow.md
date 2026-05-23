# UI-5 P2 Core Workflow Implementation Plan

**Date:** 2026-05-13
**Status:** Implementation complete; manual verification pending
**Design source:** `docs/superpowers/specs/2026-05-13-ui5-p2-core-workflow-design.md`
**Manual plan:** `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_ui5_common_parity.md`

---

## Goal

Implement UI-5 P2 core workflow parity so the React workbench is usable for
day-to-day research workflows before UI-5 P3 polish or UI-4 Streamlit retirement.

---

## Tasks

| Task | Area | Work | Status |
|---|---|---|---|
| P2-1 | Planning | Create implementation and manual test plans | Complete |
| P2-2 | Study Log | Add delete route, vector deindexing, filters, and row remove action | Complete |
| P2-3 | Datasets | Add modality filter and rich metadata response/rendering | Complete |
| P2-4 | Research | Add multi-status filters, hypothesis detail fields, and review accept/dismiss routes/actions | Complete |
| P2-5 | Knowledge Library | Add duplicate check and approve summary/indexing task flow | Complete |
| P2-6 | Chat | Add readable message renderer, formatting prompt updates, and activity display support | Complete |
| P2-7 | Tests | Add backend/frontend coverage for each workflow | Complete |
| P2-8 | Verification | Run targeted tests, frontend build, and update status docs | Complete |

---

## Implementation Notes

- Keep P2 changes vertical by workflow and avoid broad layout refactors.
- Use existing `TaskRecord`, `useTask`, and TanStack invalidation patterns.
- Keep manual checks focused on browser/server/DB/Chroma behavior; branch and
  fault coverage belongs in automated tests.
- If a P2 item exposes a larger dependency gap, land the smallest useful slice
  and record the remaining limitation in this plan before moving on.

---

## Verification

Planned verification commands:

```bash
uv run pytest tests/unit/test_api_study_log.py tests/unit/test_api_datasets.py tests/unit/test_api_research.py tests/unit/test_api_knowledge_library.py tests/unit/test_api_chat.py -q
cd frontend && npm test
cd frontend && npm run build
```

Completed verification 2026-05-13:

- `uv run pytest tests/ -q` — 509 passed.
- `cd frontend && npm test` — 50 passed.
- `cd frontend && npm run build` — passed.
