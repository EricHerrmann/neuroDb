# Manual Test Plan — Citation-Grade Phase 1: Abstract Grounding

**Feature:** Abstract-grounded Knowledge Library summaries + data tier / vintage / currency disclosure.
**Spec:** docs/superpowers/specs/2026-06-09-citation-grade-data-access-design.md (Phase 1)

## Prerequisites
1. **Automated suite green.** Run `uv run pytest tests/ -q`. Pass criterion: no new failures beyond those already tracked in `docs/testLog.md`.
2. Streamlit/API app running against a local DuckDB with provider keys loaded via `.env`.

## Tests
- **T1 — Abstract captured on queue.** In a tutor chat, run a literature search and have the agent queue a source that has an abstract. Verify in the Knowledge Library that the queued paper row stores the abstract and year, and shows tier "abstract".
- **T2 — Summary grounded in abstract.** Approve the queued source. Verify the generated summary reflects content from the abstract (not just the title) — e.g., mentions a method/finding present in the abstract but not implied by the title.
- **T3 — Metadata-only paper.** Queue a source with no abstract. Verify tier shows "metadata" and the agent, when citing it, says it is orienting from metadata only.
- **T4 — Post-cutoff disclosure.** Ask the agent about an approved source dated 2026 or later. Verify it states it has no training prior and relies on the stored text.
- **T5 — Currency warning.** Flag an approved source as retracted (via update path/DB), then ask the agent about it. Verify it surfaces a retraction warning instead of a clean citation.

## Pass/Fail
All of T1–T5 behave as described; no regression in existing queue/approve/search flows.
