# Manual Test Plan — Citation-Grade Phase 2b: OA PDF + Generic-HTML Full Text

**Scope:** Phase 2b adds a fallback acquisition ladder for papers that Phase 2a's structured
backends decline. It discovers open-access PDFs (Unpaywall, Semantic Scholar `openAccessPdf`,
landing-page `citation_pdf_url`/anchor scan), parses them (PyMuPDF-first; Docling is a deferred
seam), extracts generic publisher HTML, gates results by parse confidence, stages
medium-confidence parses for human review, and surfaces the full lifecycle in the UI.

**Status:** Pending verification · **Tester:** Eric Herrmann

**Spec:** `docs/superpowers/specs/2026-06-12-citation-grade-phase2b-pdf-html-design.md`
**Plan:** `docs/superpowers/plans/2026-06-12-citation-grade-phase2b-pdf-html.md`

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

> These cases cover the real browser workflow, real server/DB/Chroma/network wiring, and the
> UI lifecycle that the automated unit/integration tests do not exercise. Automated tests cover
> the component logic; the manual gate validates real OA discovery, real parse quality, and the
> operator review panel under production-like conditions.

---

## Prerequisites

1. **Automated suite green (run first).** No new failures beyond those tracked in
   `docs/testLog.md`:

   ```bash
   uv run pytest tests/ -q
   ```

   Pass: all backend tests pass. Current verified baseline: **985 passed** (2026-06-13,
   `phase2b-impl`). No failures.

2. **Frontend gate.**

   ```bash
   cd frontend && npm test -- --run && npm run build
   ```

   Pass: all Vitest tests pass; the `tsc -b && vite build` build is clean. Baseline:
   **116 passed (18 files)**, build clean (2026-06-13).

3. **Start the backend** against a disposable DB so checks do not alter the main working DB.
   `UNPAYWALL_EMAIL` must be set in `.env` for OA discovery to run (Unpaywall skips gracefully
   if missing, but the OA locator falls back to S2 / landing scan only):

   ```bash
   NEURODB_DB_PATH=neurodb_manual_2b.duckdb \
     uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
   ```

4. **Start the frontend** (second terminal):

   ```bash
   cd frontend && npm run dev
   ```

   Open the dev URL Vite prints (default `http://localhost:5173`). Confirm `.env` holds a
   working model API key and that `UNPAYWALL_EMAIL` is set.

---

## PB1 — OA PubMed paper: pending → verified, quote with page anchor

Queue and approve a PubMed paper whose PMC record is **not** in the JATS OA subset (so Phase 2a
declines it) but whose DOI is registered in Unpaywall or whose Semantic Scholar record carries
`openAccessPdf`. Example: search for a neuroscience paper and inspect the Knowledge Library tile
to confirm tier is `abstract` and `full_text_status` is absent/unavailable post-2a.

Click **Acquire full text**.

**Pass:**
- The tile immediately shows a `pending` indicator (spinner or "Acquiring…" label).
- Within a short time (job completes in background) the indicator resolves and tier badge
  becomes **full text**, status **verified**.
- Ask the Neuro-Tutor agent to quote a passage from the paper. The response includes a quote
  with a source annotation that shows `text_source: pdf_pymupdf` (or `pdf_docling` if Docling
  is configured) **and** a page number (e.g. `p. 3`).

---

## PB2 — PDF behind a landing-page link (citation_pdf_url / Download PDF anchor)

Queue and approve a paper whose URL is a publisher HTML landing page that does **not** expose a
direct PDF in the DOI or S2 record, but whose HTML contains a `<meta name="citation_pdf_url">`
tag or a visible "Download PDF" anchor pointing to the OA PDF (e.g. some PLOS, eLife, or
BioRxiv pages).

Click **Acquire full text**.

**Pass:**
- Status progresses `pending` → `verified` (or `needs_review` if parse confidence is medium).
- If `verified`: tier badge is **full text**; quoting works with page anchor.
- If `needs_review`: PB4 steps apply.

---

## PB3 — User-supplied PDF URL via "Supply link"

Approve any paper (OA or not). Instead of the automatic discovery path, click **Supply link /
upload PDF** and enter a known-good direct PDF URL (an OA PDF URL from Unpaywall, arXiv, or a
publisher you have access to).

