# Manual Test Plan — Literature-Search Providers

## Purpose
Verify the live multi-provider literature search end-to-end against real APIs and
the FastAPI/React workbench. Automated tests cover normalization, merge, registry,
and fan-out with fixtures; this plan covers real-network behavior, polite-pool
config, operator connectivity confirmation, and the audit row.

## Conventions / gotchas (read first)
- The helper scripts are **plain Python**, run with `uv run python …`, **not**
  `pytest` (pytest collects 0 tests and looks like it "did nothing").
- **DuckDB is single-writer.** While the API server is running it holds the lock
  on `neurodb.duckdb`; no other process (including the audit inspector or
  `pytest`) can open the DB. Stop the server before any step that reads the DB.
- The **connectivity helper** does NOT need the DB and does NOT write an audit
  row — it calls providers directly. Only the agent's `search_literature` tool
  writes a `literature_searches` row.
- `semantic_scholar` is disabled by default (`LITERATURE_PROVIDERS_DISABLED=semantic_scholar`
  in `.env`; keyless 429s / no gmail keys per LOG-014/LOG-069). The active set is
  **6 providers**: pubmed, arxiv, openalex, europepmc, crossref, biorxiv.

## Prerequisites
1. **Automated suite (mandatory, first).** With the API server **stopped**, run:
   ```bash
   uv run pytest tests/ -q
   ```
   Pass = no new failures beyond those tracked in `docs/testLog.md`. (If a server
   is up, `test_api_app_factory.py` errors at collection on the DB lock — stop it,
   or add `--continue-on-collection-errors`.)
2. **`.env` configured.** `NEURODB_CONTACT_EMAIL` set (OpenAlex/Crossref polite
   pool + Europe PMC/bioRxiv User-Agent); optional `NCBI_API_KEY`;
   `LITERATURE_PROVIDERS_DISABLED=semantic_scholar`.
3. **Provider connectivity (operator).** This needs network only (no DB / server):
   ```bash
   uv run python tests/manual/check_literature_providers.py "synaptic plasticity"
   ```
   - Expected: one line per active provider; `status ok` for pubmed, arxiv,
     openalex, europepmc, crossref, biorxiv. `semantic_scholar` must NOT appear.
   - Pass: every active provider reports `ok`. Record any provider reporting
     `error` (auth/rate-limit/unreachable) and add it to
     `LITERATURE_PROVIDERS_DISABLED` for the run.
   - Note: `count` per provider depends on the query topic; a biomedical query
     populates pubmed/europepmc, a CS/ML query populates arxiv/crossref. A `0`
     count is not a failure — only `error` is.

## Environment setup (start the workbench)
Run the two servers in separate terminals (per `README.md`):
```bash
# Terminal A — API (holds the DuckDB lock while running)
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001

# Terminal B — React frontend
cd frontend && npm run dev
```
Open the Vite URL printed by Terminal B (default http://localhost:5173).
To stop a server: `Ctrl+C` in its terminal.

## Test Steps

### Step 1 — Multi-provider merge (real network)
1. In the workbench, open a **NeuroResearch** (or NeuroTutor) chat.
2. Send a prompt that forces an external search, using a **neuroscience** query so
   biomedical and preprint providers both return hits, e.g.:
   > Search the literature for synaptic plasticity and LTP.
3. Observe the returned sources in the chat / evidence panel.

**Pass:**
- Results are returned (non-empty `results`).
- At least one result lists **multiple providers** in its `sources` (cross-provider
  merge), e.g. a paper found by both `openalex` and `pubmed`.
- Results are ordered by citation count (most-cited first).
- If a provider fails, it appears as `status: error` in the envelope `providers`
  block and the other providers still return — the call does not crash.

> Query choice matters: a CS/ML query (e.g. "transformer Hopfield memory") will
> legitimately return 0 from pubmed/europepmc/biorxiv and hits from
> arxiv/crossref/openalex. Use the neuroscience query above to exercise merge.

### Step 2 — Provider toggle
1. Stop the API server (`Ctrl+C` in Terminal A).
2. In `.env`, change the disable list to also drop Crossref:
   `LITERATURE_PROVIDERS_DISABLED=semantic_scholar,crossref`
3. Restart the API server (Terminal A command) and repeat the Step 1 query.

**Pass:** the envelope `providers` block has **no `crossref` key**; the other
active providers are present. Afterward, revert `.env` to
`LITERATURE_PROVIDERS_DISABLED=semantic_scholar` and restart.

### Step 3 — Audit row
The audit row is written by the Step 1 search (not by the connectivity helper).
1. Complete at least one Step 1 search (so a row is written into `neurodb.duckdb`).
2. **Stop the API server** (`Ctrl+C` in Terminal A) to release the DuckDB lock.
3. Inspect the latest row:
   ```bash
   uv run python tests/manual/show_last_literature_search.py
   ```

**Pass (script exits 0, prints no `WARN`):**
- `provider_counts_json` contains **one key per active provider** — the 6 active
  providers; `semantic_scholar` is absent.
- Legacy `pubmed_count` / `semantic_scholar_count` / `arxiv_count` **match** the
  JSON values (`semantic_scholar_count` = 0 while disabled).
- Individual provider counts **may be 0** depending on the query topic; that is a
  pass. The check is structural (keys present, legacy matches JSON), not that
  every provider returned hits.

Example of a passing row (CS/ML query — biomedical providers correctly 0):
```
#134  2026-06-27T16:49:04+00:00
  query: ... LLM ... transformer Hopfield
  provider_counts_json: {'pubmed': 0, 'biorxiv': 0, 'europepmc': 0,
                         'openalex': 1, 'arxiv': 10, 'crossref': 10}
  legacy: pubmed=0 semantic_scholar=0 arxiv=10
```

## Pass/Fail
All steps pass = sign off. Record the date, the query used, and any providers left
in `LITERATURE_PROVIDERS_DISABLED` for the run.
