# NeuroDb — Issue Log

Running log of issues discovered during testing, reviews, and ad hoc exploration.
Add new entries at any time using `LOG:` in chat.

Use `Log ID` for cross-references across Open, Resolved, triage, sprint planning, and future implementation notes. `Issue ID` preserves the short human-readable label used when the issue was first logged.

---

## Open Issues Summary

### Tutor
| Log ID | Issue ID | Description | Priority |
|--------|----------|-------------|----------|
| LOG-001 | P6-selector | Textbook dropdown appears pre-selected without explicit user action — agent context state is ambiguous | Deferred post-LT-3 |

### Config
| Log ID | Issue ID | Description | Priority |
|--------|----------|-------------|----------|
| LOG-006 | LT1-model-visibility | User cannot tell which agent/LLM/model is active; no model selection or persistent preference rules | Deferred post-LT-3 |
| LOG-041 | config-session-summary-visibility | No UI path to view the generated session summary; needed for T4 date/topic/key-concepts verification | Feature review |
| LOG-047 | telemetry-timestamp-format | Telemetry log timestamps should display as HH:MM:SS DD/MM/YY; current format is raw ISO 8601 | Phase 6 |
| LOG-050 | gemini-premium-testing-deferred | Further manual testing against premium Gemini models deferred | Deferred |

### UI
| Log ID | Issue ID | Description | Priority |
|--------|----------|-------------|----------|
| LOG-013 | UI-shell-rearchitecture | Streamlit cannot support fixed-pane app-shell behavior; reassess UI stack after LT-3 | Deferred post-LT-3 |
| LOG-030 | lt3-t2-pass-header-size | LT-3 T2 passed, but titles/headers render too large | UI polish |
| LOG-051 | ui-icon-pane-association | UI epoch feature: hard to associate activity-rail icons with right pane content; needs stronger tooltips/associations and icon reorder with Research first, then Study Log | UI polish |

### Research
| Log ID | Issue ID | Description | Priority |
|--------|----------|-------------|----------|
| LOG-037 | lt3-t6-research-question-actions | Research pane shows several research questions but there is no way to delete or use them | Post-LT-3 polish |
| LOG-045 | research-agent-no-knowledge-queue | Research agent cannot nominate papers for import to the knowledge library; no bridge to Tutor curation queue | Feature — Research epoch |
| LOG-048 | dismiss-draft-hypothesis | No way to dismiss a draft hypothesis from the UI; dismiss exists for reviews but not the hypothesis itself | Research UI polish |
| LOG-053 | research-agent-no-dataimport-suggestions | Research agent did not add suggestions to the data import queue even when specifically asked for suggestions | Research UI/agent polish |

---

## Open

