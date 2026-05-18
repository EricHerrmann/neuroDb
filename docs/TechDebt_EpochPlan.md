# NeuroDb — Tech Debt Epoch Plan

**Status:** Planned
**Last updated:** 2026-05-13
**Epoch directory:** Cross-cutting
**Primary issues:** `LOG-057` — arguments should not be brittle or position-dependent; TD-5 — repeated implementation patterns should become deliberate extension points only where evidence supports it

---

## Epoch Goal

Reduce brittle call surfaces that allow valid-looking commands or function calls to
do the wrong thing because arguments are order-dependent, same-typed, or implicitly
bound by position. The goal is not stylistic purity; it is fewer manual-test
failures, safer refactors, and clearer public APIs.

---

## Scope

This epoch covers both command-line and Python call surfaces:

- CLI scripts where global options or shared options are position-sensitive.
- Public Python helpers where several same-type values are accepted positionally.
- Agent/model constructors with long positional signatures.
- Test helper APIs that normalize unsafe call patterns.
- Shared parser and request-object patterns that can be reused across scripts.
- Repeated implementation patterns where a small shared abstraction would reduce
  bugs, clarify ownership, or make additional providers/tools/panels easier to
  add.

Out of scope:

- External provider SDK signatures.
- Tiny private functions with one or two obvious positional identity arguments.
- Interface methods where positional order is a deliberate protocol, unless they
  pass several same-type values.
- One-off duplication without extension pressure or a demonstrated maintenance
  cost.

---

## Findings

### CLI Surfaces

Most scripts with only named options are already order-independent because
`argparse` can parse named flags in any order. The brittle case is subcommands:
`scripts/study.py` originally accepted `--db` only before the subcommand because it
was registered as a root parser option.

Current script inventory:

| Script | Current shape | Risk |
|---|---|---|
| `scripts/study.py` | Subcommands: `tag`, `list`, `search`, `delete` | Shared global options can become position-sensitive unless normalized before subcommand parsing |
| `scripts/ingest.py` | Flat named options | Low CLI order risk; still lacks shared parser helper |
| `scripts/query_cli.py` | Flat named options | Low CLI order risk |
| `scripts/enrich.py` | Flat named options | Low CLI order risk |
| `scripts/field_coverage_audit.py` | Flat named options | Low CLI order risk; default still references legacy `neurodb.db` |
| `scripts/migrate_to_duckdb.py` | Flat named options | Low CLI order risk |

### Python Call Surfaces

An AST scan for functions with four or more positional parameters found the
highest-risk call surfaces below. The concern is strongest when several arguments
are strings, IDs, paths, booleans, or optional values.

| Area | Examples | Risk |
|---|---|---|
| Study and embedding | `tag_dataset`, `embed_note`, `VectorStore.upsert_note`, `VectorStore.upsert_dataset` | Same-typed values like `source`, `source_id`, `concept_tag`, `section_ref`, and `note_text` are easy to swap |
| Research and discovery tools | `record_research_question`, `draft_hypothesis`, `run_suggest_import`, `run_suggest_learning_source`, `run_suggest_new_source` | Tool writers and tests pass several semantically distinct strings |
| Agent constructors | `BaseAgent`, `NeuroDbAgent`, `NeuroTutorAgent`, `NeuroResearchAgent` | Long constructor signatures invite positional super-call mistakes |
| Session/model plumbing | `SessionManager.__init__`, `ModelClient.create_message`, provider `create_message` methods | Many cross-cutting parameters; some may remain protocol-driven but should be keyword-only where owned |
| API/UI helpers | `_build_agent`, `_run_tag_dataset`, `_write_chat_session_row`, `_update_status` | Internal helper mistakes can silently affect user-visible behavior |

### Abstraction and Extensibility Surfaces

Review verdict: this is a real issue, but not uniformly across the codebase. The
strongest evidence is repeated setup, task, dispatch, and status-handling code
that has already produced manual-test friction or will be touched again when new
providers, tools, or panels are added. The connector layer is the clearest
counterexample: it now has useful base behavior for external dataset lookup, so
future work should extend that pattern rather than creating provider-specific
resolvers in each agent.

