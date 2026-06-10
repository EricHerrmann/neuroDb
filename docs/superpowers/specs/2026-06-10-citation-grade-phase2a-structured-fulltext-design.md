# Citation-Grade Phase 2a — Structured-Source Full-Text RAG — Design

- **Date:** 2026-06-10
- **Status:** Design — pending user review
- **Epoch:** Tutor (write path) with read/consumer in Research
- **Parent spec:** `docs/superpowers/specs/2026-06-09-citation-grade-data-access-design.md` (this is the thin first slice of that spec's §6 "Phase 2")
- **Builds on:** Phase 1 (landed) — `Paper.data_tier`/`currency_status`, `temporal_descriptor`, tier/vintage/cutoff/currency disclosure on both agents.

---

## 1. Goal and boundary

Let the tutor and research agents **quote real paper text with provenance** for the papers the user marks citable — but only from **structured sources that arrive clean**, so no PDF parse-quality gate is needed yet.

For a paper the user explicitly acquires:
- Fetch full text from a structured source (arXiv HTML/LaTeX, PMC JATS XML, or user-supplied clean text).
- Chunk it on its own section structure, with section + character-offset provenance.
- Embed chunks into a **second** Chroma collection (`knowledge_chunks`), separate from the Phase 1 summary collection.
- Retrieve passages through a **dedicated quote tool** that applies a relevance threshold and returns provenance-anchored, **quote-verifiable** text.
- Upgrade the paper to `data_tier="full_text"` only on verified capture.

A paper with no clean structured source stays at `abstract` tier, recorded honestly as `full_text_status="unavailable"`. **No PDF is parsed and no arbitrary HTML is scraped in 2a** — that work is the deferred parse gate.

### Spec invariants satisfied in 2a

From the parent spec's eight invariants: **#1** tier-as-trust-contract (only `full_text` chunks are quotable, enforced structurally by collection separation), **#2** end-to-end provenance (every chunk carries source/section/offsets/text-source), **#3** retrieval relevance threshold (honest absence below it), **#4** quote verification (string match against stored chunks, with a fail-closed default — see §6), **#6** grounding disclosure (reused from Phase 1, extended to quotes), **#8** temporal trust modifier (reused from Phase 1, applied to quoted passages).

### Non-goals (2a — explicitly deferred to 2b/2c)

- OA PDF acquisition and the **Docling parse-quality gate** (`parse_confidence`, human confirmation view, fallback ladder).
- **Page anchors** (`page` column) — a PDF concept; structured sources carry sections/offsets, not stable pages.
- The formal **CI retrieval-eval harness** (invariant #5). 2a keeps a small fixture-based retrieval regression test, not the full measured harness.
- **Generic publisher HTML** ingestion via readability/boilerplate extraction.
- **Full automatic quote-correctness interception** — 2a verifies cooperatively via the `verify_quote` tool plus a ledger-reconciliation backstop (§6); re-deriving correctness of every quote span automatically is 2c.
- Retraction-notice lookup, preprint-vs-published version-staleness flagging.
- The **SPECTER2/SciNCL embedder upgrade** — 2a keeps the light CPU-friendly default behind the existing injected `embedder` interface (deferred-and-measured).

---

## 2. Architecture — new components

All flat modules, matching the repo convention (`literature_client.py`, `knowledge_store.py`, `temporal.py`):

| Module | Responsibility |
|---|---|
| `src/neurodb/full_text_client.py` | `FullTextBackend` protocol; `Section`/`FullTextResult`/`SuppliedInput` dataclasses; `ArxivSourceBackend`, `PmcJatsBackend`, `UserSuppliedBackend`; `FULL_TEXT_BACKENDS` list; `acquire(paper, http, supplied=None) -> FullTextResult \| AcquireFailure` orchestrator |
| `src/neurodb/chunking.py` | Pure `chunk_sections(sections, *, max_chars, overlap) -> list[Chunk]` — section-aware; splits oversize sections with overlap; carries `section`/`char_start`/`char_end` |
| `src/neurodb/chunk_store.py` | `ChunkStore` over the **second** Chroma collection `knowledge_chunks`: `add_chunks`, `delete_paper`, `search(query, n, min_score)` with the relevance threshold |
| `src/neurodb/quote_verify.py` | `normalize_quote(text)`; `verify_quote(text, chunks) -> QuoteMatch \| None`; `reconcile_quotes(answer_text, ledger) -> list[UnverifiedSpan]` (the backstop) |
| `src/neurodb/agents/full_text_tools.py` | Shared `FULL_TEXT_TOOLS` tool defs (`search_full_text`, `verify_quote`) imported by both agents, mirroring the existing `LEARNING_PLAN_TOOLS` / `READ_ONLY_DISCOVERY_TOOLS` pattern |

### Decision (a): separate `FullTextBackend`, not blocking on the search registry

The `FullTextBackend` protocol is a **separate, focused fetch interface**. It does **not** depend on the unlanded search-side `SourceBackend` registry (`2026-06-02-literature-source-registry-design.md`), and does **not** touch `literature_client.search()` (the hot path both agents rely on). Search and fetch are genuinely different operations:

| | Search (`literature_client.search`, exists) | Fetch (`full_text_client`, new) |
|---|---|---|
| Input | a query string | one already-chosen `Paper` |
| Output | a ranked candidate list | the full text of that one paper |
| Sources | PubMed, Semantic Scholar, arXiv as *discovery* APIs | arXiv (HTML/e-print), PMC (JATS) as *content* endpoints |

This is a **sequencing** choice, not a permanent fork: when the search registry lands, `FullTextBackend.fetch` can become the `fetch()` method on a unified backend, or the two registries reconcile. 2a deliberately declines to make that deferred refactor a prerequisite.

### 2.1 Interfaces

```python
@dataclass
class Section:
    label: str | None        # e.g. "Methods"; None for unlabeled/preamble
    text: str                # cleaned section text
    char_start: int          # offset into the normalized full text
    char_end: int

@dataclass
class FullTextResult:
    text_source: str         # arxiv_html | arxiv_src | jats | user_supplied
    sections: list[Section]
    full_text: str           # normalized concatenation (offsets index into this)

@dataclass
class SuppliedInput:
    url: str | None = None
    text: str | None = None
    format: str | None = None   # txt | md | jats

@dataclass
class AcquireFailure:
    status: str              # unavailable | failed
    reason: str              # e.g. needs_parser_phase2b | not_oa | fetch_error
    message: str             # human-readable, honest

class FullTextBackend(Protocol):
    name: str
    def can_handle(self, paper: Paper, supplied: SuppliedInput | None) -> bool: ...
    def fetch(self, paper: Paper, http: httpx.Client,
              supplied: SuppliedInput | None) -> FullTextResult | None: ...
```

`Chunk` (chunking output) carries `text, section, char_start, char_end, chunk_index`. `text_source` is attached at store time from the `FullTextResult`.

---

## 3. Data model

**Migration 024** (next free number; 023 is the latest registered):

`paper_chunks` table — the only place full text is embedded:

```
paper_chunks
  id            PK
  paper_id      FK -> papers.id, indexed
  chunk_index   int            # order within paper
  text          Text           # cleaned chunk text
  section       str | None     # e.g. "Methods"
  char_start    int | None     # offset into normalized full text
  char_end      int | None
  text_source   str            # arxiv_html | arxiv_src | jats | user_supplied
  chroma_id     str            # stable id in the knowledge_chunks collection
  created_at    str
```

New `Paper` columns:
- `full_text_status: str | None` — `verified | unavailable | failed` (null = never attempted).
- `text_source: str | None` — the winning backend's source label.

`data_tier` (from Phase 1) is set to `full_text` **only** when `full_text_status="verified"`. No `parse_confidence` column in 2a — there is no parse gate.

ChromaDB gets a **second collection** `knowledge_chunks`, distinct from the Phase 1 `knowledge_library` summary collection. Chunk metadata mirrors provenance so retrieval results are self-describing: `source_id, paper_id, chunk_index, section, char_start, char_end, text_source, title, year, currency_status, data_tier`.

---

## 4. Acquisition flow — the "Acquire full text" action

### Decision (c): synchronous

Trigger: `POST /api/knowledge-library/{source_id}/acquire-full-text` runs fetch → chunk → embed → store **inline** and returns the updated paper. Approve stays cheap (abstract tier, as today); acquisition is a distinct, re-runnable, human-triggered per-paper action (invariant #7 citable-intent), one paper at a time — not a bulk batch. Guards: a per-paper chunk cap and a request timeout. The `full_text_status` field is a natural place to add an `acquiring` state later if we move to background, so synchronous-now is an additive choice, not a corner.

Optional request body for user-supplied input:

```json
{ "url": "https://...", "text": "raw text", "format": "txt|md|jats" }
```

Empty body → auto-resolve from the paper's existing `url`/`doi`.

### 4.1 Routing (in `acquire`)

1. **Supplied text present** → `UserSuppliedBackend` (validate `format` ∈ `{txt, md, jats}`; `txt`/`md` → single/heading-split sections, `jats` → JATS parse). `text_source = user_supplied` (or `jats`).
2. **Candidate URL** = `supplied.url or paper.url`:
   - Resolves to an **arXiv id** → `ArxivSourceBackend`: fetch `arxiv.org/html/{id}` (preferred, section-tagged); fall back to `e-print` LaTeX source. `text_source = arxiv_html | arxiv_src`.
   - Resolves to a **PMC/PMID** (NCBI ID-converter `pmid`/`doi` → `pmcid`) → `PmcJatsBackend`: efetch JATS XML, **OA subset only**; parse `<sec>` → `Section`s. `text_source = jats`. Non-OA → `AcquireFailure(unavailable, not_oa)`.
   - Otherwise fetch the URL and inspect `Content-Type`:
     - `text/plain` / `text/markdown` → clean-text path (`user_supplied`).
     - JATS XML → `PmcJatsBackend` parser path.
     - **generic `text/html` or `application/pdf`** → `AcquireFailure(unavailable, needs_parser_phase2b)` with an honest message ("this looks like a publisher HTML/PDF page — full-text capture for those arrives in Phase 2b; paste the text or supply a `.txt`/`.md`/JATS file"). Paper stays at `abstract` tier.
3. **No source resolved / fetch failed** → `AcquireFailure(unavailable | failed, …)`. Re-runnable.

### 4.2 Acceptable user-supplied sources (2a)

| Source form | Accept in 2a? | Why |
|---|---|---|
| Pasted text / uploaded `.txt`, `.md` | ✅ | Already clean; `text_source=user_supplied` |
| Uploaded JATS `.xml` | ✅ | Structured, section-tagged |
| URL → arXiv id or PMC id | ✅ | Routes to the structured backends |
| URL → `Content-Type: text/plain` / `text/markdown` | ✅ | Clean text, no parsing |
| URL → arXiv HTML (`arxiv.org/html/…`, ar5iv) | ✅ | Semantic, section-tagged |
| URL → generic publisher **HTML** article page | ❌ → 2b | Needs boilerplate extraction = the deferred parse problem |
| URL → **PDF** | ❌ → 2b | PDF parsing is 2b/Docling |

### 4.3 On successful capture

`chunk_sections(result.sections)` → `ChunkStore.delete_paper(paper_id)` then `add_chunks(...)` (delete-then-add makes **re-acquire idempotent** — no duplicate chunks) → set `full_text_status="verified"`, `text_source=result.text_source`, `data_tier="full_text"`.

---

## 5. Retrieval and the quote tool

### 5.1 `search_full_text` (new tool, both agents)

Searches **only** `knowledge_chunks`. Applies `min_score` (relevance threshold, invariant #3). Below threshold → explicit honest absence:

```json
{ "grounded": false, "message": "No grounded full-text support for that query." }
```

Above threshold → passages with full provenance and a stable `chunk_id`:

```json
{ "grounded": true, "passages": [
  { "chunk_id": "...", "text": "...", "source_id": 12, "title": "...",
    "section": "Results", "char_start": 8123, "char_end": 8642,
    "text_source": "jats", "year": 2024, "currency_status": "current" } ] }
```

Because the collection holds only `full_text` chunks, the **tier-as-trust contract (#1) is enforced structurally** — abstract/metadata papers are absent from quote retrieval. Summaries still come from the existing `search_knowledge_library` (orientation); full text comes from `search_full_text` (quotation). The two trust tiers stay mechanically separate.

---

## 6. Quote verification — fail-closed, cooperative tool + ledger backstop

### Decision (b): default unverified; "verified" is set by evidence, never by the agent's say-so

**The default state of every quote is `unverified`.** "Verified" is *earned*, only when all three hold:

1. The agent calls **`verify_quote`** (new tool, both agents) on the exact text it intends to quote.
2. That call returns `matched: true` — `verify_quote` `normalize_quote`s (collapse whitespace, normalize hyphenation/dashes) and string-matches against the paper's stored chunks, returning `{matched, chunk_id, section, char_start, char_end}` (invariant #4).
3. The **end-of-turn ledger reconciliation** (`reconcile_quotes`) confirms the quoted span in the final answer corresponds to that `matched: true` call.

### 6.1 The ledger backstop

The agent's `verify_quote` calls and their results are already in the turn's message history (the `tool_use`/`tool_result` blocks the agent loop appends). They **are** the verification ledger. After the final synthesis, `reconcile_quotes(answer_text, ledger)`:

- finds quoted spans in the answer (the only heuristic step — quotation-mark spans), and
- reconciles each against the ledger:

| Quoted span vs. ledger | Outcome |
|---|---|
| matches a `verify_quote` call returning `matched: true` | legitimate `[verified: source §section]` |
| matches a call returning `matched: false` | append `⚠ not verified against a stored source` |
| no matching call at all | append `⚠ not verified against a stored source` |

Correctness comes from the tool's **own recorded result**, not a re-derivation — so the backstop only *reconciles* and stays cheap (this is what keeps it out of 2c). It catches both the **omission** case (agent skipped `verify_quote`) and the **false-positive** case (agent tagged `[verified]` after a `matched: false`). The agent cannot promote a quote to verified on its own assertion; the ledger is the authority.

**Residual limitation (honest):** detecting quoted spans in free text is heuristic — an agent quoting *without* quotation marks could still slip past the span detector. So the backstop is defense-in-depth with the prompt contract, not airtight. Full automatic correctness interception is 2c.

### 6.2 Prompt contract (cooperative half)

Both agents' prompts state: quote **only** text returned by `search_full_text`; before presenting any verbatim quote, call `verify_quote`; tag every quote with its status, where `[verified: …]` is permitted **only** after a matched call, and everything else is `[unverified — from memory]`. Verification is the marked state, so an unmarked/uncertain quote defaults to unverified.

---

## 7. Agent behavior / disclosure (temporal overlay)

Reuses Phase 1's `temporal_descriptor` and disclosure plumbing; applies the temporal modifier to quoted passages too:
- A quote from a `retracted`/`superseded` paper renders **with the warning**, never as a clean citation — even if quote-verified.
- A post-cutoff paper's quote is disclosed as "stored text, no training prior."
- When `search_full_text` returns `grounded: false`, the agent says so plainly rather than paraphrasing from prior.

---

## 8. UI surface

Knowledge Library React panel:
- **"Acquire full text"** button on approved papers (with an optional URL/paste input for user-supplied text).
- A **tier badge**: full text / abstract / metadata.
- `full_text_status` feedback: verified / unavailable (with the deferral reason) / failed, with **retry**.

This is the primary manual-test surface (real server + Chroma + browser flow that automation does not cover).

---

## 9. Embedding

The chunk embedder is the **same injected `embedder` interface** the Phase 1 store already uses (`embed(texts) -> vectors`). 2a default stays a **light CPU-friendly model** (e.g. `bge-small`/`all-MiniLM`) to avoid the prior SPECTER2/CPU-only hang. Batching/caching are implementation knobs. The SPECTER2/SciNCL upgrade is deferred-and-measured against a later eval harness.

---

## 10. Testing strategy (TDD + idempotency, per project rules)

- **Chunking** (pure): section-aware boundaries, char offsets round-trip, overlap, oversize-section split.
- **Backends**: arXiv id / PMC id resolution; arXiv-HTML and JATS section parsing against **checked-in fixtures** with an **injected http client** (no network); content-type routing incl. the generic-HTML/PDF **reject** path; user-supplied `txt/md/jats`; non-OA PMC → `unavailable`.
- **`ChunkStore`**: add/search, threshold behavior (below-threshold → empty), and **idempotent re-acquire** (delete-then-add, no duplicate chunks) — ephemeral Chroma + stub embedder, matching existing store tests.
- **`quote_verify`**: `normalize_quote`; `verify_quote` exact/normalized match accepts, paraphrase/fabrication rejects; `reconcile_quotes` flags omission and false-positive spans, passes a genuinely matched span.
- **Acquire pipeline (integration)**: fixture paper → stub backend → chunks stored → tier upgraded to `full_text` → re-run produces no duplicates; reject path leaves paper at `abstract`.
- **Agents**: `search_full_text` returns provenance and honest-absence; quoting/disclosure prompt assertions; ledger reconciliation appends the unverified notice when the agent quotes without a matched call.
- **Migration 024**: columns + `paper_chunks` table added idempotently; full chain reaches v24.
- **Retrieval regression (light)**: a small `known-query → expected-passage` fixture asserting the right chunk ranks first — a seed for the deferred formal harness, not the harness itself.
- **Manual test plan** under `docs/testsPlans/`, created **before** implementation, opening with the `uv run pytest tests/ -q` prerequisite (no new failures beyond `docs/testLog.md`).

---

## 11. Risks

- **Acquisition unevenness** — expected; mitigated by honest `unavailable` recording + abstract fallback. Never pretend coverage.
- **Wrong-passage retrieval** — mitigated by the relevance threshold + provenance anchors making bad retrieval checkable; the light retrieval-regression fixture catches gross regressions.
- **Quote drift / fabrication** — mitigated by the fail-closed default + `verify_quote` + ledger backstop; residual gap (un-quote-marked text) acknowledged and deferred to 2c.
- **Embedder compute** — mitigated by the light CPU default; no PDF ML in 2a.
- **Synchronous-acquire latency** — mitigated by chunk cap + request timeout; `acquiring` state reserved for a later background upgrade.
- **Scope creep into 2b** — guarded by the generic-HTML/PDF reject boundary; anything needing a parser is refused honestly, not half-ingested.

---

## 12. Open decisions deferred to implementation

- Relevance `min_score` value (set empirically against the retrieval-regression fixture).
- Chunk `max_chars` / `overlap` defaults; the per-paper chunk cap value.
- arXiv HTML-vs-LaTeX preference order (recommend HTML first, LaTeX fallback).
- Exact vs whitespace-normalized quote match (start normalized; relax/tighten on observed false rejects).
- The quoted-span detector's rules in `reconcile_quotes` (which quotation conventions to recognize).
- Whether user-supplied `jats` upload reuses the `PmcJatsBackend` parser directly (recommended) or a thin wrapper.

---

## 13. Sequencing

2a is one implementation plan: migration 024 + ORM → `full_text_client` backends → `chunking` → `chunk_store` → `quote_verify` (incl. `reconcile_quotes`) → agent tools + prompt contract → ledger backstop in the agent loop → API action → React surface → manual gate. 2b (OA PDF + Docling parse gate + page anchors) and 2c (formal eval harness, full automatic quote interception, retraction/version provenance, embedder upgrade) follow as separate specs/plans.
