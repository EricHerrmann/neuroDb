# NeuroDb — Issue Log

Running log of issues discovered during testing, reviews, and ad hoc exploration.
Add new entries at any time using `LOG:` in chat.

Use `Log ID` for cross-references across Open, Resolved, triage, sprint planning, and future implementation notes. `Issue ID` preserves the short human-readable label used when the issue was first logged.

**Severity scale:** High — data loss, blocking workflow, or silent incorrect behavior; Medium — user-visible feature gap or significant usability issue; Low — cosmetic, deferred, or minor UX improvement.

---

## Open Issues

| Log ID | Issue ID | Epoch | Severity | Description | Priority |
|--------|----------|-------|----------|-------------|----------|
| LOG-059 | study-inner-join-drops-anchors | DB | High | `list_tags()` and `search_tags()` use INNER JOIN on DatasetIndex; topic/concept/paper-anchored notes are silently filtered out | Phase 5 / study log API update |
| LOG-054 | dataset-minimal-research-value | Research | Medium | Datasets have minimal information; need to determine the right amount of dataset metadata for local research | Backlog |
| LOG-057 | args-position-dependent | Tech Debt | Medium | CLI and Python function arguments are position-dependent; review for keyword-only APIs, structured request objects, and shared parser helpers | TD-1 / Tech Debt sprint |
| LOG-001 | P6-selector | Tutor | Low | Textbook dropdown appears pre-selected without explicit user action — agent context state is ambiguous | Deferred post-LT-3 |
| LOG-013 | UI-shell-rearchitecture | UI | Low | Streamlit cannot support fixed-pane app-shell behavior; reassess UI stack after LT-3 | Deferred post-LT-3 |
| LOG-050 | gemini-premium-testing-deferred | Config | Low | Further manual testing against premium Gemini models deferred | Deferred |
| LOG-051 | ui-icon-pane-association | UI | Low | Hard to associate activity-rail icons with right pane content; needs stronger tooltips and icon reorder with Research first | UI polish |

---

## Open (detail)

| Log ID | Date | Issue ID | Epoch | Severity | Description | Context |
|--------|------|----------|-------|----------|-------------|---------|
| LOG-001 | 2026-05-04 | P6-selector | Tutor | Low | Textbook dropdown appears pre-selected without explicit user action — actual agent context is ambiguous | P6 manual test |
| LOG-013 | 2026-05-05 | UI-shell-rearchitecture | UI | Low | Pre-LT-2 fixed-pane layout failed in Streamlit even with a custom-component bridge; evaluate a UI tech-stack rearchitecture after LT-2/LT-3 once core learning capabilities mature to MVP | Pre-LT-2 manual test |
| LOG-050 | 2026-05-09 | gemini-premium-testing-deferred | Config | Low | Gemini/Google account is billing-enabled for premium tier; all wiring issues surfaced this session (GOOGLE_API_KEY rename, null streaming tokens) were fixed. Further testing against premium Gemini models deferred. | Config Phase 4 manual testing |
| LOG-051 | 2026-05-12 | ui-icon-pane-association | UI | Low | UI epoch feature: hard to associate activity-rail icons with the related right pane and know what is available in each pane; increase tooltips or associations, and reorganize icons with Research at top, then Study Log. | User logged during UI-3 manual/ad hoc review |
| LOG-054 | 2026-05-13 | dataset-minimal-research-value | Research | Medium | Datasets have minimal information; need to explore the right amount of dataset metadata for local research because current dataset value is unclear. | User logged during external dataset/agent-mode review |
| LOG-057 | 2026-05-13 | args-position-dependent | Tech Debt | Medium | CLI and Python function arguments should not be brittle or position-dependent; review the codebase for positional CLI globals and multi-argument function calls, then determine options to fix with keyword-only APIs, structured request objects, shared parser helpers, and inheritable patterns. | User logged during CLI/manual-test review |
| LOG-059 | 2026-05-18 | study-inner-join-drops-anchors | DB | High | `list_tags()` and `search_tags()` in study.py use INNER JOIN on DatasetIndex; topic/concept/paper-anchored notes are invisible to the study log API. After Phase 2 Task 4, StudyNote.index_id became nullable but the JOIN silently filters non-dataset notes. Fix deferred to Phase 5 / study log API update. | Code review / technical debt |

---

## Monitor

