# Codex DB Epoch Plan

**Date:** 2026-04-11  
**Author:** Codex  
**Source Requirements:** `NeuroDbGoals.md`

## Summary

This plan defines the DB Epoch for NeuroDb: build a local, reproducible neuroscience data platform that can **pull, merge, view, and query** public neuro databases, then support hypothesis-oriented analysis for brain plasticity research.

The plan is intentionally staged:
- start with a reliable single-source ingest and traceable lineage,
- expand to multi-source ingestion and merge logic,
- ship an MVP UI for data access and filtering,
- then add analysis/reporting workflows with explicit uncertainty and confound handling.

The recommended MVP database is **SQLite** for speed and simplicity, with a migration-ready architecture so the project can move to Postgres/DuckDB/graph storage later if scale or query needs require it.

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
5. Produce one mini-report template with findings + limitations.

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

### Option C: **Federated Query Only (No local consolidated store)**
Query sources live or through adapters; compose responses at query time.

**Pros**
- Minimal local storage needs
- Always freshest source data
- No large local ETL pipeline

**Cons**
- Reproducibility is weaker (source drift over time)
- Higher operational fragility (API outages/rate limits)
- Slower, harder-to-debug user experience

## Recommendation
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

## Alternative 1: PostgreSQL
**Pros**
- Strong concurrency and reliability
- Mature indexing/extensions ecosystem
- Good long-term production path

**Cons**
- More operational setup than SQLite
- Heavier local development footprint

## Alternative 2: DuckDB
**Pros**
- Strong analytical performance for local workflows
- Great for columnar/OLAP-style neuroscience dataset exploration
- Easy local file-based usage

**Cons**
- Less suited to high-concurrency transactional API patterns
- App integration patterns may require more care vs Postgres

## Alternative 3: Graph DB (e.g., Neo4j)
**Pros**
- Natural fit for relationship-heavy brain network and ontology queries
- Powerful traversals for connectivity-style questions

**Cons**
- Extra complexity and infrastructure
- Higher modeling overhead early in project
- Potential overkill for DB Epoch MVP

## Recommendation
- Start with **SQLite** for DB Epoch MVP.
- Design storage interface with migration path to **Postgres** (app serving) and/or **DuckDB** (analysis workloads).
- Consider graph DB only after clear relationship-query requirements are proven.

---

## 5) MVP UI Plan (DB Access)

## MVP UI Goals
- Allow non-technical exploration of ingested data
- Make lineage visible to support trust/reproducibility
- Support filters for source/modality/date/quality tags

## MVP UI Features
1. **Dataset Catalog Page**
   - list sources and dataset counts
   - last ingest time, source version/date
2. **Search + Filter Page**
   - keyword search
   - filters by source, modality, cohort tags, date range
3. **Record Detail View**
   - canonical fields
   - source-native raw snapshot
   - merge confidence + provenance chain
4. **Run History / Provenance View**
   - run_id, connector version, transform version, row counts, validation status

## MVP UI Non-Goals
- Full annotation workspace
- Advanced visual analytics dashboards
- Multi-user auth/permissions (unless needed by user request)

---

## 6) Phased Design + Implementation Plan

### Phase 0: Project Foundation (1 week)
**Deliverables**
- repository structure and coding standards
- config management (`.env.example`, run profiles)
- test harness and fixture strategy
- architecture and schema RFC draft

**Exit Criteria**
- baseline repo, CI checks, and dev runbook are in place

---

### Phase 1: Single-Source Vertical Slice (1-2 weeks)
**Deliverables**
- 1 connector for a public neuro source
- source-native storage + canonical table mapping
- provenance schema (`run_id`, source snapshot metadata)
- basic query API endpoints

**Exit Criteria**
- deterministic re-run yields expected stable results on fixture snapshot

---

### Phase 2: Multi-Source Ingest + Registry (2 weeks)
**Deliverables**
- 2nd/3rd connectors added
- dataset registry and metadata indexing
- source health/error reporting
- add-only cross-source discovery queries

**Exit Criteria**
- user can discover records across multiple sources from one query endpoint

---

### Phase 3: Merge Layer (2-3 weeks)
**Deliverables**
- canonical merge pipeline with confidence score
- merge rule config and explainability fields
- conflict handling policy (keep both + rank, or selected winner)

**Exit Criteria**
- merged entity view works with traceable provenance and confidence

---

### Phase 4: MVP UI (2 weeks)
**Deliverables**
- dataset catalog, search/filter, detail, and run history views
- API integration and pagination
- clear display of lineage + uncertainty/confidence

**Exit Criteria**
- user can pull up dataset, filter results, inspect record and provenance in UI

---

### Phase 5: Hypothesis Workflow + Mini-Report (2 weeks)
**Deliverables**
- pre-analysis plan template
- one hypothesis execution pipeline using DB outputs
- mini-report template including:
  - methods
  - findings
  - uncertainty
  - confounds/limitations

**Exit Criteria**
- reproducible report generated from versioned data + code

---

## 7) Testing and Validation Plan

## Unit Tests
- connector parsers
- normalization transforms
- merge rule functions
- confidence scoring logic

## Integration Tests
- source ingest -> normalize -> store -> query
- multi-source ingest end-to-end
- merge pipeline with known fixture truth set

## Reproducibility Tests
- same input snapshot + same transform version => same output checksum
- run metadata completeness checks

## Data Quality Tests
- required field completeness
- schema conformance
- duplicate detection and anomaly flags

## UI Tests (MVP)
- catalog rendering and pagination
- filter behavior and empty states
- record detail + provenance display
- API failure and retry UX

## Acceptance Test (DB Epoch)
- Demonstrate pull, merge, view, query across multiple public neuro datasets
- Generate one reproducible mini-report from DB-backed analysis

---

## 8) Risks and Mitigations

- **Risk:** source schema drift  
  **Mitigation:** versioned connectors, contract tests, fallback parsing

- **Risk:** incorrect merges across datasets  
  **Mitigation:** confidence scoring, explainability fields, manual override flags

- **Risk:** reproducibility gaps  
  **Mitigation:** immutable run metadata, source snapshots/checksums, deterministic transforms

- **Risk:** SQLite scalability limits  
  **Mitigation:** storage abstraction + migration scripts to Postgres/DuckDB

---

## 9) Immediate Next Actions

1. Finalize canonical schema v0.1 and provenance model.
2. Select first two public neuro sources for connector implementation.
3. Implement Phase 1 vertical slice with deterministic fixtures.
4. Stand up minimal query API and seed MVP UI skeleton.
5. Add reproducibility and lineage checks before adding more sources.

