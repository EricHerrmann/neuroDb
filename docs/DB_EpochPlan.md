# NeuroDb — DB Epoch Plan

**Status:** MVP complete (Phases 0–6); Phases 7–8 decision pending
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/db/`, `src/neurodb/connectors/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Build and maintain the local neuroscience data platform — source connectors, DuckDB schema, normalization transforms, merged views, and all structured storage schemas — that all other epochs depend on as their data substrate.

**Active work:** Phases 7 (entity resolution) and 8 (research storage schema) are next; both pending a scope decision based on Phase 6 field-coverage audit.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| Phase 0 | Schema scaffolding, provenance, test harness | Complete | — | 2026-04-11 | — |
| Phase 1 | OpenNeuro connector — GraphQL, idempotent ingest | Complete | — | 2026-04-12 | — |
| Phase 2 | MVP Streamlit browser + search UI | Complete | — | 2026-04-12 | — |
| Phase 3 | Allen Brain Atlas connector + view-based merge | Complete | — | 2026-04-13 | — |
| Phase 4 | Query and analysis layer — CLI + SQL mode | Complete | — | 2026-04-13 | — |
| Phase 5 | DuckDB migration from SQLite | Complete | 35 | 2026-04-13 | — |
| Phase 6 | NeuroVault + DANDI connectors | Complete | 74 | 2026-04-13 | — |
| Phase 7 | Entity resolution — dedup across sources | Decision pending | — | — | — |
| Phase 8 | Research storage schema — hypothesis layer tables | Not started | — | — | — |

Active test plan: none

---

## Open Backlog

No open LOG entries currently assigned to DB epoch.

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-11 | SQLite for Phases 0–2 | Zero-install, portable, sufficient for MVP scale |
| 2026-04-11 | DuckDB for Phase 3+ | Columnar performance needed for analytical queries over multi-source merged datasets |
| 2026-04-11 | PostgreSQL excluded | No multi-user or server requirements in scope |
| 2026-04-13 | DANDI two-stage ingest | NWB files are large; separate REST ingest (stage 1) from NWB parse (stage 2); `enriched_at` column tracks enrichment state per record |
| 2026-04-13 | `DatasetIndex.run_id` immutable after insert | DuckDB FK limitation: cannot UPDATE any column on a FK-referenced row after child rows exist — source-specific table `run_id` tracks subsequent runs instead |

Historical phase detail and task checklists: `docs/archive/DB_EpochPlan_historical.md`

---

## Connectors + Owned Tables

### Source Connectors

| Connector | Source | Module |
|-----------|--------|--------|
| OpenNeuro | OpenNeuro GraphQL API | `src/neurodb/connectors/openneuro.py` |
| Allen Brain Atlas | Allen Institute REST API | `src/neurodb/connectors/allen_brain.py` |
| NeuroVault | NeuroVault REST API | `src/neurodb/connectors/neurovault.py` |
| DANDI | DANDI REST API + pynwb (two-stage) | `src/neurodb/connectors/dandi.py` |

### Schema Ownership

The DB epoch owns the schema for all DuckDB tables. Write paths belong to the epoch that owns the domain (noted below). No other epoch executes raw SQL or calls ORM methods directly outside a DB-epoch helper function.

| Table | Purpose | Write path |
|-------|---------|------------|
| `openneuro_datasets` | OpenNeuro study records | DB connectors |
| `allen_brain_studies` | Allen Brain Atlas study records | DB connectors |
| `neurovault_collections` | NeuroVault collection records | DB connectors |
| `dandi_dandisets` | DANDI dandiset records | DB connectors |
| `dataset_index` | Cross-source unified index | DB connectors |
| `provenance_events` | Ingest and transform audit log | DB helpers |
| `quality_events` | QA events per dataset record | DB helpers |
| `study_notes` | User-attached study annotations | DB helpers |
| `sessions` | Agent session records | Agent Core session helper |
| `knowledge_sources` | Tutor knowledge library metadata | Tutor epoch helpers |
| `model_call_log` | Telemetry — one row per model call | Agent Core `BaseAgent` |
| `research_questions` | Research question records | Research epoch tools |
| `research_hypotheses` | Hypothesis records | Research epoch tools |
| `hypothesis_reviews` | Hypothesis review records | Research epoch tools |

### Views

| View | Purpose |
|------|---------|
| `v_all_datasets` | UNION of all 4 source tables |
| `v_dataset_summary` | Aggregated count by source + modality |