**Pass:**
- Status goes `pending` while the background job downloads and parses.
- Resolves to `verified` (high confidence) or `needs_review` (medium confidence).
- If `verified`: tier is **full text**; a Neuro-Tutor quote includes page anchor.

---

## PB4 — Medium-confidence parse → needs_review → Confirm (verified) and Reject (unavailable)

You need a paper whose PDF renders with medium parse quality (e.g. a heavily formatted document
with sidebars, tables-of-contents, or moderate encoding noise). If no natural example is
available, use the "Supply link" path (PB3) with a URL that is known to produce medium
confidence in a prior test.

**Step A — Confirm path:**
- After acquire completes with `needs_review`, click **Review parse**.
- The review panel opens showing: parse confidence score, parsed section previews (text
  excerpts), and **Confirm** / **Reject** buttons.
- Click **Confirm**.

  **Pass:** status becomes **verified**; tier badge is **full text**; the staging row is
  deleted (confirmed via `GET /api/knowledge-library/{id}` — `fulltext_staging` field is null).

**Step B — Reject path (separate paper or after a second acquire on a different paper):**
- Reach `needs_review` state on a different paper (or re-acquire after rejecting to induce
  `needs_review` again with a medium-confidence source).
- Click **Review parse** → **Reject**.

  **Pass:** status becomes **unavailable**; tier reverts to **abstract**; no chunks exist for
  this paper (confirm: `GET /api/knowledge-library/{id}` chunk count is 0 or absent); the
  staging row is deleted.

---

## PB5 — Generic publisher HTML page → extracted → gated

Queue and approve a paper whose URL is a freely accessible publisher HTML page (e.g. a PMC
full-text HTML, a Frontiers article page, or a PLOS article). Phase 2a must decline (not JATS
PMC). The 2b HTML extractor runs.

Click **Acquire full text**.

**Pass:**
- Status progresses `pending` → `verified` (high confidence) or `needs_review` (medium) or
  `unavailable` (low — see PB6 for that case).
- If `verified`: tier badge is **full text**; quoting from the paper works; source annotation
  shows `text_source: html_extracted`; no page number (HTML has no page anchors).
- If `needs_review`: review panel opens correctly (PB4 steps apply).

---

## PB6 — Non-OA / scanned PDF → unavailable with reason

Queue and approve a paper that is either (a) behind a paywall with no OA copy in Unpaywall or
S2, or (b) a scanned PDF with no text layer. Do not provide a user-supplied link.

Click **Acquire full text**.

**Pass:**
- OA locator finds no PDF URL → status becomes `unavailable` with a reason such as `not_oa`
  or `no_oa_found`.
- OR: locator finds a PDF URL, job downloads it, parse confidence is very low (scanned) →
  status `unavailable` with reason `low_confidence`.
- In either case: the "Supply link / upload PDF" option is displayed in the UI, providing a
  recovery path.
- Tier remains **abstract**.

---

## PB7 — Re-acquire on a verified paper is idempotent (no duplicate chunks)

Use a paper that is already in `verified` state from PB1, PB3, or PB4.

Note the **Re-acquire** button is shown (not a plain "Acquire full text").

Click **Re-acquire**.

**Pass:**
- Status briefly shows `pending`, then returns to `verified`.
- The chunk count for this paper is **unchanged** — no duplicate chunks. Verify via
  `GET /api/knowledge-library/{id}`: `chunk_count` before and after re-acquire are equal.
- A Neuro-Tutor quote from this paper still works and still shows the correct page anchor.

---

## PB8 — Verified paper shows Re-acquire, not plain "Acquire full text"

Inspect the Knowledge Library tile for any `verified` paper.

**Pass:**
- The acquire control label is **Re-acquire** (or similar idempotent label), not "Acquire full
  text".
- The plain "Acquire full text" button is absent for this paper.
- For a paper at `abstract` tier (no full text yet), the plain "Acquire full text" button is
  present and Re-acquire is absent.

This is the UI bug that was fixed in Phase 2b; confirm it does not regress.

---

## Sign-off

| Case | Result | Notes |
|------|--------|-------|
| PB1  |        |       |
| PB2  |        |       |
| PB3  |        |       |
| PB4A |        |       |
| PB4B |        |       |
| PB5  |        |       |
| PB6  |        |       |
| PB7  |        |       |
| PB8  |        |       |
