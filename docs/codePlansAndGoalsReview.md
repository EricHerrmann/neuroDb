# Code, Plans, and Goals Review

Date: 2026-04-28
Scope: assess how well the current implementation matches the stated plans and overall project goals

## Executive Summary

The repository is meeting the DB epoch goal substantially better than the top-level root docs imply. The codebase now contains a working local neuroscience data platform with:

- DuckDB as the primary local store
- four ingested public sources
- a unified dataset view
- CLI and Streamlit query surfaces
- study-tag capture
- semantic search via ChromaDB
- an agent layer with session-context work in progress

The implementation is not yet meeting the full project goal of producing trustworthy, testable insights about brain plasticity. The platform substrate is real, but the hypothesis, confound-control, uncertainty, and reproducible report layers are still mostly absent.

## Current Evidence

### Repository state

- The project is no longer “planning only.”
- Core implementation lives under `src/neurodb/`, with tests under `tests/` and CLI entry points under `scripts/`.
- The current worktree shows Agent P4 context-persistence work in progress.

### Test and data state

- Automated verification: `uv run pytest` passed with 119 tests.
- Current local DuckDB contents:
  - total datasets in `v_all_datasets`: 149
  - sources represented: OpenNeuro, Allen Brain, NeuroVault, DANDI
  - ingest runs recorded: OpenNeuro 2, Allen Brain 2, NeuroVault 1, DANDI 4

### Current DB summary from `neurodb.duckdb`

| Source | Modality | Datasets | Total subjects |
|---|---:|---:|---:|
| allen_brain | ISH | 39 | 0 |
| dandi | None | 10 | 0 |
| neurovault | fMRI | 50 | 0 |
| openneuro | eeg | 17 | 846 |
| openneuro | meg | 3 | 131 |
| openneuro | mri | 21 | 507 |
| openneuro | nirs | 3 | 30 |
| openneuro | None | 6 | 168 |

## Alignment With Stated Goals

### Goal 1: Applied AI execution on real neuroscience datasets

Status: mostly met for the platform layer

Evidence:
- Real public datasets are ingested from multiple sources.
- The project has a usable local DB, UI, semantic search, and an AI-agent interface.

Remaining gap:
- The AI layer currently helps exploration and tagging more than hypothesis execution.
- The system is not yet producing research-grade outputs.

### Goal 2: Evidence-grounded hypothesis testing with measurable outcomes and confound controls

Status: not yet met

Evidence:
- There is query capability.
- There is no implemented hypothesis pipeline with structured metrics, confound handling, or repeated evaluation workflow.

Remaining gap:
- No hypothesis registry.
- No reusable analysis runner for named questions.
- No explicit confound-control framework.

### Goal 3: Reproducible research practices with traceable lineage

Status: partially met

Evidence:
- `ingest_runs` and `run_id` tracking exist.
- Tests are strong for the current scope.
- Scripts and docs describe reproducible local execution.

Remaining gap:
- Provenance is present but still lightweight.
- The project does not yet appear to record source snapshot hashes, report-time DB hashes, or analysis manifests.
- Session summary persistence currently swallows errors silently, which is operationally pragmatic but weak from an auditability standpoint.

### Goal 4: Translation-ready outputs with uncertainty and limitations clearly stated

Status: not yet met

Evidence:
- No report-generation layer for research outputs is implemented yet.
- The current user-facing outputs are mainly DB/UI exploration and chat responses.

Remaining gap:
- No mini-report templates.
- No explicit uncertainty or limitations sections generated from analysis.
- No clinician/researcher-ready artifact path yet.

## Alignment With The DB Epoch Plan

### What is clearly achieved

The implementation aligns well with the plan through the platform-building phases:

- Phase 0: scaffolding and schema
- Phase 1: first connector ingest
- Phase 2: MVP UI
- Phase 3: multi-source unified view
- Phase 4: query layer
- Phase 5: DuckDB migration
- Phase 6: NeuroVault and DANDI
- Agent P1-P3: study tags, embeddings, agent interface

The repository content and test surface support the claim that these phases are substantively implemented.

### What is only partially achieved

- Agent P4 context persistence appears to be in progress rather than fully closed.
- The field-coverage audit path needs maintenance before it can serve as a clean Phase 7 decision gate, because `scripts/field_coverage_audit.py` still targets SQLite defaults.

### What is not yet achieved

- Phase 7 entity resolution is still pending.
- Phase 8 hypothesis and structured reporting is still not started in the implementation.

## Completeness Assessment

There are two honest ways to score completeness, and they should not be conflated.

### 1. DB epoch platform completion

Estimated completion: 75-85%

Reasoning:
- The local data platform objective is largely real now.
- Core ingest, merge, view, query, and UI capabilities exist.
- Four sources are already integrated.
- The remaining DB-epoch gaps are mainly Phase 7 decision work, hardening, and analysis/reporting on top.

### 2. Overall project-goal completion

Estimated completion: 50-60%

Reasoning:
- The platform substrate is strong.
- The actual science-facing objective, trustworthy hypothesis-driven NeuroAI outputs, still depends on Phase 8-style work that has not been built yet.
- The current system is better described as a capable data and exploration foundation than as an end-to-end research insight engine.

## Main Gaps Between Code And Intent

1. The codebase has a working platform, but the root goal still points toward hypothesis-driven insight generation. That layer is missing.
2. Provenance exists, but not yet at the level implied by “trustworthy, testable insights.”
3. Subject-level and cross-source linkage are still thin. `cross_refs` remains effectively dormant, and most connectors stub `fetch_subjects()`.
4. Some operational scripts have drifted from the current DuckDB architecture, which weakens confidence in plan execution discipline.

## Bottom Line

The project is meeting the DB epoch plan well and has clearly crossed from concept into implementation. It is not yet meeting the full research goal. The next major value inflection is not “add one more source.” It is to convert the current platform into a reproducible hypothesis-and-report workflow with better provenance exposure, better performance on hot paths, and clearer decision support around Phase 7 versus Phase 8.