| Surface | Evidence | Review finding | Candidate direction |
|---|---|---|---|
| Script runtime setup | `scripts/ingest.py`, `scripts/query_cli.py`, `scripts/enrich.py`, `scripts/field_coverage_audit.py`, and `scripts/migrate_to_duckdb.py` repeat `load_dotenv`, DB-path handling, engine creation, `init_db`, and often `create_views` | Issue. Relative DB defaults and repeated setup have already caused confusion between root and frontend DB files | Add a small `neurodb.cli` or `neurodb.runtime` helper for dotenv loading, root-relative DB resolution, engine/init/view setup, and shared parser parents |
| API background tasks | Dataset import and research hypothesis review routes repeat task records, thread startup, status updates, and error capture | Issue. Duplicated task lifecycle code is likely to drift as more UI actions become background jobs | Add a shared task runner or `start_background_task` helper with a typed task record and consistent status/error semantics |
| Warning propagation | Study-log and knowledge-library routes both carry partial-success warnings for Chroma/vector failures | Issue. Warning behavior is user-facing and should remain consistent across write paths | Use a small result/warning wrapper or response helper for partial-success API responses |
| Agent tool registration and dispatch | DB, tutor, and research agents manually keep tool descriptions, allowed tool names, parser branches, and dispatch branches aligned | Likely issue. Adding a new tool currently requires edits in several places and can silently miss a mode | Introduce a `ToolSpec` registry that binds name, description/schema, handler, and mode eligibility; keep per-agent policy explicit |
| Connector lookup | DANDI, OpenNeuro, NeuroVault, and Allen now share `REFERENCE_PATTERNS`, `extract_source_id`, `fetch_by_id`, and `search_by_keyword` through the connector base | Partially addressed. This is the preferred extension point and avoids brittle per-provider agent code | Keep provider-specific URL/id parsing in connector classes and generic routing in discovery tools |
| Frontend mutation panels | Suggestions, research, knowledge library, and study-log panels repeat mutation, invalidation, loading/error, and card/action patterns | Moderate issue. The repetition is manageable now but will grow with UI-5 P2/P3 parity work | Extract focused hooks/components only around repeated interaction patterns; avoid generic page frameworks |
| Test setup | Unit and integration tests repeat in-memory DB setup, `init_db`, `create_views`, session creation, and `TestClient` setup | Issue. Repetition makes fixture drift likely and obscures test intent | Add pytest fixtures/factories for initialized DB sessions, vector-store-disabled clients, and seeded API apps |

---

## Standards

Use these defaults for new code and refactors:

1. CLI options must be order-independent unless they are true positional operands.
2. Shared CLI options such as `--db` must come from a common parser helper or an
   equivalent pre-parse normalization step.
3. Python functions may use positional arguments for one or two obvious required
   identity values.
4. Functions with multiple same-type values must make those values keyword-only
   or accept a typed request object.
5. Long constructors should use keyword-only parameters after dependency injection
   basics, or accept a config dataclass.
6. Tests should use the same safe call shape expected in production code.
7. Extract shared abstractions only when at least two call sites share behavior
   and there is evidence of extension pressure, bug risk, or duplicated tests.
8. Every new abstraction must have a clear owner, focused tests at its boundary,
   and at least one simplified call site in the same change.
9. Record deliberate "do not abstract yet" decisions when duplication is visible
   but not costly enough to justify a shared layer.

Recommended patterns:

```python
def tag_dataset(session, *, source: str, source_id: str, concept_tag: str, ...):
    ...
```

```python
@dataclass(frozen=True)
class StudyTagRequest:
    source: str
    source_id: str
    concept_tag: str
    section_ref: str | None = None
    note_text: str | None = None
```

```python
def parse_cli_args(parser, argv=None, *, global_options=("db",)):
    ...
```

---

## Phases

| Phase | Focus | Status | Acceptance Criteria |
|---|---|---|---|
| TD-1 | CLI argument normalization | Started | Every script has parser tests; shared/global options work before and after subcommands |
| TD-2 | Keyword-only public helpers | Planned | High-risk helpers reject accidental positional same-type values; call sites updated |
| TD-3 | Request/config objects | Planned | Tool writers and long constructors use dataclasses or schema objects where argument lists are too long |
| TD-4 | Enforcement | Planned | Lightweight AST lint/test identifies new high-risk positional signatures and undocumented CLI globals |
| TD-5 | Reusable abstractions and extension points | Logged | Review findings are recorded; implementation candidates are prioritized by duplicated behavior and extension pressure |

---

## TD-1 — CLI Argument Normalization

Immediate target:

- Finish `scripts/study.py` normalization and keep parser tests for `--db` before
  the subcommand, after the subcommand, as `--db=value`, and through the real
  `sys.argv` path used by command execution.
- Add parser tests for every script in `scripts/`.
- Extract shared CLI helpers only after at least two scripts need the same
  behavior; do not over-abstract a single case.

2026-05-13 review note: the first parser fix covered explicit `parse_args(argv)`
unit tests but still failed when the script was executed normally because
`parse_args(None)` let `argparse` reread the original `sys.argv`. TD-1 tests must
cover both direct parser calls and real command-entry behavior.

Acceptance:

- `uv run pytest tests/unit/test_*cli*.py -q` covers script argument parsing.
- Manual test docs can put `--db` wherever it reads naturally.

