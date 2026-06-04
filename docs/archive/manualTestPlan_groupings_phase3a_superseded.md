# Manual Test Plan — Groupings Phase 3a (Backend Cutover)

> **SUPERSEDED (2026-06-04) — retained for history only.** The backend cutover
> behavior covered here was subsequently verified through Groupings Phase 3b,
> Phase 4, and the final Phase 5 post-drop manual gate. The active grouping and
> research-question completion record is
> `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_groupings_phase5.md`.

## Prerequisites
- [ ] Run the automated suite: `uv run pytest tests/ -q`. Pass criterion: no new failures beyond those tracked in `docs/testLog.md`.
- [ ] A provider API key is configured in `.env` (the matcher makes a real model call).
- [ ] Start the backend: `uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`.

## T1 — Live matcher produces suggestions
- [ ] `POST /api/research/questions` with `{"question": "How does cortical remapping support stroke recovery?"}`.
- [ ] Within a few seconds, `GET /api/research/questions/{id}` shows pending topic/concept links from the live matcher.
- [ ] Expected: relevant existing groupings appear as `pending`; a child match (e.g. `cortical remapping`) also surfaces its parent (`plasticity`) via rollup.
- [ ] Pass: at least one pending suggestion is present and reflects the question's content.

## T2 — Proposal of a new grouping
- [ ] `POST` a question whose key concept has no existing grouping (e.g. a general term not yet in the taxonomy).
- [ ] Expected: a suggestion with `proposed: true` appears (a `proposed` grouping was created).
- [ ] `PATCH /api/research/questions/{id}/topics/{grouping_id}` with `{"status":"confirmed"}`.
- [ ] Pass: the grouping is now `active` (`GET /api/research/groupings?type=topic` lists it) and the link is `confirmed`.

## T3 — Dismiss cleans up an orphan proposal
- [ ] Create a question that yields a proposed grouping; `DELETE` its link before confirming.
- [ ] Pass: the proposed grouping no longer appears in `GET /api/research/groupings`.

## T4 — Parent filter rollup
- [ ] Confirm a question's link to a child topic (e.g. `neuroplasticity`).
- [ ] `GET /api/research/questions?topic_id={plasticity_id}`.
- [ ] Pass: the question is returned via the parent filter.

## T5 — Fail-closed
- [ ] Temporarily remove provider keys from `.env` and restart the backend.
- [ ] `POST` a question.
- [ ] Pass: the question is still created (200); no links are attached; a `grouping_match_failed` row is present in `system_warnings` (e.g. via the telemetry CLI or a SQL read).
