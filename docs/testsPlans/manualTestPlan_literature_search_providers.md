# Manual Test Plan — Literature-Search Providers

## Purpose
Verify the live multi-provider literature search end-to-end against real APIs
and the FastAPI/React workbench. Automated tests cover normalization, merge,
registry, and fan-out with fixtures; this plan covers real-network behavior,
polite-pool config, and operator connectivity confirmation.

## Prerequisites
1. **Automated suite (mandatory, first):** run `uv run pytest tests/ -q`.
   Pass = no new failures beyond those tracked in `docs/testLog.md`.
   (Note: if a FastAPI dev server is running it holds the DuckDB write lock and
   `test_api_app_factory.py` will error at collection — stop the server first,
   or run with `--continue-on-collection-errors`.)
2. **Provider connectivity confirmation (operator):** confirm `.env` has
   `NEURODB_CONTACT_EMAIL` set (OpenAlex/Crossref polite pool); optional
   `NCBI_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`. Then run:
   `uv run python tests/manual/check_literature_providers.py "synaptic plasticity"`
   - Expected: one line per active provider with `status ok` and `count>0` for
     pubmed, arxiv, openalex, europepmc, crossref, biorxiv. (semantic_scholar is
     disabled by default via `LITERATURE_PROVIDERS_DISABLED=semantic_scholar` in
     `.env` — keyless 429s, no gmail keys per LOG-014/LOG-069 — so it should NOT
     appear; six active providers is correct.)
   - Pass: every active provider reports `ok`. For any provider reporting
     `error` (auth/rate-limit/unreachable), record it and add its name to
     `LITERATURE_PROVIDERS_DISABLED` for the functional run; note it in the run log.

## Test Steps
1. **Multi-provider merge (real network):** start the FastAPI API; via the
   research agent / React workbench run `search_literature` with
   "synaptic plasticity LTP".
   - Pass: results returned; at least one result shows multiple providers in
     `sources`; results ordered by citation count (highest first); no provider
     error crashes the call (failed providers appear as status error in the
     envelope, others still return).
2. **Provider toggle:** set `LITERATURE_PROVIDERS_DISABLED=crossref`, restart
   the API, repeat the query.
   - Pass: envelope `providers` has no `crossref` key; other providers present.
3. **Audit row:** an audit row is written only by the agent's `search_literature`
   tool (Step 1) — the connectivity helper does NOT log one. DuckDB is
   single-writer, so **stop the FastAPI server first**, then run:
   `uv run python tests/manual/show_last_literature_search.py`
   - Pass: the latest row prints with `provider_counts_json` containing a count
     per active provider, and the legacy
     `pubmed_count/semantic_scholar_count/arxiv_count` match the JSON (the script
     prints `WARN` and exits non-zero on any mismatch).

## Pass/Fail
All steps pass = sign off. Record date and any disabled providers.