---

## TD-2 — Keyword-Only Public Helpers

Initial candidates:

- `src/neurodb/study.py::tag_dataset`
- `src/neurodb/embed_hooks.py::embed_note`
- `src/neurodb/vector_store.py::upsert_dataset`
- `src/neurodb/vector_store.py::upsert_note`
- `src/neurodb/discovery_tools.py::run_suggest_import`
- `src/neurodb/discovery_tools.py::run_suggest_learning_source`
- `src/neurodb/research_tools.py::record_research_question`

Approach:

- Convert one ownership area at a time.
- Update tests and call sites in the same change.
- Avoid broad mechanical rewrites across epochs unless the type of bug is already
  proven in that area.

Acceptance:

- High-risk helpers either enforce keyword-only parameters or accept a request
  object.
- Tests include at least one guard that accidental positional calls fail for a
  representative helper.

---

## TD-3 — Request and Config Objects

Initial candidates:

- `BaseAgent` and concrete agent constructors.
- `SessionManager.__init__`.
- `draft_hypothesis`.
- Background task/startup helpers that pass source IDs, task IDs, status strings,
  and model metadata together.

Approach:

- Prefer dataclasses for internal request/config objects.
- Prefer Pydantic models only at API boundaries.
- Keep provider adapter protocol compatibility explicit; do not force external SDK
  conventions into internal domain helpers.

Acceptance:

- Agent construction reads as named configuration, not as ordered slots.
- Research/tool request construction is auditable in tests and logs.

---

## TD-4 — Enforcement

Add a small repo-local check that reports:

- Functions with four or more positional parameters.
- Functions with three or more positional `str` parameters.
- `argparse` scripts with subcommands and root-only global options.

This check should initially be advisory. Once the backlog is clean enough, it can
become a CI/test requirement with allowlisted exceptions for protocol methods.

---

## TD-5 — Reusable Abstractions and Extension Points

Code-review finding: the codebase has several repeated patterns that should be
turned into small, owned abstractions, but the problem is not "duplication
everywhere." The right standard is evidence-based extraction: when adding another
source, tool, background job, or panel would require copy/paste plus local
variants, create a shared extension point.

Highest-priority candidates:

- Runtime setup helper for scripts: dotenv loading, root-relative DB path
  resolution, engine initialization, optional view creation, and shared parser
  parents for `--db`.
- API background task helper: create task record, start thread, mark running,
  capture result/error, and expose consistent task status.
- Agent tool registry: bind tool name, description/schema, mode eligibility, and
  handler so DB, tutor, and research agents do not manually duplicate dispatch
  tables.
- Test fixtures: initialized DB/session/client factories that hide repetitive
  setup while preserving explicit seeded data in each test.

Medium-priority candidates:

- Warning/result response helpers for partial-success write APIs.
- Frontend hooks/components for repeated mutation, invalidation, and task-status
  flows in UI-5 P2/P3.
- Connector metadata normalization helpers if research-grade metadata enrichment
  repeats the same DOI/paper/participant/paradigm extraction logic across
  providers.

Do not abstract yet:

- Provider-specific URL patterns beyond the existing connector base fields.
- Single-use CLI behavior in scripts that do not have subcommands or shared
  lifecycle needs.
- Generic frontend page frameworks; extract narrow interaction pieces instead.

Acceptance:

- Each abstraction removes duplicated behavior from at least two real call sites.
- Each abstraction has tests at the abstraction boundary and at least one updated
  consumer test.
- Adding a new dataset source, agent tool, background task, or UI mutation panel
  requires fewer files and less copy/paste than before.
- The epoch records any visible duplication intentionally left in place.

---

## Open Questions

- Should `query_cli.py`, `ingest.py`, and `enrich.py` share a common `--db`
  helper immediately, or wait until another subcommand script exists?
- Should DB-path defaults be centralized at the same time, since relative DB paths
  have already caused `frontend/neurodb.duckdb` confusion?
- Which helper APIs are public enough to require backwards-compatible shims during
  keyword-only conversion?
- Should the background task abstraction live under `src/neurodb/api/` because it
  is API-specific, or under a shared runtime module for possible CLI reuse?
- Should the agent tool registry be introduced before the next tool is added, or
  wait until UI-5 P2/P3 creates a concrete new dispatch case?

---

## References

| Document | Purpose |
|---|---|
| `docs/testLog.md` | `LOG-057` source issue |
| `scripts/study.py` | First observed CLI order bug and initial normalization candidate |
| `tests/unit/test_study_cli.py` | Parser tests for order-independent `--db` |
| `docs/testsPlans/deferredTestPlans/manualTestPlan_ui5_p1_data_integrity.md` | Manual test that exposed `--db` placement fragility |