| Log ID | Date | Issue ID | Epoch | Description | Context |
|---|---|---|---|---|---|
| LOG-001 | 2026-05-04 | P6-selector | Tutor | Textbook dropdown appears pre-selected without explicit user action — actual agent context is ambiguous | P6 manual test |
| LOG-006 | 2026-05-05 | LT1-model-visibility | Config | User cannot tell which agent/LLM/model is active; later work should add model selection and persistent model/user-preference prompt rules | LT-1 manual/ad hoc review |
| LOG-013 | 2026-05-05 | UI-shell-rearchitecture | UI | Pre-LT-2 fixed-pane layout failed in Streamlit even with a custom-component bridge; evaluate a UI tech-stack rearchitecture after LT-2/LT-3 once core learning capabilities mature to MVP | Pre-LT-2 manual test |
| LOG-030 | 2026-05-06 | lt3-t2-pass-header-size | UI | LT-3 T2 passed, agent has correct date and knows context; minor UI fix: reduce titles/headers font, it is too big | LT-3 manual testing |
| LOG-037 | 2026-05-06 | lt3-t6-research-question-actions | Research | T6: Research pane shows several research questions, but there is no way to delete or use them | LT-3 manual testing |
| LOG-041 | 2026-05-07 | config-session-summary-visibility | Config | T4 has explicit checks for date, topic, and key concepts, so there needs to be a way to view the generated session summary in the app. | Config control Phase 1 manual testing |
| LOG-045 | 2026-05-08 | research-agent-no-knowledge-queue | Research | Research agent cannot queue studies it finds for import to the knowledge library — it can only read from it. The Tutor epoch owns the write path (curation, approval, embedding), but no bridge exists for the Research epoch to nominate papers as candidates for Tutor review. Feature request: add a `queue_for_knowledge_library` tool to the research agent that writes a lightweight nomination row to the DB, surfaced in the Tutor/Knowledge Library UI for user approval before full ingest. | Config Phase 4 manual testing — T3 ad hoc observation |
| LOG-047 | 2026-05-09 | telemetry-timestamp-format | Config | Telemetry log timestamps display as raw ISO 8601; should display as HH:MM:SS DD/MM/YY for user readability. Likely addressed in Phase 6 alongside the system_warnings CLI surface. | Config Phase 4 manual testing |
| LOG-048 | 2026-05-09 | dismiss-draft-hypothesis | Research | No way to dismiss a draft hypothesis from the UI. Dismiss exists for hypothesis reviews but not for the hypothesis itself. Hypothesis status options include "archived" but there is no button to set it. | Config Phase 4 manual testing |
| LOG-050 | 2026-05-09 | gemini-premium-testing-deferred | Config | Gemini/Google account is billing-enabled for premium tier; all wiring issues surfaced this session (GOOGLE_API_KEY rename, null streaming tokens) were fixed. Further testing against premium Gemini models deferred. | Config Phase 4 manual testing |
| LOG-051 | 2026-05-12 | ui-icon-pane-association | UI | UI epoch feature: hard to associate activity-rail icons with the related right pane and know what is available in each pane; increase tooltips or associations, and reorganize icons with Research at top, then Study Log. | User logged during UI-3 manual/ad hoc review |
| LOG-053 | 2026-05-12 | research-agent-no-dataimport-suggestions | Research | Research agent did not add suggestions to the data import queue even when specifically asked for suggestions. | User logged during UI-3 manual/ad hoc review |
| LOG-054 | 2026-05-13 | dataset-minimal-research-value | Research | Datasets have minimal information; need to explore the right amount of dataset metadata for local research because current dataset value is unclear. | User logged during external dataset/agent-mode review |
| LOG-056 | 2026-05-13 | knowledge-lib-duplicates-no-remove | Tutor | Knowledge Library has duplicate entries and no way to remove them. | User logged during UI-5 review |
| LOG-057 | 2026-05-13 | args-position-dependent | Tech Debt | CLI and Python function arguments should not be brittle or position-dependent; review the codebase for positional CLI globals and multi-argument function calls, then determine options to fix with keyword-only APIs, structured request objects, shared parser helpers, and inheritable patterns. | User logged during CLI/manual-test review |
| LOG-058 | 2026-05-13 | ui5-common-t1-pass | UI | UI-5 common manual test T1 passed. | User logged during UI-5 common manual verification |
| LOG-059 | 2026-05-18 | study-inner-join-drops-anchors | Study Log | `list_tags()` and `search_tags()` in study.py use INNER JOIN on DatasetIndex; topic/concept/paper-anchored notes are invisible to the study log API. After Phase 2 Task 4, StudyNote.index_id became nullable but the JOIN silently filters non-dataset notes. Fix deferred to Phase 5 / study log API update. | Code review / technical debt |

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
| LOG-014 | 2026-05-06 | semscholar-no-apikey | Semantic Scholar does not issue API keys to non-academic (gmail.com) accounts; unauthenticated rate limit appears sufficient for current use | Resolved: not an issue; no action required |
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
| LOG-015 | 2026-05-06 | agent-session-date | Agent logged the LTP vs. LTD study session with an incorrect date (January 27 instead of May 4, 2026); agent is not using the correct current date when writing session records | Resolved in LT-3: T2 passed with correct date/context |
| LOG-021 | 2026-05-06 | agent-mode-not-persisted | Agent mode selection does not persist across sessions; user must re-select mode each time the app is restarted | Resolved in LT-3: T1 passed with Neuro-Research mode persisting across restart |
| LOG-034 | 2026-05-06 | lt3-t6-max-turns-tool-result | LT-3 T6 failed: agent reached maximum tool iterations during grounded hypothesis drafting; retry after clearing context produced Anthropic 400 because a tool_use block lacked an immediately following tool_result. Need to understand max tool-iteration limit, whether research workflows need higher limits, context compaction, or another turn/context-management strategy. | Resolved: terminal draft-hypothesis response and valid API-history recovery verified by T6 pass |
| LOG-035 | 2026-05-06 | lt3-t6-max-turns-after-clear | LT-3 T6 fails with max turns issue even after clearing context before running T6 | Resolved: T6 passed after max-turn/tool-result remediation |
| LOG-036 | 2026-05-06 | lt3-t7-max-turns-localdb | LT-3 T7 failed with max turns error after the agent had retrieved information from the local DB; T8 deferred | Resolved: T7 and T8 passed after remediation |
| LOG-029 | 2026-05-06 | t1-pass | LT-3 T1 pass record | Test pass — not an issue |
| LOG-031 | 2026-05-06 | lt3-t3-pass | LT-3 T3 pass record | Test pass — not an issue |
| LOG-032 | 2026-05-06 | lt3-t4-pass | LT-3 T4 pass record | Test pass — not an issue |
| LOG-033 | 2026-05-06 | lt3-t5-pass | LT-3 T5 pass record | Test pass — not an issue |
| LOG-038 | 2026-05-06 | lt3-t6-pass | LT-3 T6 pass record | Test pass — not an issue |
| LOG-039 | 2026-05-06 | lt3-t7-pass | LT-3 T7 pass record | Test pass — not an issue |
| LOG-042 | 2026-05-07 | config-phase2-streamlit-lock-test-order | Config Phase 2 manual plan started Streamlit before CLI schema/telemetry checks, causing DuckDB write-lock failures | Resolved: `manualTestPlan_config_phase2.md` now runs T1 before Streamlit and instructs testers to stop Streamlit before each CLI SQL check |
| LOG-043 | 2026-05-07 | config-p2-t1-pass | Config Phase 2 T1 schema check passed | Test pass — not an issue |
| LOG-044 | 2026-05-08 | config-p3-review-json-structure | Config Phase 3 premium review returned prose instead of structured JSON | Resolved in Config Phase 4: `hypothesis_review.py` migrated to `ModelClient` with `submit_critique` tool-use, forcing structured output. 382 automated tests passing. |
| LOG-046 | 2026-05-09 | dismiss-review-no-action | Dismiss review button appeared to have no visible effect | Resolved: `_list_hypothesis_reviews` was not filtering out dismissed reviews — dismissed rows remained visible on rerender. Fixed by adding `filter(HypothesisReview.status != "dismissed")` to the query. |
| LOG-040 | 2026-05-07 | config-phase1-t3-localdb-no-results-hang | Config Phase 1 T3 apparent hang on local DB no-results response; possible model-tier fit issue | Not reproduced in subsequent testing through Config Phases 2–4; resolved as no-recurrence 2026-05-10 |
| LOG-049 | 2026-05-09 | gemini-routing-failure | Gemini provider routing failed; OpenAI worked. | Resolved 2026-05-09: Two root causes fixed — (1) `provider_factory.py` read `GEMINI_API_KEY` but key is stored as `GOOGLE_API_KEY`; renamed throughout. (2) `OpenAIModelClient.stream_message` lacked `stream_options={"include_usage": True}`, causing null token counts for all OpenAI-compat providers in streaming mode; fixed. |
| LOG-052 | 2026-05-12 | chat-markdown-plain-text | Agent returns Markdown, but chat window renders it as plain text, making responses hard to read | Resolved in UI-5 P2: React chat now renders Markdown tables/lists/code/links and separates tool activity from answer text; covered by `MessageBubble` frontend tests. |
| LOG-055 | 2026-05-13 | ui5p2-chat-md-rendering | Agent returns Markdown in the chat window, poorly rendering responses for the user; change agent prompts so responses use nicely formatted tables and text suitable for the user chat window | Resolved in UI-5 P2: DB, Tutor, and Research prompts now instruct user-readable prose/tables and no raw tool JSON; chat bubble renderer supports formatted tables and text. |
