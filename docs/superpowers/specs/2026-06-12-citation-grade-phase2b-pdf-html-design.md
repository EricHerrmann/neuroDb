# Citation-Grade Phase 2b — OA PDF + Generic-HTML Full Text (design)

**Status:** Design approved 2026-06-12 · **Author:** Eric Herrmann
**Predecessor:** `docs/superpowers/specs/2026-06-10-citation-grade-phase2a-structured-fulltext-design.md`

## 1. Goal

Let the tutor and research agents **quote real paper text with provenance** for queued papers
whose full text is **not** available as a clean structured source — i.e. the case Phase 2a
rejects with `needs_parser_phase2b`. 2b adds two lossy acquisition paths behind a
**parse-quality gate** so quotes stay trustworthy:

1. **Open-access PDF** — discover a free PDF for a landing-page URL, download, and parse it.
2. **Generic publisher HTML** — extract article text from a freely accessible HTML page.

Both feed the same confidence-tiered gate and the existing 2a chunk/retrieve/verify pipeline.

### Context / motivation

The current queue is dominated by **Semantic Scholar** and **PubMed** landing-page URLs (plus
arXiv, which 2a already handles). These landing pages are not clean structured full text, and
many PubMed papers are outside the PMC OA subset, so 2a records them as
`full_text_status="unavailable"`. 2b makes those papers quotable when an OA copy exists.

## 2. Decisions (settled during design)

| Decision | Choice |
|---|---|
| Acquisition boundary | OA PDF discovery **and** generic publisher HTML extraction (no paywalled fetch) |
| Parse-quality gate | **Confidence-tiered**: high → auto-accept, medium → needs-review, low → reject |
| Parser / compute | **Docling** primary with timeout, **PyMuPDF** fallback, run as an **async job** |
| OA discovery | **Unpaywall** (by DOI) + **Semantic Scholar `openAccessPdf`**; resolve DOI via NCBI PMID→DOI |
| Needs-review lifecycle | **Staged artifact** — chunk/embed only on auto-accept or human-confirm |

## 3. Scope / Non-goals

**In scope (2b):** OA PDF discovery (Unpaywall + S2 + **landing-page `citation_pdf_url`/anchor
scan**) + parse; generic publisher HTML extraction; **user-supplied direct source** — a
PDF/HTML URL or an uploaded PDF file routed through the parse pipeline (generalizes 2a's
user-supplied *text*); a confidence-tiered parse-quality gate with a human-confirm path;
**page anchors** (`page` on chunks); async parse jobs; a status-driven acquire UI.

**Explicitly deferred to 2c:**
- **OCR** for scanned / no-text-layer PDFs.
- **SPECTER2/SciNCL embedder upgrade** (2b keeps the light CPU-friendly embedder from 2a).
- Formal retrieval **eval harness**.
- **Automatic quote interception** (un-quote-marked text) — `verify_quote` stays fail-closed.
- **Retraction / version provenance**.
- Any **paywalled / behind-login** fetching (ToS and reproducibility risk).

## 4. Acquisition pipeline & data flow

2b is a **fallback ladder** that runs only after 2a's structured backends decline. 2a is
otherwise untouched.

```
Acquire full text (paper)
  0. [2b] user-supplied DIRECT source provided? (explicit user intent wins)
        a PDF/HTML URL, or an uploaded PDF file
        → status=pending, dispatch parse job on it (skips OA discovery)
  1. 2a structured backends (unchanged): arXiv id, PMC JATS, user-supplied TEXT
        success → verified
  2. [2b] decline → OA locator, tried in order until a PDF URL is found:
        a. Unpaywall(DOI) → direct OA PDF URL   (resolve missing DOI via NCBI PMID→DOI)
        b. S2 openAccessPdf → direct OA PDF URL
        c. landing-page scan: fetch the paper URL, read `citation_pdf_url` meta tag
           + common "Download PDF" anchors → PDF URL
        PDF URL found            → status=pending, dispatch async PDF parse job
        no PDF, reachable HTML   → status=pending, dispatch async HTML-extract job
        nothing                  → unavailable (suggest user-supplied link/upload)
  3. [2b async job] download → parse → parse_confidence
        PDF : Docling (timeout) ──fail──▶ PyMuPDF fallback
        HTML: trafilatura/readability
  4. [2b gate]  high   → chunk+embed → verified
                medium → stage artifact → needs_review
                low    → rejected (reason); paper stays at abstract tier
  5. [needs_review] user previews parse → Confirm → chunk+embed → verified
                                        → Reject  → drop artifact → unavailable
```

A **user-supplied direct source** (step 0) and the **landing-page PDF-link scan** (step 2c)
both address the common case where the PDF is not the referenced page itself but is reachable
either via a link the user already has or via the standard `citation_pdf_url` metadata. Both
feed the same parse → gate pipeline; user-supplied sources are still gated (they can be messy
too), not auto-trusted.

