# NeuroDb — DB Epoch Plan

**Status:** MVP complete (Phases 0–6); Phase 9 dataset research packets in progress
**Last updated:** 2026-05-18
**Epoch directory:** `src/neurodb/db/`, `src/neurodb/connectors/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Build and maintain the local neuroscience data platform — source connectors, DuckDB schema, normalization transforms, merged views, and all structured storage schemas — that all other epochs depend on as their data substrate.

**Active work:** Phase 9 first increment implements dataset research packets:
source-aware context harvested during ingest, usefulness states, missing-context
labels, packet coverage reporting, and manual verification support.

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
| Phase 9 | Research-grade metadata enrichment — dataset research packets, source-aware context, usefulness states, and packet coverage reports | In progress | 33 focused DB tests; full suite 517 passed / 9 config-routing failures | — | `docs/testsPlans/manualTestPlan_db_phase9_dataset_research_packets.md` |

Active test plan: `docs/testsPlans/manualTestPlan_db_phase9_dataset_research_packets.md`

---

## Open Backlog

### Phase 9 — Research-Grade Metadata Enrichment

Current dataset records are often too sparse to support learning or local research
interpretation. The DB epoch needs a feature that separates "dataset exists" from
"dataset is interpretable enough to support a research workflow."

**Primary objective:** enrich source-specific tables and merged views with the
metadata fields most useful for understanding what a dataset represents, how it was
collected, and whether it can be compared with other datasets.

**Priority order:**

1. Publication linkage: DOI and paper URL are the highest-impact fields because
   they let the user inspect the methods section when structured metadata is absent.
2. Orientation fields: subject count and cognitive paradigm are the next most useful
   fields for quickly understanding whether a dataset is relevant.
3. Research comparability fields: acquisition, preprocessing, and modeling metadata
   determine whether maps or measurements can be compared across collections.

**Metadata contract by category:**

| Category | Fields |
|---|---|
| Publication and attribution | DOI, paper URL, journal name, authors, publication status |
| Participants | Subject count, age mean, age min, age max, handedness, proportion male, inclusion criteria, exclusion criteria, group comparison flag, group description |
| Experimental design | Design type, number of imaging runs, number of experimental units, run length, block length, trial length |
| Scanner and acquisition | Scanner make, scanner model, field strength, pulse sequence, repetition time, echo time, flip angle, field of view, matrix size, slice thickness |
| Preprocessing pipeline | Motion correction, slice timing correction, B0 unwarping, intersubject registration, software used for each, smoothing FWHM, coordinate space, target template, resampled voxel size |
| Modeling | Hemodynamic response function, temporal derivatives flag, dispersion derivatives flag, motion regressors, high-pass filter method, intrasubject model type, group model type, group inference type |

**Implementation shape:**

- Add nullable structured metadata fields or a normalized research-metadata table
  keyed by `(source, source_id)`, preserving raw source metadata in `metadata_json`.
- Add connector enrichment hooks that populate the fields when source APIs expose
  them directly.
- Add DOI/paper URL recovery as the first enrichment pass. If a source provides only
  a title or accession, use source metadata and literature lookup to populate DOI,
  paper URL, authors, journal, and publication status with provenance.
- Track field-level provenance and confidence where values are inferred rather than
  directly supplied by the source API.
- Expose metadata coverage in query surfaces so users can distinguish sparse records
  from research-ready records.

**Acceptance criteria:**

- A field-coverage report shows non-null rates for every Phase 9 field by source.
- At minimum, DOI or paper URL coverage improves for NeuroVault, DANDI, OpenNeuro,
  and Allen Brain records where source metadata or linked publication data supports it.
- `v_all_datasets` or a companion view exposes DOI/paper URL, subject count,
  cognitive paradigm, and a metadata completeness score for quick filtering.
- Records with insufficient metadata remain visible but are labeled as sparse rather
  than silently treated as research-ready.

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
