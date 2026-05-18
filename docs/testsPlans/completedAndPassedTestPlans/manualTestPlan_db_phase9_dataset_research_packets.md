# Manual Test Plan - DB Phase 9 Dataset Research Packets

**Epoch scope:** DB - source-aware dataset research packet enrichment.
**Phases covered:** Learning and Research Memory Refocus Phase 1; DB Phase 9 research-grade metadata enrichment.
**Design source:** `docs/superpowers/specs/2026-05-18-learning-research-memory-refocus-design.md`
**Status:** Passed — signed off 2026-05-18.
**Date:** 2026-05-18
**Last updated:** 2026-05-18

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

**Automation boundary:** Automated tests own schema creation, helper behavior,
connector fixture extraction, and idempotent packet updates. This manual plan
verifies that a real local DB can be populated, inspected, and interpreted by an
operator without treating shallow dataset records as research-ready.

---

## Prerequisites

1. Automated test baseline is run before manual testing:

```bash
uv run pytest tests/ -q
```

Expected current baseline: `517 passed, 9 failed, 5 warnings`.

The expected failures are the existing config-routing failures already reflected
in `docs/projectStatus.md`: one knowledge-library default-model test, four
model-config tier tests, and four task-router tier tests. Pass: no new failures
beyond those already tracked in `docs/testLog.md` and the current
`docs/projectStatus.md` baseline, and the passed/warning counts do not
materially change except for intentional test additions documented with this
phase.

2. Start from a disposable DB path for manual verification:

```bash
export NEURODB_DB_PATH=/tmp/neurodb_phase9_packets.duckdb
```

Pass: the variable points to a disposable DuckDB file, not the primary
`neurodb.duckdb`.

3. Initialize and ingest a small fixture-backed or live sample.

Deterministic fixture-backed example:

```bash
uv run tests/manual/db_phase9_seed_packets.py --db "$NEURODB_DB_PATH" --source openneuro --limit 2
uv run tests/manual/db_phase9_verify_packets.py --db "$NEURODB_DB_PATH"
uv run scripts/dataset_packets.py --db "$NEURODB_DB_PATH" coverage
```

Broader fixture-backed example:

```bash
uv run tests/manual/db_phase9_seed_packets.py --db "$NEURODB_DB_PATH" --source all --limit 2
uv run tests/manual/db_phase9_verify_packets.py --db "$NEURODB_DB_PATH"
uv run scripts/dataset_packets.py --db "$NEURODB_DB_PATH" show --limit 10
```

Optional live-source examples:

```bash
uv run scripts/ingest.py --source openneuro --limit 3 --skip-embed --db "$NEURODB_DB_PATH"
uv run scripts/ingest.py --source dandi --limit 3 --skip-embed --db "$NEURODB_DB_PATH"
uv run scripts/ingest.py --source neurovault --limit 3 --skip-embed --db "$NEURODB_DB_PATH"
uv run scripts/ingest.py --source allen_brain --limit 3 --skip-embed --db "$NEURODB_DB_PATH"
```

Pass: at least one fixture-backed or live-source command populates the
disposable DB, `db_phase9_verify_packets.py` reports `PASS`, and coverage/show
commands display dataset research packet rows. If live network access is
unavailable, the fixture-backed helper is sufficient for this prerequisite.

---

## Manual Evals

### T1 - Ingest creates dataset research packets

Run a small ingest for at least one source, then inspect packet rows:

```bash
uv run scripts/ingest.py --source openneuro --limit 3 --skip-embed --db "$NEURODB_DB_PATH"
uv run tests/manual/db_phase9_verify_packets.py --db "$NEURODB_DB_PATH"
```

Pass: every ingested dataset has exactly one research packet. Packet rows include
source identity, source-native summary fields when available, usefulness state,
missing-context JSON, provenance JSON, and a harvest timestamp.

### T2 - Coverage report distinguishes sparse and enriched records

Run the coverage report:

```bash
uv run scripts/dataset_packets.py --db "$NEURODB_DB_PATH" coverage
```

Pass: output groups records by source and shows counts for total packets,
usefulness states, DOI/paper URL coverage, source summary coverage, topic
coverage, asset manifest coverage, and average missing-context count.

### T3 - Sparse records remain honest

Inspect one packet that lacks a DOI, paper URL, source summary, or task metadata:

```bash
uv run scripts/dataset_packets.py --db "$NEURODB_DB_PATH" show --limit 5
```

Pass: sparse or partial records remain visible but are labeled with missing
context. No row with only source/id/title-level data is marked
`research_context_ready` or `analysis_ready`.

### T4 - Re-ingest is idempotent

Run the same ingest again and re-run verification:

```bash
uv run scripts/ingest.py --source openneuro --limit 3 --skip-embed --db "$NEURODB_DB_PATH"
uv run tests/manual/db_phase9_verify_packets.py --db "$NEURODB_DB_PATH"
```

Pass: dataset packet count remains one per `(source, source_id)`, existing
packet rows are updated rather than duplicated, and coverage output remains
stable except for harvest timestamp/provenance updates.

---

## Completion Criteria

DB Phase 9 dataset research packet verification can be signed off when T1-T4
pass, or when failures are logged in `docs/testLog.md` and explicitly deferred
in `docs/projectStatus.md`.

**Result:** Complete and passed. T1-T4 signed off by user on 2026-05-18.
