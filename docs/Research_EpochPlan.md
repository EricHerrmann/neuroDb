# NeuroDb — Research Epoch Plan

**Status:** Scaffolded (LT-3); hypothesis review with structured tool-use output
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/research/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Apply AI capability to conduct real neuroscience investigations using existing public datasets and good scientific method — forming testable hypotheses, gathering evidence from available data, and producing structured outputs.

**Active work:** None in active development. LOG-037, LOG-045, LOG-048 are open backlog. Research run management and research question actions are the next planned work.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| LT-3 | NeuroResearchAgent scaffolding, knowledge growth metrics, hypothesis tools (`record_research_question`, `draft_hypothesis`) | Complete | — | 2026-05-06 | — |
| Config P3 | Research Synthesis Split — standard-tier research loop + premium hypothesis review via `submit_critique` tool-use | Complete | 350 (suite-wide) | 2026-05-08 | `docs/testsPlans/manualTestPlan_config_phase3.md` |

Active test plan: none

---

## Open Backlog

| Log ID | Issue |
|--------|-------|
| LOG-037 | No way to delete or act on existing research questions in the UI |
| LOG-045 | Research agent cannot nominate papers for Knowledge Library import — no bridge to Tutor curation queue |
| LOG-048 | No way to dismiss a draft hypothesis from the UI |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-06 | Research reads Knowledge Library; Tutor writes it | Clean epoch boundary; Research uses `search_knowledge_library()` only — nominations flow through the Tutor curation queue (LOG-045) |
| 2026-05-08 | Hypothesis review uses `submit_critique` tool-use to force structured output | LOG-044: premium model returned prose instead of JSON; tool-use with a defined schema forces structure regardless of model verbosity |
| 2026-05-09 | `evidence` and `datasets` tool schema items are typed objects with defined properties | Groq's strict validator rejects bare `{"type": "object"}` items; defined `{source, summary}` and `{dataset_id, relevance}` shapes give all providers unambiguous guidance and produce consistently queryable data |

---

## Owned Storage

| Store | Name | Purpose |
|-------|------|---------|
| DuckDB | `research_questions` | Questions, status, topic context |
| DuckDB | `research_hypotheses` | Title, mechanism, evidence, predictions, datasets, confounds, limitations, status |
| DuckDB | `hypothesis_reviews` | Critique, unsupported claims, missing confounds, suggested revisions, status |
