# Eric DB Epoch Plan -- merge of codex and claude

**Date:** 2026-04-11  
**Author:** Eric  
**Source Requirements:** `NeuroDbGoals.md`

## Summary

This plan defines the DB Epoch for NeuroDb: build a local, reproducible neuroscience data platform that can **pull, merge, view, and query** public neuro databases, then support hypothesis-oriented analysis for brain plasticity research.

The plan is intentionally staged:
- start with a reliable single-source ingest and traceable lineage,
- expand to multi-source ingestion and merge logic,

The recommended MVP database is **SQLite** for speed and simplicity, with a migration-ready architecture so the project can move to DuckDB storage later.

---

## 1) Goal Mapping from `NeuroDbGoals.md`

## Goal
Develop a practical, reproducible NeuroAI capability using real neuroscience data.

## DB Epoch Objective
Create a local DB that can ingest from public neuroscience projects and enable merged query access.

## MVP Success Definition
1. Ingest at least 2 public neuro datasets through repeatable connectors.
2. Normalize into a canonical schema with provenance metadata.
3. Support UI-based exploration (search/filter/detail view).
4. Support reproducible reruns with deterministic output from same source snapshots.

---

## 2) Architecture (MVP)

## Core Components
- **Connectors:** source-specific pull/parsing modules
- **Normalizer:** maps source fields to canonical schema
- **Storage:** local DB (SQLite initially)
- **Query API:** read-only endpoints for UI and analysis layer
- **MVP UI:** browse/search/filter datasets, entities, records, provenance
- **Lineage/Provenance:** source, version/date, run_id, transform version, timestamps

## Canonical Data Domains (initial)
- Dataset registry
- Study metadata
- Subject/cohort metadata (de-identified only)
- Modality/type tags (imaging, electrophysiology, etc.)
- Record-level source mapping
- Provenance and quality flags

---

## 3) Multi-Database Integration Strategy Options

### Option A: **Add-only Registry (No cross-source merge in DB)**
Each source is ingested into source-specific tables + a unified discovery index.

**Pros**
- Fastest to implement
- Low risk of incorrect entity resolution
- Easiest debugging and auditability

**Cons**
- Duplicate entities across sources remain unresolved
- Harder cross-dataset analysis
- User has to mentally reconcile records

### Option B: **Staged Canonical Merge (Recommended for MVP+)**
Ingest source-native tables first, then map into canonical merged entities with confidence scoring.

**Pros**
- Good balance of speed and analytical value
- Merge logic can evolve without re-pulling raw source
- Better support for cross-source querying

**Cons**
- Requires entity resolution rules and confidence handling
- More complex validation/testing
- Potential for merge errors if rules are weak

## Approach
- **Phase 1-2:** Option A -> Option B progression.
- Keep raw/source-native storage for auditability even after canonical merge.

---

## 4) Database Choice: SQLite vs Alternatives

## SQLite (MVP default)
**Pros**
- Zero-ops local deployment
- Portable single-file DB
- Excellent for local prototyping and deterministic testing
- Great fit for early schema evolution

**Cons**
- Limited write concurrency
- Not ideal for large-scale analytical workloads
- Fewer native advanced analytics/extension patterns than some alternatives

## Alternative 2: DuckDB
**Pros**
- Strong analytical performance for local workflows
- Great for columnar/OLAP-style neuroscience dataset exploration
- Easy local file-based usage

**Cons**
- Less suited to high-concurrency transactional API patterns
- SQLAlchemy integration is less mature than SQLite

## Recommendation Approved 
- Start with **SQLite** for DB Epoch MVP.
- Design storage interface with migration path to  **DuckDB** (analysis workloads).

