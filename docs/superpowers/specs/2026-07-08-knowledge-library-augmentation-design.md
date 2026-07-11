# Knowledge Library Augmentation — Design Spec

Date: 2026-07-08
Status: Approved design; workstreams 1–3 implemented 2026-07-08 (manual gate pending); workstream 4 future
Scope: Three implementation workstreams (1–3) plus one documented future workstream (4)

## Problem

A user asked the NeuroTutor agent to use the Knowledge Library to answer a question
about an author of an article that has full text in the library. The agent replied
that it did not have that information. Investigation showed the retrieval
infrastructure is healthy but the agent did not surface library content.

### Root cause (evidence-backed)

Ruled out (these work):
- `chunk_store` is wired end to end (`app.state.chunk_store` → `chat.py` →
  `NeuroTutorAgent(chunk_store=...)`). The `knowledge_chunks` Chroma collection holds
  ~973 chunks across 10 full-text papers (ids 2, 9, 10, 11, 14, 52, 53, 58, 62, 63).
- `search_full_text` returns strong matches when called (topic query on the Hopfield
  paper scores ~0.90; even an author-anchored query stays ~0.89, above the 0.25 floor).
- Default context mode is `contextual`, which instructs the agent to use retrieved
  context (not the training-first `general` mode).

Three compounding gaps explain the failure:

1. **No author/entity retrieval path exists.** `papers.authors_json` is NULL for every
   full-text paper; chunk metadata and summary metadata carry no authors; summary text
   contains no author names; and there is no tool to look up a paper by author/title/id.
   An author-keyed question cannot resolve an author to a paper.

2. **Content retrieval is tool-gated, and the gating misses this intent.** The injected
   context bundle (`_compact_context_lines`) contains only paper *titles*
   (`"- Knowledge hit: {title}"`), never summary bodies or full text. To get content the
   model must *choose* to call `search_full_text`, whose prompt trigger is limited to
   "quotation, specific claim, figure, or method." "Find information from an author"
   does not match, and `search_knowledge_library` returns only author-less summaries — so
   the model concludes it has nothing.

3. **Stale tier metadata hides that full text exists.** Summary-index metadata for
   full-text papers still reads `data_tier: "abstract"`/`"metadata"` (e.g. source 9,
   Hopfield, is `full_text` in DuckDB but `abstract` in the summary index). Nothing tells
   the agent quotable full text is available.

## Goals

- When a user explicitly references the Knowledge Library, the library is searched
  deterministically and either grounds the answer or the agent states plainly that the
  library was searched and had nothing relevant.
- Full-text acquisition populates the bibliographic metadata (authors, abstract, year,
  DOI/URL) that author/entity questions depend on.
- Full-text acquisition emits a domain event that reconciles derived stores so the
  three stores (DuckDB `papers`, `knowledge_chunks`, `knowledge_library`) cannot drift.

## Non-goals

- Re-summarizing papers when full text is acquired (deferred; changes content, not just
  consistency — trigger deliberately later).
