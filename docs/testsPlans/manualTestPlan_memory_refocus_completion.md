# Manual Test Plan — Memory Refocus Completion

**Phase:** Learning and Research Memory Refocus — Completion Phase
**Status:** Pending execution
**Covers:** LOG-059 study log outer join, context budgets, retrieval telemetry CLI, dataset usefulness in agents

---

## Prerequisites

1. Run automated tests and verify no new failures:
   ```
   cd /home/oldha/projects/neuroDb && uv run pytest tests/ -q
   ```
   Pass criteria: no failures beyond those tracked in `docs/testLog.md`.

2. Start the API server:
   ```
   cd /home/oldha/projects/neuroDb && uv run uvicorn neurodb.api.app:app --reload
   ```

3. Start the frontend:
   ```
   cd /home/oldha/projects/neuroDb/frontend && npm run dev
   ```

---

## T1 — Study Log Shows Topic/Concept/Paper-Anchored Notes Under "All Sources"

**Setup:** Add a study note anchored to a topic (not a dataset) using the API.

```bash
curl -s -X POST http://localhost:8000/api/study-log \
  -H "Content-Type: application/json" \
  -d '{"topic_id": 1, "concept_tag": "LTP", "note_text": "test topic note"}'
```

**Steps:**
1. Open the Study Log panel in the frontend.
2. Verify the note appears in the list with source shown as "topic".
3. Confirm the "All Sources" filter (default) includes the note.

**Pass:** Note visible under "All sources". Source field shows "topic".

---

## T2 — Source Filter Excludes Non-Dataset Notes

**Setup:** Same topic-anchored note from T1 present; at least one dataset-anchored note also present.

**Steps:**
1. In the Study Log panel, select a specific dataset source (e.g., "openneuro") from the source filter.
2. Verify the topic-anchored note does NOT appear.
3. Verify dataset-anchored notes still appear.

**Pass:** Non-dataset notes hidden when a specific source is selected; dataset notes remain visible.

---

## T3 — `neurodb-telemetry` Context Usage Section Appears After Agent Turn with Context

**Setup:** Run a grounded-mode research agent turn with an active focus set.

**Steps:**
1. In the frontend, start a research agent chat with grounded mode and an active topic focus.
2. Send a message that triggers context retrieval (e.g., "What do we know about plasticity?").
3. Wait for the response to complete.
4. Run telemetry:
   ```
   cd /home/oldha/projects/neuroDb && uv run neurodb-telemetry
   ```

**Pass:** Output includes "Context Usage" section. At least one line shows counts in format `Np / Nn / Nc / Nd`.

---

## T4 — Grounded Agent Labels `sparse` Dataset as Insufficient

**Setup:** Have at least one dataset with `usefulness_state = "sparse"` linked to a topic.

**Steps:**
1. Start a research agent chat in grounded mode.
2. Set the active focus to the topic with the sparse dataset.
3. Ask: "What datasets support this topic?"
4. Observe the agent response.

**Pass:** Agent notes the sparse dataset as an evidence gap or insufficient, does not present it as research-ready supporting evidence.

---

## T5 — Context Budget Limits Visible in Telemetry Counts

**Setup:** `neurodb_models.toml` has `[context_budgets.grounded]` with `datasets = 5`.

**Steps:**
1. Run a grounded mode turn as in T3.
2. Check telemetry output:
   ```
   uv run neurodb-telemetry
   ```

**Pass:** Context Usage line shows dataset count ≤ 5 for grounded turns.
