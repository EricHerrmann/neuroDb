# NeuroDb — Issue Log

Running log of issues discovered during testing, reviews, and ad hoc exploration.
Add new entries at any time using `LOG:` in chat.

Use `Log ID` for cross-references across Open, Resolved, triage, sprint planning, and future implementation notes. `Issue ID` preserves the short human-readable label used when the issue was first logged.

---

## Open

| Log ID | Date | Issue ID | Description | Context |
|---|---|---|---|---|
| LOG-001 | 2026-05-04 | P6-selector | Textbook dropdown appears pre-selected without explicit user action — actual agent context is ambiguous | P6 manual test |
| LOG-002 | 2026-05-05 | LT1-scroll-sync | Right workspace pane remains at top while the left agent conversation grows and scrolls down; possible design direction is newest conversation at top with older conversation below | LT-1 manual/ad hoc review |
| LOG-003 | 2026-05-05 | LT1-mode-scroll | As conversation history grows, user must scroll back to the top to change agent modes; reinforces need to revisit chat scroll/layout behavior | LT-1 manual/ad hoc review |
| LOG-004 | 2026-05-05 | LT1-pending-source-visibility | In T4, pending source box does not make title, source, and topic content clear enough; source link should be selectable so user can verify source veracity | LT-1 manual/ad hoc review |
| LOG-005 | 2026-05-05 | LT1-knowledge-title-size | Knowledge Library source titles render too large; reduce title font size | LT-1 manual/ad hoc review |
| LOG-006 | 2026-05-05 | LT1-model-visibility | User cannot tell which agent/LLM/model is active; later work should add model selection and persistent model/user-preference prompt rules | LT-1 manual/ad hoc review |
| LOG-007 | 2026-05-05 | LT1-test6-criteria | Test 6 chat-session verification query can return no visible value, making pass/fail unclear; manual plan needs more explicit command-line pass criteria | LT-1 manual test T6 |

---

## Triage for LT-2 / LT-3 Planning

| Group | Log IDs | Recommendation | Why |
|---|---|---|---|
| Knowledge Library review UX | LOG-004, LOG-005 | Add to LT-2 | LT-2 expands literature search and source review. Before adding PubMed/Semantic Scholar volume, pending source cards need clearer title/source/topic fields, smaller titles, and clickable source/DOI/URL verification. |
| Conversation layout / navigation | LOG-002, LOG-003 | Add to LT-2 as a UX/design task or pre-LT-2 hardening task | LT-2 adds Previous Topics, which will increase sidebar/workspace navigation pressure. Mode controls becoming hard to reach during long chats is a direct usability blocker. Group these into one chat layout and persistent-controls design problem. |
| Context selection ambiguity | LOG-001 | Add to LT-2 | LT-2 includes Previous Topics and user-editable topic labels. This issue is about ambiguous context state, so it belongs with session/context UI work. |
| Manual test clarity | LOG-007 | Resolve before LT-2 starts, not as LT-2 product scope | This is a process/test-plan issue. Fix manual test criteria when drafting LT-2 plans so the same ambiguity does not recur. |
| Agent/model visibility and preferences | LOG-006 | Defer until after LT-2; consider LT-3 or post-LT-3 platform UX | Showing active agent/model could be a small LT-2 improvement, but model selection and persistent preference prompts are broader product architecture. Better handled when adding more agents in LT-3. |

| Sprint Bucket | Work Item | Log IDs | Notes |
|---|---|---|---|
| LT-2 Required | Knowledge Library source review polish | LOG-004, LOG-005 | Make source identity, topic context, source type, and verification links prominent before increasing source volume. |
| LT-2 Required | Session/context UX clarity | LOG-001 | Align textbook/chapter state with Previous Topics context state and editable topic labels. |
| LT-2 UX Spike | Persistent chat controls / scroll behavior | LOG-002, LOG-003 | Decide sticky mode bar vs reversed/latest-first chat vs independent pane scrolling. |
| Pre-LT-2 Planning Fix | Manual test query pass criteria | LOG-007 | Update LT-2 manual plans with explicit expected command output and pass/fail examples. |
| Deferred | Model/agent identity and preference system | LOG-006 | Possibly split into active-model display sooner and model selection/preferences later. |

Note: `docs/projectStatus.md` should be updated the next time project status changes because its Open Issues summary still mentions `T4-clear`, which is now resolved.

---

## Resolved

| Log ID | Date | Issue ID | Description | Resolution |
|---|---|---|---|---|
| LOG-008 | 2026-05-04 | T6-lock | Import from Suggestions tab failed with DuckDB lock conflict (subprocess vs Streamlit connection) | Replaced subprocess ingest with in-process `run_ingest` call |
| LOG-009 | 2026-05-04 | T5-ctx | Agent lost multi-turn context — "yes" confirmation after dataset suggestion did not queue item | Fixed `agent.chat()` to mutate caller's message list; `chat.py` maintains `api_messages` in session state |
| LOG-010 | 2026-05-04 | H1-clear | Clear button triggered by Enter key (form default submit) | Moved Clear outside `st.form`; now requires explicit mouse click |
| LOG-011 | 2026-05-04 | ON-search | OpenNeuro connector sent invalid GraphQL `search` argument — HTTP 400 | Switched to `advancedSearch(query: DatasetSearchInput!)` |
| LOG-012 | 2026-05-05 | T4-clear | Chat history clears transiently after import action reported to agent; second query recovers without restart | Resolved during LT-1 manual testing; user approved tests 1-7 and marked issue resolved |
