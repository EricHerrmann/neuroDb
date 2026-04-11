# NeuroDb Agent Guide

## Mission

Build a practical, reproducible NeuroAI data foundation that ingests public neuroscience datasets and supports trustworthy hypothesis-driven analysis for brain plasticity research.

## Source of Truth

Primary requirements are defined in:
- `NeuroDbGoals.md`

If instructions conflict, prefer:
1. explicit user request,
2. `NeuroDbGoals.md`,
3. this file.

## Scope (Current Epoch)

Current DB epoch scope is MVP data platform delivery:
- pull from public neuroscience database projects,
- merge and normalize records,
- store in a local DB,
- support view/query workflows.

Out of scope for MVP:
- production cloud deployment,
- broad UI productization,
- advanced model training pipelines before data layer stability.

## Agent Operating Rules

1. Work from evidence and reproducibility, not assumptions.
2. Prefer small vertical increments (one connector fully working) over broad partial work.
3. Keep lineage metadata for every ingest run.
4. Treat hypothesis outputs as decision-support artifacts; include uncertainty and limitations.
5. Remove or avoid unrelated project-specific boilerplate.

## Execution Phases

### Phase 1: Data Foundation
- Define schema and source connector interface.
- Implement first source ingest with deterministic fixtures.
- Add normalization + provenance fields.

### Phase 2: Multi-Source Merge
- Add additional public neuro sources.
- Implement entity matching/merge rules.
- Add query layer for inspection and filtering.

### Phase 3: Reproducible Analysis
- Add hypothesis template and pre-analysis structure.
- Implement repeatable analysis runs tied to data versions.
- Generate concise reports with uncertainty/confound notes.

## Required Validation

For each significant change, run or provide:
- unit tests for parsing/transform logic,
- integration test for ingest-to-query path,
- idempotency test (re-ingest does not corrupt/duplicate unexpectedly),
- schema validation checks,
- a short verification note describing what was tested and what remains.

## Delivery Artifacts

When shipping increments, include:
- code changes,
- tests,
- updated schema/docs,
- run instructions,
- explicit assumptions and known gaps.

## Non-Goals

Do not import unrelated PM/Kanban project guidance.
Do not add features unrelated to NeuroDb goals without explicit request.
