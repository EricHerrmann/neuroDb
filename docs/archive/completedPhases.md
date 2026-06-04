# NeuroDb — Completed Phases

Archived from `docs/projectStatus.md`. Add new rows here when a phase reaches completion.

---

## Completed Phases

| Phase | What | Date |
|-------|------|------|
| DB Epochs 0–6 | Data platform: ingest, normalize, DuckDB, NeuroVault/DANDI connectors | 2026-04-13 |
| P1–P4 | Learning agent MVP: study tags, embeddings, agent interface, context persistence | 2026-04-29 |
| P5 | Learning Agent Enhancement: mode toggle, chapter registry, discovery tools, suggestions UI | 2026-05-04 |
| P6 | Learning Agent Features: embedding dedup, agent streaming, split-workspace UI | 2026-05-04 |
| Pre-LT-2 | Sidebar migration | 2026-05-05 |
| LT-1 | BaseAgent architecture, NeuroTutorAgent, auto-session, Knowledge Library storage + UI | 2026-05-05 |
| LT-2 | Live literature search, Previous Topics, session memory, Knowledge Library polish | 2026-05-06 |
| LT-3 | Research agent scaffolding, knowledge growth metrics, hypothesis tools | 2026-05-06 |
| Config Control Phase 1 | Per-agent model env vars and summary model routing — 332 tests plus 5 manual evals passed | 2026-05-07 |
| Config Control Phase 2 | Model-call telemetry for agent loops and summary calls — 344 tests plus 7 manual evals passed | 2026-05-08 |
| Config Control Phase 3 | Research Synthesis Split: Sonnet draft loop plus premium hypothesis review — 350 tests plus 4 manual evals passed | 2026-05-08 |
| Config Control Phase 4 | ModelClient abstraction, AnthropicModelClient, OpenAIModelClient, TaskRouter, config-driven provider selection, BaseAgent refactor, LOG-044 fix — 389 automated tests + 7 manual evals passed | 2026-05-09 |
| Config Control Phase 5A | TOML corrected, all 4 providers × 3 tiers quality-aligned (OpenAI: gpt-5.4-mini/gpt-5.4/gpt-5.5), Groq+Gemini entries added, Gemini wired, tool schemas fixed for OpenAI strict validation — 397 automated tests | 2026-05-08 |
| Config Control Phase 5B | TOML routing refactor — single [routing] section replaces env-var tier overrides; _cache patch pattern for provider tests; provider selection UI deferred to UI epoch — 398 automated tests | 2026-05-08 |
| UI-1 | FastAPI backend shell — app factory, 8 API routes (status, preferences, research, chat/SSE), zero-arg uvicorn factory; 408 automated tests + 9 manual evals passed | 2026-05-11 |
| UI-2 | React workbench prototype — Vite + React shell, typed API client, all 7 panels functional, FastAPI panel routes; 443 Python tests + 7 frontend tests + 11 manual evals passed | 2026-05-11 |
| UI-2B | React layout redesign — activity rail, resizable/collapsible right panel, agent mode in chat header, Study Log chat history; 19 frontend tests + 9 manual evals passed | 2026-05-11 |
| UI-3 | React parity migration — 7 write operations, Streamlit deprecation banner, API-backed panels; 474 Python tests + 43 frontend tests + build + manual evals passed | 2026-05-13 |
| UI-5 P1/P2/P3 | React parity completion — data integrity, core workflow parity, and polish; 515 Python tests + 57 frontend tests + build + 8 common manual evals passed | 2026-05-23 |
| Learning and Research Memory Refocus Phases 1-6 | Dataset research packets, papers/topics/concepts/study context, claims/evidence/gaps, context modes/evidence boundaries, UI evidence controls, context budgets and telemetry; manual phase gates signed off | 2026-05-24 |
| Learning and Research Memory Refocus Completion | LOG-059 study log outer join fix, context budgets, retrieval telemetry, task-type defaults, dataset usefulness in agent context; manual T1-T5 passed | 2026-05-24 |

**Deferred:** DB Epochs 7 (entity resolution) and 8 (hypothesis layer) — decision pending. See `docs/DB_EpochPlan.md`.

---

## Tech Debt Sprints (complete)

| Sprint | Focus | Status |
|--------|-------|--------|
| TD-1 | Schema migration framework, connector fetch_by_id/search_by_keyword on all sources, explicit connector registry, StudyNote unique constraint, dependency pinning | Complete — 186 tests |
| TD-2 | Unit tests: embedder, enrichment, provenance; clear button behavioral tests | Complete — 204 tests |
| TD-3 | Dead code removal, model name env var, api_messages rollback on exception, QualityEvent compound index, chapter context guard, pytest-cov | Complete — 210 tests |
