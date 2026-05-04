# NeuroDb — Issue Log

Running log of issues discovered during testing, reviews, and ad hoc exploration.
Add new entries at any time using `LOG:` in chat.

---

## Open

| Date | ID | Description | Context |
|------|----|-------------|---------|
| 2026-05-04 | T4-clear | Chat history clears transiently after import action reported to agent; second query recovers without restart | P5 manual test |
| 2026-05-04 | P6-selector | Textbook dropdown appears pre-selected without explicit user action — actual agent context is ambiguous | P6 manual test |

---

## Resolved

| Date | ID | Description | Resolution |
|------|----|-------------|------------|
| 2026-05-04 | T6-lock | Import from Suggestions tab failed with DuckDB lock conflict (subprocess vs Streamlit connection) | Replaced subprocess ingest with in-process `run_ingest` call |
| 2026-05-04 | T5-ctx | Agent lost multi-turn context — "yes" confirmation after dataset suggestion did not queue item | Fixed `agent.chat()` to mutate caller's message list; `chat.py` maintains `api_messages` in session state |
| 2026-05-04 | H1-clear | Clear button triggered by Enter key (form default submit) | Moved Clear outside `st.form`; now requires explicit mouse click |
| 2026-05-04 | ON-search | OpenNeuro connector sent invalid GraphQL `search` argument — HTTP 400 | Switched to `advancedSearch(query: DatasetSearchInput!)` |
