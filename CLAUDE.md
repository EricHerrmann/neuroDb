# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NeuroDb is focused on building an end-to-end, reproducible NeuroAI workflow with a practical local data platform.

Primary goal:
- Develop an agentic AI capability that ingests real neuroscience datasets and produces trustworthy, testable insights about brain plasticity.

Current execution context:
- The local neuroscience data platform is implemented: public-source ingest, normalization, merged views, CLI query surfaces, and a Streamlit UI all run against the local DB.
- The learning-agent layer is implemented through context persistence: study tagging, semantic search, grounded agent chat, and cross-session memory all exist on top of the DB platform.
- Live phase status, test counts, sign-off dates, active focus, and next phase are tracked only in `docs/projectStatus.md`.

## Goal-to-Epoch Mapping

### Goal Summary
- Applied AI execution on real data (not toy demos).
- Evidence-grounded hypothesis testing with measurable outcomes and confound controls.
- Reproducible research practices with traceable lineage.
- Translation-ready outputs with uncertainty and limitations clearly stated.

### Current Platform Baseline
- Ingest data from the implemented public neuroscience sources into a local analytical DB.
- Normalize and merge metadata into shared views for exploration, querying, and downstream analysis.
- Keep provenance, lineage, and reproducibility metadata so runs can be audited and repeated.
- Extend the DB substrate with study tagging, semantic retrieval, and grounded agent workflows rather than treating the project as a greenfield MVP.

## Current Repository State

- This repo contains active implementation code, tests, manual test plans, and planning docs; it is no longer a planning-only repository.
- The current architecture uses DuckDB as the source of truth for structured data, with ChromaDB collections for semantic retrieval and agent-context memory.
- Implemented surfaces include source connectors, normalization/enrichment flows, provenance helpers, query modules, CLI entry points, a Streamlit UI, and agent/session-management modules.
- Use `docs/projectStatus.md` as the live source of truth for what phase is active; use this file for standing engineering rules and defaults.

## Recommended Technical Baseline

Use these defaults unless a stronger reason emerges during implementation:

- Python for ingestion/transformation/query tooling
- SQLAlchemy ORM/data-access layer over the local DB
- DuckDB as the default local relational and analytical store
- ChromaDB as the local semantic index and agent-context store
- Streamlit for the local interactive UI, with thin Python CLI entry points for ingest, enrich, query, and study workflows
- Reproducible environment tooling (`uv` + pinned dependencies)
- SQLite remains acceptable for fast unit tests or narrow compatibility cases, but it is not the default runtime backend
- Clear separation of:
  - source connectors,
  - normalization and enrichment transforms,
  - storage and query layer,
  - UI and agent/report generation layers

## Development Process

Follow this order:

1. Define data contracts and schema before writing ingest code.
2. Build one source connector end-to-end (ingest -> normalize -> store -> query).
3. Add provenance/lineage fields from day one.
4. Expand to additional sources only after first connector is reproducible.
5. Add hypothesis/testing/report layer once data layer is stable.

## Testing and Reproducibility Requirements

Minimum expectations for all changes:

- Define the test approach before implementation begins. For any phase, feature set, or user-visible workflow that will require manual verification, create or update its manual test plan in `docs/testsPlans/` before writing implementation code. Treat this the same way automated tests are treated: expected behavior and pass criteria should exist up front, not be reconstructed after the fact.
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

## Project Process Rules

### Project State Document

`docs/projectStatus.md` is the single source of current project state. It contains:
- Phase status table (phase name, status, test count, sign-off date)
- Active focus (what is being built right now)
- Next phase (what comes after the current focus)
- Goal alignment (one line mapping current work to the top-level project goal)
- Reference table (file path and one-line description for every source document)

`docs/projectStatus.md` does not contain design rationale, implementation detail, test steps, or any content that already exists in a source document. If content belongs in a source doc, put it there and add a reference here instead.

### Sync Rules

Update `docs/projectStatus.md` in the same commit as the change that triggers it. Triggers:

- A phase changes status (started, in progress, signed off, complete) → update the phase row
- Test count changes → update the count in the phase row
- Active focus changes → update the active focus line
- A new source document is created → add it to the reference table
- A source document is deleted or renamed → update or remove its reference entry

The following do not trigger a `docs/projectStatus.md` update:
- Bug fixes, test fixes, or refactors that do not change phase status or test count
- Internal implementation changes with no effect on project state
- Edits within source documents that do not change their purpose or scope

## Coding Standards

1. Keep implementation simple and explicit; avoid premature abstractions.
2. Identify root cause before fixing issues; do not guess.
3. Preserve reproducibility over convenience.
4. Every data-changing operation should be traceable.
5. Keep planning and execution artifacts in-repo and versioned.

## Documentation Standards

Apply the same clarity, consistency, and scope discipline to documentation as to code.

- When updating a doc, review the whole doc for drift — not just the section being changed.
- A doc that tracks completed history instead of current state has accumulated drift. Refactor it.
- Remove references, tables, and sections that no longer serve the reader's current need.
- Use one term for the same concept throughout. Inconsistent language is a doc smell the same way inconsistent naming is a code smell.
- A status doc that requires reading past three screens to find current state is too long.

## Manual Test Planning

Manual test plans are phase-gate artifacts, not post-hoc documentation.

- If a change introduces or materially changes a workflow that needs manual verification, create the manual test plan before implementation begins.
- If a suitable plan already exists, update it before implementation begins so it reflects the intended behavior of the incoming change.
- Add the new manual test plan to `docs/projectStatus.md` in the same step when the plan document is first created, following the normal source-document and active-test-plan sync rules.
- If implementation materially changes the intended workflow after the plan is written, update the plan in the same change that shifts the workflow.
- **Every manual test plan must include an automated-test prerequisite step.** The Prerequisites section of every manual test plan document must contain an explicit step that runs `uv run pytest tests/ -q` and defines pass criteria: no new failures beyond those already tracked in `docs/testLog.md`. This step is always listed first in Prerequisites.

When a test plan or test run document is updated to a passing or signed-off terminal state, update `docs/projectStatus.md` in the same step — phase row, active focus, and archived test plan table. This fires on the document update itself, not on a separate user request.

## Issue Log Protocol

Issues discovered during testing, reviews, or ad hoc exploration are logged in `docs/testLog.md`. The log is persistent and not tied to a specific phase or run.

**When the user types `LOG: ...`:**
- Append a row to the Open table in `docs/testLog.md` with a stable `Log ID`, today's date, a short issue ID, the description, and context
- Use the next sequential `LOG-###` value as the stable `Log ID`; never reuse a `Log ID`, even after an issue moves to Resolved
- Respond with only: `Logged: {id or short title}` — nothing else
- Do NOT investigate, diagnose, propose a fix, or ask clarifying questions
- Do NOT treat the log entry as a trigger to enter debugging or fix mode

The user controls when issues are addressed. Take no action on a logged issue until the user explicitly requests a review or fix. At that point, read the Open table, group related items, and propose a prioritized order before touching any code.

When an issue is resolved, move its row from Open to Resolved and add a brief Resolution note.

## Working Documentation

Maintain planning and progress docs in this repository root (or `docs/` when added).

Start from:
- `NeuroDbGoals.md`

When adding implementation, also add:
- architecture note,
- data source registry,
- schema documentation,
- runbook for ingest and verification.
