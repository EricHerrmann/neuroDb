# NeuroDb — Issue Log

Running log of issues discovered during testing, reviews, and ad hoc exploration.
Add new entries at any time using `LOG:` in chat.

---

## Open

| Date | ID | Description | Context |
|------|----|-------------|---------|
| 2026-05-04 | P6-selector | Textbook dropdown appears pre-selected without explicit user action — actual agent context is ambiguous | P6 manual test |
| 2026-05-05 | LT1-scroll-sync | Right workspace pane remains at top while the left agent conversation grows and scrolls down; possible design direction is newest conversation at top with older conversation below | LT-1 manual/ad hoc review |
| 2026-05-05 | LT1-mode-scroll | As conversation history grows, user must scroll back to the top to change agent modes; reinforces need to revisit chat scroll/layout behavior | LT-1 manual/ad hoc review |
| 2026-05-05 | LT1-pending-source-visibility | In T4, pending source box does not make title, source, and topic content clear enough; source link should be selectable so user can verify source veracity | LT-1 manual/ad hoc review |
| 2026-05-05 | LT1-knowledge-title-size | Knowledge Library source titles render too large; reduce title font size | LT-1 manual/ad hoc review |
| 2026-05-05 | LT1-model-visibility | User cannot tell which agent/LLM/model is active; later work should add model selection and persistent model/user-preference prompt rules | LT-1 manual/ad hoc review |
| 2026-05-05 | LT1-test6-criteria | Test 6 chat-session verification query can return no visible value, making pass/fail unclear; manual plan needs more explicit command-line pass criteria | LT-1 manual test T6 |

---

## Resolved

| Date | ID | Description | Resolution |
|------|----|-------------|------------|
| 2026-05-04 | T6-lock | Import from Suggestions tab failed with DuckDB lock conflict (subprocess vs Streamlit connection) | Replaced subprocess ingest with in-process `run_ingest` call |
| 2026-05-04 | T5-ctx | Agent lost multi-turn context — "yes" confirmation after dataset suggestion did not queue item | Fixed `agent.chat()` to mutate caller's message list; `chat.py` maintains `api_messages` in session state |
| 2026-05-04 | H1-clear | Clear button triggered by Enter key (form default submit) | Moved Clear outside `st.form`; now requires explicit mouse click |
| 2026-05-04 | ON-search | OpenNeuro connector sent invalid GraphQL `search` argument — HTTP 400 | Switched to `advancedSearch(query: DatasetSearchInput!)` |
| 2026-05-05 | T4-clear | Chat history clears transiently after import action reported to agent; second query recovers without restart | Resolved during LT-1 manual testing; user approved tests 1-7 and marked issue resolved |
