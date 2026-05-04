# NeuroDb P6 — Learning Agent Features

**Date:** 2026-05-04
**Author:** Eric Herrmann
**Status:** Scoped — not yet designed or implemented

---

## Context

P5 established the discovery mode, suggestion queue, and chapter-grounded agent workflow. Three capability gaps surfaced during P5 manual testing that are significant enough to warrant a dedicated phase before advancing to hypothesis testing (DB Epochs 7–8).

---

## Features

### F1 — Embedding Deduplication (Hash-in-DuckDB)

**Problem:** Every ingest run re-embeds all datasets for a source regardless of whether their content has changed. SPECTER2 on CPU is slow; re-embedding on every run is the primary cause of the multi-minute embedding wall time seen in P5 testing.

**What is needed:** Track a content hash of the embedding input text (`title + modality + description`) per dataset in DuckDB. On each embed pass, compute the hash for each candidate dataset and skip it if a stored hash matches. Only embed when the content is new or has changed since the last embed run.

**Scope boundary:** This is a data-pipeline change, not an agent change. The agent and vector store interfaces are unchanged.

---

### F2 — Agent Response Streaming

**Problem:** The agent can take 10–30 seconds to complete a response, especially in discovery mode where multiple tool-use turns occur before the final answer. The UI shows only a spinner with no indication of what the agent is doing, which reads as a hang.

**What is needed:** Stream agent tokens to the UI as they arrive. Tool-use turns (searches, DB queries) should surface as visible activity — the user should see that the agent is working and what it is doing — rather than silence until the full response is ready.

**Scope boundary:** This touches the agent's `chat()` method and the Streamlit rendering loop. Session history management must be confirmed compatible with streaming before design begins.

---

### F3 — UI Redesign (Agent as Primary Surface)

**Problem:** The current UI treats the agent chat panel as one tab among many. In practice the agent has become the primary way to interact with the database — users drive queries, tagging, discovery, and session management through the chat. The tab-based layout makes the agent feel secondary and forces navigation away from it to see results.

**What is needed:** Redesign the layout so the agent chat occupies the primary surface area and supporting views (dataset browser, study log, suggestions queue) are accessible without leaving the agent context — either as collapsible panels, a sidebar, or inline agent-rendered views. The design must accommodate both learning mode and discovery mode workflows.

**Scope boundary:** This is a Streamlit layout and component restructuring. No changes to agent logic, DB schema, or tool definitions. Agent behaviour and session management are unchanged.

---

## Dependencies and Ordering

F1 has no dependencies on F2 or F3. It can be designed and implemented independently.

F2 depends on F1 being complete (streaming an embed-heavy agent is only viable once embedding is fast). F2 also requires a confirmed streaming-compatible history management approach before design begins.

F3 depends on F2 being complete or in parallel. Streaming output changes how the UI renders responses and must be accounted for in the layout redesign.

Suggested order: F1 → F2 → F3.

---

## Out of Scope for P6

- Changes to DB schema outside the embedding state table (F1)
- New agent tools or modes
- Multi-user or remote deployment
- DB Epoch 7 (entity resolution) — remains decision-pending
