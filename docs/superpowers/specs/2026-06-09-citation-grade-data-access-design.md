# Citation-Grade Data Access — Design

- **Date:** 2026-06-09
- **Status:** Design — pending user review
- **Epoch:** Tutor (write path: `src/neurodb/knowledge_store.py`, `src/neurodb/api/routes/knowledge_library.py`, `src/neurodb/agents/tutor_agent.py`, `src/neurodb/literature_client.py`); read/consumer in Research (`src/neurodb/research/`)
- **Supersedes discussion capture:** `docs/citationGradeDesign.md` (verbatim thread that motivated this spec)
- **Related specs:** `docs/superpowers/specs/2026-06-02-literature-source-registry-design.md` (acquisition layer this design builds on)

---

## 1. Goal

Let the tutor and research agents ground their assistance in the **actual content of papers the user has added**, retrieved with provenance, so the user can trust them to:

1. **Orient accurately** for most papers — "what does this paper actually say / argue" — without hallucinating. Abstract-tier suffices here, and this is the high-volume everyday function.
2. **Produce citation-grade research output** for the papers the user's argument rests on — verbatim quotes anchored to a stored, downloaded source — for building research questions, hypotheses, and citable papers.
3. **Declare their grounding** in every response that uses source material: which source, and at which tier (full text / abstract / metadata / training prior).
4. **Calibrate assistance per topic** from the tier-mix of that topic's linked sources, and surface coverage gaps as an **acquisition to-do list** — without letting coverage steer research direction (the user owns direction).

Both agent roles use the same store: tutor → accurate teaching with verifiable citations; research → grounded claims/evidence/hypotheses.

### Non-goals (this spec)