### Invariants
- **The quotable index (Chroma `knowledge_chunks`) only ever receives accepted text.** Staged
  artifacts are never chunked/embedded until auto-accept or human-confirm, so
  `search_full_text` / `verify_quote` need **no** changes and the index is trustworthy by
  construction.
- **Parsing is a background job.** The acquire request returns immediately with `pending`; the
  UI polls `full_text_status`.
- **2a fast path is preserved** — clean structured sources never enter the 2b ladder.

## 5. Data contracts & schema (migration 025)

**`papers` (extended):**
- `parse_confidence FLOAT NULL` — confidence behind the current full text (null for structured).
- `full_text_status` — gains `pending` and `needs_review` (free-text column; existing
  `verified | unavailable | failed` unchanged).
- `text_source` — gains `pdf_docling`, `pdf_pymupdf`, `html_extracted` (alongside 2a's
  `arxiv | jats | supplied`).

**`paper_chunks` (extended):**
- `page INTEGER NULL` — page anchor (PDF only; null for HTML/structured). Quotes can then cite
  section **and** page.

**New table `paper_fulltext_staging`** — parsed artifact awaiting review, one row per paper,
**insert/delete only** (never UPDATEd, to avoid the DuckDB FK/ART corruption class fixed on
2026-06-12):
- `id` (PK sequence)
- `source_id` INTEGER, indexed — **plain column, no foreign key** (deliberate)
- `text_source` VARCHAR
- `parse_confidence` FLOAT
- `fetched_url` TEXT
- `artifact_json` TEXT — ordered sections `[{section_path, text, page}]`
- `created_at` VARCHAR

On **confirm**: read artifact → chunk+embed via the existing 2a `chunk_store` (same
Section→chunk path) → `verified` → delete staging row. On **reject**: delete staging row →
`unavailable`. Both transitions are idempotent.

Rationale for a staging table (vs. a JSON column on `papers`): keeps the large parsed blob out
of the hot `papers` row and keeps writes on the FK/ART-sensitive `papers` table minimal.

## 6. Components

New modules (mirroring 2a structure; all I/O behind an injected client so tests use fixtures,
never network or ML):

| Module | Responsibility | Test seam |
|---|---|---|
| `oa_locator.py` | (doi, url, pmid, s2_pdf) → OA PDF URL via, in order, Unpaywall-by-DOI (email from `.env`), S2 `openAccessPdf`, then a **landing-page scan** of `paper.url` for `citation_pdf_url` meta + "Download PDF" anchors; NCBI PMID→DOI resolution | injected http client + fixtures (incl. a landing-page HTML fixture with `citation_pdf_url`) |
| `pdf_parser.py` | bytes → `{sections:[{section_path,text,page}], parse_confidence, text_source}`; Docling (timeout) → PyMuPDF fallback | injected parser callables; Docling mocked, fallback tested without ML |
| `html_extractor.py` | HTML → same artifact shape (no page) | injected http; fixture HTML |
| `parse_quality.py` | heuristic `parse_confidence` + gate thresholds → `accept \| review \| reject` | pure function, table-driven |
| `fulltext_staging.py` | write/read/delete staging artifact | in-memory DB |

Extended 2a pieces:
- `full_text_client.py` — append `PdfBackend` / `HtmlExtractBackend` to the ladder; the old
  `needs_parser_phase2b` reject becomes the **entry** to the 2b ladder.
- **Async runner** — the acquire endpoint sets `pending` and dispatches a background task
  (FastAPI `BackgroundTasks` / thread) that opens **its own DB session** and writes the terminal
  state on completion. Single-user scale, no external queue.
- **API**:
  - `POST /{id}/acquire-full-text` — may now return `pending`; body extended to accept an
    optional **user-supplied direct source**: `source_url` (a PDF or HTML URL) and/or a PDF
    **file upload**. When present, it takes precedence over OA discovery (step 0). This
    generalizes 2a's existing `SuppliedInput.text`; the unused `SuppliedInput.url` becomes live.
  - staging preview — exposed on `GET /{id}` (or a sub-route) for the review panel.
  - `POST /{id}/fulltext-review` `{decision: confirm|reject}`.
- **React acquire surface (status-driven; fixes the verified-paper button bug):**
  - `metadata|abstract` → **Acquire full text** + a secondary **Supply link / upload PDF**
    (user-supplied direct source)
  - `pending` → progress indicator (poll)
  - `needs_review` → **Review parse** → preview panel (confidence, sections, Confirm/Reject)
  - `unavailable|failed|rejected` → reason + **Supply link / upload PDF** (the recovery path)
  - `verified` → full-text badge + explicit, idempotent **Re-acquire** (never a naked "Acquire")
  - quotes show source-type + page.
- **Agent prompt** — parsed-source quotes disclose `text_source` (pdf/html) and page so they are
  distinguishable from clean structured quotes; `verify_quote` stays fail-closed and unchanged.

