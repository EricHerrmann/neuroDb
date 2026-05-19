# Phase 3 — Claims, Evidence Links, and Question-Centered Workflow

**Date:** 2026-05-19
**Status:** Design approved — ready for implementation plan
**Owner:** Research epoch (agent tools); DB epoch (schema, migration, claim_store helper)
**Parent spec:** `docs/superpowers/specs/2026-05-18-learning-research-memory-refocus-design.md` Phase 3

---

## Goal

Add first-class `claims`, `evidence_links`, and `research_gaps` tables. Expand `ResearchQuestion` with a `topic_id` FK. Deprecate free-text `evidence_json` on hypotheses in favour of structured FK-based evidence links. Give the research agent six new tools so it can extract candidate claims from approved papers, ground hypothesis drafts in local sources, and explicitly track evidence gaps.

---

## Architecture

Three layers:

1. **Schema** — three new tables (`claims`, `evidence_links`, `research_gaps`), `ResearchQuestion` expanded with `topic_id`, `ResearchHypothesis` evidence fields made nullable.
2. **`claim_store` helper** — DB epoch module at `src/neurodb/db/claim_store.py`; owns all read/write for claims, evidence links, gaps, and question bundles. Nothing above it calls raw SQL against these tables.
3. **Research agent** — six new tools dispatching through the helper; no raw SQL in the agent layer.

---

## Schema Changes

### New `claims` table

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer PK | sequence |
| `paper_id` | FK → papers.id | not null, indexed |
| `text` | Text | not null |
| `claim_type` | String(32) | not null — `finding`, `limitation`, `method`, `question` |
| `status` | String(16) | not null, default `candidate` — `candidate`, `approved`, `rejected` |
| `created_at` | String(32) | not null |
| `updated_at` | String(32) | not null |

Claims must originate from an approved paper. The `paper_id` FK is not nullable.

### New `evidence_links` table

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer PK | sequence |
| `hypothesis_id` | FK → research_hypotheses.id | not null, indexed |
| `claim_id` | FK → claims.id | nullable |
| `paper_id` | FK → papers.id | nullable |
| `packet_id` | FK → dataset_research_packets.id | nullable |
| `note_id` | FK → study_notes.id | nullable |
| `link_type` | String(32) | not null — `supports`, `contradicts`, `contextualizes` |
| `created_at` | String(32) | not null |

CheckConstraint: exactly one of (`claim_id`, `paper_id`, `packet_id`, `note_id`) is non-null. The target is always a hypothesis. This pattern follows `StudyNote` anchors established in Phase 2.

### New `research_gaps` table

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer PK | sequence |
| `question_id` | FK → research_questions.id | nullable |
| `hypothesis_id` | FK → research_hypotheses.id | nullable |
| `description` | Text | not null |
| `gap_type` | String(32) | not null — `missing_dataset`, `missing_paper`, `missing_evidence`, `unsupported_claim`, `other` |
| `status` | String(16) | not null, default `open` — `open`, `resolved` |
| `created_at` | String(32) | not null |
| `updated_at` | String(32) | not null |

CheckConstraint: at least one of (`question_id`, `hypothesis_id`) is non-null. A gap must be anchored to a question or hypothesis (or both).

### `research_questions` changes

Add `topic_id INTEGER FK → topics.id` (nullable). Keep `topic_context` text column as legacy fallback for records that predate Phase 3. Valid status values: `open`, `active`, `closed`, `archived` — the existing `status` column already holds these; no column change required, only documentation of valid values.

### `research_hypotheses` changes

`evidence_json`, `datasets_json`, and `confounds_json` become nullable. Existing rows retain their free-text data as archival reference. The agent no longer writes to these fields for new hypotheses; it creates `EvidenceLink` rows instead. When evidence links exist for a hypothesis the agent uses them; when none exist it may fall back to reading `evidence_json` as legacy context.

No automatic conversion of existing `evidence_json` entries to FK-based `EvidenceLink` rows — the free-text evidence items carry no paper or claim IDs and cannot be reliably resolved to DB objects without human review.

---

## Migration

**Script:** `scripts/migrate_phase3_claims_evidence.py`

Steps run in order, idempotently (each step checks current state before executing):

1. `Base.metadata.create_all(engine, checkfirst=True)` — creates `claims`, `evidence_links`, `research_gaps` if not present.
2. Add `topic_id INTEGER` to `research_questions` — skip if column exists.
3. `ALTER TABLE research_hypotheses ALTER COLUMN evidence_json DROP NOT NULL` — skip if already nullable.
4. `ALTER TABLE research_hypotheses ALTER COLUMN datasets_json DROP NOT NULL` — skip if already nullable.
5. `ALTER TABLE research_hypotheses ALTER COLUMN confounds_json DROP NOT NULL` — skip if already nullable.