- Reference/citation mining (documented as workstream 4; spec'd separately).
- Quality ranking by internal citation in-degree (premature at ~50 papers).

## Implementation order

**#2 (backfill) → #3 (event + reconciliation) → #1 (retrieval guarantee).**
Backfill produces authorship; reconciliation propagates it to the derived stores; the
retrieval guarantee then surfaces the now-correct data.

---

## Workstream 2 — Metadata backfill on acquisition

### Behavior

On full-text acquisition, fill only currently-NULL bibliographic fields on `Paper`.
Never overwrite a non-null curated field.

Source precedence:
1. **External by DOI** — Semantic Scholar / Crossref (already integrated for
   `search_literature`). Preferred; returns clean structured authors/abstract/year.
2. **Document-parsed fallback** — used only when there is no DOI to resolve.

Target fields: `authors_json`, `abstract`, `year`, and `doi`/`url` when resolvable.

### Interface

A backfill function, provider-agnostic and side-effect isolated:

```
backfill_paper_metadata(session, paper, *, metadata_client) -> BackfillResult
```

- Reads current `Paper` values; requests external metadata by DOI (fallback: title).
- Returns which fields were filled and their sources; writes only NULL fields.
- Pure decision logic (which fields to fill) is unit-tested without network.

Implementation notes (2026-07-08):
- The no-DOI fallback is an external **title** lookup (Semantic Scholar search +
  normalized-title match). No current parser extracts bibliographic metadata
  (`ParsedArtifact` carries none), so if both DOI and title lookup fail, fields stay
  NULL with a recorded warning. Extending parsers to emit document-parsed metadata
  is deferred.
- The write path is injected (`set_fields` callable) rather than passing a live
  `session`/`paper`: DuckDB rejects UPDATEs on FK-referenced `papers` rows, so the
  route supplies its FK-safe `_update_paper_fields`. Decision logic stays pure.

### Wiring

Called from the acquisition commit path in
`src/neurodb/api/routes/knowledge_library.py` (`acquire_full_text` 2a path, the 2b job,
and `fulltext_review` confirm), before the `FullTextAcquired` event is emitted so the
event handler sees populated authorship.

### Risks / handling

- External lookup may fail or return nothing → leave fields NULL, record a warning; never
  block acquisition.
- Parsed PDF metadata is noisy → only used when no DOI; still never overwrites curated
  values.

### Tests

- Unit: field-selection logic fills only NULL fields, never clobbers curated values.
- Unit: DOI-present prefers external; DOI-absent uses parsed fallback.
- Integration: acquire a fixture full-text paper with a DOI → `authors_json` populated.
- Idempotency: re-running backfill produces no change on already-filled fields.

---

## Workstream 3 — `FullTextAcquired` event + reconciliation

### Event mechanism

A small in-process event emitter — `src/neurodb/events.py`:

- A registry mapping event name → list of handlers, `subscribe(name, handler)` and
  `emit(name, **payload)`.
- Synchronous, in-process, single-process (no bus/queue — YAGNI for a local app).
- Synchronous-vs-async is orthogonal to event-driven: this is event-driven (acquisition
  is the trigger; handlers react) and runs in the same request.

`FullTextAcquired(source_id)` is emitted from the single shared commit point that all
three acquisition paths funnel through, after metadata backfill (workstream 2).

### Reconciliation handler (scope B)

Subscribes to `FullTextAcquired` and makes derived stores consistent with `papers`:

- Update the `knowledge_library` summary-index metadata `data_tier` → `full_text`.
- Push `authors` into `knowledge_chunks` metadata for the paper's chunks.
- Re-sync `year` / `currency_status` / `authors` across `papers`, the summary index, and
  the chunk index so they cannot disagree.

Constraints:
- **Idempotent** — re-acquiring the same paper reconciles to the same state; no dup rows,
  no dup Chroma entries (upsert by deterministic ids).
- **Auditable** — record an event row (what reconciled, when, which handlers ran). Reuse
  `QualityEvent` if it fits; otherwise a small dedicated events table (decided during
  implementation, before code, with the choice noted here).
  - **Decision (2026-07-08):** dedicated `event_log` table. `QualityEvent` does not
    fit: it requires a `run_id` FK to `ingest_runs` (no ingest run exists in the
    acquisition path) and its flag/severity semantics describe data-quality findings,
    not reconciliation audit. Table: `event_log(id, event_name, entity_id, handler,
    status, detail_json, created_at)` — append-only.

### Wiring

Handler registration happens once at app startup. Acquisition paths import and call
`emit("full_text_acquired", source_id=...)`; they do not call reconciliation directly
(decoupling — later handlers subscribe without changing acquisition).

### Tests

- Unit: emitter dispatches to all subscribed handlers; a handler error is isolated and
  recorded, not swallowed silently.
- Unit: reconciliation flips stale summary `data_tier` and writes authors into chunk
  metadata.
- Integration: acquire a fixture paper whose summary index has stale tier → after
  acquisition the summary metadata reads `full_text` and chunk metadata carries authors.
- Idempotency: emit twice → identical end state, no duplicate audit anomalies.

---

## Workstream 1 — Guaranteed Knowledge-Library use on explicit request

### Mechanism (orchestrator-run, deterministic)

Do not rely on model-forced `tool_choice` (provider-dependent; the task router may land
on Anthropic/Groq/others and a provider can ignore forcing). Instead the orchestrator
runs the search itself and injects results, reusing the existing
`build_context_bundle` → `prompt_block` pattern.

1. **Trigger detection** — a natural-language keyword/phrase detector on the user message
   ("knowledge library", "the library", "in the KB", "from the library", "look it up in
   the library", …). Extensible phrase list. Non-deterministic edges are accepted.
2. **Deterministic search on a flagged turn** — backend directly executes
   `search_full_text` with the user message; if it returns no grounded passages
   (abstract/metadata-tier paper), it falls back to `search_knowledge_library`.
3. **Mandatory injection** — results are injected as a full-content context block labeled
   as authoritative: "Knowledge Library results — you MUST ground on these or state
   explicitly that they were insufficient." (Contrast with today's title-only injection.)
4. **Visible surfacing** — a `searched library — full-text: M, summaries: N` line is
   emitted to the UI (SSE), so a silent skip is impossible.
5. **Empty case** — if both searches are empty, the injected block says so and the model
   is instructed to state plainly that the library was searched and had nothing relevant.

Non-flagged turns keep strengthened prompt guidance (a stronger rule than today's, but
unchanged mechanism) so ordinary topic questions still reach the library.

### Interface

- `detect_library_directive(message) -> bool` — pure, unit-tested against phrase list.
- Orchestrator hook on flagged turns that runs the searches and builds the mandatory
  block; integrates with the existing context-bundle assembly and the SSE
  `context_summary` / a new `library_search` event.

### Tests

- Unit: directive detector matches the phrase list and rejects near-misses.
- Unit: full-text-empty → summary fallback is invoked; both-empty → empty-state block.
- Integration: a flagged turn against a fixture library runs the search and emits the
  visible "searched library" line regardless of provider.
- Behavioral: flagged turn injects full-content results, not just titles.

---

## Workstream 4 — Reference mining (documented; separate spec, sequenced later)

Not implemented in this spec. Captured so the direction is coherent.

- **Value ordering:** discovery (references → acquisition candidates) is strong now;
  co-citation topic clustering needs corpus volume; in-degree "quality" is premature at
  ~50 papers and should be framed as *connectedness*, not quality, until the corpus grows.
- **When:** decoupled from the critical path — a new handler subscribing to the same
  `FullTextAcquired` event (workstream 3), running in the background (2b-style), plus a
  one-time backfill over the existing 10 full-text papers.
- **How:** prefer the Semantic Scholar references API (structured, already integrated)
  over PDF parsing; document-parse and LLM-extract only as fallbacks. Store a
  citation-edge table (`citing_paper_id` → `cited_ref`, nullable `resolved_paper_id`
  filled when the cited work is already in the library). Powers discovery, co-citation,
  and gap detection (works cited by many approved papers but absent from the library →
  ranked acquisition to-do).
- **Known bug to fix there:** References sections are likely being chunked into
  `knowledge_chunks` as quotable body text (keyword-dense noise that can false-match
  `search_full_text`). Structured extraction should pull references out of the quotable
  chunk stream.

---

## Cross-cutting requirements

- **Idempotency** across backfill, reconciliation, and acquisition (repo rule; re-runs
  must not duplicate records or diverge state).
- **Traceability** — reconciliation and metadata changes are recorded as auditable events.
- **Provenance preserved** — never overwrite curated non-null metadata; label source of
  backfilled values.
- **Manual test plans** — each user-visible workflow (the retrieval guarantee, acquisition
  backfill+reconciliation surfaced in the Knowledge Library UI) gets a manual test plan
  created before its implementation, per the project's manual-test-planning rule, each
  beginning with the `uv run pytest tests/ -q` prerequisite step.