| Log ID | Date | Issue ID | Epoch | Severity | Description | Monitor note |
|--------|------|----------|-------|----------|-------------|--------------|
| LOG-060 | 2026-05-21 | chat-turn-hang | UI / Agent Core | Medium | Chat hung periodically and caused a page error during `POST /api/chat/turn`, with no server-side errors logged at time of failure. | Monitor after renderer fix. Likely cause found during Phase 5a T10: frontend `MessageBubble` Markdown parser could infinite-loop during streaming when a partial block marker such as `## ` was present. The parser recognized it as a block start but no block handler consumed it, so `index` did not advance and the browser paused before a potential out-of-memory crash. Fixed by making `isBlockStart()` require complete heading text and adding a progress guard that renders unconsumed lines as plain text and increments `index`. Covered by `frontend/src/components/MessageBubble.test.tsx` cases for partial streamed headings and incomplete Markdown constructs. If LOG-060 recurs, first inspect `MessageBubble.tsx` parser progress, streamed partial Markdown content, and browser DevTools pause location before assuming backend/agent failure. |

---

## Resolved

| Log ID | Date | Issue ID | Epoch | Severity | Description | Resolution |
|--------|------|----------|-------|----------|-------------|------------|
| LOG-006 | 2026-05-05 | LT1-model-visibility | Config | Low | User cannot tell which agent/LLM/model is active; later work should add model selection and persistent model/user-preference prompt rules | Resolved in Config Control Phase 6: React Chat header shows a read-only active provider/model chip from `/api/model-info`; manual T4 passed 2026-05-23 |
| LOG-041 | 2026-05-07 | config-session-summary-visibility | Config | Medium | T4 has explicit checks for date, topic, and key concepts, so there needs to be a way to view the generated session summary in the app. | Resolved in Config Control Phase 6: Study Log chat history renders session summaries behind an expandable `Session summary` affordance; manual T5 passed 2026-05-23 |
| LOG-047 | 2026-05-09 | telemetry-timestamp-format | Config | Low | Telemetry log timestamps display as raw ISO 8601; should display as HH:MM:SS DD/MM/YY for user readability. Likely addressed in Phase 6 alongside the system_warnings CLI surface. | Resolved in Config Control Phase 6: `neurodb-telemetry` uses shared `format_recorded_at()` with `HH:MM:SS DD/MM/YY`; manual T3 passed 2026-05-23 |
| LOG-045 | 2026-05-23 | research-agent-no-knowledge-queue | Research | Medium | Research agent had no write path to the knowledge library | Added `nominate_paper` tool to Research Agent: creates a pending `Paper` row via the existing Knowledge Library approval flow; deduplication by DOI or normalized title matches Tutor Agent behavior |
| LOG-053 | 2026-05-23 | research-agent-no-dataimport-suggestions | Research | Medium | Research agent could not add datasets to the import queue | Added `suggest_dataset_import` tool to Research Agent: calls `run_suggest_import` to write an `import_queue` row; system prompt updated to instruct use when datasets are found via search_external or inspect_external_dataset |
| LOG-056 | 2026-05-23 | knowledge-lib-duplicates-no-remove | Tutor | Medium | Knowledge Library had no way to remove entries | Added `POST /api/knowledge-library/{id}/remove`: sets status="removed", removes from ChromaDB if approved; GET excludes removed from "all" filter; Remove button added to KnowledgeLibraryPanel for all non-removed items; "Removed" added to status filter dropdown |
| LOG-037 | 2026-05-23 | lt3-t6-research-question-actions | Research | Medium | Research pane had no way to act on research questions | Archive action added to research question status chip; filter bubbles with live status counts added; DuckDB FK update limitation resolved via migration 012 (table rebuild without FK constraints) |
| LOG-048 | 2026-05-23 | dismiss-draft-hypothesis | Research | Medium | No way to dismiss a draft hypothesis from the UI | Archive action added to hypothesis status chip via `POST /api/research/hypotheses/{id}/archive`; serialization fixed to route through `_hypothesis_item` |
| LOG-061 | 2026-05-23 | no-retract-lifecycle | Research | Medium | No retract/remove lifecycle for evidence links, questions, claims, or gaps | Full lifecycle implemented: EvidenceLink retract, ResearchQuestion archive, hypothesis archive, claim approve/reject/archive, gap resolve/archive; filter bubbles with live counts added to all sections; signed off Phase 5b T1-T7 |
| LOG-030 | 2026-05-21 | lt3-t2-pass-header-size | UI | Low | Titles/headers rendered too large in Streamlit | Resolved by React migration — React UI uses standard CSS sizing with no Streamlit rendering quirks |
| LOG-052 | 2026-05-12 | chat-markdown-plain-text | UI | High | Agent returns Markdown, but chat window renders it as plain text, making responses hard to read | Resolved in UI-5 P2: React chat now renders Markdown tables/lists/code/links and separates tool activity from answer text; covered by `MessageBubble` frontend tests. |
| LOG-055 | 2026-05-13 | ui5p2-chat-md-rendering | UI | Medium | Agent returns Markdown in the chat window, poorly rendering responses for the user; change agent prompts so responses use nicely formatted tables and text suitable for the user chat window | Resolved in UI-5 P2: DB, Tutor, and Research prompts now instruct user-readable prose/tables and no raw tool JSON; chat bubble renderer supports formatted tables and text. |
| LOG-058 | 2026-05-13 | ui5-common-t1-pass | UI | Low | UI-5 common manual test T1 passed | Test pass — not an issue |
| LOG-049 | 2026-05-09 | gemini-routing-failure | Config | High | Gemini provider routing failed; OpenAI worked. | Resolved 2026-05-09: Two root causes fixed — (1) `provider_factory.py` read `GEMINI_API_KEY` but key is stored as `GOOGLE_API_KEY`; renamed throughout. (2) `OpenAIModelClient.stream_message` lacked `stream_options={"include_usage": True}`, causing null token counts for all OpenAI-compat providers in streaming mode; fixed. |
| LOG-046 | 2026-05-09 | dismiss-review-no-action | Research | Medium | Dismiss review button appeared to have no visible effect | Resolved: `_list_hypothesis_reviews` was not filtering out dismissed reviews — dismissed rows remained visible on rerender. Fixed by adding `filter(HypothesisReview.status != "dismissed")` to the query. |
| LOG-044 | 2026-05-08 | config-p3-review-json-structure | Research | High | Config Phase 3 premium review returned prose instead of structured JSON | Resolved in Config Phase 4: `hypothesis_review.py` migrated to `ModelClient` with `submit_critique` tool-use, forcing structured output. 382 automated tests passing. |
| LOG-042 | 2026-05-07 | config-phase2-streamlit-lock-test-order | Config | Medium | Config Phase 2 manual plan started Streamlit before CLI schema/telemetry checks, causing DuckDB write-lock failures | Resolved: `manualTestPlan_config_phase2.md` now runs T1 before Streamlit and instructs testers to stop Streamlit before each CLI SQL check |
| LOG-043 | 2026-05-07 | config-p2-t1-pass | Config | Low | Config Phase 2 T1 schema check passed | Test pass — not an issue |
| LOG-040 | 2026-05-07 | config-phase1-t3-localdb-no-results-hang | Config | Low | Config Phase 1 T3 apparent hang on local DB no-results response; possible model-tier fit issue | Not reproduced in subsequent testing through Config Phases 2–4; resolved as no-recurrence 2026-05-10 |
| LOG-021 | 2026-05-06 | agent-mode-not-persisted | Config | Medium | Agent mode selection does not persist across sessions; user must re-select mode each time the app is restarted | Resolved in LT-3: T1 passed with Neuro-Research mode persisting across restart |
| LOG-034 | 2026-05-06 | lt3-t6-max-turns-tool-result | Agent Core | High | LT-3 T6 failed: agent reached maximum tool iterations during grounded hypothesis drafting; retry after clearing context produced Anthropic 400 because a tool_use block lacked an immediately following tool_result. Need to understand max tool-iteration limit, whether research workflows need higher limits, context compaction, or another turn/context-management strategy. | Resolved: terminal draft-hypothesis response and valid API-history recovery verified by T6 pass |
| LOG-035 | 2026-05-06 | lt3-t6-max-turns-after-clear | Agent Core | High | LT-3 T6 fails with max turns issue even after clearing context before running T6 | Resolved: T6 passed after max-turn/tool-result remediation |
| LOG-036 | 2026-05-06 | lt3-t7-max-turns-localdb | Agent Core | High | LT-3 T7 failed with max turns error after the agent had retrieved information from the local DB; T8 deferred | Resolved: T7 and T8 passed after remediation |
| LOG-015 | 2026-05-06 | agent-session-date | Agent Core | Medium | Agent logged the LTP vs. LTD study session with an incorrect date (January 27 instead of May 4, 2026); agent is not using the correct current date when writing session records | Resolved in LT-3: T2 passed with correct date/context |
| LOG-009 | 2026-05-04 | T5-ctx | Agent Core | High | Agent lost multi-turn context — "yes" confirmation after dataset suggestion did not queue item | Fixed `agent.chat()` to mutate caller's message list; `chat.py` maintains `api_messages` in session state |
| LOG-019 | 2026-05-06 | t4-previous-topics-not-loaded | Tutor | High | T4 fails: Previous Topics sidebar did not populate; transcripts not visible | Fixed in LT-2: same root cause as LOG-018; T4 re-run passed |
| LOG-018 | 2026-05-06 | t3-prior-context-not-loaded | Tutor | High | T3 fails: prior context not applied when session selected | Fixed in LT-2: draft ChatSession row written on first message; context fallback from inferred_topic added; T3 re-run passed |
| LOG-017 | 2026-05-06 | knowledge-library-indent-error | Tutor | High | Streamlit crashed on Knowledge Library tab with IndentationError at knowledge_library.py:111 in `_reject_source` | Fixed: removed extra indent on `row.reviewed_at` line |
| LOG-012 | 2026-05-05 | T4-clear | Tutor | Medium | Chat history clears transiently after import action reported to agent; second query recovers without restart | Resolved during LT-1 manual testing; user approved tests 1-7 and marked issue resolved |
| LOG-007 | 2026-05-05 | LT1-test6-criteria | Tutor | Low | T6 chat-session verification query had ambiguous pass/fail criteria | Resolved: LT-2 manual plan updated with explicit expected output and DuckDB read-only query |
| LOG-020 | 2026-05-06 | t5-pass | Tutor | Low | T5 passed | LT-2 signed off |
| LOG-022 | 2026-05-06 | t1-t2-t9-pass | Tutor | Low | T1, T2, T9 passed | LT-2 signed off |
| LOG-023 | 2026-05-06 | t4-arrow-indicator-works | Tutor | Low | ▸ prefix confirmed working on active session selection | LT-2 signed off |
| LOG-024 | 2026-05-06 | t3-t4-context-verified | Tutor | Low | Agent recalled prior session when asked | LT-2 signed off |
| LOG-025 | 2026-05-06 | t3-pass | Tutor | Low | T3 passed | LT-2 signed off |
| LOG-026 | 2026-05-06 | t4-pass | Tutor | Low | T4 passed | LT-2 signed off |
| LOG-028 | 2026-05-06 | t7-t8-t9-pass | Tutor | Low | T7, T8, T9 passed | LT-2 signed off |
| LOG-029 | 2026-05-06 | t1-pass | Tutor | Low | LT-3 T1 pass record | Test pass — not an issue |
| LOG-031 | 2026-05-06 | lt3-t3-pass | Tutor | Low | LT-3 T3 pass record | Test pass — not an issue |
| LOG-032 | 2026-05-06 | lt3-t4-pass | Tutor | Low | LT-3 T4 pass record | Test pass — not an issue |
| LOG-033 | 2026-05-06 | lt3-t5-pass | Tutor | Low | LT-3 T5 pass record | Test pass — not an issue |
| LOG-038 | 2026-05-06 | lt3-t6-pass | Tutor | Low | LT-3 T6 pass record | Test pass — not an issue |
| LOG-039 | 2026-05-06 | lt3-t7-pass | Tutor | Low | LT-3 T7 pass record | Test pass — not an issue |
| LOG-016 | 2026-05-06 | prev-session-context-invisible | UI | Medium | No visible indicator when a previous session is loaded as context | Fixed in LT-2: blue prior-context badge added to chat panel; ▸ prefix and "Active:" caption added to sidebar |
| LOG-010 | 2026-05-04 | H1-clear | UI | Low | Clear button triggered by Enter key (form default submit) | Moved Clear outside `st.form`; now requires explicit mouse click |
| LOG-002 | 2026-05-05 | LT1-scroll-sync | UI | Low | Right workspace pane remains at top while left agent conversation scrolls | Resolved in LT-2: workspace/chat layout redesigned; accepted as current behavior pending post-LT-3 UI shell work |
| LOG-003 | 2026-05-05 | LT1-mode-scroll | UI | Low | Mode controls require scrolling to top as conversation grows | Resolved in LT-2: mode radio always visible in sidebar; deeper layout work deferred to UI shell phase |
| LOG-004 | 2026-05-05 | LT1-pending-source-visibility | UI | Medium | Pending source cards lacked clear title/source/topic and selectable links | Resolved in LT-2: Knowledge Library polish — T7 passed |
| LOG-005 | 2026-05-05 | LT1-knowledge-title-size | UI | Low | Knowledge Library source titles rendered too large | Resolved in LT-2: Knowledge Library polish — T7 passed |
| LOG-027 | 2026-05-06 | prior-context-indicator-low-visibility | UI | Low | Prior context caption at top of chat window had low visibility | Fixed: replaced `st.caption` with styled `st.markdown` — navy background (#1e3a8a), white text, matching active tab style |
| LOG-011 | 2026-05-04 | ON-search | DB | High | OpenNeuro connector sent invalid GraphQL `search` argument — HTTP 400 | Switched to `advancedSearch(query: DatasetSearchInput!)` |
| LOG-008 | 2026-05-04 | T6-lock | DB | High | Import from Suggestions tab failed with DuckDB lock conflict (subprocess vs Streamlit connection) | Replaced subprocess ingest with in-process `run_ingest` call |
| LOG-014 | 2026-05-06 | semscholar-no-apikey | DB | Low | Semantic Scholar does not issue API keys to non-academic (gmail.com) accounts; unauthenticated rate limit appears sufficient for current use | Resolved: not an issue; no action required |
