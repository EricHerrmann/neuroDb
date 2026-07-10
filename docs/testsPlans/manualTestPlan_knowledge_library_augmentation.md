# Manual Test Plan — Knowledge Library Augmentation

Spec: `docs/superpowers/specs/2026-07-08-knowledge-library-augmentation-design.md`
Plan: `docs/superpowers/plans/2026-07-08-knowledge-library-augmentation.md`
Status: pending verification

## Prerequisites

1. **Automated test gate (always first):** run `uv run pytest tests/ -q`.
   Pass criteria: no new failures beyond those already tracked in `docs/testLog.md`.
2. Backend running (`uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`)
   and frontend dev server running against it. `.env` present with provider keys;
   `SEMANTIC_SCHOLAR_API_KEY` optional (unauthenticated works, rate-limited).
3. At least one approved paper with a DOI and NULL `authors_json`, and the existing
   full-text corpus (papers 2, 9, 10, 11, 14, 52, 53, 58, 62, 63) present.

Helper script used below:
`uv run python tests/manual/check_library_reconciliation.py <source_id>`
It prints the `papers` row, `event_log` rows, summary-index metadata, and chunk
metadata/count for one paper. Pass/fail criteria are stated per case.

## Part A — Backfill + reconciliation on acquisition

**KA1 — Metadata backfill on acquire.** Pick an approved paper with a DOI and NULL
authors. Acquire full text from the Knowledge Library UI (URL, text, or local file).
Expected: acquisition completes as before; afterwards the helper script shows
`authors_json` populated (JSON array), and `abstract`/`year`/`url` filled where they
were NULL. Curated non-null fields unchanged. Any lookup failure appears as a
response warning, never a blocked acquisition.

**KA2 — Derived stores reconciled.** For the same paper, helper script shows:
summary-index metadata `data_tier: "full_text"`, `authors` non-empty, `year` and
`currency_status` matching the `papers` row; chunk metadata carries the same
`authors`/`year`/`currency_status`; at least one `event_log` row with
`event_name=full_text_acquired`, `status=ok`.

**KA3 — Idempotent re-acquire.** Re-acquire full text for the same paper.
Expected: helper script output identical for papers row, summary metadata, chunk
metadata, and chunk count (no duplicate chunks or summary docs). A new `event_log`
row is appended (audit log is append-only by design).

**KA4 — One-time reconcile of the existing corpus.** Run
`uv run python -m neurodb.cli.reconcile_fulltext --dry-run` (lists the full-text
papers, changes nothing), then without `--dry-run`. Expected: each of the existing
full-text papers reports reconciled; helper script on source 9 (Hopfield) shows
summary `data_tier: "full_text"` (was `abstract`) and authors populated.

## Part B — Guaranteed library use on explicit request

**KB1 — Flagged turn grounds on the library.** In NeuroTutor chat ask:
"Use the knowledge library: who wrote the paper on content-addressable memory and
collective computation?" Expected: a visible notice line
"Searched Knowledge Library — full-text passages: M, summaries: N" appears on the
turn, and the answer names the author (Hopfield) grounded on library content —
not a claim that the agent has no information.

**KB2 — Flagged turn, nothing relevant.** Ask: "Check the library for lattice QCD
results on quark confinement." Expected: the searched-library notice appears with
low/zero counts and the agent states plainly that the library was searched and had
nothing relevant (no invented grounding).

**KB3 — Summary fallback.** Ask a library-flagged question that only matches an
abstract/metadata-tier paper (no full text). Expected: notice shows
`full-text passages: 0, summaries: N>0`; answer grounds on the summary content.

**KB4 — Non-flagged turn unchanged.** Ask a normal topic question with no library
phrase. Expected: no searched-library notice; agent behaves as today (may still
call library tools on its own).
