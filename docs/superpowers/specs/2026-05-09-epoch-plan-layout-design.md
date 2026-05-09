# NeuroDb Epoch Plan Doc Layout — Design Spec

**Date:** 2026-05-09
**Status:** Approved
**Applies to:** All six epoch plan docs in `docs/`

---

## Goal

Give each epoch plan doc a consistent layout that follows BLUF (Bottom Line Up Front): enough information in the first screen to decide whether deeper reading is needed, with supporting context available below. The primary job of each plan doc is status and navigation — not design rationale (that lives in specs) or test steps (that live in test plans).

---

## Design Principle: Two-Zone Layout

**Zone 1 — BLUF (visible on first screen):**
- Current state at a glance: status, active phase, when it was last touched, where the code lives
- Epoch goal in one sentence
- What is being built right now in 1–2 sentences
- Phases table: what was done, what is in progress, what is planned — with test counts, sign-off dates, and links to active test plans
- Open issues: what is blocking or deferred

**Zone 2 — Context (scroll to when needed):**
- Key decisions table: what was decided and where the rationale lives — not the rationale itself
- Epoch-specific section: storage schemas, class list, connector list, technology stack, or routing table — whichever is relevant to that epoch

Everything in Zone 2 is navigational. The content lives elsewhere; this doc holds the pointer.

---

## Template

```markdown
# NeuroDb — [Epoch Name] Epoch Plan

**Status:** [one-line current state]
**Last updated:** YYYY-MM-DD
**Epoch directory:** `src/neurodb/[dir]/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

[One sentence.]

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| ...   | ...   | ...    | ...   | ...      | ...       |

Active test plan: [link or "none"]

---

## Open Backlog

| Log ID | Issue |
|--------|-------|
| ...    | ...   |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| ...  | ...      | ...       |

---

## [Epoch-Specific Section]

[Section title and content vary by epoch — see Per-Epoch Sections below.]
```

---

## Field Definitions

### Header block

| Field | Rule |
|-------|------|
| `Status` | One line: current maturity plus the most salient fact (e.g., "Phase 5B complete — 398 tests; Phase 4 manual evals pending") |
| `Last updated` | Date this file was last meaningfully changed |
| `Epoch directory` | Primary source directory for this epoch |
| `Architecture reference` | Always points to the epoch architecture spec |

### Phases table

| Column | Rule |
|--------|------|
| Phase | Short label (e.g., "LT-1", "Phase 4") |
| Focus | One sentence: what capability this phase delivered or will deliver |
| Status | "Complete — YYYY-MM-DD", "In progress", or "Planned" |
| Tests | Automated test count at sign-off; "—" if not yet complete |
| Sign-off | Date signed off; "—" if not yet complete |
| Test plan | Link to manual test plan doc; "—" if none |

### Open Backlog

Each row is a `LOG-###` entry from `docs/testLog.md`. Include only open items that belong to this epoch. One line per issue; no details — the full entry is in the log.

### Key Decisions table

| Column | Rule |
|--------|------|
| Date | When the decision was made |
| Decision | One line: what was decided |
| Rationale | One line: why, or a pointer to the doc that explains why |

Decisions belong in this table only when they are non-obvious, would surprise a future reader, or constrain future work. Obvious implementation choices do not belong here.

---

## Per-Epoch Sections

Each epoch's Zone 2 section has a name and content type appropriate to that epoch:

| Epoch | Section name | Content |
|-------|-------------|---------|
| DB | Connectors + Owned Tables | Source connector list; DuckDB and ChromaDB tables owned by this epoch |
| Agent Core | Agent Classes + BaseAgent Contract | Concrete agent class list; the four-method contract (get_active_tools, build_system_prompt, execute_tool_block, config injection) |
| Tutor | Owned Storage | ChromaDB collections and DuckDB tables owned by the Tutor epoch |
| Research | Owned Storage | DuckDB tables owned by the Research epoch |
| UI | Technology Stack | Current UI technology; target technology; migration status |
| Config Control | Routing and Telemetry | Tier definitions; current routing table (tier → provider → model); telemetry task types (task_type, tier, max_tokens, producing code, routing key) |

---

## What Goes Where

| Content type | Where it lives | Rule |
|-------------|---------------|------|
| Phase status and test counts | Epoch plan — Phases table | Updated when status or count changes |
| Open issues | Epoch plan — Open Backlog (pointer) + `docs/testLog.md` (content) | Epoch plan holds Log ID and one-line description only |
| Decision rationale | Spec docs or design plans (Zone 2 key decisions table points there) | Not duplicated in epoch plan |
| Test steps and pass criteria | Manual test plan docs | Never in the epoch plan |
| Architecture and interface contracts | `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md` | Never duplicated in epoch plan |
| Current project focus across all epochs | `docs/projectStatus.md` | Epoch plans are the source; projectStatus summarizes |

---

## What Was Ruled Out

| Candidate | Decision | Reason |
|-----------|----------|--------|
| Decision rationale inline | Excluded | Grows stale; belongs in specs; epoch plan holds a pointer only |
| Architecture detail inline | Excluded | Already in epoch architecture spec; would duplicate |
| Test step detail | Excluded | Belongs in test plans; epoch plan links to them |
| Per-phase decision log | Excluded | Key decisions table is epoch-scoped, not phase-scoped; this is sufficient |
| Separate "Active Work" section | Excluded | Active phase row in the Phases table plus the header block Status line together communicate current focus without a third location |

---

## References

| Document | Purpose |
|----------|---------|
| `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md` | Epoch definitions, interface contracts, coupling rules |
| `docs/projectStatus.md` | Cross-epoch current status summary |
| `docs/testLog.md` | Issue log — source of truth for all LOG-### entries |
