# NeuroDb — Issue Log

Running log of issues discovered during testing, reviews, and ad hoc exploration.
Add new entries at any time using `LOG:` in chat.

Use `Log ID` for cross-references across Open, Resolved, triage, sprint planning, and future implementation notes. `Issue ID` preserves the short human-readable label used when the issue was first logged.

---

## Open Issues Summary

| Log ID | Issue ID | Description | Priority |
|--------|----------|-------------|----------|
| LOG-001 | P6-selector | Textbook dropdown appears pre-selected without explicit user action — agent context state is ambiguous | LT-3 |
| LOG-006 | LT1-model-visibility | User cannot tell which agent/LLM/model is active; no model selection or persistent preference rules | Deferred post-LT-3 |
| LOG-013 | UI-shell-rearchitecture | Streamlit cannot support fixed-pane app-shell behavior; reassess UI stack after LT-3 | Deferred post-LT-3 |
| LOG-014 | semscholar-no-apikey | Semantic Scholar does not issue API keys to non-academic accounts; connector setup docs and architecture must reflect source-dependent key requirements | Next arch update |
| LOG-015 | agent-session-date | Agent writes incorrect session date in ChromaDB summary (uses training knowledge rather than actual date) | LT-3 |
| LOG-021 | agent-mode-not-persisted | Agent mode selection does not persist across Streamlit restarts | LT-3 |

---

## Open

| Log ID | Date | Issue ID | Description | Context |
|---|---|---|---|---|
| LOG-001 | 2026-05-04 | P6-selector | Textbook dropdown appears pre-selected without explicit user action — actual agent context is ambiguous | P6 manual test |
| LOG-006 | 2026-05-05 | LT1-model-visibility | User cannot tell which agent/LLM/model is active; later work should add model selection and persistent model/user-preference prompt rules | LT-1 manual/ad hoc review |
| LOG-013 | 2026-05-05 | UI-shell-rearchitecture | Pre-LT-2 fixed-pane layout failed in Streamlit even with a custom-component bridge; evaluate a UI tech-stack rearchitecture after LT-2/LT-3 once core learning capabilities mature to MVP | Pre-LT-2 manual test |
| LOG-014 | 2026-05-06 | semscholar-no-apikey | Semantic Scholar does not issue API keys to non-academic (gmail.com) accounts; unauthenticated rate limit appears sufficient for current use, but connector design and architecture docs must reflect that API keys are source-dependent and not universally required | Ad hoc discovery |
| LOG-015 | 2026-05-06 | agent-session-date | Agent logged the LTP vs. LTD study session with an incorrect date (January 27 instead of May 4, 2026); agent is not using the correct current date when writing session records | LT-2 manual testing T1 |
| LOG-021 | 2026-05-06 | agent-mode-not-persisted | Agent mode selection does not persist across sessions; user must re-select mode each time the app is restarted | LT-2 manual testing |

---

## Resolved

| Log ID | Date | Issue ID | Description | Resolution |
|---|---|---|---|---|
| LOG-002 | 2026-05-05 | LT1-scroll-sync | Right workspace pane remains at top while left agent conversation scrolls | Resolved in LT-2: workspace/chat layout redesigned; accepted as current behavior pending post-LT-3 UI shell work |
| LOG-003 | 2026-05-05 | LT1-mode-scroll | Mode controls require scrolling to top as conversation grows | Resolved in LT-2: mode radio always visible in sidebar; deeper layout work deferred to UI shell phase |
| LOG-004 | 2026-05-05 | LT1-pending-source-visibility | Pending source cards lacked clear title/source/topic and selectable links | Resolved in LT-2: Knowledge Library polish — T7 passed |
| LOG-005 | 2026-05-05 | LT1-knowledge-title-size | Knowledge Library source titles rendered too large | Resolved in LT-2: Knowledge Library polish — T7 passed |
| LOG-007 | 2026-05-05 | LT1-test6-criteria | T6 chat-session verification query had ambiguous pass/fail criteria | Resolved: LT-2 manual plan updated with explicit expected output and DuckDB read-only query |
| LOG-008 | 2026-05-04 | T6-lock | Import from Suggestions tab failed with DuckDB lock conflict (subprocess vs Streamlit connection) | Replaced subprocess ingest with in-process `run_ingest` call |
| LOG-009 | 2026-05-04 | T5-ctx | Agent lost multi-turn context — "yes" confirmation after dataset suggestion did not queue item | Fixed `agent.chat()` to mutate caller's message list; `chat.py` maintains `api_messages` in session state |
| LOG-010 | 2026-05-04 | H1-clear | Clear button triggered by Enter key (form default submit) | Moved Clear outside `st.form`; now requires explicit mouse click |
| LOG-011 | 2026-05-04 | ON-search | OpenNeuro connector sent invalid GraphQL `search` argument — HTTP 400 | Switched to `advancedSearch(query: DatasetSearchInput!)` |
| LOG-012 | 2026-05-05 | T4-clear | Chat history clears transiently after import action reported to agent; second query recovers without restart | Resolved during LT-1 manual testing; user approved tests 1-7 and marked issue resolved |
| LOG-016 | 2026-05-06 | prev-session-context-invisible | No visible indicator when a previous session is loaded as context | Fixed in LT-2: blue prior-context badge added to chat panel; ▸ prefix and "Active:" caption added to sidebar |
| LOG-017 | 2026-05-06 | knowledge-library-indent-error | Streamlit crashed on Knowledge Library tab with IndentationError at knowledge_library.py:111 in `_reject_source` | Fixed: removed extra indent on `row.reviewed_at` line |
| LOG-018 | 2026-05-06 | t3-prior-context-not-loaded | T3 fails: prior context not applied when session selected | Fixed in LT-2: draft ChatSession row written on first message; context fallback from inferred_topic added; T3 re-run passed |
| LOG-019 | 2026-05-06 | t4-previous-topics-not-loaded | T4 fails: Previous Topics sidebar did not populate; transcripts not visible | Fixed in LT-2: same root cause as LOG-018; T4 re-run passed |
| LOG-020 | 2026-05-06 | t5-pass | T5 passed | LT-2 signed off |
| LOG-022 | 2026-05-06 | t1-t2-t9-pass | T1, T2, T9 passed | LT-2 signed off |
| LOG-023 | 2026-05-06 | t4-arrow-indicator-works | ▸ prefix confirmed working on active session selection | LT-2 signed off |
| LOG-024 | 2026-05-06 | t3-t4-context-verified | Agent recalled prior session when asked | LT-2 signed off |
| LOG-025 | 2026-05-06 | t3-pass | T3 passed | LT-2 signed off |
| LOG-026 | 2026-05-06 | t4-pass | T4 passed | LT-2 signed off |
| LOG-027 | 2026-05-06 | prior-context-indicator-low-visibility | Prior context caption at top of chat window had low visibility | Fixed: replaced `st.caption` with styled `st.markdown` — navy background (#1e3a8a), white text, matching active tab style |
| LOG-028 | 2026-05-06 | t7-t8-t9-pass | T7, T8, T9 passed | LT-2 signed off |