- Whole-document-in-context stuffing (token-expensive, doesn't scale; RAG is the chosen mechanism).
- Acquiring paywalled full text — only open-access (PMC / arXiv / Unpaywall) or user-supplied copies are stored.
- The extracted-claims-with-locations tier (the highest tier in the discussion capture). The existing claims/evidence model consumes this store; building automated claim extraction on top is a later, separate spec.
- Automated **recency/citation-velocity scoring** or automated inference that later work *contradicts* a claim. Temporal signals (invariant #8) are surfaced as reasoned metadata and flags, never as a scalar that auto-ranks papers — a recency score would wrongly devalue the canonical work the user explicitly relies on.

---

## 2. The problem this fixes

The tutor RAG path is **structurally ungrounded today**. Verified against the code:

- `tutor_agent.py` `queue_source` accepts `title, source_type, topic_context, doi, url, topics` — **no abstract** on the queue path. `_execute_queue_source` creates the `Paper` row leaving `abstract`/`year`/`authors_json` **null**, even though `search_literature` already returns an abstract (it is discarded).
- On approve, `routes/knowledge_library.py:_generate_summary` asks the model to summarize from **only** title + type + DOI + URL + topic_context — never any real paper text.
- `KnowledgeLibraryStore.add_summary` embeds that summary string into ChromaDB; `search` returns it as the retrieved document.

Net: retrieval is over the model's own prior keyed off a title — the exact hallucination surface to remove. The `Paper` table already has `abstract`, `year`, `authors_json` columns; they are simply never populated on the tutor path. **The cheapest, highest-leverage fix uses columns that already exist.**

---

## 3. Design principles (the eight invariants)

These are the testable requirements every phase must satisfy. The first six are agent-behavior/data invariants; the seventh is the trigger that bounds cost; the eighth adds the temporal dimension to value and trust.

1. **Tier-as-trust-contract.** Every paper has an explicit `data_tier` (`full_text` / `abstract` / `metadata`). Verbatim quotes are permitted **only** from `full_text` papers whose stored chunks pass the parse-quality gate. A paper at `abstract` or `metadata` tier is mechanically barred from being "quoted."
2. **End-to-end provenance.** Every stored retrieval unit carries: source id, DOI, tier, text-source (`jats` / `arxiv_src` / `pdf:<parser>` / `abstract` / `user_supplied`), section label, page/char offsets where available, parse-confidence, and ingest timestamp. A retrieved passage is always traceable back to a checkable location.
3. **Retrieval relevance threshold.** Retrieval returns only passages above a similarity threshold. If nothing clears it, the agent reports *"I don't have grounded support for that"* rather than returning the least-bad chunk. Honest absence beats confident garbage.
4. **Quote verification.** When an agent emits a quotation, it is string-matched back to a stored chunk. Unmatched text cannot be presented as a verbatim quote.
5. **Retrieval eval harness.** A small `known-query → expected-passage` fixture set with a measured hit-rate, run in CI, so retrieval quality is a regression-tested number, not an assumption.
6. **Grounding disclosure.** Every agent response that uses source material states which source(s) and tier(s) it drew from, and discloses when it is falling back to training prior.
7. **Citable-intent full-text trigger.** Full text is earned by *"will the user build citable work on this paper?"* — **not** by fame or recency. Both a foundational paper the user will cite and a frontier paper the user is exploring earn full text; a paper passed through only to orient stays at abstract tier. This bounds the expensive ingestion to where it pays off.
8. **Temporal trust modifier.** A paper's value and the trust in its claims are *time-relative*, expressed through three signals — not a scalar "newer is better" score (which would wrongly devalue canonical work):
   - **Vintage** (`year`) is surfaced as reasoned metadata so the agent distinguishes a 1982 foundational paper from a 2025 preprint and lets the user weigh them; it never auto-ranks by recency.
   - **Training-cutoff relation** (pre/post the model's Jan-2026 cutoff) sharpens disclosure: for post-cutoff papers the agent states it has *no* training prior and rests entirely on stored text.
   - **Currency status** (`current | superseded | contested | retracted`) modifies the trust contract: even a verified, quote-verified `full_text` passage from a `retracted`/`superseded` paper is surfaced **with a temporal warning**, never as a clean citation. Status is user/agent-flaggable; `retracted` may additionally be backed by a retraction-notice lookup (Phase 2 option). Automatically inferring that later literature *contradicts* a claim is explicitly out of scope.

### Topic readiness (derived, not stored as truth)

Each topic exposes a **readiness** derived from the tier-mix of its linked sources:

- `ready_for_citation` — has ≥1 `full_text` source that passed the parse gate.
- `orientation_only` — has abstracts but no verified full text.
- `needs_acquisition` — metadata only.

Readiness **calibrates the agent's confidence and disclosure**, and drives an acquisition to-do list. It does **not** rank research directions — coverage informs acquisition, the user drives direction (guards against the streetlight effect of over-exploring well-documented areas).

Readiness also exposes a **temporal coverage gap** derived from the `year` spread of a topic's linked sources: e.g., *"this topic is grounded only in 2012–2016 papers; in a fast-moving area, consider acquiring recent work."* This is frontier-seeking expressed as an acquisition to-do — temporal coverage informs acquisition, never direction.

---

## 4. Data model

### 4.1 Phase 1 — reuse existing columns

`Paper` already has `abstract`, `year`, `authors_json`, `summary`, `chroma_id`. Phase 1 adds the tier column and the temporal-trust fields (one migration, next free number at implementation time):

- `Paper.data_tier: str` — `"metadata" | "abstract" | "full_text"`, default `"metadata"`, indexed.
- `Paper.currency_status: str` — `"current" | "superseded" | "contested" | "retracted"`, default `"current"`, indexed. User/agent-flaggable; modifies the trust contract (invariant #8).

`year` (already present) carries vintage. The **training-cutoff relation** is *derived at query/render time* from `year` vs the model's Jan-2026 cutoff — it is not stored, so it stays correct if the cutoff changes. No abstract-storage migration is needed — that column already exists.

### 4.2 Phase 2 — full-text chunks

A new table for retrieval units (the only place full text is embedded):

```
paper_chunks
  id            PK
  paper_id      FK -> papers.id, indexed
  chunk_index   int                 # order within paper
  text          Text                # cleaned chunk text
  section       str | None          # e.g. "Methods"
  page          int | None
  char_start    int | None          # offset into normalized full text
  char_end      int | None
  text_source   str                 # jats | arxiv_src | pdf:docling | pdf:marker | user_supplied
  chroma_id     str                 # stable id in the chunks collection
  created_at    str
```

Plus parse-gate provenance on the paper:

- `Paper.parse_confidence: float | None`
- `Paper.text_source: str | None`
- `Paper.full_text_status: str | None` — `verified | abstract_fallback | failed`

ChromaDB gets a **second collection**, `knowledge_chunks`, distinct from the existing `knowledge_library` summary collection. Chunk metadata mirrors the provenance fields so retrieval results are self-describing.

---

## 5. Phase 1 — Abstract grounding (low effort, high leverage)

**Outcome:** the agent orients from the paper's real abstract instead of a title-derived summary, for every paper where an abstract is available. Grounding disclosure appears ("orienting from the abstract of …"). No parsing, minimal compute.

Changes (TDD, each independently testable):

1. **Capture the abstract and vintage on queue.** Add `abstract`, `year`, `authors` to the `queue_source` tool schema; persist them on the new `Paper` row in `_execute_queue_source`. The abstract and year are already in the `search_literature` envelope (and the `SourceBackend` normalized shape) — stop discarding them. Set `data_tier="abstract"` when an abstract is present, else `"metadata"`; set `currency_status="current"` by default.
2. **Ground the summary in the abstract.** `_generate_summary` includes `row.abstract` when present, and instructs the model to summarize **from the abstract**, not the title. `_fallback_summary` likewise prefers the abstract.
3. **Carry tier into retrieval metadata.** `add_summary` records `data_tier` and `abstract`-availability in the Chroma metadata so the agent knows the grounding basis at retrieval time (enables disclosure invariant #6 at Phase 1).
4. **Disclosure in agent output.** Tutor/research prompt + context assembly state the tier of each retrieved source, its **vintage**, the **training-cutoff relation** (post-cutoff → "no training prior, stored text only"), and any non-`current` **currency status** as a temporal warning (invariant #8).

**Acceptance (Phase 1):**
- A queued paper with an abstract stores that abstract and `year`; `data_tier="abstract"`, `currency_status="current"`.
- `_generate_summary` output is demonstrably derived from abstract text (test with a fixture abstract containing a sentinel claim the title does not imply).
- Retrieval surfaces tier + vintage; agent response discloses "abstract of …" and flags a post-cutoff paper as having no training prior.
- A paper flagged `superseded`/`retracted` surfaces with a temporal warning rather than a clean citation.
- Idempotent re-queue does not duplicate or wipe a captured abstract, year, or currency flag.

> Phase 1 does **not** depend on full text. It closes the worst gap for the whole library cheaply and de-risks the queue→approve→embed path before Phase 2.

---

## 6. Phase 2 — Full-text ingestion, parse gating, citation provenance

**Outcome:** for citable-intent papers, real full text is fetched, parsed, quality-gated, chunked with provenance, and embedded — enabling verbatim, anchored quotation with the trust contract enforced.

### 6.1 Acquisition (built on the SourceBackend registry)

Extend the registry pattern (`2026-06-02-literature-source-registry-design.md`) with a **fetch capability**, keeping "one new source = one file":

- Prefer **structured sources** to dodge PDF parsing: PMC **JATS XML**, arXiv **LaTeX/HTML source**. These arrive as clean structured text.
- Fall back to **OA PDF** via Unpaywall/PMC-PDF only when no structured source exists.
- Accept **user-supplied** copies (drop-in path) for papers the user already has.
- Acquisition is **uneven by design** — a paper that yields no clean full text degrades to abstract tier and is recorded as such. Never pretend coverage.
- **Versioning provenance:** record the retrieved version (preprint vs published; arXiv `v1`/`v2`) and fetch date. When a stored preprint has a known published version of record, flag the staleness. This makes the version axis of invariant #8 honest.
- **Retraction lookup (optional):** at ingest, check a retraction-notice source (Crossref / Retraction Watch); a hit sets `currency_status="retracted"`. Bounded add — automatic *contradiction* inference remains out of scope.

### 6.2 Parse + quality gate (at the existing approve gate)

PDF is a layout format; parse quality is the biggest lever on retrieval trust. The gate runs at the human approve step the project already has:

- **Parser:** structure-preserving default (**Docling** — preserves section hierarchy for provenance) when a PDF must be parsed; structured sources skip parsing entirely.
- **Proxy parse-confidence score** from reference-free signals: structural completeness (expected sections present), text coherence (language-model perplexity / sentence continuity — catches two-column scramble), character-junk ratio, coverage (extracted chars vs. page-count expectation), reference count, optional cross-parser agreement.
- **Human confirmation view:** at approve, surface the score + which signals fired + a rendered preview of the parsed text + detected outline. The score routes; the human decides; override is allowed.
- **Fallback ladder** when below threshold: structured source → stronger/LLM-assisted parser (Marker `--use_llm`) → degrade to `abstract` tier (recorded) → user-supplied/manual.
- Final state recorded in `full_text_status` + `parse_confidence` + `text_source`.

### 6.3 Chunk + embed + store

- Chunk on structural boundaries (section-aware) when available; fixed-size fallback otherwise. Carry `section`/`page`/`char_start`/`char_end` into `paper_chunks`.
- Embed via the **swappable embedder** (§7) into the `knowledge_chunks` collection with full provenance metadata.
- `Paper.data_tier="full_text"` only when `full_text_status="verified"`.

### 6.4 Retrieval + citation behavior

- `search` over `knowledge_chunks` applies the **relevance threshold** (invariant #3); below-threshold → honest "no grounded support."
- Returned chunks carry provenance; the agent renders quotes **with** their anchor (source, section, page).
- **Quote verification** (invariant #4): emitted quotations are string-matched to a stored chunk before being presented as verbatim.
- Tier governs behavior (invariant #1): only `full_text` chunks are quotable; abstract/metadata papers are orientation-only.
- Temporal modifier (invariant #8) overlays the quote: a verified quote from a `retracted`/`superseded` paper, or a post-cutoff paper, renders with the corresponding warning/disclosure alongside its provenance anchor.

**Acceptance (Phase 2):**
- A structured-source paper ingests without PDF parsing and is quotable with section anchors.
- A deliberately scrambled/garbage parse scores below threshold, is surfaced in the confirmation view, and does not reach `full_text` tier without override.
- A verbatim quote not present in any stored chunk is rejected by quote verification.
- A verified quote from a `retracted` paper renders with a temporal warning, not a clean citation.
- Below-threshold retrieval yields an explicit "no grounded support" rather than a low-relevance chunk.
- Retrieval eval harness hit-rate meets the agreed baseline and is wired into CI.

---

## 7. Embedding abstraction (deferred-and-measured)

The embedder is an **injected dependency** behind one interface — `KnowledgeLibraryStore` already accepts an optional `embedder` with `embed(texts) -> vectors`. Formalize it:

- **Default:** a light, CPU-friendly model (`bge-small` / `all-MiniLM`) to avoid the prior SPECTER2/CPU-only hang.
- **Upgrade path:** SPECTER2 / SciNCL as drop-in implementations, selected later **only if the retrieval eval harness (invariant #5) shows the relevance gain justifies the compute.**
- The choice is a measured one, not a guess. Batching/caching are implementation knobs, not blockers.

---

## 8. Testing strategy

Per the project's TDD and idempotency rules:

- **Phase 1:** unit tests for abstract+year capture/persist, summary-from-abstract (sentinel-claim fixture), tier-in-metadata, idempotent re-queue.
- **Temporal (invariant #8):** cutoff-relation derivation (pre/post Jan-2026) from `year`; disclosure includes vintage; a `superseded`/`retracted` flag produces a temporal warning in agent output; temporal-coverage-gap computation over a topic's `year` spread.
- **Parse gate:** unit tests for each proxy signal on good/scrambled/sparse fixtures; gate routing; fallback-ladder transitions; tier recording.
- **Chunk/provenance:** chunk boundary + offset carry-through; provenance round-trips into Chroma metadata and back out of `search`.
- **Retrieval quality:** the eval harness fixture set with a measured hit-rate baseline, run under `uv run pytest`; threshold behavior (below-threshold → honest absence).
- **Quote verification:** verbatim match accepts; paraphrase/fabrication rejects.
- **Disclosure:** agent output asserts tier declaration for each retrieved source.
- **Manual test plans:** Phase 1 and Phase 2 each get a manual plan under `docs/testsPlans/` created **before** implementation, each opening with the `uv run pytest tests/ -q` prerequisite step.

---

## 9. Risks

- **Acquisition unevenness** — mitigated by tier recording + abstract fallback; mixed library is expected, never hidden.
- **Parse quality** — mitigated by prefer-structured-source, structure-preserving parser, proxy gate + human confirmation, fallback ladder.
- **Retrieval-of-wrong-passage** — mitigated by relevance threshold + provenance anchors making bad retrieval *checkable* + eval harness regression.
- **Compute friction** — mitigated by light default embedder and measured upgrade.
- **Maintenance** (versions/retractions) — provenance + `full_text_status` make staleness visible; out of scope to automate now.

---

## 10. Scope / sequencing

This is **two implementation plans**, not one:

1. **Phase 1 — abstract grounding.** Small, self-contained, ships grounded orientation immediately. Coordinate with the literature-source-registry refactor (both touch `literature_client` / `queue_source`); the registry is now unblocked, so landing it first—or sharing the `abstract` normalization—avoids churn.
2. **Phase 2 — full-text + parse gating + provenance + retrieval quality.** The real engineering; depends on Phase 1's tier field and disclosure plumbing.

Each phase: spec → `writing-plans` plan → manual test plan → implementation.

---

## 11. Open decisions deferred to implementation

- Exact parse-confidence signal weights and the green/yellow/red thresholds (tune against real fixtures).
- The retrieval similarity-threshold value (set empirically via the eval harness).
- Chunk size / overlap defaults for the fixed-size fallback.
- Whether quote verification is exact-match or normalized (whitespace/hyphenation-tolerant) — start exact, relax only if it produces false rejections on clean text.
- The exact phrasing/format of temporal warnings and post-cutoff disclosure in agent output (tune for signal without clutter).
- Whether the retraction-notice lookup (Crossref / Retraction Watch) is in Phase 2 scope or deferred — depends on how often retracted papers actually enter your library.
- The temporal-coverage-gap heuristic (what `year`-spread/recency thresholds flag a topic as temporally stale in a fast-moving area).
