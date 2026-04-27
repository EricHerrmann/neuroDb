# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NeuroDb is focused on building an end-to-end, reproducible NeuroAI workflow with a practical local data platform.

Primary goal:
- Develop an agentic AI capability that ingests real neuroscience datasets and produces trustworthy, testable insights about brain plasticity.

DB epoch goal (current execution focus):
- Create a local database that collects from publicly available neuroscience data projects.
- Deliver an MVP that can pull, merge, view, and query public neuro datasets.

## Goal-to-Epoch Mapping

### Goal Summary
- Applied AI execution on real data (not toy demos).
- Evidence-grounded hypothesis testing with measurable outcomes and confound controls.
- Reproducible research practices with traceable lineage.
- Translation-ready outputs with uncertainty and limitations clearly stated.

### DB Epoch (MVP)
- Ingest data from selected public neuroscience sources.
- Normalize and merge metadata into a local DB.
- Provide basic read/query capabilities for exploration and downstream analysis.
- Keep lineage and provenance fields so runs can be audited and repeated.

## Current Repository State

- This repo currently contains planning content (`NeuroDbGoals.md`) and no production pipeline code yet.
- Prioritize establishing project structure, ingest contracts, schema, and reproducibility scaffolding first.

## Recommended Technical Baseline

Use these defaults unless a stronger reason emerges during implementation:

- Python for ingestion/transformation/query tooling
- Local relational store (SQLite for MVP, portable and simple)
- Reproducible environment tooling (`uv` + pinned dependencies)
- Clear separation of:
  - source connectors,
  - normalization transforms,
  - storage layer,
  - analysis/report generation

## Development Process

Follow this order:

1. Define data contracts and schema before writing ingest code.
2. Build one source connector end-to-end (ingest -> normalize -> store -> query).
3. Add provenance/lineage fields from day one.
4. Expand to additional sources only after first connector is reproducible.
5. Add hypothesis/testing/report layer once data layer is stable.

## Testing and Reproducibility Requirements

Minimum expectations for all changes:

- Unit tests for transforms and schema validation
- Integration tests for one full ingest path with deterministic fixture data
- Re-run test proving idempotent ingest behavior
- Query tests proving merged records are visible and searchable
- Documentation for:
  - source version/date,
  - transform version,
  - run timestamp,
  - known limitations

## Environment and Secrets

- API keys and secrets live in `.env` in the repo root (gitignored).
- Every entry point (Streamlit app, CLI scripts) must call `load_dotenv()` from `python-dotenv` before reading any environment variable.
- Never hardcode keys or read `os.environ` for secrets without a preceding `load_dotenv()`.
- `.env` is never committed; `.env.example` with placeholder values should be kept if one exists.

## Coding Standards

1. Keep implementation simple and explicit; avoid premature abstractions.
2. Identify root cause before fixing issues; do not guess.
3. Preserve reproducibility over convenience.
4. Every data-changing operation should be traceable.
5. Keep planning and execution artifacts in-repo and versioned.

## Working Documentation

Maintain planning and progress docs in this repository root (or `docs/` when added).

Start from:
- `NeuroDbGoals.md`

When adding implementation, also add:
- architecture note,
- data source registry,
- schema documentation,
- runbook for ingest and verification.
