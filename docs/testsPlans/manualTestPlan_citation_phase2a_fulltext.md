# Manual Test Plan — Citation-Grade Phase 2a: Structured Full-Text RAG

**Feature:** Acquire structured full text, chunk/embed it, retrieve quotable passages, verify quotes.
**Spec:** docs/superpowers/specs/2026-06-10-citation-grade-phase2a-structured-fulltext-design.md

## Prerequisites
1. **Automated suite green.** Run `uv run pytest tests/ -q`. Pass criterion: no new failures beyond those tracked in `docs/testLog.md`.
2. API/React app running against a local DuckDB + Chroma with `.env` loaded.

## Tests
- **T1 — Acquire arXiv full text.** Approve a paper whose URL is an arXiv abstract page. Click "Acquire full text". Verify the tier badge becomes "full text" and status "verified".
- **T2 — Acquire PMC (OA) full text.** Same for a PMC open-access paper (JATS). Verify "full text"/"verified".
- **T3 — Non-OA / publisher HTML rejected.** Acquire a paper whose URL is a publisher HTML/PDF page. Verify it stays "abstract", status "unavailable", with the Phase-2b deferral message.
- **T4 — User-supplied text.** Paste/upload `.md` text for a paper with no fetchable source. Verify "full text"/"verified".
- **T5 — Grounded quote.** In a tutor chat, ask the agent to quote a passage from a verified paper. Verify the quote renders with a source+section anchor and a `[verified]` marker.
- **T6 — Honest absence.** Ask the agent to quote about a topic absent from any acquired paper. Verify it says it has no grounded full-text support rather than inventing a quote.
- **T7 — Unverified backstop.** Induce the agent to present a quote it did not verify (e.g., a paraphrase in quotes). Verify the response carries the ⚠ unverified notice.
- **T8 — Idempotent re-acquire.** Re-run "Acquire full text" on a verified paper. Verify no duplicate chunks (chunk count unchanged) and status stays "verified".

## Pass/Fail
All of T1–T8 behave as described; no regression in queue/approve/search flows.