The script uses `NEURODB_DB_PATH` env var, defaulting to `"neurodb.duckdb"`. DuckDB-specific `ALTER COLUMN DROP NOT NULL` syntax is used, same as Phase 2 migration.

---

## `claim_store` Helper

**File:** `src/neurodb/db/claim_store.py`

All functions take a SQLAlchemy `Session` as first argument. Follows the same conventions as `topic_store.py`.

```python
# --- Claims ---

def create_claim(session: Session, paper_id: int, text: str, claim_type: str) -> Claim
# Creates a claim with status=candidate. Raises ValueError for unknown claim_type.

def update_claim_status(session: Session, claim_id: int, status: str) -> dict
# Returns {"id": ..., "status": ...}. Raises ValueError for unknown status.

def get_claims_for_paper(session: Session, paper_id: int) -> list[dict]
# Returns [{id, text, claim_type, status, paper_id}, ...]

def get_approved_claims_for_topic(session: Session, topic_id: int) -> list[dict]
# Returns approved claims from papers linked to the topic via paper_topics.
# Returns [{id, text, claim_type, paper_id, paper_title}, ...]

# --- Evidence links ---

def add_evidence_link(
    session: Session,
    hypothesis_id: int,
    link_type: str,
    *,
    claim_id: int | None = None,
    paper_id: int | None = None,
    packet_id: int | None = None,
    note_id: int | None = None,
) -> EvidenceLink
# Raises ValueError if zero or more than one source FK is provided.
# Raises ValueError for unknown link_type.

def get_evidence_links(session: Session, hypothesis_id: int) -> list[dict]
# Returns [{id, link_type, source_type, source_id, summary}, ...]
# source_type is "claim" | "paper" | "dataset" | "note"
# summary is a short label derived from the source object

# --- Gaps ---

def add_gap(
    session: Session,
    description: str,
    gap_type: str,
    *,
    question_id: int | None = None,
    hypothesis_id: int | None = None,
) -> ResearchGap
# Raises ValueError if both question_id and hypothesis_id are None.
# Raises ValueError for unknown gap_type.

def resolve_gap(session: Session, gap_id: int) -> dict
# Returns {"id": ..., "status": "resolved"}. Raises ValueError if gap not found.

def get_gaps(
    session: Session,
    *,
    question_id: int | None = None,
    hypothesis_id: int | None = None,
) -> list[dict]
# Returns open and resolved gaps filtered by question_id and/or hypothesis_id.
# Returns [{id, description, gap_type, status, question_id, hypothesis_id}, ...]

# --- Question bundle ---

def get_question_bundle(session: Session, question_id: int) -> dict
# Returns {} for unknown question_id, otherwise:
# {
#   "question": {id, question, status, topic_id},
#   "topic": {id, name, description} | None,
#   "hypotheses": [{id, title, status}, ...],
#   "claims": [{id, text, claim_type, paper_id, paper_title}, ...],
#   "gaps": [{id, description, gap_type, status}, ...]
# }
# claims = approved claims from papers linked to the question's topic
# gaps = all gaps (open and resolved) anchored to this question
```

---

## Research Agent Changes

**File:** `src/neurodb/agents/research_agent.py`

Six new tools added to `_RESEARCH_TOOLS`. All dispatch through `claim_store` helper via lazy imports to avoid circular imports.

### New tools

**`extract_claims`**
```json
{
  "name": "extract_claims",
  "description": "Extract candidate claims from an approved paper using the paper's summary and abstract. Stores each as a candidate claim for review.",
  "input_schema": {
    "type": "object",
    "properties": {
      "paper_id": {"type": "integer", "description": "ID of the approved paper to extract claims from."}
    },
    "required": ["paper_id"]
  }
}
```
Implementation: fetch paper by ID, construct a prompt from `title + abstract + summary`, call the model to produce a list of claim texts with types, persist each via `create_claim`. Returns the candidate list.

**`update_claim_status`**
```json
{
  "name": "update_claim_status",
  "description": "Approve or reject a candidate claim.",
  "input_schema": {
    "type": "object",
    "properties": {
      "claim_id": {"type": "integer"},
      "status": {"type": "string", "description": "approved or rejected"}
    },
    "required": ["claim_id", "status"]
  }
}
```

**`add_evidence_link`**
```json
{
  "name": "add_evidence_link",
  "description": "Attach a structured evidence link to a hypothesis from a claim, paper, dataset packet, or study note.",
  "input_schema": {
    "type": "object",
    "properties": {
      "hypothesis_id": {"type": "integer"},
      "link_type": {"type": "string", "description": "supports, contradicts, or contextualizes"},
      "source_type": {"type": "string", "description": "claim, paper, dataset, or note"},
      "source_id": {"type": "integer", "description": "ID of the source object"}
    },
    "required": ["hypothesis_id", "link_type", "source_type", "source_id"]
  }
}
```
Agent maps `source_type` + `source_id` to the correct nullable FK before calling `add_evidence_link` in the helper.