## 7. `full_text_status` state machine

```
(none) ──acquire──▶ pending ──┬─ high   ─▶ verified
                              ├─ medium ─▶ needs_review ──confirm─▶ verified
                              │                          └─reject─▶ unavailable
                              ├─ low    ─▶ rejected (→ stays abstract tier)
                              └─ error  ─▶ failed
verified ──re-acquire──▶ pending (idempotent chunks)
```

`unavailable` / `failed` / `rejected` always carry a human-readable `reason`
(`not_oa`, `parse_error`, `low_confidence`, …).

## 8. Confidence scoring & gate

`parse_quality.score(artifact) -> float` is an explicit heuristic over signals available
without ML, e.g.: ratio of extractable characters to expected length, fraction of lines that
parse as prose vs. garbage/encoding noise, successful section detection, and (PDF) text-layer
presence. Thresholds `H` (accept) and `L` (reject) are configurable; `L ≤ score < H` →
`needs_review`. Scanned PDFs (no text layer) score near zero → `rejected (low_confidence)` with
a message suggesting user-supplied upload. Threshold defaults are an implementation knob tuned
against fixtures; they are not hard-coded magic in business logic.

## 9. Error handling

- Docling timeout/crash → PyMuPDF; both fail → `failed (parse_error)`.
- PDF HTTP 403/404 → try next OA source; none left → `unavailable (not_oa)`.
- Unpaywall missing-email or down → skip to S2 `openAccessPdf`; emit a `SystemWarning`; never
  hard-fail the request.
- HTML extraction yields too little text → `rejected (low_confidence)`.
- Background job exception → terminal `failed (parse_error)`, never a stuck `pending`.

## 10. Idempotency & reproducibility (per CLAUDE.md)

- Re-acquire on a `verified` paper reuses the idempotent `chunk_store` keyed by source — **no
  duplicate chunks**.
- Re-acquire while `pending` is a no-op (no double job).
- `confirm` / `reject` on an already-resolved paper are no-ops.
- Provenance recorded: `text_source`, `fetched_url`, `parse_confidence`, source version/date,
  and run timestamp, so an acquisition can be audited and (for stable OA URLs) repeated.

## 11. Testing

- **Unit**: `oa_locator` (Unpaywall / S2 / PMID→DOI **and the landing-page `citation_pdf_url`/
  anchor scan** with injected http + fixtures); user-supplied direct-source routing (a
  `source_url` / uploaded PDF bypasses OA discovery and enters the parse pipeline);
  `pdf_parser` fallback path against a small checked-in fixture PDF (Docling mocked);
  `html_extractor` on fixture HTML; `parse_quality` thresholds (table-driven); staging CRUD;
  review confirm/reject transitions; idempotent re-acquire.
- **Integration**: the full acquire ladder with injected clients (no network, no ML) asserting
  each terminal state (`verified` / `needs_review` / `rejected` / `unavailable`) and the
  invariant that staged text never reaches Chroma until confirm.
- **Manual test plan** — a phase-gate artifact authored **before** implementation
  (`docs/testsPlans/manualTestPlan_citation_phase2b_pdf_html.md`), registered in
  `docs/projectStatus.md` when created. Covers: a real OA PubMed paper
  `pending`→`verified`→quote-with-page-anchor; a paper whose PDF is behind a separate link on its landing page
  (resolved via `citation_pdf_url`); a user-supplied PDF URL and a user-uploaded PDF; a
  medium-confidence parse → `needs_review` →
  Confirm and (separately) Reject; a generic publisher HTML page; a non-OA / scanned PDF →
  `unavailable`; re-acquire idempotency; and the verified-paper acquire-button-state fix.
  Prerequisites include the standard `uv run pytest tests/ -q` gate.

## 12. Risks & mitigations

- **Parse misquote** (subtly wrong text that still "verifies" against our copy) → the
  confidence-tiered gate + human-confirm for medium parses; low-confidence rejected outright.
- **CPU/ML hang** (the SPECTER2/Docling class of problem) → Docling runs in a background job
  with a timeout and a non-ML PyMuPDF fallback; the web request never blocks on ML.
- **OA-locator dependency** (Unpaywall email/availability) → S2 `openAccessPdf` fallback +
  `SystemWarning`; never hard-fails acquisition.
- **Scope creep into 2c** → OCR, embedder upgrade, eval harness, auto-interception, retraction
  provenance are explicitly out of scope.

## 13. Open decisions deferred to implementation

- Exact `H`/`L` confidence thresholds (tuned against fixtures).
- HTML extractor library choice (`trafilatura` vs. `readability-lxml`) — both behind
  `html_extractor`'s interface.
- Whether the staging preview is a sub-route or embedded in `GET /{id}` (API-shape detail).
- Docling parse timeout value.