**`add_gap`**
```json
{
  "name": "add_gap",
  "description": "Record a named evidence gap for a research question or hypothesis.",
  "input_schema": {
    "type": "object",
    "properties": {
      "description": {"type": "string"},
      "gap_type": {"type": "string", "description": "missing_dataset, missing_paper, missing_evidence, unsupported_claim, or other"},
      "question_id": {"type": "integer"},
      "hypothesis_id": {"type": "integer"}
    },
    "required": ["description", "gap_type"]
  }
}
```

**`resolve_gap`**
```json
{
  "name": "resolve_gap",
  "description": "Mark an evidence gap as resolved.",
  "input_schema": {
    "type": "object",
    "properties": {
      "gap_id": {"type": "integer"}
    },
    "required": ["gap_id"]
  }
}
```

**`get_question_bundle`**
```json
{
  "name": "get_question_bundle",
  "description": "Retrieve the full workspace context for a research question: topic, hypotheses, approved claims, and open gaps.",
  "input_schema": {
    "type": "object",
    "properties": {
      "question_id": {"type": "integer"}
    },
    "required": ["question_id"]
  }
}
```

### System prompt addition

One sentence appended to `_RESEARCH_SYSTEM_PROMPT`: *"Before answering a research question, call get_question_bundle to retrieve the active topic, hypotheses, approved claims, and open gaps; use add_evidence_link to ground hypothesis drafts in local sources rather than free-text evidence; use add_gap when local evidence is insufficient to support a claim."*

### `draft_hypothesis` change

The `evidence` parameter in the tool schema changes from required to optional (default empty list). The agent is expected to call `add_evidence_link` after drafting to attach structured evidence rather than embedding free-text evidence items in the draft call.

---

## Testing

### Unit tests

**`tests/unit/test_schema_claims.py`**
- `Claim`, `EvidenceLink`, `ResearchGap` tables have all expected columns
- `EvidenceLink` CheckConstraint rejects zero-source rows
- `EvidenceLink` CheckConstraint rejects two-source rows
- `EvidenceLink` CheckConstraint accepts each single-source combination
- `ResearchGap` CheckConstraint rejects rows with both `question_id` and `hypothesis_id` null
- `ResearchGap` CheckConstraint accepts question-only and hypothesis-only rows

**`tests/unit/test_claim_store.py`**
- `create_claim` persists with `status=candidate`
- `update_claim_status` approves and rejects correctly; rejects unknown status
- `get_claims_for_paper` returns only claims for the requested paper
- `get_approved_claims_for_topic` returns only approved claims from papers linked to the topic
- `add_evidence_link` idempotency — second call with same args does not duplicate
- `add_evidence_link` raises ValueError for zero sources
- `add_evidence_link` raises ValueError for two sources
- `get_evidence_links` returns correct shape with `source_type` and `summary`
- `add_gap` persists correctly; raises ValueError when both anchors are None
- `resolve_gap` changes status to `resolved`; raises ValueError for unknown ID
- `get_gaps` filters by `question_id` and `hypothesis_id` independently
- `get_question_bundle` returns correct shape; returns `{}` for unknown ID

**`tests/unit/test_migrate_phase3.py`**
- DuckDB in-memory; migration runs clean against a fresh DB
- `claims`, `evidence_links`, `research_gaps` tables created
- `topic_id` column present on `research_questions`
- `evidence_json`, `datasets_json`, `confounds_json` are nullable on `research_hypotheses` after migration
- Re-running migration does not raise

### Integration test

**`tests/integration/test_phase3_evidence_bundle.py`**
- Create a research question linked to a topic; call `get_question_bundle`; assert correct shape
- Create a paper, approve a claim from it, link paper to topic; assert claim appears in bundle
- Add evidence links of each source type to a hypothesis; assert `get_evidence_links` returns all four
- Add a gap to a question; assert it appears in bundle; resolve it; assert status updated
- Hypothesis with no evidence links: `get_evidence_links` returns empty list

---

## Acceptance Criteria

- A research question linked to a topic can return hypotheses, approved claims, and open gaps via `get_question_bundle` — verified by integration test
- Hypothesis drafts can be grounded via `add_evidence_link` for all four source types — verified by integration tests
- `EvidenceLink` CheckConstraint enforces exactly-one-source — verified by unit tests
- `ResearchGap` persists, resolves, and appears in question bundle — verified by integration test
- All existing research agent tools continue to work after `draft_hypothesis` evidence parameter becomes optional — verified by existing tests

---

## Out of Scope

- UI pages for claims or gaps — Phase 5
- API routes for claims, evidence links, or gaps — Phase 5
- Semantic (ChromaDB) search over claims — Phase 4
- Context modes (`General`, `Contextual`, `Grounded`) — Phase 4
- Claim extraction prompt tuning or model-tier selection — Phase 6
- Automatic conversion of existing `evidence_json` to structured links
